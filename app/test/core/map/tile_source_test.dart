import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/core/map/tile_proxy.dart';
import 'package:hiker/core/modules/feature_module.dart';
import 'package:hiker/core/network/trusted_certificates.dart';
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

  group('server with a certificate trusted by hand', () {
    test('the map asks the app for its tiles', () async {
      final upstream = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final asked = <String>[];
      upstream.listen((request) async {
        asked.add(request.uri.path);
        if (request.uri.path.endsWith('/5/1/2.png')) {
          request.response.headers.contentType = ContentType('image', 'png');
          request.response.headers.set(
            'cache-control',
            'public, max-age=86400',
          );
          request.response.add([137, 80, 78, 71]);
        } else {
          request.response.statusCode = 404;
        }
        await request.response.close();
      });
      final base = 'http://127.0.0.1:${upstream.port}';
      final container = await containerWith(
        () async => {'maps'},
        baseUrl: base,
      );
      addTearDown(() => upstream.close(force: true));

      // Not trusted by hand: the map goes to the server directly.
      expect(container.read(mapTileUrlProvider), startsWith(base));

      await container
          .read(trustedCertificatesProvider.notifier)
          .trust('127.0.0.1', upstream.port, 'AB:CD');
      await container.read(tileProxyProvider.notifier).start();
      final port = container.read(tileProxyProvider)!;
      expect(
        container.read(mapTileUrlProvider),
        'http://127.0.0.1:$port/{z}/{x}/{y}.png',
      );

      final client = HttpClient();
      addTearDown(client.close);
      Future<HttpClientResponse> get(String path) async =>
          (await client.getUrl(Uri.parse('http://127.0.0.1:$port$path')))
              .close();

      final tile = await get('/5/1/2.png');
      final bytes = await tile.expand((chunk) => chunk).toList();
      expect(tile.statusCode, 200);
      expect(bytes, [137, 80, 78, 71]);
      expect(tile.headers.contentType?.mimeType, 'image/png');
      expect(tile.headers.value('cache-control'), 'public, max-age=86400');
      expect(asked, ['/api/v1/maps/tiles/5/1/2.png']);

      final missing = await get('/5/9/9.png');
      await missing.drain<void>();
      expect(missing.statusCode, 404);
      // Nothing but tiles is passed on.
      final other = await get('/api/v1/me');
      await other.drain<void>();
      expect(other.statusCode, 404);
      expect(asked.length, 2);

      // A tile seen before comes from the device: at once, and without network.
      await upstream.close(force: true);
      final again = await get('/5/1/2.png');
      expect(again.statusCode, 200);
      expect(await again.expand((chunk) => chunk).toList(), [137, 80, 78, 71]);
      expect(asked.length, 2);
      // A tile never seen cannot be shown without network.
      final unseen = await get('/5/1/3.png');
      await unseen.drain<void>();
      expect(unseen.statusCode, 502);
    });
  });
}
