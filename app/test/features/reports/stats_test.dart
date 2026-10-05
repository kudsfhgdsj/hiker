import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/features/reports/presentation/stats_screen.dart';
import 'package:hiker/features/reports/reports_module.dart';

import '../../helpers.dart';

const totals = {
  'tours': 5,
  'tours_with_track': 3,
  'days': 4,
  'distance_m': 33500,
  'ascent_m': 2900,
  'descent_m': 2800,
  'moving_time_s': 36000,
  'peaks': 1,
};

FakeApi statsApi({List<Object?>? wishes}) => FakeApi({
  'GET /modules': (_, _) => ok([
    {'name': 'reports', 'version': '0.1.0'},
  ]),
  'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
  'GET /reports/summary': (_, _) => ok({
    'total': totals,
    'years': [
      {...totals, 'year': 2026},
    ],
  }),
  'GET /reports/peaks': (_, _) => ok([
    {
      'name': 'Säntis',
      'elevation_m': 2502,
      'lat': 47.2494,
      'lon': 9.3433,
      'count': 2,
      'first': '2025-07-01T06:00:00Z',
      'last': '2026-07-18T06:00:00Z',
      'visits': [
        {
          'tour_id': 'tour-1',
          'title': 'Gipfeltag',
          'date': '2026-07-18T06:00:00Z',
        },
      ],
    },
  ]),
  'GET /reports/calendar': (_, _) => ok({
    'year': 2026,
    'years': [2026, 2025],
    'days': [
      {
        'date': '2026-07-18',
        'tours': 1,
        'distance_m': 12300,
        'ascent_m': 1100,
        'tour_ids': ['tour-1'],
      },
    ],
  }),
  'GET /reports/wishes': (_, _) => ok([
    {
      'id': 'wish-1',
      'name': 'Piz Bernina',
      'elevation_m': 4049,
      'lat': null,
      'lon': null,
      'note': 'Biancograt',
      'climbed': false,
    },
    {
      'id': 'wish-2',
      'name': 'Säntis',
      'elevation_m': 2502,
      'lat': null,
      'lon': null,
      'note': null,
      'climbed': true,
    },
  ]),
  'GET /reports/tracks': (_, _) => ok({
    'type': 'FeatureCollection',
    'features': [
      {
        'type': 'Feature',
        'properties': {
          'tour_id': 'tour-1',
          'title': 'Gipfeltag',
          'date': '2026-07-18',
        },
        'geometry': {
          'type': 'LineString',
          'coordinates': [
            [9.0, 47.0],
            [9.01, 47.01],
            [9.02, 47.02],
          ],
        },
      },
    ],
  }),
  'POST /reports/wishes': (_, body) {
    wishes?.add(body);
    return ok(body, 201);
  },
  'DELETE /reports/wishes/wish-1': (_, _) {
    wishes?.add('deleted');
    return ok(null, 204);
  },
});

void main() {
  test('a day out gets its colour from the ascent', () {
    expect(dayLevel(null), 0);
    expect(dayLevel({'ascent_m': 0}), 1);
    expect(dayLevel({'ascent_m': 450}), 2);
    expect(dayLevel({'ascent_m': 1100}), 3);
    expect(dayLevel({'ascent_m': 2000}), 4);
  });

  testWidgets('statistics show totals, calendar, tracks, peaks and wishes', (
    tester,
  ) async {
    final wishes = <Object?>[];
    final map = FakeMap();
    await pumpApp(
      tester,
      api: statsApi(wishes: wishes),
      store: MemoryKeyValueStore(signedInStore),
      overrides: [map.override],
      modules: [reportsModule],
      size: const Size(420, 3200),
    );
    // No page of the navigation: reached from the profile.
    await tester.tap(find.text('Statistik'));
    await tester.pumpAndSettle();

    expect(find.byType(StatsScreen), findsOneWidget);
    expect(find.text('33,5 km'), findsOneWidget);
    expect(find.text('2.900 m'), findsOneWidget);
    expect(find.text('10 h'), findsOneWidget);
    expect(find.textContaining('2 Touren haben keinen Track'), findsOneWidget);
    expect(find.textContaining('5 Touren, 4 Tage'), findsOneWidget);
    // The calendar of the year with its day out, and the other year to choose.
    expect(find.text('Tage unterwegs 2026'), findsOneWidget);
    expect(find.byKey(const ValueKey('day-2026-07-18')), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, '2025'), findsOneWidget);
    // All tracks go to the map as translucent lines.
    expect(map.content!.heatLines.single.length, 3);
    expect(map.content!.heatLines.single.first.lat, 47.0);
    // Climbed peaks and wishes.
    expect(find.text('Bestiegene Gipfel (1)'), findsOneWidget);
    expect(find.text('Säntis, 2.502 m'), findsNWidgets(2));
    expect(find.textContaining('2 Besuche'), findsOneWidget);
    expect(find.text('Piz Bernina, 4.049 m'), findsOneWidget);
    expect(find.text('Biancograt'), findsOneWidget);
    expect(find.text('bestiegen'), findsOneWidget);

    await tester.tap(find.byTooltip('Wunschgipfel hinzufügen'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('wish-name')), 'Eiger');
    await tester.enterText(
      find.byKey(const ValueKey('wish-elevation')),
      '3970',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
    await tester.pumpAndSettle();
    expect((wishes.single! as Map)['name'], 'Eiger');
    expect((wishes.single! as Map)['elevation_m'], 3970);
  });
}
