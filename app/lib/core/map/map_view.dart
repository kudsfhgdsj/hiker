import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../config/app_config.dart';
import '../db/app_database.dart';
import '../format.dart';
import '../network/api_client.dart';
import '../network/api_exception.dart';
import '../modules/feature_module.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';
import 'geo.dart';
import 'map_3d_screen.dart';
import 'map_regions.dart';
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
    this.secondTrack = const [],
    this.markers = const [],
    this.highlight,
    this.onTap,
    this.onClusterTap,
    this.onPlace,
    this.controls = const [],
    this.coveredBottom = 0,
    this.interactive = true,
  });

  /// The track as a line.
  final List<GeoPoint> track;

  /// A second line in another colour, to compare with the track: e.g. what
  /// was really walked over what was planned.
  final List<GeoPoint> secondTrack;
  final List<MapMarker> markers;

  /// A point that follows the finger on the elevation profile.
  final GeoPoint? highlight;

  /// Tap on the map, for setting points and drawing a track.
  final ValueChanged<GeoPoint>? onTap;

  /// Tap on a group of merged markers, with the ids of its members.
  final ValueChanged<List<String>>? onClusterTap;

  /// Tap on the map with what the map draws there (summit, hut, path); used
  /// instead of [onTap] by screens that look things up.
  final ValueChanged<MapPlace>? onPlace;

  /// Further fields next to "Ebenen" and "Darstellung" at the top of the map.
  final List<MapControl> controls;

  /// How much of the map's lower edge a sheet covers, in logical pixels; the
  /// content is fitted into what stays visible.
  final double coveredBottom;
  final bool interactive;
}

/// A field at the top edge of the map that opens a sheet.
class MapControl {
  const MapControl({required this.label, required this.builder});

  final String label;
  final WidgetBuilder builder;
}

/// A place the user tapped, with the things the map draws there.
class MapPlace {
  const MapPlace({required this.position, this.features = const []});

  final GeoPoint position;

  /// Source layer and properties of each feature, nearest first.
  final List<({String layer, Map<String, dynamic> properties})> features;
}

typedef MapViewBuilder = Widget Function(MapContent content);

/// Where the map gets its tiles from: the user's own server, which keeps a
/// copy of every tile it was asked for. Only a server without the module
/// `maps` sends the app to the tile source directly.
final mapTileUrlProvider = Provider<String>((ref) {
  if (AppConfig.mapTileUrl.isNotEmpty) return AppConfig.mapTileUrl;
  final baseUrl = ref.watch(sessionProvider.select((s) => s.baseUrl));
  // No answer yet or no network: asData is null; then the server is tried.
  var modules = ref.watch(backendModulesProvider).asData?.value;
  // Before signing in nobody was asked (the list is empty): the server is
  // tried then, as without an answer.
  if (modules != null &&
      modules.isEmpty &&
      !ref.watch(sessionProvider.select((s) => s.isSignedIn))) {
    modules = null;
  }
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
  // The map of the server needs no login: it can be looked at before.
  final baseUrl = ref.watch(sessionProvider.select((s) => s.baseUrl));
  final port = ref.watch(tileProxyProvider);
  final dio = ref.watch(dioProvider);
  final db = ref.watch(appDatabaseProvider);
  const key = 'map_style';
  Map<String, dynamic>? style;
  try {
    // Without a server only the style seen last can be shown.
    if (baseUrl.isEmpty) {
      throw const ApiException(
        code: ApiException.network,
        message: 'no server',
      );
    }
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
    // Everything the style loads from the server's maps module goes through
    // the map server of the app instead.
    final local = 'http://127.0.0.1:$port';
    const marker = '/api/v1/maps/';
    String own(String address) => address.contains(marker)
        ? '$local/${address.substring(address.indexOf(marker) + marker.length)}'
        : address;
    final metadata = style['metadata'] as Map<String, dynamic>?;
    final hiker = metadata?['hiker'] as Map<String, dynamic>?;
    final radar = hiker?['radar'] as Map<String, dynamic>?;
    style = {
      ...style,
      if (radar != null)
        'metadata': {
          ...metadata!,
          'hiker': {
            ...hiker!,
            'radar': {
              ...radar,
              for (final key in const ['frames', 'rain', 'clouds'])
                if (radar[key] case final String address) key: own(address),
            },
          },
        },
      'glyphs': '$local/fonts/{fontstack}/{range}.pbf',
      'sources': {
        for (final entry in (style['sources'] as Map<String, dynamic>).entries)
          entry.key: {
            ...entry.value as Map<String, dynamic>,
            if ((entry.value as Map<String, dynamic>)['tiles']
                case final List<dynamic> tiles)
              'tiles': [for (final tile in tiles.cast<String>()) own(tile)],
            if ((entry.value as Map<String, dynamic>)['data']
                case final String data)
              'data': own(data),
          },
      },
    };
  }
  return jsonEncode(style);
});

