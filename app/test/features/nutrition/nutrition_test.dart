import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/features/nutrition/data/food_models.dart';
import 'package:hiker/features/nutrition/data/food_repository.dart';
import 'package:hiker/features/nutrition/presentation/barcode_scanner.dart';

import '../../helpers.dart';

const ean = '7610000000017';
const ownBar = {
  'id': 'food-own',
  'catalog_id': null,
  'name': 'Nussriegel',
  'brand': 'Bergkraft',
  'barcode': ean,
  'kcal_per_100g': 480.0,
  'protein_g': 12.5,
  'carbs_g': 45.0,
  'fat_g': 27.0,
  'sugar_g': 30.0,
  'salt_g': 0.3,
  'serving_size_g': 40.0,
  'image_url': null,
  'source': 'custom',
  'visibility': 'private',
};
const catalogSpread = {
  'id': 'food-off',
  'catalog_id': null,
  'name': 'Nuss-Nougat-Creme',
  'brand': 'Marke',
  'barcode': '3017620422003',
  'kcal_per_100g': 539.0,
  'protein_g': 6.3,
  'carbs_g': 57.5,
  'fat_g': 30.9,
  'sugar_g': 56.3,
  'salt_g': 0.11,
  'serving_size_g': null,
  'image_url': null,
  'source': 'openfoodfacts',
  'visibility': 'catalog',
};

Map<String, dynamic> page(List<Map<String, dynamic>> items) => {
  'items': items,
  'total': items.length,
  'limit': 200,
  'offset': 0,
};

FakeApi foodApi({List<Object?>? saved}) => FakeApi({
  'GET /modules': (_, _) => ok([
    {'name': 'nutrition', 'version': '0.1.0'},
  ]),
  'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
  'GET /nutrition/search': (request, _) {
    final query = request.queryParameters['q'] as String? ?? '';
    return ok(
      page(
        [
          ownBar,
          catalogSpread,
        ].where((f) => Food.fromJson(f).matches(query)).toList(),
      ),
    );
  },
  'GET /nutrition/barcode/3017620422003': (_, _) => ok(catalogSpread),
  'GET /nutrition/barcode/$ean': (_, _) => ok(ownBar),
  'GET /nutrition/barcode/4000000000006': (_, _) =>
      apiError(404, 'product_not_found'),
  'GET /nutrition/barcode/4000000000013': (_, _) =>
      apiError(502, 'source_unavailable'),
  'POST /nutrition/foods': (_, body) {
    saved?.add(body);
    return ok({
      ...ownBar,
      ...(body! as Map<String, dynamic>),
      'id': 'food-new',
    }, 201);
  },
  'PUT /nutrition/foods/food-own': (_, body) {
    saved?.add(body);
    return ok({...ownBar, ...(body! as Map<String, dynamic>)});
  },
});

/// Opens the app on the food screen; `scan` is what the camera would read
/// (null: the user leaves the scanner without a code).
Future<void> openFood(WidgetTester tester, FakeApi api, {String? scan}) =>
    pumpApp(
      tester,
      api: api,
      store: MemoryKeyValueStore(signedInStore),
      overrides: [barcodeScannerProvider.overrideWithValue((_) async => scan)],
    );

