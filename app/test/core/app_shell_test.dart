import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:hiker/core/modules/feature_module.dart';
import 'package:hiker/core/storage/key_value_store.dart';

import '../helpers.dart';

FeatureModule module(String id, String label, IconData icon) => FeatureModule(
  id: id,
  rootPath: '/$id',
  icon: icon,
  label: (_) => label,
  routes: [
    GoRoute(
      path: '/$id',
      builder: (context, state) =>
          Scaffold(body: Center(child: Text('Screen $label'))),
    ),
  ],
);

final modules = [
  module('protocols', 'Touren', Icons.terrain),
  module('gear', 'Ausrüstung', Icons.backpack),
  module('nutrition', 'Essen', Icons.restaurant),
];

FakeApi apiWithModules(List<String> names) => FakeApi({
  'GET /modules': (_, _) => ok([
    for (final name in names) {'name': name, 'version': '0.1.0'},
  ]),
  'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
});

void main() {
  testWidgets('shows only the modules the server has enabled', (tester) async {
    await pumpApp(
      tester,
      api: apiWithModules(['auth', 'gear', 'protocols']),
      store: MemoryKeyValueStore(signedInStore),
      modules: modules,
    );

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Touren'), findsOneWidget);
    expect(find.text('Ausrüstung'), findsOneWidget);
    expect(find.text('Essen'), findsNothing);
    expect(find.text('Profil'), findsOneWidget);
    // The first active module is the start screen.
    expect(find.text('Screen Touren'), findsOneWidget);
  });

  testWidgets('navigation switches between modules and the profile', (
    tester,
  ) async {
    await pumpApp(
      tester,
      api: apiWithModules(['gear', 'protocols', 'nutrition']),
      store: MemoryKeyValueStore(signedInStore),
      modules: modules,
    );

    await tester.tap(find.text('Essen'));
    await tester.pumpAndSettle();
    expect(find.text('Screen Essen'), findsOneWidget);

    await tester.tap(find.text('Profil'));
    await tester.pumpAndSettle();
    expect(find.text('Angemeldet als Anna'), findsOneWidget);
  });

  testWidgets('wide screens use a navigation rail', (tester) async {
    await pumpApp(
      tester,
      api: apiWithModules(['gear', 'protocols']),
      store: MemoryKeyValueStore(signedInStore),
      modules: modules,
      size: const Size(1200, 800),
    );

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
  });

  testWidgets('offline all built-in modules stay reachable', (tester) async {
    await pumpApp(
      tester,
      api: FakeApi()..offline = true,
      store: MemoryKeyValueStore(signedInStore),
      modules: modules,
    );

    expect(find.text('Touren'), findsOneWidget);
    expect(find.text('Essen'), findsOneWidget);
  });

  testWidgets('without any module the profile is shown without navigation', (
    tester,
  ) async {
    await pumpApp(
      tester,
      api: apiWithModules(['auth']),
      store: MemoryKeyValueStore(signedInStore),
      modules: modules,
    );

    expect(find.byType(NavigationBar), findsNothing);
    expect(find.text('Angemeldet als Anna'), findsOneWidget);
  });
}
