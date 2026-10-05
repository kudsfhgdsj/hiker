import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_regions.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/l10n/app_localizations.dart';
import 'package:sqlite3/sqlite3.dart';

import '../../helpers.dart';

/// A search index as the server builds it.
void writeIndex(String path, List<List<Object?>> places) {
  final database = sqlite3.open(path)
    ..execute(
      'CREATE TABLE places (name TEXT, folded TEXT, kind TEXT, rank INTEGER, '
      'lat REAL, lon REAL, elevation_m REAL)',
    );
  for (final place in places) {
    database.execute('INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?)', [
      place[0],
      foldName(place[0]! as String),
      ...place.skip(1),
    ]);
  }
  database.close();
}

void main() {
  test('names are folded like in the index of the server', () {
    expect(foldName('Säntis'), 'santis');
    expect(foldName(' Großglockner '), 'grossglockner');
    expect(foldName('Piz Güglia'), 'piz guglia');
    expect(foldName('Cima d’Asta'), 'cima d’asta');
  });

  test(
    'the server searches; without network the index on the device',
    () async {
      final asked = <Map<String, dynamic>>[];
      final api = FakeApi({
        'GET /maps/search': (request, _) {
          asked.add(request.queryParameters);
          return ok([
            {
              'name': 'Säntis',
              'kind': 'peak',
              'lat': 47.249,
              'lon': 9.343,
              'elevation_m': 2502,
            },
          ]);
        },
      });
      final container = createContainer(api: api);
      final store = container.read(mapRegionStoreProvider);
      final folder = (await store.directory).path;
      writeIndex('$folder/switzerland.search.sqlite', [
        ['Säntis', 'peak', 4, 47.249, 9.343, 2502.0],
        ['Säntisdorf', 'village', 3, 47.3, 9.4, null],
        ['Berggasthaus Alter Säntis', 'hut', 4, 47.25, 9.345, null],
        ['Seealpsee', 'lake', 4, 47.27, 9.40, null],
        ['Fälensee', 'lake', 4, 47.25, 9.50, null],
      ]);
      // The same summit in the index of the neighbouring region.
      writeIndex('$folder/austria.search.sqlite', [
        ['Säntis', 'peak', 4, 47.249, 9.343, 2502.0],
      ]);

      final online = await store.search('santis', lat: 47.2, lon: 9.3);
      expect(online.single.name, 'Säntis');
      expect(online.single.elevationM, 2502);
      expect(asked.single['q'], 'santis');
      expect(asked.single['lat'], 47.2);
      // Too short to search for: nobody is asked.
      expect(await store.search('s'), isEmpty);
      expect(asked.length, 1);

      api.offline = true;
      final offline = await store.search('SÄNTIS');
      // The name itself, then what starts with it, then what contains it; once each.
      expect(
        [for (final place in offline) place.name],
        ['Säntis', 'Säntisdorf', 'Berggasthaus Alter Säntis'],
      );
      expect(offline.first.kind, 'peak');
      // Among equals the nearer place comes first.
      final lakes = await store.search('ee', lat: 47.25, lon: 9.5);
      expect(
        [for (final place in lakes) place.name],
        ['Fälensee', 'Seealpsee'],
      );
      expect(await store.search('100%'), isEmpty);

      // A removed region takes its index along.
      await store.delete('switzerland');
      expect((await store.search('seealp')), isEmpty);
    },
  );

  testWidgets('the search sheet lists what was found and returns the choice', (
    tester,
  ) async {
    final queries = <String>[];
    FoundPlace? chosen;
    await tester.pumpWidget(
      MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () async {
                chosen = await showModalBottomSheet<FoundPlace>(
                  context: context,
                  isScrollControlled: true,
                  builder: (_) => PlaceSearchSheet(
                    search: (query) async {
                      queries.add(query);
                      return query == 'nichts'
                          ? const []
                          : const [
                              FoundPlace(
                                name: 'Säntis',
                                kind: 'peak',
                                lat: 47.249,
                                lon: 9.343,
                                elevationM: 2502,
                              ),
                              FoundPlace(
                                name: 'Schwägalp',
                                kind: 'hamlet',
                                lat: 47.25,
                                lon: 9.32,
                              ),
                            ];
                    },
                  ),
                );
              },
              child: const Text('open'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 's');
    await tester.pump(const Duration(milliseconds: 400));
    expect(queries, isEmpty);
    await tester.enterText(find.byType(TextField), 'nichts');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
    expect(find.text('Nichts gefunden.'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'sant');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
    expect(queries, ['nichts', 'sant']);
    expect(find.text('Gipfel, 2.502 m'), findsOneWidget);
    expect(find.text('Weiler'), findsOneWidget);

    await tester.tap(find.text('Säntis'));
    await tester.pumpAndSettle();
    expect(chosen!.name, 'Säntis');
  });
}
