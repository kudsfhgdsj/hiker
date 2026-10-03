import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/format.dart';
import 'package:hiker/core/map/elevation_profile.dart';
import 'package:hiker/core/map/geo.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/features/protocols/data/tour_models.dart';
import 'package:hiker/features/protocols/data/tour_repository.dart';

import '../../helpers.dart';

Map<String, dynamic> tourJson({
  String id = 'tour-1',
  String title = 'Säntis',
  String permission = 'owner',
  int version = 3,
  Map<String, dynamic> extra = const {},
}) => {
  'id': id,
  'owner': {'id': 'u1', 'display_name': 'Anna'},
  'permission': permission,
  'title': title,
  'summary': 'Schöne Tour',
  'start_time': '2026-08-01T06:00:00Z',
  'end_time': '2026-08-01T14:30:00Z',
  'duration_minutes': null,
  'pack_weight_start_g': null,
  'calories_burned': null,
  'calories_burned_source': 'estimated',
  'calories_estimate': {
    'method': 'heart_rate',
    'reason': null,
    'parameters': {},
  },
  'computed': {
    'duration_minutes': 510,
    'pack_weight_start_g': 1740,
    'calories_eaten': 384.0,
    'calories_burned': 3120.0,
  },
  'cover_photo_id': null,
  'version': version,
  'start_point': {'lat': 47.0, 'lon': 9.0, 'name': null},
  'end_point': {'lat': 47.004, 'lon': 9.0, 'name': null},
  'points_source': 'gpx',
  'track_source': 'device',
  'track_stats': {
    'distance_m': 12340,
    'ascent_m': 1180,
    'descent_m': 1175,
    'max_elevation_m': 2502,
    'moving_time_s': 21600,
    'heart_rate': {'avg': 136, 'max': 172},
  },
  'photo_time_offset_seconds': 0,
  'photo_count': 2,
  'weather': [
    {
      'sample_point': 'summit',
      'temperature_c': 4.2,
      'wind_speed_kmh': 22.0,
      'cloud_cover_pct': 40.0,
    },
  ],
  'weather_outdated': true,
  'gear': [
    {
      'id': 'g1',
      'gear_item_id': 'item-tent',
      'name': 'Zelt',
      'brand': 'MSR',
      'weight_g': 1500,
      'quantity': 1,
      'carried': true,
    },
  ],
  'food': [
    {
      'id': 'f1',
      'food_item_id': 'food-1',
      'name': 'Nussriegel',
      'kcal_per_100g': 480.0,
      'amount_g': 80.0,
      'kcal': 384.0,
      'carried': true,
      'eaten': true,
      'eaten_at': null,
    },
  ],
  'peaks': [
    {
      'id': 'p1',
      'name': 'Säntis',
      'elevation_m': 2502,
      'lat': 47.003,
      'lon': 9.0,
      'reached_at': null,
    },
  ],
  'partners': [
    {'contact_id': 'c1', 'display_name': 'Dani', 'linked_user_id': null},
  ],
  ...extra,
};

const trackJson = {
  'source': 'device',
  'stats': null,
  'series': {
    'time': null,
    'distance_m': [0.0, 111.0, 222.0, 333.0, 444.0],
    'lat': [47.0, 47.001, 47.002, 47.003, 47.004],
    'lon': [9.0, 9.0, 9.0, 9.0, 9.0],
    'elevation_m': [1000.0, 1010.0, 1020.0, 1030.0, 1040.0],
    'heart_rate': [100, 110, 120, 130, 140],
    'cadence': null,
    'temperature': null,
  },
};

const photosJson = [
  {
    'id': 'photo-1',
    'caption': 'Gipfelkreuz',
    'taken_at': '2026-08-01T10:00:00Z',
    'lat': 47.003,
    'lon': 9.0,
    'position_source': 'exif_gps',
    'track_distance_m': 333.0,
    'elevation_m': 1030.0,
    'waypoint_id': null,
    'is_cover': false,
  },
  {
    'id': 'photo-2',
    'caption': null,
    'taken_at': null,
    'lat': null,
    'lon': null,
    'position_source': 'none',
    'track_distance_m': null,
    'elevation_m': null,
    'waypoint_id': null,
    'is_cover': false,
  },
];

