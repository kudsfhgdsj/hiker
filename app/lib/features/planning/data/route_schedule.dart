import '../../../core/sun.dart';
import 'route_models.dart';

/// When the walker is where, and where the sun is then. Computed on the
/// device from the line, the pace and the start, by the same rules as the
/// server (`planning/schedule.py`): it needs no network, and a new start
/// time needs no new line.

/// Seconds from the start at every point of the line; the last one is the
/// walking time. Each piece gets its share by the rule of the whole.
List<int> timesAlong(RouteResult result, Pace pace) {
  final distances = result.distances;
  final elevations = result.elevations;
  final shares = <double>[0];
  for (var i = 1; i < distances.length; i++) {
    final horizontal =
        (distances[i] - distances[i - 1]) / (pace.distanceKmPerH * 1000);
    final before = elevations?[i - 1], after = elevations?[i];
    var vertical = 0.0;
    if (before != null && after != null) {
      final change = after - before;
      vertical = change > 0
          ? change / pace.ascentMPerH
          : -change / pace.descentMPerH;
    }
    final longer = horizontal > vertical ? horizontal : vertical;
    final shorter = horizontal > vertical ? vertical : horizontal;
    shares.add(shares.last + longer + shorter / 2);
  }
  final total = shares.last == 0 ? 1.0 : shares.last;
  final duration = pace.walkingTimeS(
    result.distanceM,
    result.ascentM,
    result.descentM,
  );
  return [for (final share in shares) (share / total * duration).round()];
}

/// The highest point of the route and the sun when the walker is there.
class SummitMoment {
  const SummitMoment({
    required this.time,
    required this.elevationM,
    required this.sunHeightDeg,
    required this.sunDirectionDeg,
  });

  final DateTime time;
  final double elevationM;
  final double sunHeightDeg;
  final double sunDirectionDeg;
}

/// How a tour lies in its day: sunrise and sunset at the start point.
class SunReport {
  const SunReport({
    required this.sun,
    required this.start,
    required this.end,
    this.summit,
  });

  final SunTimes sun;
  final DateTime start;

  /// Start plus walking time, without breaks.
  final DateTime end;
  final SummitMoment? summit;

  /// Walking in the dark: before first light or after last light.
  bool get startsInDark => sun.dawn != null && start.isBefore(sun.dawn!);
  bool get endsInDark => sun.dusk != null && end.isAfter(sun.dusk!);

  /// Between the end of the tour and sunset; negative if the sun sets first.
  Duration? get daylightLeft => sun.sunset?.difference(end);
}

SunReport? sunReport(RouteResult? result, DateTime? start, Pace pace) {
  if (result == null || start == null) return null;
  final points = result.points;
  if (points.isEmpty) return null;
  final begin = start.toUtc();
  final times = timesAlong(result, pace);
  final elevations = result.elevations;
  SummitMoment? summit;
  if (elevations != null) {
    var top = -1;
    for (var i = 0; i < elevations.length; i++) {
      final value = elevations[i];
      if (value != null && (top < 0 || value > elevations[top]!)) top = i;
    }
    if (top >= 0) {
      final moment = begin.add(Duration(seconds: times[top]));
      final position = sunPosition(points[top].lat, points[top].lon, moment);
      summit = SummitMoment(
        time: moment,
        elevationM: elevations[top]!,
        sunHeightDeg: position.height,
        sunDirectionDeg: position.direction,
      );
    }
  }
  return SunReport(
    sun: sunTimes(points.first.lat, points.first.lon, begin),
    start: begin,
    end: begin.add(Duration(seconds: times.last)),
    summit: summit,
  );
}