/// Which layers of the map the user switched on; the same for every map in
/// the app.
class MapLayerChoice {
  const MapLayerChoice({
    this.base = 'map',
    this.overlays = const {},
    this.slopeLow,
    this.slopeHigh,
    this.day,
    this.radar = const {},
    this.opacity = const {},
  });

  /// `map` (the drawn map) or `satellite` (aerial image under paths and names).
  final String base;
  final Set<String> overlays;

  /// From and up to which angle slopes are coloured; null: as the server
  /// draws them.
  final int? slopeLow;
  final int? slopeHigh;

  /// A day in the past (`2026-02-01`) for the layers with a history; null: today.
  final String? day;

  /// `rain` and `clouds`: images with their time, laid over the map.
  final Set<String> radar;

  /// How opaque an overlay is drawn (0 to 1), by its id; missing: as the
  /// server draws it. Used for the aerial image over the map.
  final Map<String, double> opacity;

  MapLayerChoice _with({
    String? base,
    Set<String>? overlays,
    (int?, int?)? slope,
    (String?,)? day,
    Set<String>? radar,
    Map<String, double>? opacity,
  }) => MapLayerChoice(
    opacity: opacity ?? this.opacity,
    base: base ?? this.base,
    overlays: overlays ?? this.overlays,
    slopeLow: slope == null ? slopeLow : slope.$1,
    slopeHigh: slope == null ? slopeHigh : slope.$2,
    day: day == null ? this.day : day.$1,
    radar: radar ?? this.radar,
  );

  static bool _same(Set<String> a, Set<String> b) =>
      a.length == b.length && a.containsAll(b);

  @override
  bool operator ==(Object other) =>
      other is MapLayerChoice &&
      other.base == base &&
      _same(other.overlays, overlays) &&
      other.slopeLow == slopeLow &&
      other.slopeHigh == slopeHigh &&
      other.day == day &&
      _same(other.radar, radar) &&
      other.opacity.length == opacity.length &&
      opacity.entries.every((entry) => other.opacity[entry.key] == entry.value);

  @override
  int get hashCode => Object.hash(
    base,
    Object.hashAllUnordered(overlays),
    slopeLow,
    slopeHigh,
    day,
    Object.hashAllUnordered(radar),
    Object.hashAllUnordered(opacity.keys),
    Object.hashAllUnordered(opacity.values),
  );
}

class MapLayerChoiceNotifier extends Notifier<MapLayerChoice> {
  @override
  MapLayerChoice build() => const MapLayerChoice();

  void setBase(String base) => state = state._with(base: base);

  void setOverlay(String overlay, {required bool on}) => state = state._with(
    overlays: on
        ? {...state.overlays, overlay}
        : state.overlays.difference({overlay}),
  );

  /// The angles of the slope layer; null for both: the usual colours.
  void setSlope(int? low, int? high) => state = state._with(slope: (low, high));

  void setOpacity(String overlay, double value) =>
      state = state._with(opacity: {...state.opacity, overlay: value});

