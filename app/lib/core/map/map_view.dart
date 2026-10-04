import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../modules/feature_module.dart';
import '../session/session.dart';
import 'geo.dart';
import 'maplibre_map_view.dart';

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
  return '$baseUrl${AppConfig.serverTilePath}';
});

/// Builds the map. Tests replace it, because the real map needs the platform.
final mapViewBuilderProvider = Provider<MapViewBuilder>((ref) {
  final tileUrl = ref.watch(mapTileUrlProvider);
  return (content) => MapLibreMapView(content: content, tileUrl: tileUrl);
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
