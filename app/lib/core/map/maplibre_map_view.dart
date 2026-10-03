import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../config/app_config.dart';
import 'geo.dart';
import 'map_view.dart';

/// The map drawn by MapLibre. The track is a line layer of the map; markers are
/// Flutter widgets laid over it and moved along with the camera.
class MapLibreMapView extends StatefulWidget {
  const MapLibreMapView({super.key, required this.content});

  final MapContent content;

  /// MapLibre GL JS is served by the app itself instead of a foreign CDN.
  static void configureWeb() {
    if (!kIsWeb) return;
    MapLibreMap.webLibrarySource = const MapLibreJsSource.urls(
      scriptUrl: 'maplibre/maplibre-gl.mjs',
      styleUrl: 'maplibre/maplibre-gl.css',
    );
  }

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

  /// Raster tiles from the configured source; replaceable until Phase 2.
  static final _style = jsonEncode({
    'version': 8,
    'sources': {
      'tiles': {
        'type': 'raster',
        'tiles': [AppConfig.mapTileUrl],
        'tileSize': 256,
        'attribution': '© OpenStreetMap contributors',
      },
    },
    'layers': [
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

  @override
  void didUpdateWidget(MapLibreMapView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_styleLoaded) return;
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
    // Android reports physical pixels, the browser logical ones.
    final ratio = kIsWeb ? 1.0 : MediaQuery.devicePixelRatioOf(context);
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
        Positioned(
          left: highlight.x - 8,
          top: highlight.y - 8,
          child: IgnorePointer(
            child: Container(
              width: 16,
              height: 16,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 3),
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
            rotateGesturesEnabled: false,
            tiltGesturesEnabled: false,
            scrollGesturesEnabled: widget.content.interactive,
            zoomGesturesEnabled: widget.content.interactive,
            onMapCreated: (controller) => _controller = controller,
            onStyleLoadedCallback: _onStyleLoaded,
            onCameraMove: (_) => _updatePositions(),
            onCameraIdle: _updatePositions,
            onMapClick: (_, coordinates) => widget.content.onTap?.call(
              GeoPoint(coordinates.latitude, coordinates.longitude),
            ),
          ),
          ..._overlay(),
        ],
      ),
    );
  }
}
