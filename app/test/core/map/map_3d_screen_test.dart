import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_3d_screen.dart';
import 'package:hiker/l10n/app_localizations.dart';

// In a file of its own: widget tests switch off real network connections,
// which the test of the map server next door needs.
void main() {
  testWidgets('the 3D screen shows the page of the own map server', (
    tester,
  ) async {
    Uri? shown;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          map3dViewBuilderProvider.overrideWithValue((page) {
            shown = page;
            return const Text('WEBVIEW');
          }),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Map3DScreen(
            page: Uri.parse('http://127.0.0.1:4711/3d/index.html'),
          ),
        ),
      ),
    );

    expect(find.text('3D-Ansicht'), findsOneWidget);
    expect(find.text('WEBVIEW'), findsOneWidget);
    expect(find.textContaining('mit zwei Fingern drehen'), findsOneWidget);
    expect(shown!.host, '127.0.0.1');
  });
}
