import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/format.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/core/widgets/file_pick.dart';
import 'package:hiker/features/gear/data/gear_models.dart';
import 'package:hiker/features/gear/data/gear_repository.dart';
import 'package:hiker/features/gear/presentation/gear_manage_screen.dart';

import '../../helpers.dart';

const tent = {
  'id': 'item-tent',
  'name': 'Zelt Hubba',
  'brand': 'MSR',
  'type_id': 'type-tent',
  'weight_g': 1500,
  'purchase_price': 399.9,
  'currency': 'CHF',
  'status': 'active',
  'tag_ids': ['tag-winter'],
  'catalog_id': null,
  'image_file_id': null,
};
const stove = {
  'id': 'item-stove',
  'name': 'Kocher',
  'brand': 'Primus',
  'type_id': null,
  'weight_g': 300,
  'status': 'retired',
  'tag_ids': <String>[],
  'catalog_id': null,
  'image_file_id': null,
};
const types = [
  {
    'id': 'type-tent',
    'name': 'Zelt & Biwak',
    'sort_order': 10,
    'standard': true,
  },
  {
    'id': 'type-photo',
    'name': 'Fotoausrüstung',
    'sort_order': 20,
    'standard': false,
  },
];
const tags = [
  {'id': 'tag-winter', 'name': 'Winter', 'color': '#3366cc'},
  {'id': 'tag-loan', 'name': 'Verleihbar', 'color': null},
];

Map<String, dynamic> page(List<Map<String, dynamic>> items) => {
  'items': items,
  'total': items.length,
  'limit': 200,
  'offset': 0,
};

/// A fake server with the gear endpoints; `saved` collects what was written.
FakeApi gearApi({List<Object?>? saved, List<Map<String, dynamic>>? items}) {
  final all = items ?? [tent, stove];
  return FakeApi({
    'GET /modules': (_, _) => ok([
      {'name': 'gear', 'version': '0.1.0'},
    ]),
    'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
    'GET /gear/types': (_, _) => ok(types),
    'GET /gear/tags': (_, _) => ok(tags),
    'GET /gear/items': (request, _) {
      final filter = GearFilter(
        query: request.queryParameters['q'] as String? ?? '',
        status: request.queryParameters['status'] as String?,
        typeId: request.queryParameters['type_id'] as String?,
        tagIds: {
          ...?(request.queryParameters['tag_id'] as List<dynamic>?)
              ?.cast<String>(),
        },
      );
      return ok(
        page(all.where((i) => filter.matches(GearItem.fromJson(i))).toList()),
      );
    },
    'GET /gear/items/item-tent': (_, _) => ok(tent),
    'POST /gear/items': (_, body) {
      saved?.add(body);
      return ok({
        ...tent,
        ...(body! as Map<String, dynamic>),
        'id': 'item-new',
      }, 201);
    },
    'PUT /gear/items/item-tent': (_, body) {
      saved?.add(body);
      return ok({...tent, ...(body! as Map<String, dynamic>)});
    },
  });
}

Future<void> openGear(
  WidgetTester tester,
  FakeApi api, {
  Map<String, String>? store,
}) async {
  await pumpApp(
    tester,
    api: api,
    store: MemoryKeyValueStore(store ?? signedInStore),
  );
}

/// Chips sit in a horizontal scroller and may be outside the visible part.
Future<void> tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
}

