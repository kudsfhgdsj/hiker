import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/core/modules/feature_module.dart';
import 'package:hiker/core/session/session.dart';

import '../../helpers.dart';

void main() {
  Future<ProviderContainer> containerWith(
    Future<Set<String>> Function() modules, {
    String baseUrl = 'https://hiker.example.org',
  }) async {
    final container = createContainer(
      api: FakeApi(),
      overrides: [backendModulesProvider.overrideWith((ref) => modules())],
    );
    if (baseUrl.isNotEmpty) {
      await container.read(sessionProvider.notifier).setBaseUrl(baseUrl);
    }
    // Let the answer about the modules arrive.
    try {
      await container.read(backendModulesProvider.future);
    } catch (_) {}
    return container;
  }

  test('tiles come from the own server if it has the module maps', () async {
    final container = await containerWith(() async => {'auth', 'maps'});

    expect(
      container.read(mapTileUrlProvider),
      'https://hiker.example.org/api/v1/maps/tiles/{z}/{x}/{y}.png',
    );
  });

  test(
    'a server without the module sends the app to the tile source',
    () async {
      final container = await containerWith(() async => {'auth', 'gear'});

      expect(
        container.read(mapTileUrlProvider),
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      );
    },
  );

  test('without an answer about the modules the own server is tried', () async {
    final container = await containerWith(
      () async => throw Exception('offline'),
    );

    expect(
      container.read(mapTileUrlProvider),
      startsWith('https://hiker.example.org/api/v1/maps/tiles/'),
    );
  });

  test('without a server address the tile source is used', () async {
    final container = await containerWith(() async => {'maps'}, baseUrl: '');

    expect(container.read(mapTileUrlProvider), startsWith('https://tile.'));
  });
}
