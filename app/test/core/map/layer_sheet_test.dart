import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/l10n/app_localizations.dart';

import '../../helpers.dart';

void main() {
  testWidgets('the sheet offers what the style of the server has', (
    tester,
  ) async {
    final container = createContainer(api: FakeApi());
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: MapLayerSheet(
              options: {
                'bases': [
                  {'id': 'map', 'show': <String>[], 'hide': <String>[]},
                  {
                    'id': 'satellite',
                    'show': ['satellite'],
                    'hide': <String>[],
                  },
                ],
                'overlays': [
                  {
                    'id': 'slope',
                    'layers': ['slope'],
                  },
                ],
              },
            ),
          ),
        ),
      ),
    );

    expect(find.text('Karte'), findsOneWidget);
    expect(find.textContaining('violett ab 45°'), findsOneWidget);
    await tester.tap(find.text('Luftbild'));
    await tester.tap(find.text('Hangneigung'));
    await tester.pump();

    expect(
      container.read(mapLayerChoiceProvider),
      const MapLayerChoice(base: 'satellite', overlays: {'slope'}),
    );
  });

  test('the app carries the same fonts as the server', () {
    final server = Directory('../backend/app/modules/maps/fonts');
    final fonts = server.listSync().whereType<Directory>().toList();
    expect(fonts.length, 3);
    for (final font in fonts) {
      final name = font.uri.pathSegments.lastWhere((part) => part.isNotEmpty);
      final folder = Uri.decodeComponent(name)
          .toLowerCase()
          .replaceAll(' ', '-');
      for (final file in font.listSync().whereType<File>()) {
        final range = file.uri.pathSegments.last;
        expect(
          File('assets/fonts/$folder/$range').readAsBytesSync(),
          file.readAsBytesSync(),
          reason: '$folder/$range',
        );
      }
    }
  });
}
