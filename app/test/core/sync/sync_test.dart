import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/db/app_database.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/core/sync/sync_service.dart';
import 'package:hiker/core/widgets/file_pick.dart';
import 'package:hiker/features/gear/data/gear_models.dart';
import 'package:hiker/features/gear/data/gear_repository.dart';
import 'package:hiker/features/nutrition/data/food_models.dart';
import 'package:hiker/features/nutrition/data/food_repository.dart';
import 'package:hiker/features/protocols/data/tour_models.dart';
import 'package:hiker/features/protocols/data/tour_repository.dart';

import '../../helpers.dart';

const serverTime = '2026-08-02T10:00:00Z';

Map<String, dynamic> changes([Map<String, dynamic> collections = const {}]) => {
  'server_time': serverTime,
  'collections': collections,
};

Map<String, dynamic> collection({
  List<Map<String, dynamic>> changed = const [],
  List<String> deleted = const [],
  bool full = false,
  List<String>? ids,
}) => {'changed': changed, 'deleted': deleted, 'full': full, 'ids': ids};

/// A fake server whose push answers every operation with `ok` and echoes the
/// data; tests replace routes for other answers.
FakeApi syncApi({List<Map<String, dynamic>>? pushed}) => FakeApi({
  'GET /sync/changes': (_, _) => ok(changes()),
  'POST /sync/push': (_, body) {
    final operations = ((body! as Map<String, dynamic>)['operations'] as List)
        .cast<Map<String, dynamic>>();
    pushed?.addAll(operations);
    return ok({
      'results': [
        for (final op in operations)
          {
            'collection': op['collection'],
            'id': op['id'],
            'status': 'ok',
            'record': op['data'] == null
                ? null
                : {
                    ...(op['data'] as Map<String, dynamic>),
                    'id': op['id'],
                    'synced': true,
                  },
          },
      ],
    });
  },
});

Future<ProviderContainer> signedIn(
  FakeApi api, {
  MemoryKeyValueStore? store,
}) async {
  final container = createContainer(
    api: api,
    store: store ?? MemoryKeyValueStore(signedInStore),
  );
  await container.read(sessionProvider.notifier).restore();
  return container;
}