  void setDay(String? day) => state = state._with(day: (day,));

  void setRadar(String kind, {required bool on}) => state = state._with(
    radar: on ? {...state.radar, kind} : state.radar.difference({kind}),
  );
}

final mapLayerChoiceProvider =
    NotifierProvider<MapLayerChoiceNotifier, MapLayerChoice>(
      MapLayerChoiceNotifier.new,
    );

/// What the style of the server offers to switch (`metadata.hiker`).
Map<String, dynamic>? mapLayerOptions(String? styleJson) {
  if (styleJson == null) return null;
  final metadata = (jsonDecode(styleJson) as Map<String, dynamic>)['metadata'];
  return (metadata as Map<String, dynamic>?)?['hiker'] as Map<String, dynamic>?;
}

/// The style with the chosen angles of the slope layer and the chosen day in
/// its addresses: the map then asks for exactly those tiles.
String styleWithChoice(String styleJson, MapLayerChoice choice) {
  final slope = choice.slopeLow != null && choice.slopeHigh != null
      ? 'low=${choice.slopeLow}&high=${choice.slopeHigh}'
      : null;
  if (slope == null && choice.day == null) return styleJson;
  final style = jsonDecode(styleJson) as Map<String, dynamic>;
  final hiker =
      (style['metadata'] as Map<String, dynamic>?)?['hiker']
          as Map<String, dynamic>?;
  final dated = {
    if (choice.day != null)
      ...((hiker?['history'] as Map<String, dynamic>?)?['sources']
                  as List<dynamic>? ??
              const [])
          .cast<String>(),
  };
  String withQuery(String address, String query) =>
      '$address${address.contains('?') ? '&' : '?'}$query';
  final sources = style['sources'] as Map<String, dynamic>;
  for (final name in sources.keys.toList()) {
    final query = [
      if (name == 'slope' && slope != null) slope,
      if (dated.contains(name)) 'date=${choice.day}',
    ].join('&');
    if (query.isEmpty) continue;
    final source = Map<String, dynamic>.of(
      sources[name] as Map<String, dynamic>,
    );
    if (source['tiles'] case final List<dynamic> tiles) {
      source['tiles'] = [
        for (final tile in tiles.cast<String>()) withQuery(tile, query),
      ];
    }
    if (source['data'] case final String data) {
      source['data'] = withQuery(data, query);
    }
    sources[name] = source;
  }
  return jsonEncode(style);
}

/// "#e3b000" → colour; grey for anything else.
Color _hexColor(String text) {
  final value = int.tryParse(text.replaceFirst('#', ''), radix: 16);
  return value == null || text.length != 7
      ? const Color(0xFF888888)
      : Color(0xFF000000 | value);
}

/// Which of the two sheets of the map: what lies on it, or how it is drawn.
enum MapSheetPart { layers, looks }

/// The sheets in which the user chooses overlays ("Ebenen": with the angles
/// of the slope layer, a day in the past and the radar) and the base map
/// ("Darstellung": drawn map, winter or aerial image, colours of the paths).
class MapLayerSheet extends ConsumerWidget {
  const MapLayerSheet({
    super.key,
    required this.options,
    this.part = MapSheetPart.layers,
  });

