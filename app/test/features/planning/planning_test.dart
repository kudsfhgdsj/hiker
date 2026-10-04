import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/elevation_profile.dart';
import 'package:hiker/core/map/geo.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/core/sync/sync_service.dart';
import 'package:hiker/features/planning/data/route_models.dart';
import 'package:hiker/features/planning/data/route_repository.dart';
import 'package:hiker/features/planning/planning_module.dart';

import '../../helpers.dart';

const routeId = '55555555-5555-4555-8555-555555555555';
const start = {'lat': 47.0, 'lon': 9.0, 'name': 'Parkplatz', 'direct': false};
const hut = {'lat': 47.01, 'lon': 9.0, 'name': null, 'direct': false};

const result = {
  'engine': 'brouter',
  'series': {
    'distance_m': [0.0, 600.0, 1200.0],
    'lat': [47.0, 47.005, 47.01],
    'lon': [9.0, 9.002, 9.0],
    'elevation_m': [1000.0, 1050.0, 1100.0],
  },
  'distance_m': 1200.0,
  'ascent_m': 100.0,
  'descent_m': 0.0,
  'min_elevation_m': 1000.0,
  'max_elevation_m': 1100.0,
  'duration_s': 2100,
  'duration_estimated': true,
};

const route = {
  'id': routeId,
  'title': 'Auf den Gipfel',
  'description': 'Über die Hütte',
  'planned_date': '2026-07-18',
  'profile': 'hiking',
  'max_difficulty': 4,
  'via_ferrata': false,
  'version': 3,
  'waypoints': [start, hut],
  ...result,
};

Map<String, dynamic> page(List<Map<String, dynamic>> items) => {
  'items': items,
  'total': items.length,
  'limit': 200,
  'offset': 0,
};

FakeApi planApi({
  List<Object?>? previews,
  List<Object?>? saved,
  bool routing = true,
  FakeResponse? preview,
}) => FakeApi({
  'GET /modules': (_, _) => ok([
    {'name': 'planning', 'version': '0.1.0'},
  ]),
  'GET /planning/info': (_, _) => ok({
    'routing_available': routing,
    'attribution': routing ? 'Wegführung: BRouter (ODbL)' : null,
    'max_waypoints': 100,
  }),
  'GET /planning/routes': (_, _) => ok(page([route])),
  'GET /planning/routes/$routeId': (_, _) => ok(route),
  'POST /planning/preview': (_, body) {
    previews?.add(body);
    return preview ?? ok(result);
  },
  'POST /planning/routes': (_, body) {
    saved?.add(body);
    return ok({
      ...route,
      ...(body! as Map<String, dynamic>),
      'id': 'new',
      'version': 1,
    }, 201);
  },
  'PUT /planning/routes/$routeId': (_, body) {
    saved?.add(body);
    return ok({...route, ...(body! as Map<String, dynamic>), 'version': 4});
  },
  'DELETE /planning/routes/$routeId': (_, _) => ok(null, 204),
});

Future<FakeMap> openPlanning(WidgetTester tester, FakeApi api) async {
  final map = FakeMap();
  await pumpApp(
    tester,
    api: api,
    store: MemoryKeyValueStore(signedInStore),
    overrides: [map.override],
    modules: [planningModule],
    // Tall enough that the whole planner is laid out.
    size: const Size(420, 2400),
  );
  return map;
}

RouteDraft draft({String title = 'Offline geplant'}) => RouteDraft(
  title: title,
  waypoints: [
    RouteWaypoint.fromJson(start),
    RouteWaypoint.fromJson(hut).copyWith(direct: true),
  ],
);

