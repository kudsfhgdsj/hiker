import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../../l10n/app_localizations.dart';
import 'geo.dart';
import 'map_view.dart';

/// The map drawn by MapLibre. The track is a line layer of the map; markers are
/// Flutter widgets laid over it and moved along with the camera.
class MapLibreMapView extends StatefulWidget {
  const MapLibreMapView({
    super.key,
    required this.content,
    required this.tileUrl,
    this.styleJson,
    this.layerOptions,
    this.layerChoice = const MapLayerChoice(),
    this.layerSheet,
  });

  final MapContent content;

  /// URL template of the raster tiles.
  final String tileUrl;

  /// Style of the own vector map; null shows the raster tiles.
  final String? styleJson;

  /// What the style offers to switch (see [mapLayerOptions]) and what is chosen.
  final Map<String, dynamic>? layerOptions;
  final MapLayerChoice layerChoice;

  /// Builds the sheets for choosing layers and looks; null hides the fields.
  final Widget Function(BuildContext context, MapSheetPart part)? layerSheet;

  @override
  State<MapLibreMapView> createState() => _MapLibreMapViewState();
}

class _MapLibreMapViewState extends State<MapLibreMapView> {
  static const _source = 'track';
  static const _clusterRadius = 44.0;
  static const _fallback = LatLng(46.8, 8.2);

  MapLibreMapController? _controller;
  bool _styleLoaded = false;
  Map<String, math.Point<double>> _positions = const {};

  /// The view is fitted to the content once, not after every change of style.
  bool _fitted = false;

  /// Rain radar and clouds: the times that have an image, and the one shown.
  ({List<int> rain, List<int> clouds, List<int> times})? _frames;
  int _frame = 0;
  Timer? _player;
  final Set<String> _radarShown = {};

  /// The own vector map, or else a map of raster tiles only.
  String get _style => widget.styleJson ?? _rasterStyle;

  late final String _rasterStyle = jsonEncode({
    'version': 8,
    'sources': {
      'tiles': {
        'type': 'raster',
        'tiles': [widget.tileUrl],
        'tileSize': 256,
        'attribution': '© OpenStreetMap contributors',
      },
    },
    'layers': [
      // Shown while tiles load or if they cannot be loaded.
      {
        'id': 'background',
        'type': 'background',
        'paint': {'background-color': '#E4E9E6'},
      },
      {'id': 'tiles', 'type': 'raster', 'source': 'tiles'},
    ],
  });

  static LatLng _latLng(GeoPoint point) => LatLng(point.lat, point.lon);

  List<GeoPoint> get _everything => [
    ...widget.content.track,
    for (final marker in widget.content.markers) marker.position,
  ];

  Map<String, dynamic> _trackGeoJson() => {
    'type': 'FeatureCollection',
    'features': [
      if (widget.content.track.length > 1)
        {
          'type': 'Feature',
          'properties': <String, dynamic>{},
          'geometry': {
            'type': 'LineString',
            'coordinates': [
              for (final point in widget.content.track) [point.lon, point.lat],
            ],
          },
        },
    ],
  };

  /// Shows the layers of the chosen base map and overlays, hides the others.
  Future<void> _applyLayerChoice() async {
    final controller = _controller;
    final options = widget.layerOptions;
    if (controller == null || options == null || !_styleLoaded) return;
    final choice = widget.layerChoice;
    final bases = (options['bases'] as List<dynamic>)
        .cast<Map<String, dynamic>>();
    final chosen = bases.firstWhere(
      (base) => base['id'] == choice.base,
      orElse: () => bases.first,
    );
    List<String> names(Map<String, dynamic> entry, String key) =>
        (entry[key] as List<dynamic>).cast<String>();
    final visible = <String, bool>{};
    for (final base in bases) {
      for (final layer in names(base, 'show')) {
        visible[layer] = identical(base, chosen);
      }
      for (final layer in names(base, 'hide')) {
        visible[layer] = true;
      }
    }
    for (final layer in names(chosen, 'hide')) {
      visible[layer] = false;
    }
    for (final overlay
        in (options['overlays'] as List<dynamic>)
            .cast<Map<String, dynamic>>()) {
      for (final layer in names(overlay, 'layers')) {
        visible[layer] = choice.overlays.contains(overlay['id']);
      }
    }
    for (final entry in visible.entries) {
      try {
        await controller.setLayerVisibility(entry.key, entry.value);
      } on Exception {
        // A layer the style does not have: nothing to switch.
      }
    }
    // How much of the map shines through an overlay, e.g. the aerial image.
    for (final overlay
        in (options['overlays'] as List<dynamic>)
            .cast<Map<String, dynamic>>()) {
      final opacity = overlay['opacity'] as Map<String, dynamic>?;
      if (opacity == null) continue;
      try {
        await controller.setLayerProperties(
          opacity['layer'] as String,
          RasterLayerProperties(
            rasterOpacity:
                choice.opacity[overlay['id']] ??
                (opacity['default'] as num).toDouble(),
          ),
        );
      } on Exception {
        // Not a layer of this style.
      }
    }
  }