  final Map<String, dynamic> options;
  final MapSheetPart part;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final choice = ref.watch(mapLayerChoiceProvider);
    final notifier = ref.read(mapLayerChoiceProvider.notifier);
    final bases = (options['bases'] as List<dynamic>)
        .cast<Map<String, dynamic>>();
    final overlays = (options['overlays'] as List<dynamic>)
        .cast<Map<String, dynamic>>();
    final history = options['history'] as Map<String, dynamic>?;
    final radar = options['radar'] as Map<String, dynamic>?;
    String baseLabel(String id) => switch (id) {
      'map' => l10n.mapBaseMap,
      'winter' => l10n.mapBaseWinter,
      'satellite' => l10n.mapBaseSatellite,
      _ => id,
    };
    String overlayLabel(String id) => switch (id) {
      'slope' => l10n.mapOverlaySlope,
      'satellite' => l10n.mapBaseSatellite,
      'avalanche' => l10n.mapOverlayAvalanche,
      'snow' => l10n.mapOverlaySnow,
      'precipitation' => l10n.mapOverlayPrecipitation,
      'weather0' => l10n.mapOverlayWeather0,
      'weather1' => l10n.mapOverlayWeather1,
      'weather2' => l10n.mapOverlayWeather2,
      'snowdepth' => l10n.mapOverlaySnowDepth,
      _ => id,
    };
    String? overlayNote(String id) => switch (id) {
      'slope' => l10n.mapSlopeLegend,
      'avalanche' => l10n.mapAvalancheNote,
      'snow' => l10n.mapSnowNote,
      'precipitation' => l10n.mapPrecipitationNote,
      'weather2' => l10n.mapWeatherNote,
      'snowdepth' => l10n.mapSnowDepthNote,
      _ => null,
    };
    Widget heading(String text) => Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
      child: Text(text, style: theme.textTheme.titleMedium),
    );

    final looks = [
      heading(l10n.mapLooks),
      if (bases.length > 1)
        RadioGroup<String>(
          groupValue: choice.base,
          onChanged: (base) => notifier.setBase(base!),
          child: Column(
            children: [
              for (final base in bases)
                RadioListTile<String>(
                  value: base['id'] as String,
                  title: Text(baseLabel(base['id'] as String)),
                ),
            ],
          ),
        ),
      if (options['legend'] case final List<dynamic> legend
          when legend.isNotEmpty)
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
          child: Wrap(
            spacing: 10,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(l10n.mapPaths),
              for (final entry in legend.cast<Map<String, dynamic>>())
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 14,
                      height: 14,
                      margin: const EdgeInsets.only(right: 4),
                      decoration: BoxDecoration(
                        color: _hexColor(entry['color'] as String),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                    Text(entry['label'] as String),
                  ],
                ),
            ],
          ),
        ),
    ];

    String groupLabel(String id) => switch (id) {
      'terrain' => l10n.mapGroupTerrain,
      'snow' => l10n.mapGroupSnow,
      'weather' => l10n.mapGroupWeather,
      _ => id,
    };
    Widget groupHeading(String id) => Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Text(
        groupLabel(id),
        style: theme.textTheme.labelLarge?.copyWith(
          color: theme.colorScheme.primary,
        ),
      ),
    );
    // Radar and clouds belong to the weather, the last group of the overlays.
    final radarSwitches = [
      if (radar != null) ...[
        if (overlays.every((overlay) => overlay['group'] != 'weather'))
          groupHeading('weather'),
        for (final (kind, label) in [
          ('rain', l10n.mapRadarRain),
          ('clouds', l10n.mapRadarClouds),
        ])
          SwitchListTile(
            value: choice.radar.contains(kind),
            title: Text(label),
            onChanged: (on) => notifier.setRadar(kind, on: on),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: Text(l10n.mapRadarNote, style: theme.textTheme.bodySmall),
        ),
      ],
    ];

    final layers = [
      heading(l10n.mapLayers),
      for (final (index, overlay) in overlays.indexed) ...[
        // The overlays come in groups: the ground, snow and avalanches, weather.
        if (overlay['group'] case final String group
            when index == 0 || overlays[index - 1]['group'] != group)
          groupHeading(group),
        SwitchListTile(
          value: choice.overlays.contains(overlay['id']),
          title: Text(overlayLabel(overlay['id'] as String)),
          subtitle: switch (overlayNote(overlay['id'] as String)) {
            final note? => Text(note),
            null => null,
          },
          onChanged: (on) =>
              notifier.setOverlay(overlay['id'] as String, on: on),
        ),
        if (overlay['range'] case final Map<String, dynamic> range
            when choice.overlays.contains(overlay['id']))
          _SlopeRange(range: range),
        if (overlay['opacity'] case final Map<String, dynamic> opacity
            when choice.overlays.contains(overlay['id']))
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Text(l10n.mapOpacity),
                Expanded(
                  child: Slider(
                    key: ValueKey('opacity-${overlay['id']}'),
                    min: (opacity['min'] as num).toDouble(),
                    max: 1,
                    divisions: 18,
                    value:
                        choice.opacity[overlay['id']] ??
                        (opacity['default'] as num).toDouble(),
                    onChanged: (value) =>
                        notifier.setOpacity(overlay['id'] as String, value),
                  ),
                ),
                Text(
                  '${(100 * (choice.opacity[overlay['id']] ?? (opacity['default'] as num).toDouble())).round()} %',
                ),
              ],
            ),
          ),
      ],
      ...radarSwitches,
      if (history != null) ...[
        const Divider(),
        ListTile(
          leading: const Icon(Icons.history),
          title: Text(l10n.mapHistory),
          subtitle: Text(
            choice.day == null
                ? l10n.mapHistoryNote
                : Format.date(DateTime.parse(choice.day!)),
          ),
          trailing: choice.day == null
              ? null
              : TextButton(
                  onPressed: () => notifier.setDay(null),
                  child: Text(l10n.mapHistoryToday),
                ),
          onTap: () async {
            final now = DateTime.now();
            final picked = await showDatePicker(
              context: context,
              initialDate: DateTime.tryParse(choice.day ?? '') ?? now,
              firstDate: now.subtract(
                Duration(days: (history['days'] as num).toInt()),
              ),
              lastDate: now,
            );
            if (picked == null) return;
            final today = DateUtils.isSameDay(picked, now);
            notifier.setDay(
              today ? null : picked.toIso8601String().substring(0, 10),
            );
          },
        ),
      ],
    ];

    // The list can be longer than the sheet is high.
    return SafeArea(
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: part == MapSheetPart.looks ? looks : layers,
        ),
      ),
    );
  }
}

