import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../../../core/db/app_database.dart';
import '../../../core/map/geo.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import 'route_models.dart';

/// Planning without network: BRouter runs on the device and computes on path
/// data the app downloaded from the user's own server. The server stays the
/// authority: it computes the line again when the route is synced.

/// A point of a line with its elevation, if known.
typedef LinePoint = ({double lat, double lon, double? ele});

/// No path data on the device for the area of a waypoint.
const offlineNoData = 'offline_no_data';

/// The tile of 5° x 5° a position lies in, named after its south-west corner.
String segmentNameFor(GeoPoint point) {
  final lon = (point.lon / 5).floor() * 5;
  final lat = (point.lat / 5).floor() * 5;
  return '${lon < 0 ? 'W${-lon}' : 'E$lon'}_${lat < 0 ? 'S${-lat}' : 'N$lat'}';
}

/// Path data of one tile, on the server or on the device.
class SegmentInfo {
  const SegmentInfo({
    required this.name,
    required this.sizeBytes,
    this.modified,
  });

  factory SegmentInfo.fromJson(Json json) => SegmentInfo(
    name: json['name'] as String,
    sizeBytes: json['size_bytes'] as int,
    modified: DateTime.tryParse(json['modified'] as String? ?? ''),
  );

  final String name;
  final int sizeBytes;
  final DateTime? modified;

  /// E5_N45 → 5, 45: the south-west corner in degrees.
  (int, int) get corner {
    final parts = name.split('_');
    int degrees(String part, String negative) =>
        int.parse(part.substring(1)) * (part.startsWith(negative) ? -1 : 1);
    return (degrees(parts[0], 'W'), degrees(parts[1], 'S'));
  }
}

/// Where the app keeps BRouter's files; tests use a temporary folder.
final routingDirectoryProvider = FutureProvider<Directory>((ref) async {
  final support = await getApplicationSupportDirectory();
  return Directory('${support.path}/brouter');
});

/// The path data on the device and on the server.
class SegmentStore {
  const SegmentStore(this._dio, this._db, this._root);

  final Dio _dio;
  final AppDatabase _db;
  final Future<Directory> _root;

  static const _known = 'planning_segments';

  Future<Directory> get directory async {
    final folder = Directory('${(await _root).path}/segments');
    await folder.create(recursive: true);
    return folder;
  }

  Future<List<SegmentInfo>> installed() async {
    final files = (await directory).listSync().whereType<File>().where(
      (file) => file.path.endsWith('.rd5'),
    );
    return [
      for (final file in files)
        SegmentInfo(
          name: file.uri.pathSegments.last.replaceAll('.rd5', ''),
          sizeBytes: file.lengthSync(),
          modified: file.lastModifiedSync(),
        ),
    ]..sort((a, b) => a.name.compareTo(b.name));
  }

  Future<bool> has(String name) async =>
      File('${(await directory).path}/$name.rd5').existsSync();

  /// What the server offers; offline the last known answer.
  Future<List<SegmentInfo>> available() async {
    try {
      final response = await apiCall(
        () => _dio.get<List<dynamic>>('/planning/segments'),
      );
      final items = (response.data ?? const []).cast<Json>();
      await _db.putDocument(_known, _known, {'items': items});
      return [for (final item in items) SegmentInfo.fromJson(item)];
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final cached = await _db.getDocument(_known, _known);
      return [
        for (final item in cached?['items'] as List<dynamic>? ?? const [])
          SegmentInfo.fromJson(item as Json),
      ];
    }
  }

  /// Downloads a tile; [onProgress] gets the share that is done (0 to 1).
  /// The file only appears when it is complete.
  Future<void> download(
    String name, {
    void Function(double share)? onProgress,
    CancelToken? cancel,
  }) async {
    final target = File('${(await directory).path}/$name.rd5');
    final part = File('${target.path}.part');
    try {
      await apiCall(
        () => _dio.download(
          '/planning/segments/$name',
          part.path,
          cancelToken: cancel,
          // A tile has some hundred megabytes: no limit for the whole download.
          options: Options(receiveTimeout: Duration.zero),
          onReceiveProgress: (received, total) {
            if (total > 0) onProgress?.call(received / total);
          },
        ),
      );
      await part.rename(target.path);
    } finally {
      if (part.existsSync()) part.deleteSync();
    }
  }

  Future<void> delete(String name) async {
    final file = File('${(await directory).path}/$name.rd5');
    if (file.existsSync()) await file.delete();
  }
}

final segmentStoreProvider = Provider<SegmentStore>(
  (ref) => SegmentStore(
    ref.watch(dioProvider),
    ref.watch(appDatabaseProvider),
    ref.watch(routingDirectoryProvider.future),
  ),
);

/// Counts up when path data was loaded or removed.
class SegmentGeneration extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final segmentGenerationProvider = NotifierProvider<SegmentGeneration, int>(
  SegmentGeneration.new,
);

