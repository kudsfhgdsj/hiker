import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/geo.dart';
import 'package:hiker/features/protocols/data/tour_models.dart';

import '../../helpers.dart';
import 'protocols_test.dart'
    show listItem, openTours, page, tapSave, tourApi, tourJson;

/// Three own tours, two of them with tags, and their lines for the map.
FakeApi taggedApi({List<Object?>? saved}) {
  final tours = [
    {
      ...listItem(tourJson()),
      'tags': ['Wandern', 'Gipfel'],
    },
    {
      ...listItem(tourJson(id: 'tour-3', title: 'Piz Palü')),
      'tags': ['Skitour', 'gipfel'],
    },
    listItem(tourJson(id: 'tour-4', title: 'Alpstein')),
  ];
  final api = tourApi(saved: saved);
  api.routes['GET /tours'] = (request, _) =>
      ok(page(request.queryParameters['scope'] == 'shared' ? [] : tours));
  api.routes['GET /tours/tracks'] = (request, _) => ok({
    'type': 'FeatureCollection',
    'features': request.queryParameters['scope'] == 'shared'
        ? <Object>[]
        : [
            {
              'type': 'Feature',
              'properties': {
                'tour_id': 'tour-1',
                'title': 'Säntis',
                'date': '2026-08-01',
                'tags': ['Wandern', 'Gipfel'],
                'own': true,
              },
              'geometry': {
                'type': 'LineString',
                'coordinates': [
                  [9.0, 47.0],
                  [9.0, 47.004],
                ],
              },
            },
            {
              'type': 'Feature',
              'properties': {
                'tour_id': 'tour-3',
                'title': 'Piz Palü',
                'date': null,
                'tags': ['Skitour', 'gipfel'],
                'own': true,
              },
              'geometry': {
                'type': 'Point',
                'coordinates': [9.96, 46.38],
              },
            },
          ],
  });
  return api;
}

void main() {
  group('tags', () {
    test('are read from one field, trimmed and without repeats', () {
      expect(parseTags(' Skitour, Gletscher ,, skitour , mit Kindern'), [
        'Skitour',
        'Gletscher',
        'mit Kindern',
      ]);
      expect(parseTags('  '), isEmpty);
    });

    test('are counted over tours, the most used first', () {
      expect(
        countTags([
          ['Wandern', 'Gipfel'],
          ['Skitour', 'gipfel'],
          <String>[],
        ]),
        [('Gipfel', 2), ('Skitour', 1), ('Wandern', 1)],
      );
    });

    test('belong to the document of a tour; old tours leave them alone', () {
      final tagged = Tour({
        ...tourJson(),
        'tags': ['Skitour'],
      });
      expect(tagged.tags, ['Skitour']);
      expect(tagged.hasTag('SKITOUR'), isTrue);
      expect(documentOf(tagged.json)['tags'], ['Skitour']);
      // A tour stored before tags existed: null means "unchanged" to the server.
      final old = Tour(tourJson());
      expect(old.tags, isEmpty);
      expect(documentOf(old.json)['tags'], isNull);
      // Tags changed on both sides to different lists collide like any field.
      final merged = mergeDocuments(documentOf(tagged.json), {
        ...documentOf(tagged.json),
        'tags': ['Skitour', 'Gletscher'],
      }, documentOf(tagged.json));
      expect(merged.merged['tags'], ['Skitour', 'Gletscher']);
      expect(merged.conflicts, isEmpty);
    });

    test('a line of the map is read from its feature', () {
      final line = TourLine.fromFeature({
        'properties': {
          'tour_id': 't',
          'title': 'Säntis',
          'date': '2026-08-01',
          'tags': ['Wandern'],
        },
        'geometry': {
          'type': 'LineString',
          'coordinates': [
            [9.0, 47.0],
            [9.1, 47.1],
          ],
        },
      });
      expect(line.points, const [GeoPoint(47.0, 9.0), GeoPoint(47.1, 9.1)]);
      expect(line.date, DateTime(2026, 8, 1));
      expect(line.hasTag('wandern'), isTrue);
    });

    testWidgets('the list shows the tags and filters by one of them', (
      tester,
    ) async {
      await openTours(tester, taggedApi());

      expect(find.text('#Wandern  #Gipfel'), findsOneWidget);
      // The tags in use with the number of tours, the most used first.
      expect(find.text('Gipfel · 2'), findsOneWidget);
      expect(find.text('Skitour · 1'), findsOneWidget);

      await tester.tap(find.text('Skitour · 1'));
      await tester.pumpAndSettle();
      expect(find.text('Piz Palü'), findsOneWidget);
      expect(find.text('Alpstein'), findsNothing);
      // The tour with the other tags is gone (its name also is a peak of every card).
      expect(find.text('#Wandern  #Gipfel'), findsNothing);

      // A tap on the chosen tag shows all tours again.
      await tester.tap(find.text('Skitour · 1'));
      await tester.pumpAndSettle();
      expect(find.text('Alpstein'), findsOneWidget);
    });

    testWidgets('all tours are shown on one map and open from there', (
      tester,
    ) async {
      final map = await openTours(tester, taggedApi());

      await tester.tap(find.byTooltip('Alle Touren auf der Karte'));
      await tester.pumpAndSettle();

      // The track as a line; every tour with a marker at its start.
      expect(find.text('MAP'), findsOneWidget);
      expect(map.content!.heatLines, [
        const [GeoPoint(47.0, 9.0), GeoPoint(47.004, 9.0)],
      ]);
      expect(map.content!.markers.map((marker) => marker.id), [
        'tour-1',
        'tour-3',
      ]);
      expect(map.content!.markers.last.position, const GeoPoint(46.38, 9.96));
      // The search belongs to the list.
      expect(find.byType(TextField), findsNothing);

      // The tag filter works on the map too.
      await tester.tap(find.text('Skitour · 1'));
      await tester.pumpAndSettle();
      expect(map.content!.markers.single.id, 'tour-3');
      expect(map.content!.heatLines, isEmpty);
      await tester.tap(find.text('Skitour · 1'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const ValueKey('marker-tour-1')));
      await tester.pumpAndSettle();
      expect(find.text('Schöne Tour'), findsOneWidget);
    });

    testWidgets('the map says so when no tour has a track', (tester) async {
      await openTours(tester, taggedApi());
      await tester.tap(find.text('Mit mir geteilt'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Alle Touren auf der Karte'));
      await tester.pumpAndSettle();

      expect(find.textContaining('hat einen Track'), findsOneWidget);
      // And back to the list.
      await tester.tap(find.byTooltip('Als Liste'));
      await tester.pumpAndSettle();
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('the editor saves the tags of a tour', (tester) async {
      final saved = <Object?>[];
      await openTours(tester, taggedApi(saved: saved));

      await tester.tap(find.text('Neue Tour'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Titel'),
        'Tödi',
      );
      await tester.enterText(
        find.byKey(const ValueKey('tour-tags')),
        'Hochtour, Gletscher, hochtour',
      );
      await tapSave(tester);

      final body = saved.single! as Map<String, dynamic>;
      expect(body['tags'], ['Hochtour', 'Gletscher']);
      // The detail screen of the new tour shows them.
      expect(find.widgetWithText(Chip, 'Gletscher'), findsOneWidget);
    });
  });
}
