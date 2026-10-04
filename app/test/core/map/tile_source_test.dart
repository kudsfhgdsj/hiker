import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/map_regions.dart';
import 'package:hiker/core/map/map_view.dart';
import 'package:hiker/core/map/tile_proxy.dart';
import 'package:hiker/core/modules/feature_module.dart';
import 'package:hiker/core/network/trusted_certificates.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:sqlite3/sqlite3.dart';

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

  group('own vector map', () {
    /// A map file like the server builds them, with one tile.
    void writeMap(
      String path, {
      required int z,
      required int x,
      required int y,
    }) {
      final database = sqlite3.open(path);
      database
        ..execute('CREATE TABLE metadata (name TEXT, value TEXT)')
        ..execute(
          'CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, '
          'tile_row INTEGER, tile_data BLOB)',
        )
        ..execute('INSERT INTO tiles VALUES (?, ?, ?, ?)', [
          z,
          x,
          (1 << z) - 1 - y,
          Uint8List.fromList([31, 139, 1, 2]),
        ])
        ..close();
    }

    test('the style asks the app for tiles and glyphs', () async {
      final api = FakeApi({
        'GET /maps/style.json': (_, _) => ok({
          'version': 8,
          'glyphs': 'https://hiker.example.org/api/v1/maps/fonts/{fontstack}/{range}.pbf',
          'sources': {
            'hiker': {
              'type': 'vector',
              'tiles': [
                'https://hiker.example.org/api/v1/maps/vector/{z}/{x}/{y}.pbf',
              ],
              'maxzoom': 14,
            },
            'terrain': {
              'type': 'raster-dem',
              'tiles': [
                'https://hiker.example.org/api/v1/maps/raster/terrain/{z}/{x}/{y}',
              ],
            },
            'avalanche': {
              'type': 'geojson',
              'data': 'https://hiker.example.org/api/v1/maps/avalanche.geojson',
            },
            'slope': {
              'type': 'raster',
              'tiles': [
                'https://hiker.example.org/api/v1/maps/slope/{z}/{x}/{y}.png',
              ],
            },
          },
          'metadata': {
            'hiker': {
              'bases': [
                {'id': 'map', 'show': <String>[], 'hide': <String>[]},
                {
                  'id': 'satellite',
                  'show': ['satellite'],
                  'hide': ['wood'],
                },
              ],
              'overlays': [
                {
                  'id': 'slope',
                  'layers': ['slope'],
                },
              ],
            },
          },
          'layers': <dynamic>[],
        }),
      });
      final container = createContainer(
        api: api,
        store: MemoryKeyValueStore(signedInStore),
      );
      await container.read(sessionProvider.notifier).restore();
      await container.read(tileProxyProvider.notifier).start();
      final port = container.read(tileProxyProvider)!;

      final style = jsonDecode(
        (await container.read(mapStyleProvider.future))!,
      ) as Map<String, dynamic>;

      expect(
        style['glyphs'],
        'http://127.0.0.1:$port/fonts/{fontstack}/{range}.pbf',
      );
      final source = (style['sources'] as Map)['hiker'] as Map;
      expect(source['tiles'], [
        'http://127.0.0.1:$port/vector/{z}/{x}/{y}.pbf',
      ]);
      expect(source['maxzoom'], 14);
      final sources = style['sources'] as Map;
      expect((sources['terrain'] as Map)['tiles'], [
        'http://127.0.0.1:$port/raster/terrain/{z}/{x}/{y}',
      ]);
      expect((sources['slope'] as Map)['tiles'], [
        'http://127.0.0.1:$port/slope/{z}/{x}/{y}.png',
      ]);
      expect(
        (sources['avalanche'] as Map)['data'],
        'http://127.0.0.1:$port/avalanche.geojson',
      );
      // What can be switched travels with the style.
      final options = mapLayerOptions(jsonEncode(style))!;
      expect((options['bases'] as List).length, 2);
      expect(mapLayerOptions(null), isNull);

      // Without network the style seen before is used.
      api.offline = true;
      container.invalidate(mapStyleProvider);
      expect(await container.read(mapStyleProvider.future), isNotNull);
    });

    test('a server without vector map keeps the raster tiles', () async {
      final container = createContainer(
        api: FakeApi(),
        store: MemoryKeyValueStore(signedInStore),
      );
      await container.read(sessionProvider.notifier).restore();

      expect(await container.read(mapStyleProvider.future), isNull);
    });

    test('tiles come from a map on the device, else from the server', () async {
      final upstream = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final asked = <String>[];
      upstream.listen((request) async {
        asked.add(request.uri.path);
        if (request.uri.path.endsWith('/vector/10/538/360.pbf')) {
          request.response.headers.contentType = ContentType(
            'application',
            'x-protobuf',
          );
          request.response.headers.set('content-encoding', 'gzip');
          request.response.add([31, 139, 9, 9]);
        } else if (request.uri.path.contains('/raster/') ||
            request.uri.path.contains('/slope/')) {
          request.response.add([1, 2, 3]);
        } else if (request.uri.path.contains('/fonts/')) {
          request.response.add([7, 7, 7]);
        } else {
          request.response.statusCode = 204;
        }
        await request.response.close();
      });
      addTearDown(() => upstream.close(force: true));
      final container = await containerWith(
        () async => {'maps'},
        baseUrl: 'http://127.0.0.1:${upstream.port}',
      );
      final store = container.read(mapRegionStoreProvider);
      writeMap(
        '${(await store.directory).path}/switzerland.mbtiles',
        z: 10,
        x: 538,
        y: 359,
      );
      expect((await store.installed()).single.name, 'switzerland');
      await container.read(tileProxyProvider.notifier).start();
      final port = container.read(tileProxyProvider)!;
      final client = HttpClient()..autoUncompress = false;
      addTearDown(client.close);
      Future<(int, List<int>, String?)> get(String path) async {
        final response = await (await client.getUrl(
          Uri.parse('http://127.0.0.1:$port$path'),
        )).close();
        final bytes = await response.expand((chunk) => chunk).toList();
        return (
          response.statusCode,
          bytes,
          response.headers.value('content-encoding'),
        );
      }

      // On the device: the server is not asked.
      final r1 = await get('/vector/10/538/359.pbf');
      expect(r1.$1, 200);
      expect(r1.$2, [31, 139, 1, 2]);
      expect(r1.$3, 'gzip');
      expect(asked, isEmpty);
      // Not on the device: from the server, compressed as it is.
      final r2 = await get('/vector/10/538/360.pbf');
      expect(r2.$1, 200);
      expect(r2.$2, [31, 139, 9, 9]);
      expect(r2.$3, 'gzip');
      // The map has nothing there.
      expect((await get('/vector/10/1/1.pbf')).$1, 204);
      expect((await get('/fonts/Noto%20Sans%20Regular/0-255.pbf')).$2, [
        7,
        7,
        7,
      ]);
      expect(asked, [
        '/api/v1/maps/vector/10/538/360.pbf',
        '/api/v1/maps/vector/10/1/1.pbf',
        '/api/v1/maps/fonts/Noto%20Sans%20Regular/0-255.pbf',
      ]);

      // Elevation, aerial images and slope come from the server and are kept too.
      expect((await get('/raster/terrain/12/2153/1436')).$2, [1, 2, 3]);
      expect((await get('/raster/satellite/12/2153/1436')).$2, [1, 2, 3]);
      expect((await get('/slope/12/2153/1436.png')).$2, [1, 2, 3]);
      expect((await get('/contours/12/2153/1436.pbf')).$1, 204);
      expect((await get('/raster/other/12/2153/1436')).$1, 404);
      expect(asked.sublist(3), [
        '/api/v1/maps/raster/terrain/12/2153/1436',
        '/api/v1/maps/raster/satellite/12/2153/1436',
        '/api/v1/maps/slope/12/2153/1436.png',
        '/api/v1/maps/contours/12/2153/1436.pbf',
      ]);
      asked.removeRange(3, asked.length);

      // What was seen stays without network, also "nothing there".
      await upstream.close(force: true);
      expect((await get('/vector/10/538/360.pbf')).$2, [31, 139, 9, 9]);
      expect((await get('/vector/10/1/1.pbf')).$1, 204);
      expect((await get('/fonts/Noto%20Sans%20Regular/0-255.pbf')).$2, [
        7,
        7,
        7,
      ]);
      expect((await get('/vector/10/2/2.pbf')).$1, 502);

      expect((await get('/slope/12/2153/1436.png')).$2, [1, 2, 3]);
      // A removed map no longer answers.
      await store.delete('switzerland');
      expect((await get('/vector/10/538/359.pbf')).$1, 502);
    });
  });

  group('layer choice', () {
    test('base and overlays are chosen independently', () {
      final container = createContainer(api: FakeApi());
      final notifier = container.read(mapLayerChoiceProvider.notifier);

      expect(container.read(mapLayerChoiceProvider), const MapLayerChoice());
      notifier.setOverlay('slope', on: true);
      notifier.setBase('satellite');
      expect(
        container.read(mapLayerChoiceProvider),
        const MapLayerChoice(base: 'satellite', overlays: {'slope'}),
      );
      notifier.setOverlay('slope', on: false);
      expect(container.read(mapLayerChoiceProvider).overlays, isEmpty);
      expect(container.read(mapLayerChoiceProvider).base, 'satellite');
    });
  });
}
