import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/misc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_regions.dart';
import 'package:hiker/core/map/elevation_profile.dart';
import 'package:hiker/core/map/geo.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/core/sync/sync_service.dart';
import 'package:hiker/core/widgets/file_pick.dart';
import 'package:hiker/features/planning/data/offline_routing.dart';
import 'package:hiker/features/planning/data/route_models.dart';
import 'package:hiker/features/planning/data/route_repository.dart';
import 'package:hiker/features/planning/planning_module.dart';

import 'package:hiker/features/planning/data/route_schedule.dart';

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
  'tags': ['Sommer', 'Gipfel'],
  'start_time': '2026-07-18T05:30:00Z',
  'profile': 'hiking',
  'max_difficulty': 4,
  'via_ferrata': false,
  'pace': {
    'preset': 'sac',
    'name': null,
    'ascent_m_per_h': 400,
    'descent_m_per_h': 800,
    'distance_km_per_h': 4,
  },
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

const savedPace = {
  'id': '66666666-6666-4666-8666-666666666666',
  'name': 'Mit Kindern',
  'ascent_m_per_h': 250,
  'descent_m_per_h': 400,
  'distance_km_per_h': 3,
};

FakeApi planApi({
  List<Object?>? previews,
  List<Object?>? saved,
  List<Object?>? paces,
  bool routing = true,
  FakeResponse? preview,
}) => FakeApi({
  'GET /planning/paces': (_, _) => ok([savedPace]),
  'GET /planning/routes/$routeId/tours': (_, _) => ok([
    {
      'tour_id': 'tour-1',
      'title': 'Gipfeltag',
      'start_time': null,
      'has_track': true,
    },
  ]),
  'POST /planning/routes/$routeId/tour': (_, _) {
    saved?.add('tour');
    return ok({'tour_id': 'tour-2'}, 201);
  },
  'GET /planning/routes/$routeId/comparison/tour-1': (_, _) => ok({
    'route_id': routeId,
    'tour_id': 'tour-1',
    'tour_title': 'Gipfeltag',
    'planned': {
      'distance_m': 1200,
      'ascent_m': 100,
      'descent_m': 0,
      'duration_s': 2100,
      'total_time_s': null,
    },
    'actual': {
      'distance_m': 1350,
      'ascent_m': 120,
      'descent_m': 15,
      'duration_s': 2400,
      'total_time_s': 3600,
    },
    'deviation': {'mean_m': 35, 'max_m': 150, 'on_plan_share': 0.8},
    'track': {
      'distance_m': [0, 700, 1350],
      'lat': [47.0, 47.006, 47.011],
      'lon': [9.0, 9.004, 9.001],
      'elevation_m': null,
    },
  }),
  'POST /planning/routes/import': (_, _) {
    saved?.add('import');
    return ok(route, 201);
  },
  'POST /planning/paces': (_, body) {
    paces?.add(body);
    return ok(body, 201);
  },
  'DELETE /planning/paces/${savedPace['id']}': (_, _) {
    paces?.add('deleted');
    return ok(null, 204);
  },
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

/// Stands in for BRouter on the device: a path with a bend and elevations.
class FakeDeviceRouter implements DeviceRouter {
  final calls = <(List<GeoPoint>, int, bool)>[];
  bool noRoute = false;

  @override
  Future<List<LinePoint>> route(
    List<GeoPoint> points, {
    required int maxDifficulty,
    required bool viaFerrata,
  }) async {
    calls.add((points, maxDifficulty, viaFerrata));
    if (noRoute) {
      throw const ApiException(code: 'no_route', message: 'island');
    }
    double elevation(double lat) => 1000 + (lat - 47) * 10000;
    return [
      for (var i = 0; i < points.length; i++) ...[
        (lat: points[i].lat, lon: points[i].lon, ele: elevation(points[i].lat)),
        if (i + 1 < points.length)
          (
            lat: (points[i].lat + points[i + 1].lat) / 2,
            lon: points[i].lon + 0.002,
            ele: null,
          ),
      ],
    ];
  }
}

Future<bool> always(String _) async => true;

void main() {
  group('Planning on the device', () {
    test('tiles are named after their south-west corner', () {
      expect(segmentNameFor(const GeoPoint(47.25, 9.34)), 'E5_N45');
      expect(segmentNameFor(const GeoPoint(46.5, 11.3)), 'E10_N45');
      expect(segmentNameFor(const GeoPoint(-0.5, -0.5)), 'W5_S5');
      expect(const SegmentInfo(name: 'W10_S5', sizeBytes: 1).corner, (-10, -5));
    });

    test('app and server route with the same profile', () {
      // The app carries a copy of the server's BRouter profile.
      expect(
        File('assets/brouter/hiker-hiking.brf').readAsStringSync(),
        File('../deploy/brouter/profiles/hiker-hiking.brf').readAsStringSync(),
      );
      expect(File('assets/brouter/lookups.dat').existsSync(), isTrue);
    });

    test('walking time follows the pace', () {
      // DAV (DIN 33466): the larger time in full, the smaller by half.
      expect(Pace.dav.walkingTimeS(8000, 600, 0), 3 * 3600);
      expect(Pace.dav.walkingTimeS(4000, 900, 500), 4.5 * 3600);
      expect(Pace.dav.walkingTimeS(6000, null, null), 1.5 * 3600);
      // SAC and "Profi" are faster; own values count as given.
      expect(Pace.sac.walkingTimeS(4000, 800, 800), 3.5 * 3600);
      expect(Pace.pro.walkingTimeS(6000, 600, 1000), 2.5 * 3600);
      const own = Pace.custom(
        name: 'Mit Kindern',
        ascentMPerH: 250,
        descentMPerH: 400,
        distanceKmPerH: 3,
      );
      expect(own.walkingTimeS(3000, 500, 0), 2.5 * 3600);
      expect(own.toJson()['preset'], 'custom');
      expect(Pace.fromJson(own.toJson()), own);
      expect(Pace.sac.toJson(), {'preset': 'sac'});
      expect(Pace.fromJson(null), Pace.dav);
    });

    test('times along the line and the sun follow pace and start', () {
      const line = RouteResult(result);
      final times = timesAlong(line, Pace.dav);
      // Evenly rising: half of the walking time at half of the way.
      expect(times.first, 0);
      expect(times.last, Pace.dav.walkingTimeS(1200, 100, 0));
      expect(times[1], closeTo(times.last / 2, 1));

      expect(sunReport(line, null, Pace.dav), isNull);
      final start = DateTime.utc(2026, 7, 18, 5, 30);
      final report = sunReport(line, start, Pace.dav)!;
      expect(report.end, start.add(Duration(seconds: times.last)));
      expect(report.startsInDark, isFalse);
      expect(report.endsInDark, isFalse);
      expect(report.daylightLeft!.inHours, greaterThan(12));
      // The highest point is the end of this line; the sun stands in the east.
      expect(report.summit!.elevationM, 1100);
      expect(report.summit!.time, report.end);
      expect(report.summit!.sunDirectionDeg, inInclusiveRange(70, 110));

      // Setting out in the evening: the tour ends in the dark.
      final late = sunReport(line, DateTime.utc(2026, 7, 18, 20), Pace.dav)!;
      expect(late.endsInDark, isTrue);
      expect(late.daylightLeft!.isNegative, isTrue);
      final early = sunReport(line, DateTime.utc(2026, 7, 18, 1), Pace.dav)!;
      expect(early.startsInDark, isTrue);
    });

    test('a route along paths gets line, figures and walking time', () async {
      final router = FakeDeviceRouter();

      final line = await computeOnDevice(
        RouteDraft(
          maxDifficulty: 4,
          viaFerrata: true,
          waypoints: [
            RouteWaypoint.fromJson(start),
            RouteWaypoint.fromJson(hut),
          ],
        ),
        router: router,
        hasSegment: always,
      );

      expect(router.calls.single.$2, 4);
      expect(router.calls.single.$3, isTrue);
      expect(line.onDevice, isTrue);
      expect(line.json['engine'], 'device');
      expect(line.points.length, 3);
      expect(line.elevations, [1000, null, 1100]);
      expect(line.ascentM, 100);
      expect(line.descentM, 0);
      // The path bends: longer than the straight 1112 m.
      expect(line.distanceM, greaterThan(1112));
      expect(line.durationS, Pace.dav.walkingTimeS(line.distanceM, 100, 0));
    });

    test('straight legs need neither router nor path data', () async {
      final line = await computeOnDevice(
        RouteDraft(
          profile: 'direct',
          waypoints: [
            RouteWaypoint.fromJson(start),
            RouteWaypoint.fromJson(hut),
          ],
        ),
        router: null,
        hasSegment: (_) async => false,
      );

      expect(line.json['engine'], 'direct');
      expect(line.distanceM, 1112);
      // A point about every 50 m; no elevations without the server.
      expect(line.points.length, 23);
      expect(line.elevations, isNull);
      expect(line.ascentM, isNull);
      expect(line.durationS, Pace.dav.walkingTimeS(1112, null, null));
    });

    test('single straight legs split the request to the router', () async {
      final router = FakeDeviceRouter();
      const peak = {'lat': 47.02, 'lon': 9.01, 'name': null, 'direct': true};
      const saddle = {'lat': 47.03, 'lon': 9.01, 'name': null, 'direct': false};

      final line = await computeOnDevice(
        RouteDraft(
          waypoints: [
            for (final point in [start, hut, peak, saddle])
              RouteWaypoint.fromJson(point),
          ],
        ),
        router: router,
        hasSegment: always,
      );

      expect([for (final call in router.calls) call.$1.length], [2, 2]);
      expect(line.points.first, const GeoPoint(47.0, 9.0));
      expect(line.points.last, const GeoPoint(47.03, 9.01));
      final lats = [for (final point in line.points) point.lat];
      expect(lats, [...lats]..sort());
    });

    test('missing path data and missing routes are told apart', () async {
      final draft = RouteDraft(
        waypoints: [RouteWaypoint.fromJson(start), RouteWaypoint.fromJson(hut)],
      );
      await expectLater(
        computeOnDevice(
          draft,
          router: FakeDeviceRouter(),
          hasSegment: (_) async => false,
        ),
        throwsA(
          isA<ApiException>()
              .having((e) => e.code, 'code', offlineNoData)
              .having((e) => e.message, 'tile', 'E5_N45'),
        ),
      );
      await expectLater(
        computeOnDevice(
          draft,
          router: FakeDeviceRouter()..noRoute = true,
          hasSegment: always,
        ),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'no_route')),
      );
    });

    test('the GPX file holds the line', () {
      final gpx = routeGpx('Hütte & Gipfel', const RouteResult(result));

      expect(gpx, contains('<name>Hütte &amp; Gipfel</name>'));
      expect('<trkpt'.allMatches(gpx).length, 3);
      expect(
        gpx,
        contains('<trkpt lat="47.0100000" lon="9.0000000"><ele>1100.0</ele>'),
      );
    });
  });

  group('RouteRepository', () {
    test('without network the line comes from the device', () async {
      final router = FakeDeviceRouter();
      final api = planApi()..offline = true;
      final container = createContainer(api: api, deviceRouter: router);
      final folder = await container.read(segmentStoreProvider).directory;
      File('${folder.path}/E5_N45.rd5').writeAsStringSync('path data');
      final repository = container.read(routeRepositoryProvider);

      final line = await repository.preview(draft());

      // The second leg is marked as straight: only the first goes to the router.
      expect(router.calls, isEmpty);
      expect(line.onDevice, isTrue);

      final routed = await repository.preview(
        RouteDraft(
          waypoints: [
            RouteWaypoint.fromJson(start),
            RouteWaypoint.fromJson(hut),
          ],
        ),
      );
      expect(router.calls.length, 1);
      expect(routed.ascentM, 100);

      // Saved offline, the draft keeps the line computed here.
      final saved = await repository.save(draft(), computed: routed);
      expect(saved.result!.onDevice, isTrue);
      expect(saved.distanceM, routed.distanceM);
    });

    test('a draft sends its course and reads the line', () async {
      final previews = <Object?>[];
      final repository = createContainer(api: planApi(previews: previews))
          .read(routeRepositoryProvider);

      final line = await repository.preview(draft());

      expect(previews.single, {
        'profile': 'hiking',
        'max_difficulty': 3,
        'via_ferrata': false,
        'pace': {'preset': 'dav'},
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
      expect(find.textContaining('Sommer · Gipfel'), findsOneWidget);
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
      // DAV: 100 m up count in full (20 min), 1.2 km by half (9 min).
      expect(find.text('29 min'), findsOneWidget);
      expect(find.textContaining('300 Hm/h auf, 500 Hm/h ab'), findsOneWidget);
      // No start yet: nothing about the sun.
      expect(find.textContaining('Sonnenaufgang'), findsNothing);
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
      await tester.tap(find.widgetWithText(TextButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(saved, isEmpty);
      expect(find.text('Bitte einen Titel eingeben.'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextField, 'Titel'),
        'Hüttenweg',
      );
      await tester.enterText(
        find.byKey(const ValueKey('plan-tags')),
        'Herbst, Hütte, ',
      );
      await tester.tap(find.widgetWithText(TextButton, 'Speichern'));
      await tester.pumpAndSettle();
      final body = saved.single! as Map<String, dynamic>;
      expect(body['tags'], ['Herbst', 'Hütte']);
      expect(body['start_time'], isNull);
      expect(body['pace'], {'preset': 'dav'});
      expect(body.containsKey('planned_date'), isFalse);
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
        expect(find.text('Parkplatz'), findsOneWidget);
        // SAC pace of the route: 1.2 km in full (18 min), 100 m up by half.
        expect(find.text('26 min'), findsOneWidget);
        expect(
          find.textContaining('400 Hm/h auf, 800 Hm/h ab'),
          findsOneWidget,
        );
        // With its start the route shows how it lies in the day.
        expect(find.textContaining('Sonnenaufgang: '), findsOneWidget);
        expect(find.textContaining('Sonnenuntergang: '), findsOneWidget);
        expect(find.textContaining('Höchster Punkt (1.100 m)'), findsOneWidget);
        expect(find.textContaining('bis Sonnenuntergang'), findsOneWidget);
        expect(find.textContaining('Stirnlampe'), findsNothing);
        expect(
          tester
              .widget<TextField>(find.byKey(const ValueKey('plan-tags')))
              .controller!
              .text,
          'Sommer, Gipfel',
        );

        // Paths and pace live in the field "Schwierigkeit" on the map.
        await tester.tap(find.text('Schwierigkeit'));
        await tester.pumpAndSettle();
        expect(find.text('T4 – Schwere Bergtour'), findsOneWidget);
        expect(find.textContaining('SAC: 400 Hm auf'), findsOneWidget);
        Navigator.of(tester.element(find.text('Klettersteige benutzen'))).pop();
        await tester.pumpAndSettle();

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

        await tester.tap(find.widgetWithText(TextButton, 'Speichern'));
        await tester.pumpAndSettle();
        expect((saved.single! as Map)['version'], 3);
        expect((saved.single! as Map)['pace'], {'preset': 'sac'});
        expect((saved.single! as Map)['tags'], ['Sommer', 'Gipfel']);
        expect(
          (saved.single! as Map)['start_time'],
          '2026-07-18T05:30:00.000Z',
        );
      },
    );

    testWidgets('the pace is chosen, typed in and saved under a name', (
      tester,
    ) async {
      final previews = <Object?>[];
      final paces = <Object?>[];
      await openPlanning(tester, planApi(previews: previews, paces: paces));
      await tester.tap(find.text('Auf den Gipfel'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Schwierigkeit'));
      await tester.pumpAndSettle();

      // A saved pace of the user brings its values.
      await tester.tap(find.textContaining('SAC: 400 Hm auf'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Mit Kindern').last);
      await tester.pumpAndSettle();
      expect((previews.last! as Map)['pace'], {
        'preset': 'custom',
        'name': 'Mit Kindern',
        'ascent_m_per_h': 250.0,
        'descent_m_per_h': 400.0,
        'distance_km_per_h': 3.0,
      });
      expect(find.text('„Mit Kindern“ löschen'), findsOneWidget);

      // Own values under a new name.
      await tester.tap(find.text('Mit Kindern').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Individuell').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.widgetWithText(TextField, 'Hm/h auf'), '350');
      await tester.pumpAndSettle();
      expect(((previews.last! as Map)['pace'] as Map)['ascent_m_per_h'], 350.0);
      expect(((previews.last! as Map)['pace'] as Map)['name'], isNull);
      await tester.enterText(
        find.byKey(const ValueKey('plan-pace-name')),
        'Gemütlich',
      );
      await tester.tap(find.widgetWithText(OutlinedButton, 'Speichern'));
      await tester.pumpAndSettle();
      final stored = paces.single! as Map<String, dynamic>;
      expect(stored['name'], 'Gemütlich');
      expect(stored['ascent_m_per_h'], 350.0);
      expect(stored['descent_m_per_h'], 400.0);
      expect(((previews.last! as Map)['pace'] as Map)['name'], 'Gemütlich');
    });

    testWidgets('a route is compared with the tour started from it', (
      tester,
    ) async {
      final saved = <Object?>[];
      final map = await openPlanning(tester, planApi(saved: saved));
      await tester.tap(find.text('Auf den Gipfel'));
      await tester.pumpAndSettle();

      expect(find.text('Touren zu dieser Route'), findsOneWidget);
      await tester.ensureVisible(find.text('Gipfeltag'));
      await tester.tap(find.text('Gipfeltag'));
      await tester.pumpAndSettle();
      expect(find.text('Geplant'), findsOneWidget);
      expect(find.text('Gegangen'), findsOneWidget);
      expect(find.text('1,4 km'), findsOneWidget);
      expect(find.text('40 min'), findsOneWidget);
      expect(find.text('1 h'), findsOneWidget);
      expect(
        find.textContaining(
          'im Mittel 35 m neben dem Plan, höchstens 150 m; 80 %',
        ),
        findsOneWidget,
      );
      // The walked track is drawn over the plan and taken away again.
      expect(map.content!.secondTrack, isEmpty);
      await tester.tap(find.text('Auf der Karte zeigen'));
      await tester.pumpAndSettle();
      expect(map.content!.secondTrack.length, 3);
      expect(map.content!.secondTrack.last.lat, 47.011);
      expect(map.content!.track.length, 3);
      expect(find.text('Blau: gegangen (Gipfeltag)'), findsOneWidget);
      tester
          .widget<InputChip>(find.byKey(const ValueKey('plan-walked')))
          .onDeleted!();
      await tester.pumpAndSettle();
      expect(map.content!.secondTrack, isEmpty);

      // The menu starts a new tour from the route.
      await tester.tap(find.byKey(const ValueKey('plan-menu')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tour aus dieser Route anlegen'));
      await tester.pumpAndSettle();
      expect(saved, ['tour']);
    });

    testWidgets('a GPX file is imported as a route', (tester) async {
      final saved = <Object?>[];
      final map = FakeMap();
      final Override picker = filePickerProvider.overrideWithValue(
        ({required List<String> extensions, bool multiple = false}) async => [
          PickedFile('runde.gpx', Uint8List.fromList(utf8.encode('<gpx/>'))),
        ],
      );
      await pumpApp(
        tester,
        api: planApi(saved: saved),
        store: MemoryKeyValueStore(signedInStore),
        overrides: [map.override, picker],
        modules: [planningModule],
        size: const Size(420, 2400),
      );
      await tester.tap(find.byTooltip('GPX-Datei als Route importieren'));
      await tester.pumpAndSettle();

      expect(saved, ['import']);
      // The planner opens with the imported route.
      expect(map.content!.track.length, 3);
      expect(find.text('Parkplatz'), findsOneWidget);
    });

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

  group('Offline path data', () {
    FakeApi offlineApi() {
      final api = planApi();
      api.routes['GET /planning/segments'] = (_, _) => ok([
        {
          'name': 'E5_N45',
          'size_bytes': 252776294,
          'modified': '2026-10-04T01:03:01Z',
        },
      ]);
      api.routes['GET /planning/segments/E5_N45'] = (_, _) => ok('path data');
      return api;
    }

    test('a tile is loaded onto the device and removed again', () async {
      final container = createContainer(
        api: offlineApi(),
        store: MemoryKeyValueStore(signedInStore),
      );
      await container.read(sessionProvider.notifier).restore();
      final store = container.read(segmentStoreProvider);
      final progress = <double>[];

      expect((await store.available()).single.sizeBytes, 252776294);
      expect(await store.has('E5_N45'), isFalse);

      await store.download('E5_N45', onProgress: progress.add);

      expect(await store.has('E5_N45'), isTrue);
      final local = (await store.installed()).single;
      expect(local.name, 'E5_N45');
      expect(local.sizeBytes, greaterThan(0));
      // Nothing half-finished stays behind.
      final folder = await store.directory;
      expect(folder.listSync().length, 1);

      await store.delete('E5_N45');
      expect(await store.installed(), isEmpty);
    });

    testWidgets('the screen lists the tiles with region, size and state', (
      tester,
    ) async {
      final map = FakeMap();
      final Override local = installedSegmentsProvider.overrideWith(
        (ref) async => [
          SegmentInfo(
            name: 'E5_N45',
            sizeBytes: 252776294,
            modified: DateTime(2026, 10, 4),
          ),
          const SegmentInfo(name: 'E10_N45', sizeBytes: 120000000),
        ],
      );
      await pumpApp(
        tester,
        api: offlineApi(),
        store: MemoryKeyValueStore(signedInStore),
        overrides: [map.override, local],
        modules: [planningModule],
        size: const Size(420, 1600),
      );
      await tester.tap(find.byTooltip('Offline-Daten'));
      await tester.pumpAndSettle();

      // This server offers path data, but no maps of its own.
      expect(
        find.textContaining('keine Karten zum Herunterladen'),
        findsOneWidget,
      );
      expect(find.text('E5_N45'), findsOneWidget);
      expect(find.textContaining('Schweiz'), findsOneWidget);
      expect(find.textContaining('5°–10° Ost, 45°–50° Nord'), findsOneWidget);
      expect(
        find.textContaining('253 MB · geladen am 04.10.2026'),
        findsOneWidget,
      );
      expect(find.textContaining('nur Ausschnitte'), findsOneWidget);
      expect(find.text('Neu laden'), findsOneWidget);
      // On the device, but no longer offered by the server: it can only be removed.
      expect(find.text('E10_N45'), findsOneWidget);
      expect(find.text('Vom Gerät entfernen'), findsNWidgets(2));
      expect(find.text('Laden'), findsNothing);
    });

    // The levels of detail packs the server was asked for.
    final asked = <int>[];
    FakeApi mapApi() {
      final api = offlineApi();
      api.routes['GET /maps/regions'] = (_, _) => ok([
        {
          'name': 'austria',
          'size_bytes': 700000000,
          'modified': '2026-10-06T08:00:00Z',
          'layers_size_bytes': 270000000,
          'search_size_bytes': 6000000,
          'details': [
            {'level': 1, 'size_bytes': 470000000},
            {'level': 2, 'size_bytes': 1050000000},
            {'level': 3, 'size_bytes': 2500000000},
          ],
        },
      ]);
      api.routes['GET /maps/regions/austria'] = (_, _) => ok('map');
      api.routes['GET /maps/regions/austria/layers'] = (_, _) => ok('layers');
      api.routes['GET /maps/regions/austria/search'] = (_, _) => ok('index');
      for (final level in [1, 2, 3]) {
        api.routes['GET /maps/regions/austria/layers/$level'] = (_, _) {
          asked.add(level);
          return ok('detail $level');
        };
      }
      return api;
    }

    test(
      'a map is loaded with finer elevation up to the chosen level',
      () async {
        final api = mapApi();
        final container = createContainer(
          api: api,
          store: MemoryKeyValueStore(signedInStore),
        );
        await container.read(sessionProvider.notifier).restore();
        final store = container.read(mapRegionStoreProvider);
        final region = (await store.available()).single;
        Future<List<String>> files() async => [
          for (final file in (await store.directory).listSync())
            file.uri.pathSegments.last,
        ]..sort();

        expect(region.detailSizes, [470000000, 1050000000, 2500000000]);
        // Map, layer pack and index, and the detail packs on top of each other.
        expect(region.bytesWith(0), 976000000);
        expect(region.bytesWith(2), 976000000 + 470000000 + 1050000000);

        final progress = <double>[];
        await store.download(region, detail: 2, onProgress: progress.add);
        expect(await files(), [
          'austria.detail1.layers.sqlite',
          'austria.detail2.layers.sqlite',
          'austria.layers.sqlite',
          'austria.mbtiles',
          'austria.search.sqlite',
        ]);
        expect((await store.installed()).single.detail, 2);
        expect(asked, isNot(contains(3)));

        // Loaded again with a coarser choice: what lies above it goes.
        await store.download(region, detail: 1);
        expect((await store.installed()).single.detail, 1);
        expect(await files(), isNot(contains('austria.detail2.layers.sqlite')));
        // More than the server offers is as much as it offers.
        await store.download(region, detail: 7);
        expect((await store.installed()).single.detail, 3);

        await store.delete('austria');
        expect(await files(), isEmpty);
      },
    );

    testWidgets('loading a map asks how fine it should be without network', (
      tester,
    ) async {
      final map = FakeMap();
      final Override local = installedMapRegionsProvider.overrideWith(
        (ref) async => [
          MapRegion(
            name: 'austria',
            sizeBytes: 700000000,
            modified: DateTime(2026, 10, 6),
            layersSizeBytes: 270000000,
            detailSizes: const [470000000],
            detail: 1,
          ),
        ],
      );
      await pumpApp(
        tester,
        api: mapApi(),
        store: MemoryKeyValueStore(signedInStore),
        overrides: [map.override, local],
        modules: [planningModule],
        size: const Size(420, 1800),
      );
      await tester.tap(find.byTooltip('Offline-Daten'));
      await tester.pumpAndSettle();

      // What is on the device: the map with its layer pack and one detail pack.
      expect(
        find.textContaining('Höhendaten ohne Netz: Klein'),
        findsOneWidget,
      );
      expect(find.textContaining('1.440 MB'), findsOneWidget);

      await tester.tap(find.text('Neu laden').first);
      await tester.pumpAndSettle();
      expect(find.text('Wie fein ohne Netz?'), findsOneWidget);
      expect(find.text('Grob · 976 MB'), findsOneWidget);
      expect(find.text('Klein · 1.446 MB'), findsOneWidget);
      expect(find.text('Mittel · 2.496 MB'), findsOneWidget);
      expect(find.text('Voll · 4.996 MB'), findsOneWidget);
      // The level that is on the device is chosen.
      final small = tester.widget<RadioListTile<int>>(
        find.byKey(const ValueKey('detail-1')),
      );
      expect(small.value, 1);
      expect(
        tester.widget<RadioGroup<int>>(find.byType(RadioGroup<int>)).groupValue,
        1,
      );
      // Closed without a choice: nothing is loaded.
      await tester.tap(find.text('Abbrechen'));
      await tester.pumpAndSettle();
      expect(find.text('Wie fein ohne Netz?'), findsNothing);
      expect(find.byType(LinearProgressIndicator), findsNothing);
    });

    testWidgets('the planner saves the line as a GPX file', (tester) async {
      final files = <(String, String)>[];
      final map = FakeMap();
      final Override saver = fileSaverProvider.overrideWithValue(({
        required String name,
        required Uint8List bytes,
        required String mimeType,
      }) async {
        files.add((name, utf8.decode(bytes)));
        return true;
      });
      await pumpApp(
        tester,
        api: planApi(),
        store: MemoryKeyValueStore(signedInStore),
        overrides: [map.override, saver],
        modules: [planningModule],
        size: const Size(420, 2400),
      );
      await tester.tap(find.text('Auf den Gipfel'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const ValueKey('plan-menu')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Als GPX speichern'));
      await tester.pumpAndSettle();

      expect(files.single.$1, 'Auf den Gipfel.gpx');
      expect(files.single.$2, contains('<trkpt lat="47.0050000"'));
      expect(find.text('GPX-Datei gespeichert.'), findsOneWidget);
    });
  });
}
