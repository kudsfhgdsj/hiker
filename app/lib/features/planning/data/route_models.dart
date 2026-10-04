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

/// How fast the walker is: what they cover in an hour. Of the time for the
/// distance and the time for the elevation the larger one counts in full and
/// the smaller one by half; breaks are not included.
class Pace {
  const Pace({
    required this.preset,
    required this.ascentMPerH,
    required this.descentMPerH,
    required this.distanceKmPerH,
    this.name,
  });

  const Pace.custom({
    required this.ascentMPerH,
    required this.descentMPerH,
    required this.distanceKmPerH,
    this.name,
  }) : preset = customPreset;

  factory Pace.fromJson(Json? json) {
    if (json == null) return dav;
    final preset = json['preset'] as String? ?? 'dav';
    return presets[preset] ??
        Pace.custom(
          name: json['name'] as String?,
          ascentMPerH: (json['ascent_m_per_h'] as num?)?.toDouble() ?? 300,
          descentMPerH: (json['descent_m_per_h'] as num?)?.toDouble() ?? 500,
          distanceKmPerH: (json['distance_km_per_h'] as num?)?.toDouble() ?? 4,
        );
  }

  static const customPreset = 'custom';

  /// German Alpine Club (DIN 33466).
  static const dav = Pace(
    preset: 'dav',
    ascentMPerH: 300,
    descentMPerH: 500,
    distanceKmPerH: 4,
  );

  /// Swiss Alpine Club.
  static const sac = Pace(
    preset: 'sac',
    ascentMPerH: 400,
    descentMPerH: 800,
    distanceKmPerH: 4,
  );

  /// Well trained.
  static const pro = Pace(
    preset: 'pro',
    ascentMPerH: 600,
    descentMPerH: 1000,
    distanceKmPerH: 6,
  );

  static const presets = {'dav': dav, 'sac': sac, 'pro': pro};

  /// `dav`, `sac`, `pro` or `custom`.
  final String preset;

  /// Name of the saved pace the values come from, if any.
  final String? name;
  final double ascentMPerH;
  final double descentMPerH;
  final double distanceKmPerH;

  bool get isCustom => preset == customPreset;

  /// Seconds for a route; without elevation only the distance counts.
  int walkingTimeS(double distanceM, double? ascentM, double? descentM) {
    final horizontal = distanceM / (distanceKmPerH * 1000);
    final vertical =
        (ascentM ?? 0) / ascentMPerH + (descentM ?? 0) / descentMPerH;
    final longer = horizontal > vertical ? horizontal : vertical;
    final shorter = horizontal > vertical ? vertical : horizontal;
    return ((longer + shorter / 2) * 3600).round();
  }

  Json toJson() => isCustom
      ? {
          'preset': preset,
          'name': name,
          'ascent_m_per_h': ascentMPerH,
          'descent_m_per_h': descentMPerH,
          'distance_km_per_h': distanceKmPerH,
        }
      : {'preset': preset};

  @override
  bool operator ==(Object other) =>
      other is Pace &&
      other.preset == preset &&
      other.name == name &&
      other.ascentMPerH == ascentMPerH &&
      other.descentMPerH == descentMPerH &&
      other.distanceKmPerH == distanceKmPerH;

  @override
  int get hashCode =>
      Object.hash(preset, name, ascentMPerH, descentMPerH, distanceKmPerH);
}

/// A pace the user saved under a name; only they see it.
class SavedPace {
  const SavedPace(this.json);

  final Json json;

  String get id => json['id'] as String;
  String get name => json['name'] as String? ?? '';

  Pace get pace => Pace.custom(
    name: name,
    ascentMPerH: (json['ascent_m_per_h'] as num).toDouble(),
    descentMPerH: (json['descent_m_per_h'] as num).toDouble(),
    distanceKmPerH: (json['distance_km_per_h'] as num).toDouble(),
  );
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

  /// Computed on the device without network; the server computes it again
  /// when the route is synced.
  bool get onDevice => json['on_device'] == true;

  /// Estimated walking time without breaks, for the pace it was asked with.
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
    this.tags = const [],
    this.startTime,
    this.profile = 'hiking',
    this.maxDifficulty = 3,
    this.viaFerrata = false,
    this.pace = Pace.dav,
    this.waypoints = const [],
  });

  final String title;
  final String? description;

  final List<String> tags;

  /// When the walker sets out; null if not decided yet.
  final DateTime? startTime;

  /// `hiking`: along paths. `direct`: straight lines.
  final String profile;

  /// Hardest allowed path on the SAC scale, 1 (T1) to 6 (T6).
  final int maxDifficulty;
  final bool viaFerrata;

  /// For the walking time.
  final Pace pace;
  final List<RouteWaypoint> waypoints;

  /// What line and figures depend on; the same for preview and saving.
  Json courseJson() => {
    'profile': profile,
    'max_difficulty': maxDifficulty,
    'via_ferrata': viaFerrata,
    'pace': pace.toJson(),
    'waypoints': [for (final point in waypoints) point.toJson()],
  };

  Json toJson() => {
    'title': title,
    'description': description,
    'tags': tags,
    'start_time': startTime?.toUtc().toIso8601String(),
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

  DateTime? get startTime =>
      DateTime.tryParse(json['start_time'] as String? ?? '')?.toUtc();

  List<String> get tags => [
    for (final tag in json['tags'] as List<dynamic>? ?? const []) tag as String,
  ];

  Pace get pace => Pace.fromJson(json['pace'] as Json?);

  double? get distanceM => (json['distance_m'] as num?)?.toDouble();
  double? get ascentM => (json['ascent_m'] as num?)?.toDouble();
  int? get durationS => (json['duration_s'] as num?)?.round();

  RouteResult? get result => RouteResult.of(json);

  RouteDraft get draft => RouteDraft(
    title: title,
    description: json['description'] as String?,
    tags: tags,
    startTime: startTime,
    profile: profile,
    maxDifficulty: json['max_difficulty'] as int? ?? 3,
    viaFerrata: json['via_ferrata'] as bool? ?? false,
    pace: pace,
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
