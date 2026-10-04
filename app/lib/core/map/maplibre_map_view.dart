import 'dart:convert';
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

  /// Builds the sheet for choosing layers; null hides the button.
  final WidgetBuilder? layerSheet;

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

  /// The own vector map, or else a map of raster tiles only.
  late final String _style =
      widget.styleJson ??
      jsonEncode({
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
  }

  @override
  void didUpdateWidget(MapLibreMapView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_styleLoaded) return;
    if (oldWidget.layerChoice != widget.layerChoice) _applyLayerChoice();
    if (!listEquals(oldWidget.content.track, widget.content.track)) {
      _controller?.setGeoJsonSource(_source, _trackGeoJson());
    }
    _updatePositions();
  }

  Future<void> _onStyleLoaded() async {
    final controller = _controller;
    if (controller == null) return;
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
    final bounds = GeoBounds.around(_everything);
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
                top: 40,
                right: 40,
                bottom: 40,
              ),
      );
    }
    await _updatePositions();
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
            onMapClick: (_, coordinates) => widget.content.onTap?.call(
              GeoPoint(coordinates.latitude, coordinates.longitude),
            ),
          ),
          ..._overlay(),
          if (widget.layerSheet != null && widget.content.interactive)
            Positioned(
              left: 8,
              top: 8,
              child: Material(
                color: Theme.of(context).colorScheme.surface,
                shape: const CircleBorder(),
                elevation: 2,
                child: IconButton(
                  tooltip: AppLocalizations.of(context).mapLayers,
                  icon: const Icon(Icons.layers_outlined),
                  onPressed: () => showModalBottomSheet<void>(
                    context: context,
                    builder: widget.layerSheet!,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
