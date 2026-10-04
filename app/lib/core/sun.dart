import 'dart:math' as math;

/// Where the sun is: sunrise, sunset and twilight for a place and a day.
///
/// The same formulas as on the server (`core/sun.py`, after the NOAA solar
/// calculator), so that the app can tell the times without network. The
/// horizon is the mathematical one: mountains around a place make the sun
/// rise later and set earlier there.
class SunTimes {
  const SunTimes({
    required this.noon,
    this.dawn,
    this.sunrise,
    this.sunset,
    this.dusk,
  });

  /// All times in UTC; null where the sun does not cross that height.
  final DateTime? dawn;
  final DateTime? sunrise;
  final DateTime noon;
  final DateTime? sunset;
  final DateTime? dusk;
}

const _sunriseDeg = -0.833;
const _civilDeg = -6.0;

double _rad(double degrees) => degrees * math.pi / 180;
double _deg(double radians) => radians * 180 / math.pi;

/// Declination of the sun (radians) and equation of time (minutes) at noon UTC.
(double, double) _declinationAndEquation(DateTime day) {
  final julian =
      DateTime.utc(day.year, day.month, day.day, 12).millisecondsSinceEpoch /
          86400000 +
      2440587.5;
  final century = (julian - 2451545.0) / 36525.0;
  final meanLongitude = _rad(
    (280.46646 + century * (36000.76983 + century * 0.0003032)) % 360,
  );
  final meanAnomaly = _rad(
    357.52911 + century * (35999.05029 - 0.0001537 * century),
  );
  final eccentricity =
      0.016708634 - century * (0.000042037 + 0.0000001267 * century);
  final centre = _rad(
    math.sin(meanAnomaly) *
            (1.914602 - century * (0.004817 + 0.000014 * century)) +
        math.sin(2 * meanAnomaly) * (0.019993 - 0.000101 * century) +
        math.sin(3 * meanAnomaly) * 0.000289,
  );
  final trueLongitude = meanLongitude + centre;
  final omega = _rad(125.04 - 1934.136 * century);
  final apparent = trueLongitude - _rad(0.00569 + 0.00478 * math.sin(omega));
  final obliquity = _rad(
    23 +
        (26 +
                (21.448 -
                        century *
                            (46.815 +
                                century * (0.00059 - century * 0.001813))) /
                    60) /
            60 +
        0.00256 * math.cos(omega),
  );
  final declination = math.asin(math.sin(obliquity) * math.sin(apparent));
  final y = math.pow(math.tan(obliquity / 2), 2).toDouble();
  final equation =
      4 *
      _deg(
        y * math.sin(2 * meanLongitude) -
            2 * eccentricity * math.sin(meanAnomaly) +
            4 *
                eccentricity *
                y *
                math.sin(meanAnomaly) *
                math.cos(2 * meanLongitude) -
            0.5 * y * y * math.sin(4 * meanLongitude) -
            1.25 * eccentricity * eccentricity * math.sin(2 * meanAnomaly),
      );
  return (declination, equation);
}

DateTime _plusMinutes(DateTime moment, double minutes) =>
    moment.add(Duration(microseconds: (minutes * 60e6).round()));

/// The day at a place. With an elevation the horizon lies lower, as seen
/// from a summit that stands above its surroundings: the sun rises earlier
/// and sets later there.
SunTimes sunTimes(
  double lat,
  double lon,
  DateTime day, {
  double elevationM = 0,
}) {
  final (declination, equation) = _declinationAndEquation(day);
  final midnight = DateTime.utc(day.year, day.month, day.day);
  final noon = _plusMinutes(midnight, 720 - 4 * lon - equation);

  // Half of the time the sun spends above the height, in minutes.
  double? crossing(double heightDeg) {
    final cosine =
        (math.sin(_rad(heightDeg)) -
            math.sin(_rad(lat)) * math.sin(declination)) /
        (math.cos(_rad(lat)) * math.cos(declination));
    if (cosine < -1 || cosine > 1) return null;
    return 4 * _deg(math.acos(cosine));
  }

  // Dip of the horizon: about 1.76 arc minutes times the root of the height.
  final dip = 1.76 / 60 * math.sqrt(math.max(0, elevationM));
  final day_ = crossing(_sunriseDeg - dip);
  final light = crossing(_civilDeg);
  return SunTimes(
    noon: noon,
    sunrise: day_ == null ? null : _plusMinutes(noon, -day_),
    sunset: day_ == null ? null : _plusMinutes(noon, day_),
    dawn: light == null ? null : _plusMinutes(noon, -light),
    dusk: light == null ? null : _plusMinutes(noon, light),
  );
}

/// Height above the horizon and compass direction of the sun, in degrees.
({double height, double direction}) sunPosition(
  double lat,
  double lon,
  DateTime moment,
) {
  final utc = moment.toUtc();
  final (declination, equation) = _declinationAndEquation(utc);
  final minutes = utc.hour * 60 + utc.minute + utc.second / 60;
  final hourAngle = _rad((minutes + equation + 4 * lon) / 4 - 180);
  final latitude = _rad(lat);
  final sine =
      math.sin(latitude) * math.sin(declination) +
      math.cos(latitude) * math.cos(declination) * math.cos(hourAngle);
  final height = math.asin(sine.clamp(-1.0, 1.0));
  final azimuth = math.atan2(
    math.sin(hourAngle),
    math.cos(hourAngle) * math.sin(latitude) -
        math.tan(declination) * math.cos(latitude),
  );
  return (height: _deg(height), direction: (_deg(azimuth) + 180) % 360);
}
