import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/geo.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/features/map/map_module.dart';
import 'package:hiker/features/map/presentation/map_screen.dart';

import '../../helpers.dart';

const saentis = MapPlace(
  position: GeoPoint(47.2494, 9.3433),
  features: [
    (layer: '', properties: {'name': 'Säntis', 'ele': 2502, 'class': 'peak'}),
    (
      layer: '',
      properties: {'sac_scale': 'alpine_hiking', 'name': 'Lisengrat'},
    ),
    (layer: '', properties: {'highway': 'via_ferrata'}),
    (layer: '', properties: {'class': 'grass'}),
  ],
);

void main() {
  testWidgets('the map opens without signing in and tells about a place', (
    tester,
  ) async {
    final map = FakeMap();
    await pumpApp(
      tester,
      api: FakeApi(),
      overrides: [map.override],
      modules: [mapModule],
    );
    await tester.tap(find.text('Karte ohne Anmeldung ansehen'));
    await tester.pumpAndSettle();

    expect(find.byType(MapScreen), findsOneWidget);
    expect(map.content!.markers, isEmpty);
    map.content!.onPlace!(saentis);
    await tester.pumpAndSettle();

    // Summit with its height, paths with their difficulty, the place itself.
    expect(find.text('Säntis, 2.502 m'), findsOneWidget);
    expect(find.text('Lisengrat: T4 – Schwere Bergtour'), findsOneWidget);
    expect(find.text('Klettersteig'), findsOneWidget);
    expect(find.text('47.24940° N, 9.34330° O'), findsOneWidget);
    // The sun there today, and for the free view from the summit.
    expect(find.textContaining('Sonnenaufgang'), findsOneWidget);
    expect(
      find.textContaining('Bei freiem Horizont vom Gipfel'),
      findsOneWidget,
    );
    expect(find.textContaining('Hell von'), findsOneWidget);
    expect(map.content!.markers.single.id, 'place');

    // Back to the sign-in screen.
    Navigator.of(tester.element(find.text('Klettersteig'))).pop();
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Zur Anmeldung'));
    await tester.pumpAndSettle();
    expect(find.byType(MapScreen), findsNothing);
  });

  testWidgets('signed in the map is a page of the navigation', (tester) async {
    final map = FakeMap();
    await pumpApp(
      tester,
      api: FakeApi({
        'GET /modules': (_, _) => ok([
          {'name': 'maps', 'version': '0.1.0'},
        ]),
      }),
      store: MemoryKeyValueStore(signedInStore),
      overrides: [map.override],
      modules: [mapModule],
    );

    expect(find.byType(MapScreen), findsOneWidget);
    expect(find.byTooltip('Zur Anmeldung'), findsNothing);
    // A place without anything drawn there still has its coordinates and sun.
    map.content!.onPlace!(const MapPlace(position: GeoPoint(46.5, 8.0)));
    await tester.pumpAndSettle();
    expect(find.text('46.50000° N, 8.00000° O'), findsOneWidget);
    expect(find.textContaining('Bei freiem Horizont'), findsNothing);
  });
}