Map<String, dynamic> listItem(Map<String, dynamic> tour) => {
  for (final key in [
    'id',
    'owner',
    'permission',
    'title',
    'start_time',
    'end_time',
    'version',
  ])
    key: tour[key],
  'cover_photo_id': null,
  'peaks': [for (final peak in tour['peaks'] as List) (peak as Map)['name']],
};

Map<String, dynamic> page(List<Map<String, dynamic>> items) => {
  'items': items,
  'total': items.length,
  'limit': 200,
  'offset': 0,
};

FakeApi tourApi({Map<String, dynamic>? tour, List<Object?>? saved}) {
  var current = tour ?? tourJson();
  return FakeApi({
    'GET /modules': (_, _) => ok([
      {'name': 'protocols', 'version': '0.1.0'},
    ]),
    'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
    'GET /tours': (request, _) => ok(
      page(
        request.queryParameters['scope'] == 'shared'
            ? [
                listItem(
                  tourJson(id: 'tour-2', title: 'Altmann', permission: 'read'),
                ),
              ]
            : [listItem(current)],
      ),
    ),
    'GET /tours/tour-1': (_, _) => ok(current),
    'GET /tours/tour-1/track': (_, _) => ok(trackJson),
    'GET /tours/tour-1/photos': (_, _) => ok(photosJson),
    'GET /tours/tour-1/waypoints': (_, _) => ok([
      {'id': 'w1', 'name': 'Hütte', 'lat': 47.002, 'lon': 9.0},
    ]),
    'POST /tours': (_, body) {
      saved?.add(body);
      current = tourJson(extra: body! as Map<String, dynamic>, version: 1);
      return ok(current, 201);
    },
    'PUT /tours/tour-1': (_, body) {
      saved?.add(body);
      final document = Map<String, dynamic>.of(body! as Map<String, dynamic>)
        ..remove('version');
      current = {
        ...current,
        ...document,
        'version': (current['version'] as int) + 1,
      };
      return ok(current);
    },
  });
}

Future<FakeMap> openTours(WidgetTester tester, FakeApi api) async {
  final map = FakeMap();
  await pumpApp(
    tester,
    api: api,
    store: MemoryKeyValueStore(signedInStore),
    overrides: [map.override],
    // Tall enough that the whole detail screen and the editor are laid out.
    size: const Size(420, 3000),
  );
  return map;
}

Future<FakeMap> openDetail(WidgetTester tester, FakeApi api) async {
  final map = await openTours(tester, api);
  // The card shows the title and, below it, the peak of the same name.
  await tester.tap(find.text('Säntis').first);
  await tester.pumpAndSettle();
  return map;
}

