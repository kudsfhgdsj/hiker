import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/sun.dart';

String clock(DateTime? moment) =>
    '${moment!.hour.toString().padLeft(2, '0')}:${moment.minute.toString().padLeft(2, '0')}';

void main() {
  test('sunrise and sunset match the almanac, as on the server', () {
    // Säntis at midsummer and midwinter (UTC).
    final summer = sunTimes(47.2494, 9.3433, DateTime.utc(2026, 6, 21));
    expect(clock(summer.sunrise), '03:26');
    expect(clock(summer.sunset), '19:22');
    expect(summer.dawn!.isBefore(summer.sunrise!), isTrue);
    expect(summer.dusk!.isAfter(summer.sunset!), isTrue);
    final winter = sunTimes(47.2494, 9.3433, DateTime.utc(2026, 12, 21));
    expect(clock(winter.sunrise), '07:06');
    expect(clock(winter.sunset), '15:34');
  });

  test('north of the polar circle the sun does not set in summer', () {
    expect(sunTimes(78.2, 15.6, DateTime.utc(2026, 6, 21)).sunrise, isNull);
  });

  test('from a summit the sun is seen some minutes longer', () {
    final day = DateTime.utc(2026, 6, 21);
    final valley = sunTimes(47.2494, 9.3433, day);
    final summit = sunTimes(47.2494, 9.3433, day, elevationM: 2500);
    final earlier = valley.sunrise!.difference(summit.sunrise!).inMinutes;
    expect(earlier, inInclusiveRange(6, 19));
    expect(summit.sunset!.isAfter(valley.sunset!), isTrue);
    expect(summit.dawn, valley.dawn);
  });

  test('at noon the sun stands in the south, high in summer', () {
    final noon = sunTimes(47.2494, 9.3433, DateTime.utc(2026, 6, 21)).noon;
    final position = sunPosition(47.2494, 9.3433, noon);
    expect(position.height, inInclusiveRange(65, 67));
    expect(position.direction, inInclusiveRange(179, 181));
  });
}