void main() {
  group('formatting', () {
    test('weights, money and number input', () {
      expect(Format.weight(890), '890 g');
      expect(Format.weight(1500), '1,5 kg');
      expect(Format.weight(12345), '12,35 kg');
      expect(Format.weight(null), '–');
      expect(Format.money(399.9, 'CHF'), '399,90 CHF');
      expect(Format.money(1234.5, 'EUR'), '1.234,50 EUR');
      expect(Format.parseNumber(' 70,5 '), 70.5);
      expect(Format.parseNumber('abc'), isNull);
      expect(Format.input(72.0), '72');
      expect(Format.input(72.5), '72,5');
    });

    test('tag colours', () {
      expect(parseTagColor('#3366cc'), const Color(0xFF3366CC));
      expect(parseTagColor('red'), isNull);
      expect(parseTagColor(null), isNull);
    });
  });

  group('GearFilter', () {
    final item = GearItem.fromJson(tent);

    test('matches like the server', () {
      expect(const GearFilter().matches(item), isTrue);
      expect(const GearFilter(query: 'msr').matches(item), isTrue);
      expect(const GearFilter(query: 'hubba').matches(item), isTrue);
      expect(const GearFilter(query: 'kocher').matches(item), isFalse);
      expect(const GearFilter(status: 'retired').matches(item), isFalse);
      expect(const GearFilter(typeId: 'type-tent').matches(item), isTrue);
      expect(const GearFilter(tagIds: {'tag-winter'}).matches(item), isTrue);
      expect(
        const GearFilter(tagIds: {'tag-winter', 'tag-loan'}).matches(item),
        isFalse,
      );
    });

    test('query parameters and equality', () {
      const filter = GearFilter(
        query: 'zelt',
        status: 'active',
        tagIds: {'a', 'b'},
      );
      expect(filter.toQuery(), {
        'q': 'zelt',
        'status': 'active',
        'tag_id': ['a', 'b'],
      });
      expect(const GearFilter().toQuery(), isEmpty);
      expect(
        filter,
        const GearFilter(query: 'zelt', status: 'active', tagIds: {'b', 'a'}),
      );
      expect(filter.copyWith(status: () => null).status, isNull);
    });
  });

  group('GearRepository', () {
    test(
      'keeps a copy of the full list and serves it offline with the filter',
      () async {
        final api = gearApi();
        final container = createContainer(api: api);
        final repository = container.read(gearRepositoryProvider);

        final online = await repository.listItems(const GearFilter());
        api.offline = true;
        final offline = await repository.listItems(const GearFilter());
        final filtered = await repository.listItems(
          const GearFilter(status: 'retired'),
        );

        expect(online.offline, isFalse);
        expect(online.value.map((i) => i.name), ['Zelt Hubba', 'Kocher']);
        expect(offline.offline, isTrue);
        expect(offline.value.map((i) => i.name), ['Kocher', 'Zelt Hubba']);
        expect(filtered.value.map((i) => i.name), ['Kocher']);
      },
    );

    test('a filtered request does not replace the full copy', () async {
      final api = gearApi();
      final repository = createContainer(api: api).read(gearRepositoryProvider);
      await repository.listItems(const GearFilter());
      await repository.listItems(const GearFilter(query: 'kocher'));

      api.offline = true;

      expect(
        (await repository.listItems(const GearFilter())).value,
        hasLength(2),
      );
    });

    test('loads all pages', () async {
      final many = [
        for (var i = 0; i < 450; i++)
          {...stove, 'id': 'item-$i', 'name': 'Teil $i'},
      ];
      final api = FakeApi({
        'GET /gear/items': (request, _) {
          final offset = request.queryParameters['offset'] as int;
          return ok({
            'items': many.skip(offset).take(200).toList(),
            'total': many.length,
            'limit': 200,
            'offset': offset,
          });
        },
      });

      final loaded = await createContainer(api: api)
          .read(gearRepositoryProvider)
          .listItems(const GearFilter());

      expect(loaded.value, hasLength(450));
      expect(api.calls, hasLength(3));
    });

    test('creating sends the catalog template, updating does not', () async {
      final saved = <Object?>[];
      final repository = createContainer(api: gearApi(saved: saved))
          .read(gearRepositoryProvider);

      await repository.saveItem(
        const GearItem(name: 'Neu'),
        catalogId: 'catalog-1',
      );
      await repository.saveItem(GearItem.fromJson(tent));

      expect((saved[0]! as Map)['catalog_id'], 'catalog-1');
      expect((saved[0]! as Map).containsKey('id'), isFalse);
      expect((saved[1]! as Map).containsKey('catalog_id'), isFalse);
      expect((saved[1]! as Map)['tag_ids'], ['tag-winter']);
    });

    test('other errors than a missing network are passed on', () async {
      final api = FakeApi({
        'GET /gear/items': (_, _) => apiError(403, 'forbidden'),
      });
      final repository = createContainer(api: api).read(gearRepositoryProvider);

      expect(repository.listItems(const GearFilter()), throwsA(anything));
    });
  });

  group('gear list', () {
    testWidgets('shows the items with brand, type and weight', (tester) async {
      await openGear(tester, gearApi());

      expect(find.text('Ausrüstung'), findsWidgets);
      expect(find.text('Zelt Hubba'), findsOneWidget);
      expect(find.text('MSR · Zelt & Biwak'), findsOneWidget);
      expect(find.text('1,5 kg'), findsOneWidget);
      expect(find.text('Kocher'), findsOneWidget);
      expect(find.text('300 g'), findsOneWidget);
    });

    testWidgets('filters by status, tag and search text', (tester) async {
      final api = gearApi();
      await openGear(tester, api);

      await tapVisible(tester, find.widgetWithText(ChoiceChip, 'Ausgemustert'));
      await tester.pumpAndSettle();
      expect(find.text('Zelt Hubba'), findsNothing);
      expect(find.text('Kocher'), findsOneWidget);

      await tapVisible(tester, find.widgetWithText(ChoiceChip, 'Alle'));
      await tapVisible(tester, find.widgetWithText(FilterChip, 'Winter'));
      await tester.pumpAndSettle();
      expect(find.text('Zelt Hubba'), findsOneWidget);
      expect(find.text('Kocher'), findsNothing);

      await tapVisible(tester, find.widgetWithText(FilterChip, 'Winter'));
      await tester.enterText(find.byType(TextField), 'koch');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();
      expect(find.text('Kocher'), findsOneWidget);
      expect(find.text('Zelt Hubba'), findsNothing);
      expect(api.calls.last.path, '/gear/items');
    });

    testWidgets('shows the stored copy with a hint when offline', (
      tester,
    ) async {
      final api = gearApi();
      final store = MemoryKeyValueStore(signedInStore);
      final container = await pumpApp(tester, api: api, store: store);
      expect(find.text('Zelt Hubba'), findsOneWidget);

      api.offline = true;
      container.invalidate(gearItemsProvider);
      await tester.pumpAndSettle();

      expect(
        find.text('Ohne Verbindung – gespeicherter Stand'),
        findsOneWidget,
      );
      expect(find.text('Zelt Hubba'), findsOneWidget);
    });

    testWidgets('empty list explains itself', (tester) async {
      await openGear(tester, gearApi(items: []));

      expect(find.text('Noch keine Ausrüstung erfasst.'), findsOneWidget);
    });
  });

  group('gear item form', () {
    testWidgets('creates an item with tags and validated price', (
      tester,
    ) async {
      final saved = <Object?>[];
      await openGear(tester, gearApi(saved: saved));

      await tester.tap(find.text('Neuer Gegenstand'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Name'), 'Pickel');
      await tester.enterText(field('Gewicht (g)'), '450');
      await tester.tap(find.widgetWithText(FilterChip, 'Winter'));
      await tester.enterText(field('Kaufpreis'), '120,555');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Betrag zwischen 0 und 1 000 000 mit höchstens zwei Nachkommastellen',
        ),
        findsOneWidget,
      );
      expect(saved, isEmpty);

      await tester.enterText(field('Kaufpreis'), '120,50');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      final body = saved.single! as Map<String, dynamic>;
      expect(body['name'], 'Pickel');
      expect(body['weight_g'], 450);
      expect(body['purchase_price'], 120.5);
      // Prices are always in EUR: nothing to send.
      expect(body.containsKey('currency'), isFalse);
      expect(body['tag_ids'], ['tag-winter']);
      expect(body['status'], 'active');
      expect(body['brand'], isNull);
      // Back on the list.
      expect(find.text('Neuer Gegenstand'), findsOneWidget);
    });

    testWidgets('edits an existing item', (tester) async {
      final saved = <Object?>[];
      await openGear(tester, gearApi(saved: saved));

      await tester.tap(find.text('Zelt Hubba'));
      await tester.pumpAndSettle();
      expect(find.text('Gegenstand bearbeiten'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, 'MSR'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, '399,9'), findsOneWidget);

      await tester.enterText(field('Name'), 'Zelt Hubba NX');
      await tester.tap(find.text('Ausgemustert'));
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      final body = saved.single! as Map<String, dynamic>;
      expect(body['name'], 'Zelt Hubba NX');
      expect(body['status'], 'retired');
      expect(body['purchase_price'], 399.9);
      expect(body['type_id'], 'type-tent');
    });

    testWidgets('shows the extra fields of the type and sends them', (
      tester,
    ) async {
      final saved = <Object?>[];
      final api = gearApi(saved: saved);
      api.routes['GET /gear/types'] = (_, _) => ok([
        {...types[0], 'kind': 'backpack'},
        {...types[1], 'kind': 'shoes'},
      ]);
      api.routes['GET /gear/items/item-tent'] = (_, _) => ok({
        ...tent,
        'attributes': {'volume_l': 35},
      });
      await openGear(tester, api);

      await tester.tap(find.text('Zelt Hubba'));
      await tester.pumpAndSettle();
      // The type has the kind "backpack": its field is there, the one for shoes is not.
      expect(find.widgetWithText(TextFormField, '35'), findsOneWidget);
      expect(find.text('Schuhkategorie'), findsNothing);
      expect(find.textContaining('JPEG, PNG oder WebP'), findsOneWidget);
      expect(find.text('Währung'), findsNothing);

      await tester.enterText(field('Volumen (Liter)'), '42,5');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      final body = saved.single! as Map<String, dynamic>;
      expect(body['attributes'], {'volume_l': 42.5});
    });

    testWidgets('the star sets and removes the favourite tag', (tester) async {
      final saved = <Object?>[];
      final api = gearApi(saved: saved);
      api.routes['GET /gear/tags'] = (_, _) => ok([
        {
          'id': 'tag-favorite',
          'name': 'Favorit',
          'color': '#f5b400',
          'system': 'favorite',
        },
        ...tags,
      ]);
      await openGear(tester, api);

      await tester.tap(find.byTooltip('Favorit').first);
      await tester.pumpAndSettle();

      final body = saved.single! as Map<String, dynamic>;
      expect(body['tag_ids'], ['tag-winter', 'tag-favorite']);
      expect(body['name'], 'Zelt Hubba');
    });

    testWidgets('uploads an image and proposes the item to the catalog', (
      tester,
    ) async {
      final api = gearApi();
      api.routes['POST /gear/items/item-tent/image'] = (_, _) =>
          ok({...tent, 'image_file_id': 'file-1'});
      api.routes['POST /gear/items/item-tent/propose-to-catalog'] = (_, _) =>
          ok({}, 201);
      await pumpApp(
        tester,
        api: api,
        store: MemoryKeyValueStore(signedInStore),
        overrides: [
          filePickerProvider.overrideWithValue(
            ({required extensions, multiple = false}) async => [
              PickedFile('zelt.jpg', Uint8List.fromList([1, 2, 3])),
            ],
          ),
        ],
      );
      await tester.tap(find.text('Zelt Hubba'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Bild wählen'));
      await tester.pumpAndSettle();
      expect(api.requested, contains('POST /gear/items/item-tent/image'));
      expect(find.text('Bild entfernen'), findsOneWidget);

      await tester.ensureVisible(find.text('Im Katalog teilen'));
      await tester.tap(find.text('Im Katalog teilen'));
      await tester.pumpAndSettle();
      expect(
        api.requested,
        contains('POST /gear/items/item-tent/propose-to-catalog'),
      );
      expect(find.textContaining('Vorschlag eingereicht'), findsOneWidget);
    });

    testWidgets('takes a catalog entry as template', (tester) async {
      final saved = <Object?>[];
      final api = gearApi(saved: saved);
      api.routes['GET /gear/catalog'] = (_, _) => ok(
        page([
          {
            'id': 'catalog-1',
            'name': 'Aeon 35',
            'brand': 'Rab',
            'type_id': 'type-tent',
            'nominal_weight_g': 890,
            'website_url': null,
            'image_file_id': null,
            'status': 'approved',
          },
        ]),
      );
      await openGear(tester, api);
      await tester.tap(find.text('Neuer Gegenstand'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Aus Katalog übernehmen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Aeon 35'));
      await tester.pumpAndSettle();

      expect(find.widgetWithText(TextFormField, 'Aeon 35'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, '890'), findsOneWidget);
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      final body = saved.single! as Map<String, dynamic>;
      expect(body['catalog_id'], 'catalog-1');
      expect(body['brand'], 'Rab');
    });
  });

  group('summary', () {
    Map<String, dynamic> totals(
      int count,
      int weight, {
      String? key,
      String? label,
    }) => {
      'item_count': count,
      'weight_g': weight,
      'items_without_weight': 1,
      'value': [
        {'currency': 'CHF', 'amount': 520.0},
        {'currency': 'EUR', 'amount': 95.5},
      ],
      'items_without_price': 0,
      'key': key,
      'label': label,
    };

    testWidgets('shows totals and groups them by tag', (tester) async {
      final api = gearApi();
      api.routes['GET /gear/summary'] = (request, _) => ok({
        'group_by': request.queryParameters['group_by'],
        'total': totals(4, 2750),
        'groups': request.queryParameters['group_by'] == 'tag'
            ? [
                totals(2, 1950, key: 'tag-loan', label: 'Verleihbar'),
                totals(1, 0),
              ]
            : <Object>[],
      });
      await openGear(tester, api);

      await tester.tap(find.byTooltip('Summen'));
      await tester.pumpAndSettle();

      expect(find.text('4 Gegenstände'), findsOneWidget);
      expect(find.text('2,75 kg'), findsOneWidget);
      expect(find.text('520,00 CHF + 95,50 EUR'), findsOneWidget);
      expect(find.text('1 ohne Gewicht'), findsOneWidget);

      await tester.tap(find.widgetWithText(ChoiceChip, 'Tag'));
      await tester.pumpAndSettle();

      expect(find.text('Verleihbar'), findsOneWidget);
      expect(find.text('1,95 kg'), findsOneWidget);
      expect(find.text('Nicht zugeordnet'), findsOneWidget);
      expect(find.text('1 Gegenstand'), findsOneWidget);
      expect(find.textContaining('zählt in jedem seiner Tags'), findsOneWidget);
    });
  });

  group('tags and types', () {
    testWidgets('creates a tag with colour and protects standard types', (
      tester,
    ) async {
      final saved = <Object?>[];
      final api = gearApi();
      api.routes['POST /gear/tags'] = (_, body) {
        saved.add(body);
        return ok(body, 201);
      };
      await openGear(tester, api);
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tags und Kategorien'));
      await tester.pumpAndSettle();

      expect(find.text('Winter'), findsOneWidget);
      await tester.tap(find.text('Neuer Tag'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Name'), 'Hochtour');
      await tester.enterText(field('Farbe (#RRGGBB)'), 'rot');
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(find.text('Format #RRGGBB, z. B. #3366CC'), findsOneWidget);
      await tester.enterText(field('Farbe (#RRGGBB)'), '#FF8800');
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();
      expect(saved.single, {'name': 'Hochtour', 'color': '#FF8800'});

      await tester.tap(find.widgetWithText(Tab, 'Kategorie'));
      await tester.pumpAndSettle();
      // A normal user cannot change or delete the standard type.
      final standard = tester.widget<ListTile>(
        find.widgetWithText(ListTile, 'Zelt & Biwak'),
      );
      final own = tester.widget<ListTile>(
        find.widgetWithText(ListTile, 'Fotoausrüstung'),
      );
      expect(standard.enabled, isFalse);
      expect(standard.trailing, isNull);
      expect(own.enabled, isTrue);
      expect(own.trailing, isNotNull);
    });

    testWidgets('an own category can get extra fields', (tester) async {
      final saved = <Object?>[];
      final api = gearApi();
      api.routes['PUT /gear/types/type-photo'] = (_, body) {
        saved.add(body);
        return ok(body);
      };
      api.routes['POST /gear/types'] = (_, body) {
        saved.add(body);
        return ok(body, 201);
      };
      await openGear(tester, api);
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tags und Kategorien'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(Tab, 'Kategorie'));
      await tester.pumpAndSettle();

      // An existing own category: choose the fields of shoes.
      await tester.tap(find.text('Fotoausrüstung'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Keine'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Schuhe (Schuhkategorie)').last);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      expect(saved.single, {
        'name': 'Fotoausrüstung',
        'kind': 'shoes',
        'sort_order': 20,
      });
    });
  });

  group('catalog', () {
    const proposal = {
      'id': 'catalog-1',
      'name': 'Aeon 35',
      'brand': 'Rab',
      'type_id': null,
      'nominal_weight_g': 890,
      'website_url': null,
      'image_file_id': null,
      'status': 'rejected',
    };

    testWidgets('users see the status of their proposals', (tester) async {
      final api = gearApi();
      api.routes['GET /gear/catalog/mine'] = (_, _) => ok(page([proposal]));
      await openGear(tester, api);
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Katalog'));
      await tester.pumpAndSettle();

      expect(find.text('Meine Vorschläge'), findsOneWidget);
      expect(find.text('Aeon 35'), findsOneWidget);
      expect(find.text('Rab · 890 g'), findsOneWidget);
      expect(find.text('Abgelehnt'), findsOneWidget);
      expect(find.text('Offene Vorschläge'), findsNothing);
      expect(api.requested, isNot(contains('GET /gear/catalog/pending')));
    });

    testWidgets('admins approve open proposals', (tester) async {
      final moderated = <Object?>[];
      final api = gearApi();
      api.routes['GET /gear/catalog/mine'] = (_, _) => ok(page([]));
      api.routes['GET /gear/catalog/pending'] = (_, _) => ok(
        page(
          moderated.isEmpty
              ? [
                  {...proposal, 'status': 'pending'},
                ]
              : [],
        ),
      );
      api.routes['PATCH /gear/catalog/catalog-1'] = (_, body) {
        moderated.add(body);
        return ok({...proposal, 'status': 'approved'});
      };
      final adminStore = {
        ...signedInStore,
        'user': signedInStore['user']!.replaceFirst(
          '"role":"user"',
          '"role":"admin"',
        ),
      };
      final container = await pumpApp(
        tester,
        api: api,
        store: MemoryKeyValueStore(adminStore),
      );
      expect(container.read(sessionProvider).user!.isAdmin, isTrue);
      await tester.tap(find.byType(PopupMenuButton<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Katalog'));
      await tester.pumpAndSettle();

      expect(find.text('Offene Vorschläge'), findsOneWidget);
      await tester.tap(find.byTooltip('Freigeben'));
      await tester.pumpAndSettle();

      expect(moderated.single, {'status': 'approved'});
      expect(find.text('Keine Vorschläge.'), findsOneWidget);
    });
  });

  group('packing lists', () {
    testWidgets('creates a list with quantities and shows its weight', (
      tester,
    ) async {
      final saved = <Object?>[];
      final api = gearApi();
      api.routes['GET /gear/lists'] = (_, _) => ok(
        saved.isEmpty
            ? <Object>[]
            : [
                {
                  'id': 'list-1',
                  'name': 'Sommer 2 Tage',
                  'description': null,
                  'entries': [
                    {'gear_item_id': 'item-tent', 'quantity': 2},
                  ],
                  'total_weight_g': 3000,
                },
              ],
      );
      api.routes['POST /gear/lists'] = (_, body) {
        saved.add(body);
        return ok(body, 201);
      };
      await openGear(tester, api);
      await tester.tap(find.byTooltip('Packlisten'));
      await tester.pumpAndSettle();
      expect(find.text('Noch keine Packliste.'), findsOneWidget);

      await tester.tap(find.text('Neue Packliste'));
      await tester.pumpAndSettle();
      await tester.enterText(
        field('Name').evaluate().isEmpty
            ? find.byType(TextField).first
            : field('Name'),
        'Sommer 2 Tage',
      );
      await tester.tap(find.widgetWithText(CheckboxListTile, 'Zelt Hubba'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Anzahl +'));
      await tester.pumpAndSettle();
      expect(find.text('Gesamtgewicht: 3 kg'), findsOneWidget);
      // Retired gear is not offered for new lists.
      expect(find.widgetWithText(CheckboxListTile, 'Kocher'), findsNothing);

      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      expect(saved.single, {
        'name': 'Sommer 2 Tage',
        'description': null,
        'entries': [
          {'gear_item_id': 'item-tent', 'quantity': 2},
        ],
      });
      expect(find.text('Sommer 2 Tage'), findsOneWidget);
      expect(find.text('1 Gegenstand · 3 kg'), findsOneWidget);
    });
  });
}