Future<void> tapSave(WidgetTester tester) async {
  final button = find.widgetWithText(FilledButton, 'Speichern');
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  group('formatting', () {
    test('durations and distances', () {
      expect(Format.duration(510), '8 h 30 min');
      expect(Format.duration(45), '45 min');
      expect(Format.duration(120), '2 h');
      expect(Format.duration(null), '–');
      expect(Format.distance(12340), '12,3 km');
      expect(Format.distance(450), '450 m');
      expect(Format.meters(2502), '2.502 m');
    });
  });

  group('Tour', () {
    test('manual values win over computed ones', () {
      final computed = Tour(tourJson());
      final manual = Tour(
        tourJson(
          extra: {
            'duration_minutes': 480,
            'pack_weight_start_g': 9000,
            'calories_burned': 2500.0,
            'calories_burned_source': 'manual',
          },
        ),
      );

      expect(computed.durationMinutes, 510);
      expect(computed.packWeightG, 1740);
      expect(computed.caloriesBurned, 3120);
      expect(computed.caloriesBurnedEstimated, isTrue);
      expect(manual.durationMinutes, 480);
      expect(manual.packWeightG, 9000);
      expect(manual.caloriesBurned, 2500);
      expect(manual.caloriesBurnedEstimated, isFalse);
    });

    test('permissions and track data', () {
      expect(Tour(tourJson(permission: 'read')).canEdit, isFalse);
      expect(Tour(tourJson(permission: 'edit')).canEdit, isTrue);
      expect(Tour(tourJson(permission: 'edit')).isOwner, isFalse);
      final track = TrackData(trackJson);
      expect(track.points.first, const GeoPoint(47.0, 9.0));
      expect(track.pointAt(230), const GeoPoint(47.002, 9.0));
      expect(track.heartRates, [100, 110, 120, 130, 140]);
      expect(
        const TrackData({'source': 'none', 'series': null}).isEmpty,
        isTrue,
      );
    });
  });

  group('mergeDocuments', () {
    final base = documentOf(tourJson());

    test('changes of both sides in different fields are combined', () {
      final mine = {...base, 'title': 'Mein Titel'};
      final current = {...base, 'summary': 'Ihr Fazit'};

      final result = mergeDocuments(base, mine, current);

      expect(result.conflicts, isEmpty);
      expect(result.merged['title'], 'Mein Titel');
      expect(result.merged['summary'], 'Ihr Fazit');
      expect(result.merged['gear'], base['gear']);
    });

    test('a field changed by both to different values is a conflict', () {
      final mine = {...base, 'title': 'Mein Titel', 'peaks': <Object>[]};
      final current = {...base, 'title': 'Ihr Titel'};

      final result = mergeDocuments(base, mine, current);

      expect(result.conflicts, ['title']);
      // Until the user decides, the newer state stands.
      expect(result.merged['title'], 'Ihr Titel');
      expect(result.merged['peaks'], isEmpty);
    });

    test('the same change on both sides is no conflict', () {
      final mine = {...base, 'title': 'Gleich'};
      final current = {...base, 'title': 'Gleich'};

      expect(mergeDocuments(base, mine, current).conflicts, isEmpty);
    });

    test('lists are compared by content', () {
      final mine = documentOf(tourJson());
      (mine['gear'] as List).cast<Map<String, dynamic>>().first['quantity'] = 2;

      final result = mergeDocuments(base, mine, documentOf(tourJson()));

      expect(result.conflicts, isEmpty);
      expect(((result.merged['gear'] as List).first as Map)['quantity'], 2);
    });
  });

  group('TourRepository', () {
    test('update sends the base version and reports conflicts with the current tour', () async {
      final api = tourApi();
      api.routes['PUT /tours/tour-1'] = (_, body) => (
        status: 409,
        body: {
          'error': {'code': 'version_conflict', 'message': 'changed'},
          'current': tourJson(version: 4, title: 'Neuer'),
        },
      );
      final repository = createContainer(api: api).read(tourRepositoryProvider);

      final error =
          await repository
                  .update('tour-1', documentOf(tourJson()), 3)
                  .then<Object?>((_) => null, onError: (Object e) => e)
              as ApiException;

      expect((api.calls.single.body! as Map)['version'], 3);
      expect(error.code, 'version_conflict');
      expect((error.body!['current'] as Map)['version'], 4);
    });

    test(
      'tours, tracks and photos are available offline once loaded',
      () async {
        final api = tourApi();
        final repository = createContainer(api: api)
            .read(tourRepositoryProvider);
        await repository.list(scope: 'mine');
        await repository.get('tour-1');
        await repository.track('tour-1');
        await repository.photos('tour-1');

        api.offline = true;

        final list = await repository.list(scope: 'mine');
        final tour = await repository.get('tour-1');
        expect(list.offline, isTrue);
        expect(list.value.single.title, 'Säntis');
        expect(tour.offline, isTrue);
        expect(tour.value.gear.single['name'], 'Zelt');
        expect((await repository.track('tour-1')).points, hasLength(5));
        expect(await repository.photos('tour-1'), hasLength(2));
        expect(repository.get('unknown'), throwsA(isA<ApiException>()));
      },
    );

    test('user lookup returns null for unknown addresses', () async {
      final api = FakeApi({
        'GET /users/lookup': (request, _) =>
            request.queryParameters['email'] == 'bea@example.org'
            ? ok({'id': 'u2', 'display_name': 'Bea'})
            : apiError(404, 'not_found'),
      });
      final repository = createContainer(api: api).read(tourRepositoryProvider);

      expect((await repository.lookupUser('bea@example.org'))!['id'], 'u2');
      expect(await repository.lookupUser('nobody@example.org'), isNull);
    });
  });

  group('tour list', () {
    testWidgets('shows own and shared tours in two tabs', (tester) async {
      await openTours(tester, tourApi());

      expect(find.text('Säntis'), findsWidgets);
      expect(find.text('01.08.2026'), findsOneWidget);

      await tester.tap(find.text('Mit mir geteilt'));
      await tester.pumpAndSettle();

      expect(find.text('Altmann'), findsOneWidget);
      expect(find.text('von Anna'), findsOneWidget);
    });
  });

  group('tour detail', () {
    testWidgets('shows facts, lists, weather and the estimate marked as such', (
      tester,
    ) async {
      await openDetail(tester, tourApi());

      expect(find.text('8 h 30 min'), findsOneWidget);
      // Once as pack weight in the facts, once as sum of the gear list.
      expect(find.text('1,74 kg'), findsNWidgets(2));
      expect(find.text('3.120 kcal'), findsOneWidget);
      expect(find.text('geschätzt'), findsOneWidget);
      expect(find.text('12,3 km'), findsOneWidget);
      expect(find.text('1.180 m'), findsOneWidget);
      expect(find.text('Ø 136 · max. 172'), findsOneWidget);
      expect(find.text('Zelt'), findsOneWidget);
      expect(find.text('Nussriegel · 80 g'), findsOneWidget);
      expect(find.text('384 kcal'), findsWidgets);
      expect(find.text('4 °C · Wind 22 km/h · 40 % Wolken'), findsOneWidget);
      expect(
        find.text('Punkte oder Zeiten haben sich geändert.'),
        findsOneWidget,
      );
      expect(find.text('Dani'), findsOneWidget);
      expect(find.text('Schöne Tour'), findsOneWidget);
    });

    testWidgets(
      'map gets the track and markers for start, end, peak, waypoint and photos',
      (tester) async {
        final map = await openDetail(tester, tourApi());

        final content = map.content!;
        expect(content.track, hasLength(5));
        expect(content.markers.map((m) => m.id), [
          'start',
          'end',
          'peak-p1',
          'waypoint-w1',
          'photo-1',
        ]);
        // Only photos merge into groups; the photo without position has no marker.
        expect(content.markers.where((m) => m.clusters).map((m) => m.id), [
          'photo-1',
        ]);
      },
    );

    testWidgets('moving over the profile moves the point on the map', (
      tester,
    ) async {
      final map = await openDetail(tester, tourApi());
      final profile = tester.getRect(find.byType(ElevationProfile));
      expect(map.content!.highlight, isNull);

      final gesture = await tester.startGesture(profile.center);
      await tester.pump();

      expect(map.content!.highlight, const GeoPoint(47.002, 9.0));
      await gesture.up();
      await tester.pump();
    });

    testWidgets(
      'a photo marker opens the gallery, which can show the photo on the map',
      (tester) async {
        final map = await openDetail(tester, tourApi());

        await tester.tap(find.byKey(const ValueKey('marker-photo-1')));
        await tester.pumpAndSettle();

        expect(find.text('1 / 2'), findsOneWidget);
        expect(find.text('Gipfelkreuz'), findsOneWidget);
        expect(find.textContaining('1.030 m'), findsOneWidget);

        await tester.tap(find.byTooltip('Auf Karte zeigen'));
        await tester.pumpAndSettle();

        expect(map.content!.highlight, const GeoPoint(47.003, 9.0));
      },
    );

    testWidgets('readers get no actions that change the tour', (tester) async {
      await openDetail(tester, tourApi(tour: tourJson(permission: 'read')));

      expect(find.byTooltip('Bearbeiten'), findsNothing);
      expect(find.byTooltip('Teilen'), findsNothing);
      expect(find.byType(PopupMenuButton<VoidCallback>), findsNothing);
      expect(find.byTooltip('Verlauf'), findsOneWidget);
      expect(find.text('von Anna'), findsOneWidget);
    });

    testWidgets('editors can add photos but not change the track', (
      tester,
    ) async {
      await openDetail(tester, tourApi(tour: tourJson(permission: 'edit')));

      await tester.tap(find.byType(PopupMenuButton<VoidCallback>));
      await tester.pumpAndSettle();

      expect(find.text('Fotos hinzufügen'), findsOneWidget);
      expect(find.text('GPX hochladen'), findsNothing);
      expect(find.text('Löschen'), findsNothing);
      expect(find.byTooltip('Teilen'), findsNothing);
    });

    testWidgets('the owner fetches the weather again', (tester) async {
      final api = tourApi();
      api.routes['POST /tours/tour-1/weather/fetch'] = (_, _) =>
          ok(tourJson(extra: {'weather_outdated': false}));
      await openDetail(tester, api);

      await tester.tap(find.widgetWithText(TextButton, 'Wetter neu abrufen'));
      await tester.pumpAndSettle();

      expect(api.requested, contains('POST /tours/tour-1/weather/fetch'));
    });
  });

  group('tour editor', () {
    testWidgets('creates a tour with a peak', (tester) async {
      final saved = <Object?>[];
      await openTours(tester, tourApi(saved: saved));

      await tester.tap(find.text('Neue Tour'));
      await tester.pumpAndSettle();
      await tapSave(tester);
      expect(find.text('Pflichtfeld'), findsOneWidget);

      await tester.enterText(field('Titel'), 'Altmann');
      await tester.tap(find.text('Gipfel hinzufügen'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Name des Gipfels'),
        'Altmann',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Höhe (m)'),
        '2435',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Hinzufügen'));
      await tester.pumpAndSettle();
      await tapSave(tester);

      final body = saved.single! as Map<String, dynamic>;
      expect(body['title'], 'Altmann');
      expect(body['peaks'], [
        {'name': 'Altmann', 'elevation_m': 2435},
      ]);
      expect(body['gear'], isEmpty);
      expect(body.containsKey('version'), isFalse);
    });

    testWidgets('saves changes with the base version', (tester) async {
      final saved = <Object?>[];
      await openDetail(tester, tourApi(saved: saved));

      await tester.tap(find.byTooltip('Bearbeiten'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Titel'), 'Säntis Nord');
      await tester.enterText(field('Dauer (Minuten)'), '480');
      await tester.tap(find.byTooltip('Anzahl +'));
      await tester.pumpAndSettle();
      await tapSave(tester);

      final body = saved.single! as Map<String, dynamic>;
      expect(body['version'], 3);
      expect(body['title'], 'Säntis Nord');
      expect(body['duration_minutes'], 480);
      expect((body['gear'] as List).single['quantity'], 2);
      expect((body['gear'] as List).single['id'], 'g1');
      expect(body['start_time'], '2026-08-01T06:00:00Z');
      // Back on the detail screen with the new title.
      expect(find.text('Säntis Nord'), findsWidgets);
    });

    testWidgets(
      'editors cannot change times and numbers and send them back unchanged',
      (tester) async {
        final saved = <Object?>[];
        await openDetail(
          tester,
          tourApi(
            tour: tourJson(permission: 'edit'),
            saved: saved,
          ),
        );

        await tester.tap(find.byTooltip('Bearbeiten'));
        await tester.pumpAndSettle();

        expect(find.textContaining('kann nur der Besitzer'), findsOneWidget);
        expect(
          tester.widget<TextFormField>(field('Dauer (Minuten)')).enabled,
          isFalse,
        );
        await tester.enterText(field('Fazit'), 'Von Bea ergänzt');
        await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
        await tester.pumpAndSettle();

        final body = saved.single! as Map<String, dynamic>;
        expect(body['summary'], 'Von Bea ergänzt');
        expect(body['duration_minutes'], isNull);
        expect(body['start_time'], '2026-08-01T06:00:00Z');
      },
    );

    testWidgets('a conflict in another field is merged without asking', (
      tester,
    ) async {
      final api = tourApi();
      final bodies = <Map<String, dynamic>>[];
      api.routes['PUT /tours/tour-1'] = (_, body) {
        bodies.add(body! as Map<String, dynamic>);
        if (bodies.length == 1) {
          return (
            status: 409,
            body: {
              'error': {'code': 'version_conflict', 'message': 'changed'},
              'current': tourJson(version: 4, extra: {'summary': 'Von Anna'}),
            },
          );
        }
        return ok(tourJson(version: 5));
      };
      await openDetail(tester, api);
      await tester.tap(find.byTooltip('Bearbeiten'));
      await tester.pumpAndSettle();

      await tester.enterText(field('Titel'), 'Mein Titel');
      await tapSave(tester);

      expect(bodies, hasLength(2));
      expect(bodies[1]['version'], 4);
      expect(bodies[1]['title'], 'Mein Titel');
      expect(bodies[1]['summary'], 'Von Anna');
      expect(find.text('Die Tour wurde inzwischen geändert'), findsNothing);
    });

    testWidgets('a conflict in the same field asks which state wins', (
      tester,
    ) async {
      final api = tourApi();
      final bodies = <Map<String, dynamic>>[];
      api.routes['PUT /tours/tour-1'] = (_, body) {
        bodies.add(body! as Map<String, dynamic>);
        if (bodies.length == 1) {
          return (
            status: 409,
            body: {
              'error': {'code': 'version_conflict', 'message': 'changed'},
              'current': tourJson(version: 4, title: 'Ihr Titel'),
            },
          );
        }
        return ok(tourJson(version: 5));
      };
      await openDetail(tester, api);
      await tester.tap(find.byTooltip('Bearbeiten'));
      await tester.pumpAndSettle();

      await tester.enterText(field('Titel'), 'Mein Titel');
      await tapSave(tester);

      expect(find.text('Die Tour wurde inzwischen geändert'), findsOneWidget);
      await tester.tap(find.text('Neuer Stand'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern').last);
      await tester.pumpAndSettle();

      expect(bodies[1]['version'], 4);
      expect(bodies[1]['title'], 'Ihr Titel');
    });
  });

  group('history', () {
    final revisions = [
      {
        'version': 3,
        'kind': 'updated',
        'change_summary': 'title, gear',
        'author': {'id': 'u2', 'display_name': 'Bea'},
        'created_at': '2026-08-02T10:00:00Z',
      },
      {
        'version': 2,
        'kind': 'restored',
        'change_summary': 'version 1',
        'author': null,
        'created_at': '2026-08-02T09:00:00Z',
      },
      {
        'version': 1,
        'kind': 'created',
        'change_summary': '',
        'author': {'id': 'u1', 'display_name': 'Anna'},
        'created_at': '2026-08-01T15:00:00Z',
      },
    ];

    FakeApi historyApi() {
      final api = tourApi();
      api.routes['GET /tours/tour-1/revisions'] = (_, _) => ok(page(revisions));
      api.routes['GET /tours/tour-1/revisions/2'] = (_, _) => ok({
        ...revisions[1],
        'snapshot': <String, dynamic>{},
        'diff': {
          'title': {'old': 'Kaputt', 'new': 'Säntis'},
          'gear': {
            'added': [
              {'id': 'g1', 'name': 'Zelt'},
            ],
            'removed': <Object>[],
            'changed': <Object>[],
            'reordered': false,
          },
        },
      });
      api.routes['POST /tours/tour-1/revisions/2/restore'] = (_, _) =>
          ok(tourJson(version: 4));
      return api;
    }

    testWidgets('lists the revisions with author and changed fields', (
      tester,
    ) async {
      await openDetail(tester, historyApi());

      await tester.tap(find.byTooltip('Verlauf'));
      await tester.pumpAndSettle();

      expect(find.text('Geändert: Titel, Ausrüstung'), findsOneWidget);
      expect(find.text('Wiederhergestellt'), findsOneWidget);
      expect(find.text('Angelegt'), findsOneWidget);
      expect(find.textContaining('Bea'), findsOneWidget);
      expect(find.textContaining('Entfernter Nutzer'), findsOneWidget);
    });

    testWidgets('shows the diff of a revision and restores it', (tester) async {
      final api = historyApi();
      await openDetail(tester, api);
      await tester.tap(find.byTooltip('Verlauf'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Wiederhergestellt'));
      await tester.pumpAndSettle();

      expect(find.text('Version 2'), findsOneWidget);
      expect(find.text('Titel: Kaputt → Säntis'), findsOneWidget);
      expect(find.text('Ausrüstung hinzugefügt: Zelt'), findsOneWidget);
      await tester.tap(find.text('Diesen Stand wiederherstellen'));
      await tester.pumpAndSettle();

      expect(api.requested, contains('POST /tours/tour-1/revisions/2/restore'));
    });
  });

  group('sharing', () {
    FakeApi shareApi(List<Object?> sent) {
      final api = tourApi();
      final shares = <Map<String, dynamic>>[];
      final links = <Map<String, dynamic>>[];
      api.routes['GET /tours/tour-1/shares'] = (_, _) => ok(shares);
      api.routes['GET /tours/tour-1/public-link'] = (_, _) => ok(links);
      api.routes['GET /users/lookup'] = (request, _) =>
          request.queryParameters['email'] == 'bea@example.org'
          ? ok({'id': 'u2', 'display_name': 'Bea'})
          : apiError(404, 'not_found');
      api.routes['POST /tours/tour-1/shares'] = (_, body) {
        sent.add(body);
        shares.add({
          'user': {'id': 'u2', 'display_name': 'Bea'},
          'permission': (body! as Map)['permission'],
          'created_at': '2026-08-02T10:00:00Z',
        });
        return ok(shares.last, 201);
      };
      api.routes['POST /tours/tour-1/public-link'] = (_, body) {
        sent.add(body);
        links.add({
          'id': 'link-1',
          'url': 'https://hiker.test/p/0b9d6c1e-1111-4222-8333-444455556666',
          'active': true,
          'revoked_at': null,
          ...(body! as Map<String, dynamic>),
        });
        return ok(links.last, 201);
      };
      return api;
    }

    Future<void> openShare(WidgetTester tester, FakeApi api) async {
      await openDetail(tester, api);
      await tester.tap(find.byTooltip('Teilen'));
      await tester.pumpAndSettle();
    }

    testWidgets('shares the tour with a user found by e-mail', (tester) async {
      final sent = <Object?>[];
      await openShare(tester, shareApi(sent));
      expect(find.text('Mit niemandem geteilt.'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextField, 'E-Mail'),
        'nobody@example.org',
      );
      await tester.tap(find.byType(IconButton).first);
      await tester.pumpAndSettle();
      expect(
        find.text('Kein Nutzer mit dieser E-Mail-Adresse.'),
        findsOneWidget,
      );
      expect(sent, isEmpty);

      await tester.enterText(
        find.widgetWithText(TextField, 'E-Mail'),
        'bea@example.org',
      );
      await tester.tap(find.byType(IconButton).first);
      await tester.pumpAndSettle();

      expect(sent.single, {'user_id': 'u2', 'permission': 'read'});
      expect(find.text('Bea'), findsOneWidget);
    });

    testWidgets('creates a public link with health data hidden by default', (
      tester,
    ) async {
      final sent = <Object?>[];
      await openShare(tester, shareApi(sent));

      await tester.tap(find.text('Neuer Link'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(SwitchListTile, 'Genauen Start verbergen'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Neuer Link'));
      await tester.pumpAndSettle();

      expect(sent.single, {
        'hide_exact_start': true,
        'strip_photo_gps': false,
        'show_health_data': false,
      });
      expect(find.textContaining('https://hiker.test/p/'), findsOneWidget);
      expect(find.text('Genauen Start verbergen'), findsOneWidget);
      expect(find.byTooltip('Widerrufen'), findsOneWidget);
    });
  });
}