/// Two handles: from which angle and up to which angle slopes are coloured.
class _SlopeRange extends ConsumerStatefulWidget {
  const _SlopeRange({required this.range});

  /// `min`, `max`, `step`, `low`, `high` as the style of the server names them.
  final Map<String, dynamic> range;

  @override
  ConsumerState<_SlopeRange> createState() => _SlopeRangeState();
}

class _SlopeRangeState extends ConsumerState<_SlopeRange> {
  static const _vertical = 90.0;
  RangeValues? _dragged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final choice = ref.watch(mapLayerChoiceProvider);
    final range = widget.range;
    final min = (range['min'] as num).toDouble();
    final step = (range['step'] as num).toDouble();
    final usualLow = (range['low'] as num).toDouble();
    final values =
        _dragged ??
        RangeValues(
          choice.slopeLow?.toDouble() ?? usualLow,
          choice.slopeHigh?.toDouble() ?? _vertical,
        );
    final top = values.end >= _vertical
        ? l10n.mapSlopeOpen
        : '${values.end.round()}°';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          RangeSlider(
            min: min,
            max: _vertical,
            divisions: ((_vertical - min) / step).round(),
            values: values,
            labels: RangeLabels('${values.start.round()}°', top),
            onChanged: (changed) => setState(() => _dragged = changed),
            // The tiles are only asked for anew when the finger lets go.
            onChangeEnd: (changed) {
              setState(() => _dragged = null);
              final usual =
                  changed.start == usualLow && changed.end >= _vertical;
              ref
                  .read(mapLayerChoiceProvider.notifier)
                  .setSlope(
                    usual ? null : changed.start.round(),
                    usual ? null : changed.end.round(),
                  );
            },
          ),
          Text(
            l10n.mapSlopeRange('${values.start.round()}°', top),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

/// The sheet of the search: a field and the places found while typing.
class PlaceSearchSheet extends StatefulWidget {
  const PlaceSearchSheet({super.key, required this.search});

  final Future<List<FoundPlace>> Function(String query) search;

  @override
  State<PlaceSearchSheet> createState() => _PlaceSearchSheetState();
}

class _PlaceSearchSheetState extends State<PlaceSearchSheet> {
  List<FoundPlace>? _places;
  int _asked = 0;
  Timer? _wait;

  @override
  void dispose() {
    _wait?.cancel();
    super.dispose();
  }

  void _changed(String text) {
    _wait?.cancel();
    // Not a request for every letter.
    _wait = Timer(const Duration(milliseconds: 300), () => _ask(text));
  }

  Future<void> _ask(String text) async {
    final current = ++_asked;
    if (text.trim().length < 2) {
      setState(() => _places = null);
      return;
    }
    List<FoundPlace> places;
    try {
      places = await widget.search(text.trim());
    } on Exception {
      places = const [];
    }
    // A newer search is already on its way.
    if (mounted && current == _asked) setState(() => _places = places);
  }

  static IconData _icon(String kind) => switch (kind) {
    'peak' || 'saddle' || 'volcano' => Icons.terrain,
    'hut' || 'shelter' => Icons.cabin,
    'lake' || 'waterfall' || 'spring' => Icons.water,
    'station' || 'halt' => Icons.train,
    'parking' => Icons.local_parking,
    'viewpoint' => Icons.visibility_outlined,
    'camp_site' => Icons.holiday_village_outlined,
    'city' || 'town' || 'village' || 'hamlet' => Icons.location_city,
    _ => Icons.place_outlined,
  };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final places = _places;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.6,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: TextField(
                autofocus: true,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.search),
                  labelText: l10n.mapSearch,
                ),
                onChanged: _changed,
                onSubmitted: _ask,
              ),
            ),
            Expanded(
              child: places == null
                  ? const SizedBox.shrink()
                  : places.isEmpty
                  ? Center(child: Text(l10n.mapSearchNone))
                  : ListView(
                      children: [
                        for (final place in places)
                          ListTile(
                            leading: Icon(_icon(place.kind)),
                            title: Text(place.name),
                            subtitle: Text(
                              [
                                l10n.mapPlaceKind(place.kind),
                                if (place.elevationM != null)
                                  Format.meters(place.elevationM),
                              ].join(', '),
                            ),
                            onTap: () => Navigator.pop(context, place),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Builds the map. Tests replace it, because the real map needs the platform.
final mapViewBuilderProvider = Provider<MapViewBuilder>((ref) {
  final tileUrl = ref.watch(mapTileUrlProvider);
  final style = ref.watch(mapStyleProvider).asData?.value;
  final choice = ref.watch(mapLayerChoiceProvider);
  final port = ref.watch(tileProxyProvider);
  final options = mapLayerOptions(style);
  // The chosen angles and day are part of the addresses the map asks for.
  final shown = style == null ? null : styleWithChoice(style, choice);
  return (content) => MapLibreMapView(
    // Raster tiles and the own map are different maps; a changed style of
    // the same map is taken over in place and keeps the view.
    key: ValueKey(style == null ? tileUrl : 'vector'),
    content: content,
    tileUrl: tileUrl,
    styleJson: shown,
    layerOptions: options,
    layerChoice: choice,
    layerSheet: options == null
        ? null
        : (context, part) => MapLayerSheet(options: options, part: part),
    // The 3D view is a page of the app's own map server.
    on3D: port == null
        ? null
        : (context, scene) {
            ref.read(tileProxyProvider.notifier).scene3d = jsonEncode(scene);
            Navigator.of(context, rootNavigator: true).push(
              MaterialPageRoute<void>(
                builder: (_) => Map3DScreen(
                  page: Uri.parse('http://127.0.0.1:$port/3d/index.html'),
                ),
              ),
            );
          },
    // The search knows the places of the own map.
    onSearch: style == null
        ? null
        : (query, near) => ref
              .read(mapRegionStoreProvider)
              .search(query, lat: near.lat, lon: near.lon),
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
