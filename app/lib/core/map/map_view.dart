import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../db/app_database.dart';
import '../network/api_client.dart';
import '../network/api_exception.dart';
import '../modules/feature_module.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';
import 'geo.dart';
import 'maplibre_map_view.dart';
import 'tile_proxy.dart';

/// A marker on the map, drawn as a Flutter widget.
class MapMarker {
  const MapMarker({
    required this.id,
    required this.position,
    required this.child,
    this.onTap,
    this.clusters = false,
    this.size = 40,
  });

  final String id;
  final GeoPoint position;
  final Widget child;
  final VoidCallback? onTap;

  /// Markers of this kind are merged into one when they come close on screen.
  final bool clusters;
  final double size;
}

/// What a map shows; the same for the real map and the stand-in used in tests.
class MapContent {
  const MapContent({
    this.track = const [],
    this.markers = const [],
    this.highlight,
    this.onTap,
    this.onClusterTap,
    this.interactive = true,
  });

  /// The track as a line.
  final List<GeoPoint> track;
  final List<MapMarker> markers;

  /// A point that follows the finger on the elevation profile.
  final GeoPoint? highlight;

  /// Tap on the map, for setting points and drawing a track.
  final ValueChanged<GeoPoint>? onTap;

  /// Tap on a group of merged markers, with the ids of its members.
  final ValueChanged<List<String>>? onClusterTap;
  final bool interactive;
}

typedef MapViewBuilder = Widget Function(MapContent content);

/// Where the map gets its tiles from: the user's own server, which keeps a
/// copy of every tile it was asked for. Only a server without the module
/// `maps` sends the app to the tile source directly.
final mapTileUrlProvider = Provider<String>((ref) {
  if (AppConfig.mapTileUrl.isNotEmpty) return AppConfig.mapTileUrl;
  final baseUrl = ref.watch(sessionProvider.select((s) => s.baseUrl));
  // No answer yet or no network: asData is null; then the server is tried.
  final modules = ref.watch(backendModulesProvider).asData?.value;
  final serverHasTiles = modules == null || modules.contains('maps');
  if (baseUrl.isEmpty || !serverHasTiles) return AppConfig.fallbackTileUrl;
  // The server shows a certificate the user trusted by hand: the map cannot
  // check it, so the tiles go through the app (see TileProxy).
  final server = Uri.tryParse(baseUrl);
  final port = ref.watch(tileProxyProvider);
  final trusted = ref.watch(trustedCertificatesProvider);
  if (server != null && port != null) {
    final endpoint = '${server.host}:${server.hasPort ? server.port : 443}';
    if (trusted.containsKey(endpoint)) {
      return 'http://127.0.0.1:$port/{z}/{x}/{y}.png';
    }
  }
  return '$baseUrl${AppConfig.serverTilePath}';
});

/// The style of the own vector map, as JSON, if the user's server has one;
/// null means the raster tiles are shown. The map asks the app's own map
/// server (see TileProxy) for tiles and glyphs, which answers from the device
/// where it can. Without network the style last seen is used.
final mapStyleProvider = FutureProvider<String?>((ref) async {
  if (!ref.watch(sessionProvider.select((s) => s.isSignedIn))) return null;
  final port = ref.watch(tileProxyProvider);
  final dio = ref.watch(dioProvider);
  final db = ref.watch(appDatabaseProvider);
  const key = 'map_style';
  Map<String, dynamic>? style;
  try {
    final response = await apiCall(
      () => dio.get<Map<String, dynamic>>('/maps/style.json'),
    );
    style = response.data;
    if (style != null) await db.putDocument(key, key, style);
  } on ApiException catch (error) {
    if (error.code != ApiException.network) return null;
    style = await db.getDocument(key, key);
  }
  if (style == null) return null;
  if (port != null) {
    final local = 'http://127.0.0.1:$port';
    style = {
      ...style,
      'glyphs': '$local/fonts/{fontstack}/{range}.pbf',
      'sources': {
        for (final entry in (style['sources'] as Map<String, dynamic>).entries)
          entry.key: (entry.value as Map<String, dynamic>)['type'] == 'vector'
              ? {
                  ...entry.value as Map<String, dynamic>,
                  'tiles': ['$local/vector/{z}/{x}/{y}.pbf'],
                }
              : entry.value,
      },
    };
  }
  return jsonEncode(style);
});

/// Builds the map. Tests replace it, because the real map needs the platform.
final mapViewBuilderProvider = Provider<MapViewBuilder>((ref) {
  final tileUrl = ref.watch(mapTileUrlProvider);
  final style = ref.watch(mapStyleProvider).asData?.value;
  return (content) => MapLibreMapView(
    // Another style is another map: it is built anew.
    key: ValueKey(style == null ? tileUrl : style.hashCode),
    content: content,
    tileUrl: tileUrl,
    styleJson: style,
  );
});

/// The map of the app: track, markers and an optional highlighted point.
class HikerMap extends ConsumerWidget {
  const HikerMap({super.key, required this.content});

  final MapContent content;

  @override
  Widget build(BuildContext context, WidgetRef ref) =>
      ref.watch(mapViewBuilderProvider)(content);
}

/// Round marker with an icon, for start, end, peaks and waypoints.
class IconMarker extends StatelessWidget {
  const IconMarker({
    super.key,
    required this.icon,
    required this.color,
    this.tooltip,
  });

  final IconData icon;
  final Color color;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final marker = DecoratedBox(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: const [BoxShadow(blurRadius: 3, color: Colors.black38)],
      ),
      child: Center(child: Icon(icon, size: 18, color: Colors.white)),
    );
    return tooltip == null ? marker : Tooltip(message: tooltip, child: marker);
  }
}

/// Stands for several markers that are too close to be shown one by one.
class ClusterMarker extends StatelessWidget {
  const ClusterMarker({super.key, required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.tertiary,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
      ),
      child: Center(
        child: Text(
          '$count',
          style: TextStyle(
            color: scheme.onTertiary,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

/// The glyph ranges of Latin script; the labels of the map need nothing else.
const _glyphRanges = [
  '0-255',
  '256-511',
  '512-767',
  '768-1023',
  '7680-7935',
  '8192-8447',
];

/// Makes sure a map on the device can be shown without network: the style
/// and the glyphs of its fonts are fetched once and kept by the app.
Future<void> prepareOfflineMap(WidgetRef ref) async {
  final style = await ref.read(mapStyleProvider.future);
  final port = ref.read(tileProxyProvider);
  if (style == null || port == null) return;
  final fonts = <String>{};
  for (final layer
      in (jsonDecode(style) as Map<String, dynamic>)['layers']
          as List<dynamic>) {
    final font =
        ((layer as Map<String, dynamic>)['layout']
            as Map<String, dynamic>?)?['text-font'];
    if (font is List) fonts.add(font.join(','));
  }
  final client = HttpClient();
  try {
    for (final font in fonts) {
      for (final range in _glyphRanges) {
        final uri = Uri.parse(
          'http://127.0.0.1:$port/fonts/${Uri.encodeComponent(font)}/$range.pbf',
        );
        try {
          await (await (await client.getUrl(uri)).close()).drain<void>();
        } on Exception {
          // The map works without one range; the next look at the map tries again.
        }
      }
    }
  } finally {
    client.close();
  }
}