final installedSegmentsProvider = FutureProvider.autoDispose<List<SegmentInfo>>(
  (ref) {
    ref.watch(segmentGenerationProvider);
    return ref.watch(segmentStoreProvider).installed();
  },
);

final availableSegmentsProvider = FutureProvider.autoDispose<List<SegmentInfo>>(
  (ref) => ref.watch(segmentStoreProvider).available(),
);

/// Computes a line along paths on the device.
abstract class DeviceRouter {
  /// Throws an [ApiException] with `no_route` if no path connects the points.
  Future<List<LinePoint>> route(
    List<GeoPoint> points, {
    required int maxDifficulty,
    required bool viaFerrata,
  });
}

/// BRouter inside the app (see `MainActivity.kt`), with the same profile as
/// the server uses.
class BRouterDeviceRouter implements DeviceRouter {
  BRouterDeviceRouter(this._store, this._root);

  final SegmentStore _store;
  final Future<Directory> _root;

  static const _channel = MethodChannel('hiker/routing');
  static const _assets = ['hiker-hiking.brf', 'lookups.dat'];
  String? _profile;

  /// BRouter reads its profile from a file: copy it out of the app once per start.
  Future<String> _profilePath() async {
    final ready = _profile;
    if (ready != null) return ready;
    final folder = Directory('${(await _root).path}/profiles');
    await folder.create(recursive: true);
    for (final name in _assets) {
      final data = await rootBundle.load('assets/brouter/$name');
      await File('${folder.path}/$name')
          .writeAsBytes(data.buffer.asUint8List(), flush: true);
    }
    return _profile = '${folder.path}/${_assets.first}';
  }

  @override
  Future<List<LinePoint>> route(
    List<GeoPoint> points, {
    required int maxDifficulty,
    required bool viaFerrata,
  }) async {
    try {
      final line = await _channel.invokeMethod<Float64List>('route', {
        'segments': (await _store.directory).path,
        'profile': await _profilePath(),
        'points': [
          for (final point in points) [point.lat, point.lon],
        ],
        // The same parameters the server hands to its BRouter.
        'parameters': {
          'SAC_scale_limit': '$maxDifficulty',
          'SAC_scale_preferred': '$maxDifficulty',
          'allow_via_ferrata': viaFerrata ? '1' : '0',
        },
        'timeoutMs': 25000,
      });
      return [
        for (var i = 0; i + 2 < line!.length; i += 3)
          (
            lat: line[i],
            lon: line[i + 1],
            ele: line[i + 2].isNaN ? null : line[i + 2],
          ),
      ];
    } on PlatformException catch (error) {
      throw ApiException(
        code: error.code == 'no_route' ? 'no_route' : ApiException.unknown,
        message: error.message ?? '',
      );
    }
  }
}

/// The router of the device; null where there is none (tests replace it).
final deviceRouterProvider = Provider<DeviceRouter?>(
  (ref) => BRouterDeviceRouter(
    ref.watch(segmentStoreProvider),
    ref.watch(routingDirectoryProvider.future),
  ),
);

// --- The same computation as on the server (planning/service.py, estimate.py) ---

const _directStepM = 50.0;
const _elevationThresholdM = 3.0;
const _maxSeriesPoints = 2000;
const _earthRadiusM = 6371000.0;

double haversineM(double lat1, double lon1, double lat2, double lon2) {
  double rad(double degrees) => degrees * math.pi / 180;
  final halfLat = rad(lat2 - lat1) / 2, halfLon = rad(lon2 - lon1) / 2;
  final a =
      math.pow(math.sin(halfLat), 2) +
      math.cos(rad(lat1)) *
          math.cos(rad(lat2)) *
          math.pow(math.sin(halfLon), 2);
  return 2 * _earthRadiusM * math.asin(math.min(1, math.sqrt(a)));
}

/// Walking time after DIN 33466: 4 km/h, 300 m up and 500 m down per hour;
/// the larger of distance and elevation time counts in full, the other by half.
int walkingTimeS(double distanceM, double? ascentM, double? descentM) {
  final horizontal = distanceM / 4000;
  final vertical = (ascentM ?? 0) / 300 + (descentM ?? 0) / 500;
  return ((math.max(horizontal, vertical) +
              math.min(horizontal, vertical) / 2) *
          3600)
      .round();
}

List<LinePoint> _straight(LinePoint from, GeoPoint to) {
  final length = haversineM(from.lat, from.lon, to.lat, to.lon);
  final steps = math.max(1, (length / _directStepM).round());
  return [
    for (var step = 0; step <= steps; step++)
      (
        lat: from.lat + (to.lat - from.lat) * step / steps,
        lon: from.lon + (to.lon - from.lon) * step / steps,
        // Straight legs have no elevation offline; the server fills it in.
        ele: null,
      ),
  ];
}