void main() {
  group('RouteRepository', () {
    test('a draft sends its course and reads the line', () async {
      final previews = <Object?>[];
      final repository = createContainer(api: planApi(previews: previews))
          .read(routeRepositoryProvider);

      final line = await repository.preview(draft());

      expect(previews.single, {
        'profile': 'hiking',
        'max_difficulty': 3,
        'via_ferrata': false,
        'waypoints': [
          start,
          {...hut, 'direct': true},
        ],
      });
      expect(line.points.length, 3);
      expect(line.pointAt(650), const GeoPoint(47.005, 9.002));
      expect(line.durationS, 2100);
    });

    test(
      'saving offline keeps a draft and sends it with the next sync',
      () async {
        final saved = <Object?>[];
        final api = planApi(saved: saved);
        final container = createContainer(
          api: api,
          store: MemoryKeyValueStore(signedInStore),
        );
        await container.read(sessionProvider.notifier).restore();
        final repository = container.read(routeRepositoryProvider);
        api.offline = true;

        final local = await repository.save(draft());

        // No line yet: the server computes it.
        expect(local.result, isNull);
        expect(local.version, 0);
        final offline = await repository.list();
        expect(offline.offline, isTrue);
        expect(offline.value.single.title, 'Offline geplant');
        expect(
          container.read(syncProvider).pending.single.collection,
          'routes',
        );

        api.routes['POST /sync/push'] = (_, body) {
          final operation =
              ((body! as Map<String, dynamic>)['operations'] as List).single
                  as Map<String, dynamic>;
          saved.add(operation);
          return ok({
            'results': [
              {
                'collection': 'routes',
                'id': operation['id'],
                'status': 'ok',
                'record': {...route, 'id': operation['id'], 'version': 1},
              },
            ],
          });
        };
        api.routes['GET /sync/changes'] = (_, _) => ok({
          'server_time': '2026-10-04T12:00:00Z',
          'collections': <String, dynamic>{},
        });
        api.offline = false;
        expect(await container.read(syncProvider.notifier).sync(), isTrue);

        final operation = saved.single! as Map<String, dynamic>;
        expect(operation['op'], 'upsert');
        expect(operation['base_version'], isNull);
        expect((operation['data'] as Map)['title'], 'Offline geplant');
        expect(container.read(syncProvider).isClean, isTrue);
        api.offline = true;
        final synced = await repository.get(local.id);
        expect(synced.value.result, isNotNull);
      },
    );

    test('an offline change of the course drops the outdated line', () async {
      final api = planApi();
      final container = createContainer(
        api: api,
        store: MemoryKeyValueStore(signedInStore),
      );
      final repository = container.read(routeRepositoryProvider);
      final existing = (await repository.get(routeId)).value;
      api.offline = true;

      final renamed = await repository.save(
        RouteDraft(
          title: 'Neuer Name',
          description: existing.draft.description,
          plannedDate: existing.draft.plannedDate,
          maxDifficulty: 4,
          waypoints: existing.draft.waypoints,
        ),
        existing: existing,
      );
      expect(renamed.result, isNotNull);

      final harder = await repository.save(
        RouteDraft(
          title: 'Neuer Name',
          maxDifficulty: 6,
          waypoints: existing.draft.waypoints,
        ),
        existing: existing,
      );
      expect(harder.result, isNull);
      final change = container.read(syncProvider).pending.single;
      expect(change.baseVersion, 3);
    });

    test('errors of the routing keep their code', () async {
      final repository = createContainer(
        api: planApi(preview: apiError(422, 'no_route')),
      ).read(routeRepositoryProvider);

      await expectLater(
        repository.preview(draft()),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'no_route')),
      );
    });
  });

  group('Planning screens', () {
    testWidgets('the list shows routes with their key figures', (tester) async {
      await openPlanning(tester, planApi());

      expect(find.text('Auf den Gipfel'), findsOneWidget);
      expect(find.textContaining('18.07.2026'), findsOneWidget);
      expect(find.textContaining('1,2 km · ↑ 100 m · 35 min'), findsOneWidget);
    });

    testWidgets('taps on the map set waypoints and the server draws the line', (
      tester,
    ) async {
      final previews = <Object?>[];
      final saved = <Object?>[];
      final map = await openPlanning(
        tester,
        planApi(previews: previews, saved: saved),
      );
      await tester.tap(find.text('Neue Route'));
      await tester.pumpAndSettle();

      expect(find.textContaining('um den Start zu setzen'), findsOneWidget);
      map.content!.onTap!(const GeoPoint(47.0, 9.0));
      await tester.pumpAndSettle();
      // One point is not a route yet.
      expect(previews, isEmpty);
      map.content!.onTap!(const GeoPoint(47.01, 9.0));
      await tester.pumpAndSettle();

      expect(previews.length, 1);
      expect(map.content!.track.length, 3);
      expect(map.content!.markers.length, 2);
      expect(find.text('1,2 km'), findsOneWidget);
      expect(find.text('35 min'), findsOneWidget);
      expect(find.textContaining('geschätzt'), findsOneWidget);
      expect(find.byType(ElevationProfile), findsOneWidget);
      expect(find.text('Wegführung: BRouter (ODbL)'), findsOneWidget);

      // The leg to the second point as a straight line: a new line is asked for.
      await tester.tap(find.byTooltip('Punkt 2'));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(
          CheckedPopupMenuItem<VoidCallback>,
          'Luftlinie hierher',
        ),
      );
      await tester.pumpAndSettle();
      expect(previews.length, 2);
      final course = previews.last! as Map<String, dynamic>;
      expect(((course['waypoints'] as List)[1] as Map)['direct'], isTrue);

      // Saving needs a title.
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(saved, isEmpty);
      expect(find.text('Bitte einen Titel eingeben.'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextField, 'Titel'),
        'Hüttenweg',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final body = saved.single! as Map<String, dynamic>;
      expect(body['title'], 'Hüttenweg');
      expect(body['max_difficulty'], 3);
      expect((body['waypoints'] as List).length, 2);
      expect(body.containsKey('version'), isFalse);
    });

    testWidgets(
      'a stored route opens with its line and saves with its version',
      (tester) async {
        final previews = <Object?>[];
        final saved = <Object?>[];
        final map = await openPlanning(
          tester,
          planApi(previews: previews, saved: saved),
        );
        await tester.tap(find.text('Auf den Gipfel'));
        await tester.pumpAndSettle();

        // The stored line is shown without asking the server again.
        expect(previews, isEmpty);
        expect(map.content!.track.length, 3);
        expect(find.text('T4 – Schwere Bergtour'), findsOneWidget);
        expect(find.text('Parkplatz'), findsOneWidget);

        // Choosing a point and tapping the map moves it.
        await tester.tap(find.byKey(const ValueKey('marker-waypoint-1')));
        await tester.pumpAndSettle();
        expect(find.textContaining('um Punkt 2 zu versetzen'), findsOneWidget);
        map.content!.onTap!(const GeoPoint(47.02, 9.01));
        await tester.pumpAndSettle();
        expect(map.content!.markers.length, 2);
        final course = previews.single! as Map<String, dynamic>;
        expect(((course['waypoints'] as List)[1] as Map)['lat'], 47.02);
        expect(course['max_difficulty'], 4);

        await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
        await tester.pumpAndSettle();
        expect((saved.single! as Map)['version'], 3);
      },
    );

    testWidgets('no route and no routing are explained', (tester) async {
      final map = await openPlanning(
        tester,
        planApi(preview: apiError(422, 'no_route'), routing: false),
      );
      await tester.tap(find.text('Neue Route'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('keine Wegführung eingerichtet'),
        findsOneWidget,
      );
      map.content!.onTap!(const GeoPoint(47.0, 9.0));
      map.content!.onTap!(const GeoPoint(47.01, 9.0));
      await tester.pumpAndSettle();

      expect(find.textContaining('keinen Weg'), findsOneWidget);
      // Without a line the points are joined directly, as a sketch.
      expect(map.content!.track.length, 2);
      expect(find.byType(ElevationProfile), findsNothing);
    });
  });
}
