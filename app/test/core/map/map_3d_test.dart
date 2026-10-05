import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/tile_proxy.dart';

import '../../helpers.dart';

void main() {
  test('the app carries the same map library as the web frontend', () {
    const web = '../web/hiker_web/static/vendor/maplibre-gl';
    for (final name in [
      'maplibre-gl-csp.js',
      'maplibre-gl-csp-worker.js',
      'maplibre-gl.css',
      'LICENSE.txt',
    ]) {
      expect(
        File('assets/map3d/$name').readAsBytesSync(),
        File('$web/$name').readAsBytesSync(),
        reason: name,
      );
    }
    // The page loads nothing from anywhere else.
    final page = File('assets/map3d/index.html').readAsStringSync();
    final script = File('assets/map3d/view.js').readAsStringSync();
    expect(page.contains('http'), isFalse);
    expect(script.contains('https://'), isFalse);
  });

  test(
    'the map server of the app hands out the 3D page and its scene',
    () async {
      final container = createContainer(
        api: FakeApi(),
        overrides: [
          bundledPageProvider.overrideWithValue((name) async {
            final file = File('assets/map3d/$name');
            return file.existsSync() ? file.readAsBytesSync() : null;
          }),
        ],
      );
      final proxy = container.read(tileProxyProvider.notifier);
      await proxy.start();
      final port = container.read(tileProxyProvider)!;
      final client = HttpClient();
      addTearDown(client.close);
      Future<(int, String, String?)> get(String path) async {
        final response = await (await client.getUrl(
          Uri.parse('http://127.0.0.1:$port$path'),
        )).close();
        return (
          response.statusCode,
          await utf8.decodeStream(response),
          response.headers.contentType?.mimeType,
        );
      }

      final page = await get('/3d/index.html');
      expect(page.$1, 200);
      expect(page.$3, 'text/html');
      expect(page.$2, contains('view.js'));
      expect((await get('/3d/view.js')).$3, 'text/javascript');
      expect((await get('/3d/maplibre-gl.css')).$3, 'text/css');
      expect((await get('/3d/maplibre-gl-csp.js')).$1, 200);

      // Nothing to show yet, nothing outside the folder, no other files.
      expect((await get('/3d/scene.json')).$1, 404);
      expect((await get('/3d/missing.js')).$1, 404);
      expect((await get('/3d/../pubspec.yaml')).$1, 404);

      proxy.scene3d = jsonEncode({
        'center': [9.34, 47.25],
        'zoom': 12,
      });
      final scene = await get('/3d/scene.json');
      expect(scene.$3, 'application/json');
      expect((jsonDecode(scene.$2) as Map)['zoom'], 12);
    },
  );
}
