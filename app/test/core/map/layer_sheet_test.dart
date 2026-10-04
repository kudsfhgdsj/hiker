import 'dart:convert';
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
    const options = <String, dynamic>{
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
          'range': {'min': 15, 'max': 60, 'step': 5, 'low': 30},
        },
      ],
      'history': {
        'sources': ['snow', 'avalanche'],
        'days': 400,
      },
      'radar': {'frames': 'f', 'rain': 'r', 'clouds': 'c'},
    };
    Future<void> show(MapSheetPart part) => tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: Scaffold(
            body: MapLayerSheet(options: options, part: part),
          ),
        ),
      ),
    );

    // "Darstellung": how the map is drawn.
    await show(MapSheetPart.looks);
    expect(find.text('Darstellung'), findsOneWidget);
    expect(find.text('Karte'), findsOneWidget);
    expect(find.text('Hangneigung'), findsNothing);
    await tester.tap(find.text('Luftbild'));
    await tester.pump();

    // "Ebenen": what lies on it, with angles, a past day and the radar.
    await show(MapSheetPart.layers);
    expect(find.textContaining('violett ab 45°'), findsOneWidget);
    expect(find.byType(RangeSlider), findsNothing);
    await tester.tap(find.text('Hangneigung'));
    await tester.pump();
    expect(find.byType(RangeSlider), findsOneWidget);
    expect(find.text('Eingefärbt von 30° bis senkrecht'), findsOneWidget);
    expect(find.text('Stand vom'), findsOneWidget);
    await tester.tap(find.text('Regenradar'));
    await tester.pump();

    expect(
      container.read(mapLayerChoiceProvider),
      const MapLayerChoice(
        base: 'satellite',
        overlays: {'slope'},
        radar: {'rain'},
      ),
    );
  });

  test('chosen angles and day become part of the addresses of the map', () {
    const style =
        '{"metadata":{"hiker":{"history":{"sources":["snow","avalanche"]}}},'
        '"sources":{"slope":{"tiles":["http://x/slope/{z}/{x}/{y}.png"]},'
        '"snow":{"tiles":["http://x/raster/snow/{z}/{x}/{y}"]},'
        '"avalanche":{"data":"http://x/avalanche.geojson"},'
        '"hiker":{"tiles":["http://x/vector/{z}/{x}/{y}.pbf"]}}}';
    // Nothing chosen: the style stays as it is.
    expect(styleWithChoice(style, const MapLayerChoice()), style);

    final chosen = jsonDecode(
      styleWithChoice(
        style,
        const MapLayerChoice(slopeLow: 35, slopeHigh: 50, day: '2026-02-01'),
      ),
    ) as Map<String, dynamic>;
    final sources = chosen['sources'] as Map<String, dynamic>;
    expect((sources['slope'] as Map)['tiles'], [
      'http://x/slope/{z}/{x}/{y}.png?low=35&high=50',
    ]);
    expect((sources['snow'] as Map)['tiles'], [
      'http://x/raster/snow/{z}/{x}/{y}?date=2026-02-01',
    ]);
    expect(
      (sources['avalanche'] as Map)['data'],
      'http://x/avalanche.geojson?date=2026-02-01',
    );
    expect((sources['hiker'] as Map)['tiles'], [
      'http://x/vector/{z}/{x}/{y}.pbf',
    ]);
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