void main() {
  group('queue', () {
    test(
      'several changes of one record become one, on the oldest base',
      () async {
        final container = await signedIn(syncApi());
        final sync = container.read(syncProvider.notifier);

        await sync.enqueue(
          collection: 'gear_items',
          id: 'a',
          data: {'name': 'Erste'},
          baseUpdatedAt: '2026-08-01T00:00:00Z',
        );
        await sync.enqueue(
          collection: 'gear_items',
          id: 'a',
          data: {'name': 'Zweite'},
        );
        await sync.enqueue(
          collection: 'gear_items',
          id: 'b',
          data: {'name': 'Andere'},
        );

        final pending = container.read(syncProvider).pending;
        expect(pending, hasLength(2));
        expect(pending.first.data, '{"name":"Zweite"}');
        expect(pending.first.baseUpdatedAt, '2026-08-01T00:00:00Z');
        expect(container.read(syncProvider).waiting, 2);
      },
    );

    test('created and deleted offline never reaches the server', () async {
      final pushed = <Map<String, dynamic>>[];
      final container = await signedIn(syncApi(pushed: pushed));
      final sync = container.read(syncProvider.notifier);

      await sync.enqueue(
        collection: 'gear_items',
        id: 'new',
        data: {'name': 'Kurz'},
      );
      await sync.enqueue(collection: 'gear_items', id: 'new');
      await sync.enqueue(
        collection: 'gear_items',
        id: 'old',
        data: {'name': 'Alt'},
        baseUpdatedAt: '2026-08-01T00:00:00Z',
      );
      await sync.enqueue(collection: 'gear_items', id: 'old');
      await sync.sync();

      expect(pushed.map((op) => (op['id'], op['op'])), [('old', 'delete')]);
      expect(container.read(syncProvider).isClean, isTrue);
    });
  });

  group('push', () {
    test(
      'sends the queue in order, stores the answers and empties the queue',
      () async {
        final pushed = <Map<String, dynamic>>[];
        final container = await signedIn(syncApi(pushed: pushed));
        final sync = container.read(syncProvider.notifier);
        await sync.enqueue(
          collection: 'gear_items',
          id: 'a',
          data: {'name': 'Zelt'},
        );
        await sync.enqueue(
          collection: 'tours',
          id: 't',
          data: {'title': 'Säntis'},
          baseVersion: 3,
        );

        final reached = await sync.sync();

        expect(reached, isTrue);
        expect(pushed.map((op) => op['collection']), ['gear_items', 'tours']);
        expect(pushed[1]['base_version'], 3);
        expect(container.read(syncProvider).isClean, isTrue);
        final db = container.read(appDatabaseProvider);
        expect((await db.getDocument('gear_items', 'a'))!['synced'], isTrue);
        expect(container.read(syncGenerationProvider), 1);
      },
    );

    test('without network everything stays in the queue', () async {
      final api = syncApi()..offline = true;
      final container = await signedIn(api);
      final sync = container.read(syncProvider.notifier);
      await sync.enqueue(
        collection: 'gear_items',
        id: 'a',
        data: {'name': 'Zelt'},
      );

      final reached = await sync.sync();

      expect(reached, isFalse);
      expect(container.read(syncProvider).pending, hasLength(1));
      expect(container.read(syncProvider).running, isFalse);
    });

    test('a rejected change is marked and can be discarded', () async {
      final api = syncApi();
      api.routes['POST /sync/push'] = (_, _) => ok({
        'results': [
          {
            'collection': 'gear_items',
            'id': 'a',
            'status': 'error',
            'code': 'validation',
          },
        ],
      });
      final container = await signedIn(api);
      final sync = container.read(syncProvider.notifier);
      await sync.enqueue(
        collection: 'gear_items',
        id: 'a',
        data: {'name': ' '},
      );

      await sync.sync();
      final failed = container.read(syncProvider).failed;
      expect(failed.single.error, 'validation');
      // A marked change is not sent again by itself.
      await sync.sync();
      expect(api.requested.where((r) => r == 'POST /sync/push'), hasLength(1));

      await sync.discard(failed.single);
      expect(container.read(syncProvider).isClean, isTrue);
    });

    test(
      'a conflict waits for the user: keep mine or take the server state',
      () async {
        final api = syncApi();
        final bodies = <Map<String, dynamic>>[];
        api.routes['POST /sync/push'] = (_, body) {
          final op =
              ((body! as Map)['operations'] as List).first
                  as Map<String, dynamic>;
          bodies.add(op);
          if (op['base_updated_at'] == 'old') {
            return ok({
              'results': [
                {
                  'collection': 'gear_items',
                  'id': 'a',
                  'status': 'conflict',
                  'current': {'id': 'a', 'name': 'Server', 'updated_at': 'new'},
                },
              ],
            });
          }
          return ok({
            'results': [
              {
                'collection': 'gear_items',
                'id': 'a',
                'status': 'ok',
                'record': op['data'],
              },
            ],
          });
        };
        final container = await signedIn(api);
        final sync = container.read(syncProvider.notifier);
        await sync.enqueue(
          collection: 'gear_items',
          id: 'a',
          data: {'id': 'a', 'name': 'Meins'},
          baseUpdatedAt: 'old',
        );

        await sync.sync();
        final conflict = container.read(syncProvider).conflicts.single;
        expect(conflict.conflict, contains('Server'));

        await sync.keepMine(conflict);

        expect(bodies.last['base_updated_at'], 'new');
        expect(container.read(syncProvider).isClean, isTrue);
        final db = container.read(appDatabaseProvider);
        expect((await db.getDocument('gear_items', 'a'))!['name'], 'Meins');
      },
    );

    test('discarding a conflict takes the state of the server', () async {
      final api = syncApi();
      api.routes['POST /sync/push'] = (_, _) => ok({
        'results': [
          {
            'collection': 'gear_items',
            'id': 'a',
            'status': 'conflict',
            'current': {'id': 'a', 'name': 'Server'},
          },
        ],
      });
      final container = await signedIn(api);
      final sync = container.read(syncProvider.notifier);
      await sync.enqueue(
        collection: 'gear_items',
        id: 'a',
        data: {'id': 'a', 'name': 'Meins'},
      );
      await sync.sync();

      await sync.discard(container.read(syncProvider).conflicts.single);

      final db = container.read(appDatabaseProvider);
      expect((await db.getDocument('gear_items', 'a'))!['name'], 'Server');
      expect(container.read(syncProvider).isClean, isTrue);
    });

    test(
      'a tour conflict in different fields is merged and pushed again',
      () async {
        final api = syncApi();
        final bodies = <Map<String, dynamic>>[];
        final base = {
          for (final f in documentFields) f: null,
          'title': 'Alt',
          'summary': 'Alt',
        };
        api.routes['POST /sync/push'] = (_, body) {
          final op =
              ((body! as Map)['operations'] as List).first
                  as Map<String, dynamic>;
          bodies.add(op);
          if (op['base_version'] == 3) {
            return ok({
              'results': [
                {
                  'collection': 'tours',
                  'id': 't',
                  'status': 'conflict',
                  'current': {
                    ...base,
                    'id': 't',
                    'summary': 'Vom Server',
                    'version': 4,
                  },
                },
              ],
            });
          }
          return ok({
            'results': [
              {
                'collection': 'tours',
                'id': 't',
                'status': 'ok',
                'record': op['data'],
              },
            ],
          });
        };
        final container = await signedIn(api);
        final sync = container.read(syncProvider.notifier);
        await sync.enqueue(
          collection: 'tours',
          id: 't',
          data: {...base, 'title': 'Mein Titel'},
          baseVersion: 3,
          base: base,
        );

        await sync.sync();

        expect(bodies, hasLength(2));
        expect(bodies[1]['base_version'], 4);
        expect((bodies[1]['data'] as Map)['title'], 'Mein Titel');
        expect((bodies[1]['data'] as Map)['summary'], 'Vom Server');
        expect(container.read(syncProvider).isClean, isTrue);
      },
    );

    test('a tour conflict in the same field waits for the user', () async {
      final api = syncApi();
      final base = {for (final f in documentFields) f: null, 'title': 'Alt'};
      api.routes['POST /sync/push'] = (_, _) => ok({
        'results': [
          {
            'collection': 'tours',
            'id': 't',
            'status': 'conflict',
            'current': {...base, 'id': 't', 'title': 'Ihr Titel', 'version': 4},
          },
        ],
      });
      final container = await signedIn(api);
      final sync = container.read(syncProvider.notifier);
      await sync.enqueue(
        collection: 'tours',
        id: 't',
        data: {...base, 'title': 'Mein Titel'},
        baseVersion: 3,
        base: base,
      );

      await sync.sync();

      expect(container.read(syncProvider).conflicts, hasLength(1));
      expect(api.requested.where((r) => r == 'POST /sync/push'), hasLength(1));
    });
  });

  group('pull', () {
    test(
      'applies changed, deleted, full collections and the list of visible ids',
      () async {
        final api = syncApi();
        api.routes['GET /sync/changes'] = (_, _) => ok(
          changes({
            'gear_items': collection(
              changed: [
                {'id': 'new', 'name': 'Neu'},
              ],
              deleted: ['gone'],
            ),
            'gear_tags': collection(
              changed: [
                {'id': 'tag', 'name': 'Winter'},
              ],
              full: true,
            ),
            'tours': collection(ids: ['mine']),
          }),
        );
        final store = MemoryKeyValueStore(signedInStore);
        final container = await signedIn(api, store: store);
        final db = container.read(appDatabaseProvider);
        await db.putDocument('gear_items', 'gone', {'id': 'gone'});
        await db.putDocument('gear_items', 'kept', {'id': 'kept'});
        await db.putDocument('gear_tags', 'old', {'id': 'old'});
        await db.putDocument('tours', 'mine', {'id': 'mine'});
        await db.putDocument('tours', 'revoked', {'id': 'revoked'});

        await container.read(syncProvider.notifier).sync();

        Future<Set<Object?>> ids(String name) async => {
          for (final d in await db.listDocuments(name)) d['id'],
        };
        expect(await ids('gear_items'), {'new', 'kept'});
        expect(await ids('gear_tags'), {'tag'});
        // The share was taken away: the local copy is gone.
        expect(await ids('tours'), {'mine'});
        expect(store.values[lastSyncStorageKey], serverTime);
      },
    );

    test('asks only for what changed since the last sync', () async {
      final api = syncApi();
      final container = await signedIn(api);
      final sync = container.read(syncProvider.notifier);

      await sync.sync();
      await sync.sync();

      final pulls = api.calls.where((c) => c.path == '/sync/changes').toList();
      expect(pulls, hasLength(2));
      expect(api.calls.last.method, 'GET');
    });

    test('a record that still waits to be pushed is not overwritten', () async {
      final api = syncApi();
      api.routes['POST /sync/push'] = (_, _) => ok({
        'results': [
          {
            'collection': 'gear_items',
            'id': 'a',
            'status': 'error',
            'code': 'validation',
          },
        ],
      });
      api.routes['GET /sync/changes'] = (_, _) => ok(
        changes({
          'gear_items': collection(
            changed: [
              {'id': 'a', 'name': 'Server'},
            ],
          ),
        }),
      );
      final container = await signedIn(api);
      final db = container.read(appDatabaseProvider);
      await db.putDocument('gear_items', 'a', {'id': 'a', 'name': 'Lokal'});
      await container
          .read(syncProvider.notifier)
          .enqueue(
            collection: 'gear_items',
            id: 'a',
            data: {'id': 'a', 'name': 'Lokal'},
          );

      await container.read(syncProvider.notifier).sync();

      expect((await db.getDocument('gear_items', 'a'))!['name'], 'Lokal');
    });

    test('nothing happens while signed out', () async {
      final api = syncApi();
      final container = createContainer(api: api);

      expect(await container.read(syncProvider.notifier).sync(), isFalse);
      expect(api.calls, isEmpty);
    });
  });

  group('repositories offline', () {
    test(
      'gear is saved on the device, shown in the list and pushed later',
      () async {
        final pushed = <Map<String, dynamic>>[];
        final api = syncApi(pushed: pushed)..offline = true;
        final container = await signedIn(api);
        final repository = container.read(gearRepositoryProvider);

        final created = await repository.saveItem(
          const GearItem(name: 'Pickel', weightG: 450),
        );
        await repository.saveItem(
          GearItem(id: created.id, name: 'Pickel leicht', weightG: 400),
        );
        final list = await repository.listItems(const GearFilter());

        expect(created.id, isNotNull);
        expect(list.offline, isTrue);
        expect(list.value.single.name, 'Pickel leicht');
        expect(container.read(syncProvider).waiting, 1);

        api.offline = false;
        await container.read(syncProvider.notifier).sync();

        expect(pushed.single['id'], created.id);
        expect((pushed.single['data'] as Map)['weight_g'], 400);
        expect(pushed.single['base_updated_at'], isNull);
        expect(container.read(syncProvider).isClean, isTrue);
      },
    );

    test(
      'editing a known record offline carries its base for the conflict check',
      () async {
        final pushed = <Map<String, dynamic>>[];
        final api = syncApi(pushed: pushed);
        api.routes['GET /gear/items'] = (_, _) => ok({
          'items': [
            {
              'id': 'a',
              'name': 'Zelt',
              'updated_at': '2026-08-01T00:00:00Z',
              'tag_ids': [],
            },
          ],
          'total': 1,
        });
        final container = await signedIn(api);
        final repository = container.read(gearRepositoryProvider);
        await repository.listItems(const GearFilter());

        api.offline = true;
        await repository.saveItem(const GearItem(id: 'a', name: 'Zelt neu'));
        await repository.deleteItem('a');
        api.offline = false;
        await container.read(syncProvider.notifier).sync();

        expect(pushed.single['op'], 'delete');
        expect(pushed.single['base_updated_at'], '2026-08-01T00:00:00Z');
      },
    );

    test('foods are saved offline and found by barcode', () async {
      final api = syncApi()..offline = true;
      final container = await signedIn(api);
      final repository = container.read(foodRepositoryProvider);

      await repository.save(
        const Food(
          name: 'Trockenobst',
          barcode: '4000000000006',
          kcalPer100g: 280,
        ),
      );

      final found = await repository.lookupBarcode('4000000000006');
      expect((found as BarcodeFound).food.name, 'Trockenobst');
      expect(container.read(syncProvider).pending.single.collection, 'foods');
    });

    test(
      'a tour is created and edited offline and appears in the list',
      () async {
        final pushed = <Map<String, dynamic>>[];
        final api = syncApi(pushed: pushed)..offline = true;
        final container = await signedIn(api);
        final repository = container.read(tourRepositoryProvider);
        final document = <String, dynamic>{
          for (final f in documentFields) f: null,
          'title': 'Offline geplant',
        };
        for (final list in ['gear', 'food', 'peaks', 'partners']) {
          document[list] = <Map<String, dynamic>>[];
        }

        final tour = await repository.create(document);
        await repository.update(tour.id, {
          ...document,
          'summary': 'Notiz',
        }, tour.version);
        final list = await repository.list(scope: 'mine');
        final shared = await repository.list(scope: 'shared');

        expect(list.value.single.title, 'Offline geplant');
        expect(shared.value, isEmpty);
        expect((await repository.get(tour.id)).value.summary, 'Notiz');

        api.offline = false;
        await container.read(syncProvider.notifier).sync();

        expect(pushed.single['collection'], 'tours');
        expect(pushed.single['base_version'], isNull);
        expect((pushed.single['data'] as Map)['summary'], 'Notiz');
      },
    );

    test(
      'files wait in the upload queue and are sent with the next sync',
      () async {
        final api = syncApi()..offline = true;
        api.routes['PUT /tours/t/gpx'] = (_, _) =>
            ok({'id': 't', 'title': 'T', 'version': 2});
        api.routes['POST /tours/t/photos'] = (_, _) => ok([], 201);
        final container = await signedIn(api);
        final repository = container.read(tourRepositoryProvider);
        final file = PickedFile('track.gpx', Uint8List.fromList([1, 2, 3]));

        final sent = await repository.uploadGpx('t', file);
        await repository.uploadPhotos('t', [
          PickedFile('a.jpg', Uint8List.fromList([4])),
          PickedFile('b.jpg', Uint8List.fromList([5])),
        ]);

        expect(sent, isFalse);
        expect(container.read(syncProvider).uploads, 3);

        // Only what is sent from here on counts; the failed attempts are
        // recorded too.
        api.calls.clear();
        api.offline = false;
        await container.read(syncProvider.notifier).sync();

        expect(api.requested.where((r) => r.contains('/tours/t/')), [
          'PUT /tours/t/gpx',
          'POST /tours/t/photos',
          'POST /tours/t/photos',
        ]);
        expect(container.read(syncProvider).isClean, isTrue);
      },
    );

    test('a file the server rejects is not sent again and again', () async {
      final api = syncApi()..offline = true;
      api.routes['PUT /tours/t/gpx'] = (_, _) => apiError(422, 'invalid_gpx');
      final container = await signedIn(api);
      await container
          .read(tourRepositoryProvider)
          .uploadGpx('t', PickedFile('x.gpx', Uint8List.fromList([1])));

      api.offline = false;
      expect(await container.read(syncProvider.notifier).sync(), isTrue);

      final db = container.read(appDatabaseProvider);
      expect(
        (await db.select(db.pendingUploads).get()).single.error,
        'invalid_gpx',
      );
    });
  });

  group('profile screen', () {
    testWidgets('shows what waits and syncs on request', (tester) async {
      final api = syncApi();
      api.routes['GET /modules'] = (_, _) => ok([]);
      api.routes['GET /me/profile'] = (_, _) => ok(<String, dynamic>{});
      final container = await pumpApp(
        tester,
        api: api,
        store: MemoryKeyValueStore(signedInStore),
      );
      expect(
        find.text('Alles ist mit dem Server abgeglichen.'),
        findsOneWidget,
      );

      await tester.runAsync(
        () => container
            .read(syncProvider.notifier)
            .enqueue(collection: 'gear_items', id: 'a', data: {'name': 'Zelt'}),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('1 Änderung wartet auf eine Verbindung'),
        findsOneWidget,
      );

      await tester.tap(
        find.widgetWithText(FilledButton, 'Jetzt synchronisieren'),
      );
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 200)),
      );
      await tester.pumpAndSettle();

      expect(api.requested, contains('POST /sync/push'));
      expect(
        find.text('Alles ist mit dem Server abgeglichen.'),
        findsOneWidget,
      );
    });

    testWidgets('a conflict can be decided on the profile screen', (
      tester,
    ) async {
      final api = syncApi();
      api.routes['GET /modules'] = (_, _) => ok([]);
      api.routes['GET /me/profile'] = (_, _) => ok(<String, dynamic>{});
      api.routes['POST /sync/push'] = (_, _) => ok({
        'results': [
          {
            'collection': 'gear_items',
            'id': 'a',
            'status': 'conflict',
            'current': {'id': 'a', 'name': 'Server'},
          },
        ],
      });
      final container = await pumpApp(
        tester,
        api: api,
        store: MemoryKeyValueStore(signedInStore),
      );
      await tester.runAsync(() async {
        final sync = container.read(syncProvider.notifier);
        await sync.enqueue(
          collection: 'gear_items',
          id: 'a',
          data: {'id': 'a', 'name': 'Zelt'},
        );
        await sync.sync();
      });
      await tester.pumpAndSettle();

      expect(find.text('Ausrüstung: Zelt'), findsOneWidget);
      expect(find.text('Inzwischen am Server geändert'), findsOneWidget);

      await tester.tap(find.text('Stand des Servers übernehmen'));
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 200)),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('Alles ist mit dem Server abgeglichen.'),
        findsOneWidget,
      );
    });
  });
}
