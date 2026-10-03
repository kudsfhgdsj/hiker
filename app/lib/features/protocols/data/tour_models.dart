import 'package:collection/collection.dart';

import '../../../core/map/geo.dart';

const _deepEquals = DeepCollectionEquality();

/// A tour as the API delivers it. The document is kept as JSON, so that the
/// app can send it back unchanged; the getters give typed access.
class Tour {
  const Tour(this.json);

  final Map<String, dynamic> json;

  String get id => json['id'] as String;
  String get title => json['title'] as String;
  String? get summary => json['summary'] as String?;
  int get version => json['version'] as int;
  String get permission => json['permission'] as String? ?? 'owner';
  bool get isOwner => permission == 'owner';
  bool get canEdit => permission != 'read';
  String? get ownerName =>
      (json['owner'] as Map<String, dynamic>?)?['display_name'] as String?;
  String? get coverPhotoId => json['cover_photo_id'] as String?;
  DateTime? get startTime => _time(json['start_time']);
  DateTime? get endTime => _time(json['end_time']);

  List<Map<String, dynamic>> _list(String key) => [
    ...?(json[key] as List<dynamic>?)?.cast<Map<String, dynamic>>(),
  ];

  List<Map<String, dynamic>> get gear => _list('gear');
  List<Map<String, dynamic>> get food => _list('food');
  List<Map<String, dynamic>> get peaks => _list('peaks');
  List<Map<String, dynamic>> get partners => _list('partners');
  List<Map<String, dynamic>> get weather => _list('weather');

  /// Names of the peaks; the list endpoint only delivers the names.
  List<String> get peakNames => [
    for (final peak in (json['peaks'] as List<dynamic>? ?? const []))
      peak is String ? peak : (peak as Map<String, dynamic>)['name'] as String,
  ];

  Map<String, dynamic> get computed =>
      json['computed'] as Map<String, dynamic>? ?? const {};
  Map<String, dynamic>? get trackStats =>
      json['track_stats'] as Map<String, dynamic>?;
  Map<String, dynamic>? get caloriesEstimate =>
      json['calories_estimate'] as Map<String, dynamic>?;
  String get trackSource => json['track_source'] as String? ?? 'none';
  bool get hasTrack => trackSource != 'none';
  bool get weatherOutdated => json['weather_outdated'] as bool? ?? false;
  int get photoCount => json['photo_count'] as int? ?? 0;
  int get photoTimeOffsetSeconds =>
      json['photo_time_offset_seconds'] as int? ?? 0;

  /// The manual value, otherwise the computed one.
  int? get durationMinutes =>
      json['duration_minutes'] as int? ?? computed['duration_minutes'] as int?;
  int? get packWeightG =>
      json['pack_weight_start_g'] as int? ??
      computed['pack_weight_start_g'] as int?;
  double? get caloriesEaten => (computed['calories_eaten'] as num?)?.toDouble();

  /// Manual value, otherwise the estimate; [caloriesBurnedEstimated] tells which.
  double? get caloriesBurned =>
      ((json['calories_burned'] ?? computed['calories_burned']) as num?)
          ?.toDouble();
  bool get caloriesBurnedEstimated =>
      json['calories_burned_source'] == 'estimated';

  GeoPoint? _point(String key) {
    final point = json[key] as Map<String, dynamic>?;
    if (point == null) return null;
    return GeoPoint(
      (point['lat'] as num).toDouble(),
      (point['lon'] as num).toDouble(),
    );
  }

  GeoPoint? get startPoint => _point('start_point');
  GeoPoint? get endPoint => _point('end_point');
  String? get startName =>
      (json['start_point'] as Map<String, dynamic>?)?['name'] as String?;
  String? get endName =>
      (json['end_point'] as Map<String, dynamic>?)?['name'] as String?;

  static DateTime? _time(Object? value) =>
      value == null ? null : DateTime.parse(value as String);
}

/// The fields of the tour document that `PUT /tours/{id}` replaces.
const documentFields = [
  'title',
  'summary',
  'start_time',
  'end_time',
  'duration_minutes',
  'pack_weight_start_g',
  'calories_burned',
  'gear',
  'food',
  'peaks',
  'partners',
];

/// Fields only the owner may change; with `edit` they are sent back unchanged.
const ownerOnlyFields = {
  'start_time',
  'end_time',
  'duration_minutes',
  'pack_weight_start_g',
  'calories_burned',
};

/// The editable part of a tour, as a copy that can be changed freely.
Map<String, dynamic> documentOf(Map<String, dynamic> tour) => {
  for (final field in documentFields)
    field: switch (tour[field]) {
      final List<dynamic> list => [
        for (final entry in list)
          Map<String, dynamic>.of(entry as Map<String, dynamic>),
      ],
      final value => value,
    },
};

class MergeResult {
  const MergeResult(this.merged, this.conflicts);

  /// My changes on top of the current state; for conflicts the current value.
  final Map<String, dynamic> merged;

  /// Fields both sides changed to different values.
  final List<String> conflicts;
}

/// Field-wise merge after a version conflict: [base] is what the edit started
/// from, [mine] the edited document, [current] the newer state of the server.
MergeResult mergeDocuments(
  Map<String, dynamic> base,
  Map<String, dynamic> mine,
  Map<String, dynamic> current,
) {
  final merged = <String, dynamic>{};
  final conflicts = <String>[];
  for (final field in documentFields) {
    final iChanged = !_deepEquals.equals(base[field], mine[field]);
    final theyChanged = !_deepEquals.equals(base[field], current[field]);
    if (iChanged &&
        theyChanged &&
        !_deepEquals.equals(mine[field], current[field])) {
      conflicts.add(field);
      merged[field] = current[field];
    } else {
      merged[field] = iChanged ? mine[field] : current[field];
    }
  }
  return MergeResult(merged, conflicts);
}

/// The track series of a tour: columns of equal length.
class TrackData {
  const TrackData(this.json);

  final Map<String, dynamic> json;

  Map<String, dynamic>? get _series => json['series'] as Map<String, dynamic>?;
  Map<String, dynamic>? get stats => json['stats'] as Map<String, dynamic>?;
  bool get isEmpty =>
      _series == null || (_series!['lat'] as List<dynamic>).isEmpty;

  List<double> _numbers(String key) => [
    for (final v in _series![key] as List<dynamic>) (v as num).toDouble(),
  ];

  List<double> get distances => isEmpty ? const [] : _numbers('distance_m');

  List<GeoPoint> get points {
    if (isEmpty) return const [];
    final lat = _numbers('lat'), lon = _numbers('lon');
    return [for (var i = 0; i < lat.length; i++) GeoPoint(lat[i], lon[i])];
  }

  List<double?>? get elevations => (_series?['elevation_m'] as List<dynamic>?)
      ?.map((v) => (v as num?)?.toDouble())
      .toList();

  List<int?>? get heartRates => (_series?['heart_rate'] as List<dynamic>?)
      ?.map((v) => (v as num?)?.round())
      .toList();

  /// The point of the track closest to a distance along it.
  GeoPoint? pointAt(double distanceM) {
    final index = nearestIndex(distances, distanceM);
    return index < 0 ? null : points[index];
  }
}