  @override
  void didUpdateWidget(MapLibreMapView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_styleLoaded) return;
    if (oldWidget.styleJson != widget.styleJson) {
      // The map loads the new style and reports it; until then nothing of
      // the old one may be touched.
      _styleLoaded = false;
      _radarShown.clear();
      return;
    }
    if (oldWidget.layerChoice != widget.layerChoice) {
      _applyLayerChoice();
      _applyRadar();
    }
    if (!listEquals(oldWidget.content.track, widget.content.track)) {
      _controller?.setGeoJsonSource(_source, _trackGeoJson());
    }
    _updatePositions();
  }

  Future<void> _onStyleLoaded() async {
    final controller = _controller;
    if (controller == null) return;
    // The map counts in physical pixels.
    final covered =
        widget.content.coveredBottom * MediaQuery.devicePixelRatioOf(context);
    await controller.addGeoJsonSource(_source, _trackGeoJson());
    await controller.addLineLayer(
      _source,
      'track-line',
      const LineLayerProperties(
        lineColor: '#E8731A',
        lineWidth: 4,
        lineJoin: 'round',
        lineCap: 'round',
      ),
    );
    _styleLoaded = true;
    await _applyLayerChoice();
    await _applyRadar();
    final bounds = _fitted ? null : GeoBounds.around(_everything);
    _fitted = true;
    if (bounds != null) {
      await controller.moveCamera(
        bounds.southWest == bounds.northEast
            ? CameraUpdate.newLatLngZoom(_latLng(bounds.southWest), 13)
            : CameraUpdate.newLatLngBounds(
                LatLngBounds(
                  southwest: _latLng(bounds.southWest),
                  northeast: _latLng(bounds.northEast),
                ),
                left: 40,
                // Below the fields at the top, above what covers the bottom.
                top: 70,
                right: 40,
                bottom: 40 + covered,
              ),
      );
    }
    await _updatePositions();
  }

  Map<String, dynamic>? get _radar =>
      widget.layerOptions?['radar'] as Map<String, dynamic>?;

  /// Asks which times have a radar or cloud image.
  Future<void> _loadFrames() async {
    final address = _radar?['frames'] as String?;
    if (address == null) return;
    final client = HttpClient();
    try {
      final response = await (await client.getUrl(Uri.parse(address))).close();
      final body =
          jsonDecode(await utf8.decodeStream(response)) as Map<String, dynamic>;
      List<int> times(String key) => [
        for (final time in body[key] as List<dynamic>? ?? const [])
          (time as num).toInt(),
      ];
      final rain = times('rain'), clouds = times('clouds');
      final all = {...rain, ...clouds}.toList()..sort();
      if (!mounted) return;
      setState(() {
        _frames = (rain: rain, clouds: clouds, times: all);
        _frame = all.isEmpty ? 0 : all.length - 1;
      });
    } on Object {
      // No network or no radar right now: the map stays as it is.
      if (mounted) {
        setState(() => _frames = (rain: [], clouds: [], times: []));
      }
    } finally {
      client.close();
    }
  }

  /// Lays the radar and cloud image of the chosen time over the map.
  Future<void> _applyRadar() async {
    final controller = _controller;
    final radar = _radar;
    if (controller == null || radar == null || !_styleLoaded) return;
    final chosen = widget.layerChoice.radar;
    if (chosen.isEmpty) {
      _player?.cancel();
      _player = null;
    } else if (_frames == null) {
      await _loadFrames();
    }
    final frames = _frames;
    for (final kind in const ['clouds', 'rain']) {
      final id = 'radar-$kind';
      if (_radarShown.remove(id)) {
        try {
          await controller.removeLayer(id);
          await controller.removeSource(id);
        } on Exception {
          // Already gone with the style.
        }
      }
      if (!chosen.contains(kind) || frames == null || frames.times.isEmpty) {
        continue;
      }
      // The image of that kind closest before the chosen time.
      final time = frames.times[_frame.clamp(0, frames.times.length - 1)];
      final known = (kind == 'rain' ? frames.rain : frames.clouds).where(
        (frame) => frame <= time,
      );
      if (known.isEmpty) continue;
      try {
        await controller.addSource(
          id,
          RasterSourceProperties(
            tiles: [
              (radar[kind] as String).replaceFirst('{time}', '${known.last}'),
            ],
            tileSize: 256,
            maxzoom: (radar['${kind}_max_zoom'] as num?)?.toDouble() ?? 7,
          ),
        );
        await controller.addRasterLayer(
          id,
          id,
          RasterLayerProperties(
            rasterOpacity: kind == 'rain' ? 0.75 : 0.55,
            rasterFadeDuration: 0,
          ),
          belowLayerId: 'track-line',
        );
        _radarShown.add(id);
      } on Exception {
        // The image of this time cannot be shown; the next one may.
      }
    }
  }

  void _showFrame(int index) {
    setState(() => _frame = index);
    _applyRadar();
  }

  void _togglePlay() {
    if (_player != null) {
      _player!.cancel();
      setState(() => _player = null);
      return;
    }
    setState(() {
      _player = Timer.periodic(const Duration(milliseconds: 900), (_) {
        final count = _frames?.times.length ?? 0;
        if (count > 0) _showFrame((_frame + 1) % count);
      });
    });
  }

  @override
  void dispose() {
    _player?.cancel();
    super.dispose();
  }

  /// A tap for looking things up: what the map draws around the finger.
  Future<void> _lookUp(math.Point<double> point, LatLng coordinates) async {
    final onPlace = widget.content.onPlace;
    final controller = _controller;
    if (onPlace == null || controller == null) return;
    final features = <({String layer, Map<String, dynamic> properties})>[];
    try {
      final found = await controller.queryRenderedFeaturesInRect(
        Rect.fromCircle(center: Offset(point.x, point.y), radius: 22),
        const [],
        null,
      );
      for (final feature in found) {
        final json = feature is String ? jsonDecode(feature) : feature;
        if (json is! Map) continue;
        final properties = json['properties'];
        final layer = json['sourceLayer'] ?? json['source-layer'];
        if (properties is Map) {
          features.add((
            layer: '${layer ?? properties['layer'] ?? ''}',
            properties: properties.cast<String, dynamic>(),
          ));
        }
      }
    } on Exception {
      // The place is still worth showing without what lies there.
    }
    onPlace(
      MapPlace(
        position: GeoPoint(coordinates.latitude, coordinates.longitude),
        features: features,
      ),
    );
  }

  String _clock(int seconds) {
    final time = DateTime.fromMillisecondsSinceEpoch(seconds * 1000);
    String two(int value) => value.toString().padLeft(2, '0');
    return '${two(time.hour)}:${two(time.minute)}';
  }

  /// Where the markers and the highlight are on screen right now.
  Future<void> _updatePositions() async {
    final controller = _controller;
    if (controller == null || !_styleLoaded || !mounted) return;
    final highlight = widget.content.highlight;
    final ids = [
      for (final marker in widget.content.markers) marker.id,
      if (highlight != null) '_highlight',
    ];
    final points = [
      for (final marker in widget.content.markers) _latLng(marker.position),
      if (highlight != null) _latLng(highlight),
    ];
    if (points.isEmpty) {
      if (_positions.isNotEmpty) setState(() => _positions = const {});
      return;
    }
    final screen = await controller.toScreenLocationBatch(points);
    if (!mounted) return;
    // Android reports physical pixels; Flutter lays out in logical ones.
    final ratio = MediaQuery.devicePixelRatioOf(context);
    setState(() {
      _positions = {
        for (var i = 0; i < ids.length; i++)
          ids[i]: math.Point(screen[i].x / ratio, screen[i].y / ratio),
      };
    });
  }

  List<Widget> _overlay() {
    final placed = [
      for (final marker in widget.content.markers)
        if (_positions[marker.id] != null) marker,
    ];
    Widget at(
      math.Point<double> position,
      double size,
      Widget child,
      VoidCallback? onTap,
    ) => Positioned(
      left: position.x - size / 2,
      top: position.y - size / 2,
      width: size,
      height: size,
      child: GestureDetector(onTap: onTap, child: child),
    );

    final single = placed.where((m) => !m.clusters).toList();
    final clustering = placed.where((m) => m.clusters).toList();
    final groups = clusterByDistance([
      for (final marker in clustering) _positions[marker.id]!,
    ], _clusterRadius);
    final highlight = _positions['_highlight'];
    return [
      for (final marker in single)
        at(_positions[marker.id]!, marker.size, marker.child, marker.onTap),
      for (final group in groups)
        if (group.length == 1)
          at(
            _positions[clustering[group.first].id]!,
            clustering[group.first].size,
            clustering[group.first].child,
            clustering[group.first].onTap,
          )
        else
          at(
            _positions[clustering[group.first].id]!,
            40,
            ClusterMarker(count: group.length),
            () => widget.content.onClusterTap?.call([
              for (final i in group) clustering[i].id,
            ]),
          ),
      if (highlight != null)
        // The place chosen in the elevation profile: a dot with a halo that
        // stands out against track and markers.
        Positioned(
          left: highlight.x - 18,
          top: highlight.y - 18,
          child: IgnorePointer(
            child: Container(
              width: 36,
              height: 36,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.error
                    .withValues(alpha: 0.25),
                shape: BoxShape.circle,
              ),
              child: Container(
                width: 18,
                height: 18,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.error,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 3),
                  boxShadow: const [
                    BoxShadow(color: Colors.black38, blurRadius: 4),
                  ],
                ),
              ),
            ),
          ),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final start = _everything.isEmpty ? _fallback : _latLng(_everything.first);
    return ClipRect(
      child: Stack(
        children: [
          MapLibreMap(
            styleString: _style,
            initialCameraPosition: CameraPosition(
              target: start,
              zoom: _everything.isEmpty ? 6 : 12,
            ),
            trackCameraPosition: true,
            // Rotating is for finding one's way; markers follow the camera.
            rotateGesturesEnabled: widget.content.interactive,
            compassEnabled: true,
            tiltGesturesEnabled: false,
            scrollGesturesEnabled: widget.content.interactive,
            zoomGesturesEnabled: widget.content.interactive,
            onMapCreated: (controller) {
              _controller = controller;
              // Without network the map library would not even ask for tiles.
              // The tiles kept on the device (TileProxy, the library's own
              // cache) must still be shown, so it is told to ask anyway.
              controller.forceOnlineMode().catchError((_) {});
            },
            onStyleLoadedCallback: _onStyleLoaded,
            onCameraMove: (_) => _updatePositions(),
            onCameraIdle: _updatePositions,
            onMapClick: (point, coordinates) {
              if (widget.content.onPlace != null) {
                _lookUp(point, coordinates);
                return;
              }
              widget.content.onTap?.call(
                GeoPoint(coordinates.latitude, coordinates.longitude),
              );
            },
          ),
          ..._overlay(),
          if (widget.content.interactive &&
              (widget.layerSheet != null || widget.content.controls.isNotEmpty))
            Positioned(
              left: 8,
              top: 8,
              // The compass of the map sits in the right corner.
              right: 56,
              child: _MapFields(
                fields: [
                  if (widget.layerSheet case final sheet?) ...[
                    MapControl(
                      label: AppLocalizations.of(context).mapLayers,
                      builder: (context) => sheet(context, MapSheetPart.layers),
                    ),
                    MapControl(
                      label: AppLocalizations.of(context).mapLooks,
                      builder: (context) => sheet(context, MapSheetPart.looks),
                    ),
                  ],
                  ...widget.content.controls,
                ],
              ),
            ),
          if (widget.layerChoice.radar.isNotEmpty &&
              (_frames?.times.isNotEmpty ?? false))
            Positioned(
              left: 8,
              right: 8,
              bottom: 8,
              child: Material(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(24),
                elevation: 2,
                child: Row(
                  children: [
                    IconButton(
                      tooltip: AppLocalizations.of(context).mapRadarPlay,
                      icon: Icon(
                        _player == null ? Icons.play_arrow : Icons.pause,
                      ),
                      onPressed: _togglePlay,
                    ),
                    Expanded(
                      child: Slider(
                        max: (_frames!.times.length - 1).toDouble(),
                        divisions: math.max(1, _frames!.times.length - 1),
                        value: _frame
                            .clamp(0, _frames!.times.length - 1)
                            .toDouble(),
                        onChanged: _frames!.times.length < 2
                            ? null
                            : (value) => _showFrame(value.round()),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(right: 16),
                      child: Text(
                        _clock(
                          _frames!.times[_frame.clamp(
                            0,
                            _frames!.times.length - 1,
                          )],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// The fields at the top edge of the map; each opens a sheet.
class _MapFields extends StatelessWidget {
  const _MapFields({required this.fields});

  final List<MapControl> fields;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final field in fields)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Material(
                color: scheme.surface,
                borderRadius: BorderRadius.circular(18),
                elevation: 2,
                child: InkWell(
                  borderRadius: BorderRadius.circular(18),
                  onTap: () => showModalBottomSheet<void>(
                    context: context,
                    isScrollControlled: true,
                    useSafeArea: true,
                    // The map stays visible above the sheet: what is switched
                    // there shows at once.
                    constraints: BoxConstraints(
                      maxHeight: MediaQuery.sizeOf(context).height * 0.7,
                    ),
                    builder: field.builder,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 6, 6, 6),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          field.label,
                          style: Theme.of(context).textTheme.labelLarge,
                        ),
                        const Icon(Icons.arrow_drop_down, size: 20),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