/// Line and key figures of a draft, computed on the device. Legs along paths
/// need [router] and path data for the area ([hasSegment]).
Future<RouteResult> computeOnDevice(
  RouteDraft draft, {
  required DeviceRouter? router,
  required Future<bool> Function(String name) hasSegment,
}) async {
  final waypoints = draft.waypoints;
  final line = <LinePoint>[];
  void join(List<LinePoint> leg) =>
      line.addAll(line.isEmpty ? leg : leg.skip(1));
  var pending = [waypoints.first.position];
  var routed = false;

  Future<void> flush() async {
    if (pending.length < 2) return;
    if (router == null) {
      throw const ApiException(code: offlineNoData, message: 'no router');
    }
    for (final point in pending) {
      if (!await hasSegment(segmentNameFor(point))) {
        throw ApiException(code: offlineNoData, message: segmentNameFor(point));
      }
    }
    join(
      await router.route(
        pending,
        maxDifficulty: draft.maxDifficulty,
        viaFerrata: draft.viaFerrata,
      ),
    );
    routed = true;
  }

  for (final waypoint in waypoints.skip(1)) {
    if (draft.profile == 'direct' || waypoint.direct) {
      await flush();
      final last = pending.last;
      join(
        _straight(
          line.isEmpty ? (lat: last.lat, lon: last.lon, ele: null) : line.last,
          waypoint.position,
        ),
      );
      pending = [waypoint.position];
    } else {
      pending.add(waypoint.position);
    }
  }
  await flush();

  final distances = <double>[0];
  for (var i = 1; i < line.length; i++) {
    distances.add(
      distances.last +
          haversineM(
            line[i - 1].lat,
            line[i - 1].lon,
            line[i].lat,
            line[i].lon,
          ),
    );
  }
  final elevations = [for (final point in line) ?point.ele];
  double? ascent, descent, lowest, highest;
  if (elevations.isNotEmpty) {
    ascent = descent = 0;
    var reference = elevations.first;
    for (final elevation in elevations.skip(1)) {
      final change = elevation - reference;
      if (change >= _elevationThresholdM) {
        ascent = ascent! + change;
        reference = elevation;
      } else if (change <= -_elevationThresholdM) {
        descent = descent! - change;
        reference = elevation;
      }
    }
    lowest = elevations.reduce(math.min).roundToDouble();
    highest = elevations.reduce(math.max).roundToDouble();
    ascent = ascent!.roundToDouble();
    descent = descent!.roundToDouble();
  }
  // Long lines are thinned out evenly, like the series of the server.
  final count = line.length;
  final indexes = count > _maxSeriesPoints
      ? {
          for (var i = 0; i < _maxSeriesPoints; i++)
            (i * (count - 1) / (_maxSeriesPoints - 1)).round(),
        }.toList()
      : [for (var i = 0; i < count; i++) i];
  double round(double value, int digits) =>
      double.parse(value.toStringAsFixed(digits));
  final total = distances.last.roundToDouble();
  return RouteResult({
    'engine': routed ? 'device' : 'direct',
    'on_device': true,
    'series': {
      'distance_m': [for (final i in indexes) round(distances[i], 1)],
      'lat': [for (final i in indexes) round(line[i].lat, 6)],
      'lon': [for (final i in indexes) round(line[i].lon, 6)],
      'elevation_m': elevations.isEmpty
          ? null
          : [
              for (final i in indexes)
                line[i].ele == null ? null : round(line[i].ele!, 1),
            ],
    },
    'distance_m': total,
    'ascent_m': ascent,
    'descent_m': descent,
    'min_elevation_m': lowest,
    'max_elevation_m': highest,
    'duration_s': walkingTimeS(total, ascent, descent),
    'duration_estimated': true,
  });
}

/// A route as a GPX file with one track, written on the device.
String routeGpx(String title, RouteResult result) {
  String escape(String text) => text
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;');
  final points = result.points;
  final elevations = result.elevations;
  final buffer = StringBuffer()
    ..writeln('<?xml version="1.0" encoding="UTF-8"?>')
    ..writeln(
      '<gpx version="1.1" creator="hiker" xmlns="http://www.topografix.com/GPX/1/1">',
    )
    ..writeln('<trk><name>${escape(title)}</name><trkseg>');
  for (var i = 0; i < points.length; i++) {
    final elevation = elevations?[i];
    buffer.writeln(
      '<trkpt lat="${points[i].lat.toStringAsFixed(7)}" '
      'lon="${points[i].lon.toStringAsFixed(7)}">'
      '${elevation == null ? '' : '<ele>${elevation.toStringAsFixed(1)}</ele>'}'
      '</trkpt>',
    );
  }
  buffer.writeln('</trkseg></trk></gpx>');
  return buffer.toString();
}