Future<void> tapSave(WidgetTester tester, [String label = 'Speichern']) async {
  final button = find.widgetWithText(FilledButton, label);
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  group('Food', () {
    test('barcode formats', () {
      for (final code in ['12345678', '123456789012', ean, '12345678901234']) {
        expect(isValidBarcode(code), isTrue, reason: code);
      }
      for (final code in [
        '',
        '1234567',
        '123456789',
        '76100000000ab',
        '123456789012345',
      ]) {
        expect(isValidBarcode(code), isFalse, reason: code);
      }
    });

    test('calories of an amount and search matching', () {
      final bar = Food.fromJson(ownBar);

      expect(bar.kcalFor(50), 240);
      expect(const Food(name: 'x').kcalFor(50), isNull);
      expect(bar.matches('nuss'), isTrue);
      expect(bar.matches('BERG'), isTrue);
      expect(bar.matches(ean), isTrue);
      expect(bar.matches('brot'), isFalse);
      expect(Food.fromJson(catalogSpread).isFromOpenFoodFacts, isTrue);
      expect(bar.isOwn, isTrue);
    });
  });

  group('FoodRepository', () {
    test(
      'search results are kept and searched offline, own foods first',
      () async {
        final api = foodApi();
        final repository = createContainer(api: api)
            .read(foodRepositoryProvider);
        await repository.search('');

        api.offline = true;
        final all = await repository.search('');
        final filtered = await repository.search('creme');

        expect(all.offline, isTrue);
        expect(all.value.map((f) => f.name), [
          'Nussriegel',
          'Nuss-Nougat-Creme',
        ]);
        expect(filtered.value.map((f) => f.name), ['Nuss-Nougat-Creme']);
      },
    );

    test(
      'barcode lookup distinguishes found, unknown and unavailable',
      () async {
        final repository = createContainer(api: foodApi())
            .read(foodRepositoryProvider);

        final found = await repository.lookupBarcode('3017620422003');
        final unknown = await repository.lookupBarcode('4000000000006');
        final unavailable = await repository.lookupBarcode('4000000000013');

        expect((found as BarcodeFound).food.name, 'Nuss-Nougat-Creme');
        expect(found.offline, isFalse);
        expect(unknown, isA<BarcodeUnknown>());
        expect(unavailable, isA<BarcodeUnavailable>());
      },
    );

    test('a scanned product is found again without network', () async {
      final api = foodApi();
      final repository = createContainer(api: api).read(foodRepositoryProvider);
      await repository.lookupBarcode('3017620422003');

      api.offline = true;
      final again = await repository.lookupBarcode('3017620422003');
      final never = await repository.lookupBarcode(ean);

      expect((again as BarcodeFound).offline, isTrue);
      expect(again.food.kcalPer100g, 539);
      expect(never, isA<BarcodeUnavailable>());
    });

    test('a correction of a catalog product is saved as own copy', () async {
      final saved = <Object?>[];
      final repository = createContainer(api: foodApi(saved: saved))
          .read(foodRepositoryProvider);

      await repository.save(
        const Food(name: 'Creme', kcalPer100g: 545),
        catalogId: 'food-off',
      );
      await repository.save(Food.fromJson(ownBar));

      expect((saved[0]! as Map)['catalog_id'], 'food-off');
      expect((saved[1]! as Map).containsKey('catalog_id'), isFalse);
    });
  });

  group('food list', () {
    testWidgets('lists own foods and catalog entries with their calories', (
      tester,
    ) async {
      await openFood(tester, foodApi());

      expect(find.text('Nussriegel'), findsOneWidget);
      expect(find.text('Bergkraft · Eigenes'), findsOneWidget);
      expect(find.text('480 kcal'), findsOneWidget);
      expect(find.text('Marke · Katalog'), findsOneWidget);
      expect(
        find.widgetWithText(FloatingActionButton, 'Barcode scannen'),
        findsOneWidget,
      );
      expect(find.byTooltip('Barcode eingeben'), findsOneWidget);
    });

    testWidgets('search narrows the list', (tester) async {
      await openFood(tester, foodApi());

      await tester.enterText(find.byType(TextField), 'creme');
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(find.text('Nuss-Nougat-Creme'), findsOneWidget);
      expect(find.text('Nussriegel'), findsNothing);
    });

    testWidgets('details name Open Food Facts as the source', (tester) async {
      await openFood(tester, foodApi());

      await tester.tap(find.text('Nuss-Nougat-Creme'));
      await tester.pumpAndSettle();

      expect(find.text('Daten: Open Food Facts (ODbL)'), findsOneWidget);
      expect(find.text('539 kcal'), findsWidgets);
      expect(find.text('56,3 g'), findsOneWidget);
      expect(find.text('Eigene Korrektur speichern'), findsOneWidget);
    });

    testWidgets('own foods show no source note', (tester) async {
      await openFood(tester, foodApi());

      await tester.tap(find.text('Nussriegel'));
      await tester.pumpAndSettle();

      expect(find.text('Daten: Open Food Facts (ODbL)'), findsNothing);
      expect(find.widgetWithText(FilledButton, 'Bearbeiten'), findsOneWidget);
    });
  });

  group('barcode', () {
    testWidgets('a scanned known product opens its details', (tester) async {
      final api = foodApi();
      await openFood(tester, api, scan: '3017620422003');

      await tester.tap(
        find.widgetWithText(FloatingActionButton, 'Barcode scannen'),
      );
      await tester.pumpAndSettle();

      expect(api.requested, contains('GET /nutrition/barcode/3017620422003'));
      expect(find.text('Daten: Open Food Facts (ODbL)'), findsOneWidget);
    });

    testWidgets(
      'an unknown product leads to the form with the barcode filled in',
      (tester) async {
        final saved = <Object?>[];
        await openFood(tester, foodApi(saved: saved), scan: '4000000000006');

        await tester.tap(
          find.widgetWithText(FloatingActionButton, 'Barcode scannen'),
        );
        await tester.pumpAndSettle();
        expect(find.text('Produkt nicht gefunden'), findsOneWidget);
        await tester.tap(find.text('Selbst anlegen'));
        await tester.pumpAndSettle();

        expect(find.text('Neues Lebensmittel'), findsOneWidget);
        expect(
          find.widgetWithText(TextFormField, '4000000000006'),
          findsOneWidget,
        );
        await tester.enterText(field('Name'), 'Trockenobst');
        await tester.enterText(field('Kalorien (kcal je 100 g)'), '280');
        await tapSave(tester);

        final body = saved.single! as Map<String, dynamic>;
        expect(body['barcode'], '4000000000006');
        expect(body['name'], 'Trockenobst');
        expect(body['kcal_per_100g'], 280);
      },
    );

    testWidgets('an unreachable product database is explained', (tester) async {
      await openFood(tester, foodApi(), scan: '4000000000013');

      await tester.tap(
        find.widgetWithText(FloatingActionButton, 'Barcode scannen'),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('gerade nicht erreichbar'), findsOneWidget);
    });

    testWidgets('a typed barcode is validated before the lookup', (
      tester,
    ) async {
      final api = foodApi();
      await openFood(tester, api);

      await tester.tap(find.byTooltip('Barcode eingeben'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Barcode'), '12345');
      await tester.tap(find.widgetWithText(FilledButton, 'Suchen'));
      await tester.pumpAndSettle();
      expect(find.text('8, 12, 13 oder 14 Ziffern'), findsOneWidget);
      expect(api.requested.where((r) => r.contains('/barcode/')), isEmpty);

      await tester.enterText(field('Barcode'), ean);
      await tester.tap(find.widgetWithText(FilledButton, 'Suchen'));
      await tester.pumpAndSettle();
      expect(api.requested, contains('GET /nutrition/barcode/$ean'));
      expect(find.widgetWithText(FilledButton, 'Bearbeiten'), findsOneWidget);
    });
  });

  group('food form', () {
    Future<void> openNew(WidgetTester tester, FakeApi api) async {
      await openFood(tester, api);
      await tester.tap(find.byTooltip('Neues Lebensmittel'));
      await tester.pumpAndSettle();
    }

    testWidgets('checks the plausibility of the nutrition values', (
      tester,
    ) async {
      final saved = <Object?>[];
      await openNew(tester, foodApi(saved: saved));

      await tester.enterText(field('Name'), 'Müsli');
      await tester.enterText(field('Kalorien (kcal je 100 g)'), '950');
      await tester.enterText(field('Eiweiß (g)'), '40');
      await tester.enterText(field('Kohlenhydrate (g)'), '50');
      await tester.enterText(field('Fett (g)'), '30');
      await tester.enterText(field('davon Zucker (g)'), '60');
      await tapSave(tester);

      expect(find.text('Zahl zwischen 0 und 900'), findsOneWidget);
      expect(
        find.text('Zucker kann nicht mehr sein als Kohlenhydrate'),
        findsOneWidget,
      );
      expect(
        find.text(
          'Eiweiß, Kohlenhydrate und Fett ergeben zusammen mehr als 100 g',
        ),
        findsOneWidget,
      );
      expect(saved, isEmpty);

      await tester.enterText(field('Kalorien (kcal je 100 g)'), '380,5');
      await tester.enterText(field('Fett (g)'), '8');
      await tester.enterText(field('davon Zucker (g)'), '12');
      await tapSave(tester);

      final body = saved.single! as Map<String, dynamic>;
      expect(body['kcal_per_100g'], 380.5);
      expect(body['sugar_g'], 12);
      expect(body['barcode'], isNull);
    });

    testWidgets('calories are required', (tester) async {
      final saved = <Object?>[];
      await openNew(tester, foodApi(saved: saved));

      await tester.enterText(field('Name'), 'Müsli');
      await tapSave(tester);

      expect(find.text('Zahl zwischen 0 und 900'), findsOneWidget);
      expect(saved, isEmpty);
    });

    testWidgets('editing an own food updates it', (tester) async {
      final saved = <Object?>[];
      final api = foodApi(saved: saved);
      await openFood(tester, api);
      await tester.tap(find.text('Nussriegel'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Bearbeiten'));
      await tester.pumpAndSettle();

      expect(find.text('Lebensmittel bearbeiten'), findsOneWidget);
      await tester.enterText(field('Kalorien (kcal je 100 g)'), '455');
      await tapSave(tester);

      expect(api.requested, contains('PUT /nutrition/foods/food-own'));
      expect((saved.single! as Map)['kcal_per_100g'], 455);
    });

    testWidgets('correcting a catalog product creates an own copy', (
      tester,
    ) async {
      final saved = <Object?>[];
      final api = foodApi(saved: saved);
      await openFood(tester, api);
      await tester.tap(find.text('Nuss-Nougat-Creme'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Eigene Korrektur speichern'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('als deine eigene Kopie gespeichert'),
        findsOneWidget,
      );
      await tester.enterText(field('Kalorien (kcal je 100 g)'), '545');
      await tapSave(tester, 'Eigene Korrektur speichern');

      expect(api.requested, contains('POST /nutrition/foods'));
      final body = saved.single! as Map<String, dynamic>;
      expect(body['catalog_id'], 'food-off');
      expect(body['kcal_per_100g'], 545);
      expect(body['name'], 'Nuss-Nougat-Creme');
    });
  });

  group('catalog', () {
    testWidgets('shows the status of own proposals', (tester) async {
      final api = foodApi();
      api.routes['GET /nutrition/catalog/mine'] = (_, _) => ok(
        page([
          {...ownBar, 'id': 'p1', 'visibility': 'catalog_pending'},
          {
            ...ownBar,
            'id': 'p2',
            'name': 'Riegel alt',
            'visibility': 'catalog_rejected',
          },
        ]),
      );
      await openFood(tester, api);

      await tester.tap(find.byTooltip('Katalog'));
      await tester.pumpAndSettle();

      expect(find.text('Offen'), findsOneWidget);
      expect(find.text('Abgelehnt'), findsOneWidget);
      expect(find.text('Bergkraft · 480 kcal'), findsNWidgets(2));
    });
  });
}
