import '../../../core/map/geo.dart';

typedef Json = Map<String, dynamic>;

/// A point the user set; the route passes through all of them in order.
class RouteWaypoint {
  const RouteWaypoint({
    required this.position,
    this.name = '',
    this.direct = false,
  });

  factory RouteWaypoint.fromJson(Json json) => RouteWaypoint(
    position: GeoPoint(
      (json['lat'] as num).toDouble(),
      (json['lon'] as num).toDouble(),
    ),
    name: json['name'] as String? ?? '',
    direct: json['direct'] as bool? ?? false,
  );

  final GeoPoint position;
  final String name;

  /// The leg to this point is a straight line, whatever the profile says.
  final bool direct;

  RouteWaypoint copyWith({GeoPoint? position, String? name, bool? direct}) =>
      RouteWaypoint(
        position: position ?? this.position,
        name: name ?? this.name,
        direct: direct ?? this.direct,
      );

  Json toJson() => {
    'lat': position.lat,
    'lon': position.lon,
    'name': name.isEmpty ? null : name,
    'direct': direct,
  };
}

/// The line the server computed from the waypoints, with its key figures.
class RouteResult {
  const RouteResult(this.json);

  final Json json;

  static RouteResult? of(Json json) =>
      json['series'] == null ? null : RouteResult(json);

  Json get _series => json['series'] as Json;

  List<double> _numbers(String key) => [
    for (final v in _series[key] as List<dynamic>) (v as num).toDouble(),
  ];

  List<double> get distances => _numbers('distance_m');

  List<GeoPoint> get points {
    final lat = _numbers('lat'), lon = _numbers('lon');
    return [for (var i = 0; i < lat.length; i++) GeoPoint(lat[i], lon[i])];
  }

  List<double?>? get elevations => (_series['elevation_m'] as List<dynamic>?)
      ?.map((v) => (v as num?)?.toDouble())
      .toList();

  double get distanceM => (json['distance_m'] as num).toDouble();
  double? get ascentM => (json['ascent_m'] as num?)?.toDouble();
  double? get descentM => (json['descent_m'] as num?)?.toDouble();

  /// Estimated walking time without breaks (DIN 33466).
  int get durationS => (json['duration_s'] as num).round();

  /// The point of the line closest to a distance along it.
  GeoPoint? pointAt(double distanceM) {
    final index = nearestIndex(distances, distanceM);
    return index < 0 ? null : points[index];
  }
}

/// What the user decides about a route; the line follows from it.
class RouteDraft {
  const RouteDraft({
    this.title = '',
    this.description,
    this.plannedDate,
    this.profile = 'hiking',
    this.maxDifficulty = 3,
    this.viaFerrata = false,
    this.waypoints = const [],
  });

  final String title;
  final String? description;

  /// ISO date, e.g. `2026-07-18`.
  final String? plannedDate;

  /// `hiking`: along paths. `direct`: straight lines.
  final String profile;

  /// Hardest allowed path on the SAC scale, 1 (T1) to 6 (T6).
  final int maxDifficulty;
  final bool viaFerrata;
  final List<RouteWaypoint> waypoints;

  /// What the course of the line depends on; the same for preview and saving.
  Json courseJson() => {
    'profile': profile,
    'max_difficulty': maxDifficulty,
    'via_ferrata': viaFerrata,
    'waypoints': [for (final point in waypoints) point.toJson()],
  };

  Json toJson() => {
    'title': title,
    'description': description,
    'planned_date': plannedDate,
    ...courseJson(),
  };
}

/// A stored route. Drafted offline it has no line until the next sync.
class PlannedRoute {
  const PlannedRoute(this.json);

  final Json json;

  String get id => json['id'] as String;
  String get title => json['title'] as String? ?? '';
  int get version => json['version'] as int? ?? 0;
  String get profile => json['profile'] as String? ?? 'hiking';

  DateTime? get plannedDate =>
      DateTime.tryParse(json['planned_date'] as String? ?? '');

  double? get distanceM => (json['distance_m'] as num?)?.toDouble();
  double? get ascentM => (json['ascent_m'] as num?)?.toDouble();
  int? get durationS => (json['duration_s'] as num?)?.round();

  RouteResult? get result => RouteResult.of(json);

  RouteDraft get draft => RouteDraft(
    title: title,
    description: json['description'] as String?,
    plannedDate: json['planned_date'] as String?,
    profile: profile,
    maxDifficulty: json['max_difficulty'] as int? ?? 3,
    viaFerrata: json['via_ferrata'] as bool? ?? false,
    waypoints: [
      for (final point in json['waypoints'] as List<dynamic>? ?? const [])
        RouteWaypoint.fromJson(point as Json),
    ],
  );
}

/// What the server can plan with.
class PlanningInfo {
  const PlanningInfo({required this.routingAvailable, this.attribution});

  factory PlanningInfo.fromJson(Json json) => PlanningInfo(
    routingAvailable: json['routing_available'] as bool? ?? false,
    attribution: json['attribution'] as String?,
  );

  /// False: only straight lines can be planned.
  final bool routingAvailable;

  /// Must be shown with routes along paths (ODbL).
  final String? attribution;
}
