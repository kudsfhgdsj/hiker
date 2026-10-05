import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/core/widgets/app_shell.dart';
import 'package:hiker/core/widgets/empty_list.dart';
import 'package:hiker/core/widgets/mountain_background.dart';

import '../helpers.dart';

void main() {
  testWidgets('an empty list can be pulled down to ask again', (tester) async {
    var asked = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: EmptyList(
            text: 'Noch keine Tour.',
            onRefresh: () async => asked++,
          ),
        ),
      ),
    );

    await tester.fling(
      find.text('Noch keine Tour.'),
      const Offset(0, 400),
      1000,
    );
    await tester.pumpAndSettle();

    expect(asked, 1);
    expect(find.text('Noch keine Tour.'), findsOneWidget);
  });

  testWidgets('the mountain stands on the navigation bar, not behind it', (
    tester,
  ) async {
    await pumpApp(
      tester,
      api: FakeApi({
        'GET /modules': (_, _) => ok([
          {'name': 'gear', 'version': '0.1.0'},
        ]),
        'GET /gear/items': (_, _) =>
            ok({'items': <dynamic>[], 'total': 0, 'limit': 200, 'offset': 0}),
        'GET /gear/types': (_, _) => ok(<dynamic>[]),
        'GET /gear/tags': (_, _) => ok(<dynamic>[]),
      }),
      store: MemoryKeyValueStore(signedInStore),
    );

    final background = tester.getRect(
      find.descendant(
        of: find.byType(AppShell),
        matching: find.byType(MountainBackground),
      ),
    );
    final navigation = tester.getRect(find.byType(NavigationBar));

    expect(background.bottom, navigation.top);
  });
}
