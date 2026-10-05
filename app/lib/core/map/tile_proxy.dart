import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../config/app_config.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';
import 'map_regions.dart';

/// The map server inside the app, on the loopback address.
///
/// The map is drawn by a native library with its own network code. It asks
/// this small server for everything it shows:
///
/// - `/{z}/{x}/{y}.png`: raster tiles of the user's server,
/// - `/vector/{z}/{x}/{y}.pbf`: tiles of the own vector map, first from a map
///   file on the device (see [MapRegionStore]), else from the user's server,
/// - `/fonts/{font}/{range}.pbf`: the glyphs for the labels,
/// - `/raster/{layer}/{z}/{x}/{y}` and `/slope/{z}/{x}/{y}.png`: elevation,
///   aerial images, snow, precipitation and the slope layer of the user's
///   server, and `/avalanche.geojson`, the avalanche danger of today,
/// - `/sprite.json`, `/sprite.png` (and `@2x`): the symbols of the map,
/// - `/3d/…`: the page of the 3D view with its map library and what it shows,
/// - `/radar/frames` and `/radar/{kind}/{time}/{z}/{x}/{y}.png`: rain radar
///   and cloud images with their times.
///
/// `?low=&high=` chooses the angles of the slope layer, `?date=` a day in the
/// past for snow, precipitation, weather and avalanche danger.
///
/// What comes from the server goes over the connection the app trusts (also
/// with a certificate the user confirmed by hand) and is kept as a file. A
/// file seen before is handed out at once and also without network; after
/// [_freshFor] the server is asked again. Only what the user looked at is
/// kept this way; whole regions come as map files the server built itself.
class TileProxy extends Notifier<int?> {
  static final _raster = RegExp(r'^/(\d{1,2})/(\d{1,7})/(\d{1,7})\.png$');
  static final _vector = RegExp(
    r'^/vector/(\d{1,2})/(\d{1,7})/(\d{1,7})\.pbf$',
  );
  static final _contours = RegExp(
    r'^/contours/(\d{1,2})/(\d{1,7})/(\d{1,7})\.pbf$',
  );
  static final _weather = RegExp(
    r'^/weather/(\d{1,2})/(\d{1,7})/(\d{1,7})\.pbf$',
  );
  static final _glyphs = RegExp(
    r'^/fonts/([\w ,%-]{1,200})/(\d{1,5}-\d{1,5})\.pbf$',
  );
  static final _layer = RegExp(
    r'^/raster/(terrain|satellite|snow|precipitation)/(\d{1,2})/(\d{1,7})/(\d{1,7})$',
  );
  static final _slope = RegExp(r'^/slope/(\d{1,2})/(\d{1,7})/(\d{1,7})\.png$');
  static final _radar = RegExp(
    r'^/radar/(rain|clouds)/(\d{1,12})/(\d{1,2})/(\d{1,7})/(\d{1,7})\.png$',
  );
  static final _day = RegExp(r'^\d{4}-\d{2}-\d{2}$');
  static const _freshFor = Duration(days: 7);

  /// Above this size the files not used for the longest time are removed.
  static const _maxCacheBytes = 300 * 1024 * 1024;
  static final _png = ContentType('image', 'png');
  static final _protobuf = ContentType('application', 'x-protobuf');

  HttpServer? _server;
  HttpClient? _client;

  /// What the 3D view shows (style, camera, track), as JSON; the page asks
  /// for it as `/3d/scene.json`.
  String? scene3d;

  static const _pageTypes = {
    'html': 'text/html',
    'js': 'text/javascript',
    'css': 'text/css',
    'json': 'application/json',
  };
  static final _sprite = RegExp(r'^/sprite(@[23]x)?\.(json|png)$');
  static final _page = RegExp(r'^/3d/([a-z0-9-]+)\.(html|js|css|json)$');

  /// The port it listens on, or null while it is not running.
  @override
  int? build() {
    ref.onDispose(stop);
    return null;
  }

  Future<File?> _cacheFile(String name) async {
    try {
      final folder = await ref.read(tileCacheDirectoryProvider.future);
      return File('${folder.path}/$name');
    } on Object {
      // No place to keep files: the map still works with the server.
      return null;
    }
  }

  /// Removes the files used least recently once the cache is too large.
  Future<void> _prune() async {
    try {
      final folder = await ref.read(tileCacheDirectoryProvider.future);
      if (!folder.existsSync()) return;
      final files = folder.listSync(recursive: true).whereType<File>().toList();
      var total = files.fold<int>(0, (sum, file) => sum + file.lengthSync());
      if (total <= _maxCacheBytes) return;
      files.sort(
        (a, b) => a.lastAccessedSync().compareTo(b.lastAccessedSync()),
      );
      for (final file in files) {
        if (total <= _maxCacheBytes * 0.8) break;
        total -= file.lengthSync();
        file.deleteSync();
      }
    } on Object {
      // Housekeeping must never get in the way of the map.
    }
  }

  /// Starting twice at the same time must not open two servers.
  Future<void>? _starting;

  Future<void> start() => _starting ??= _start();

  Future<void> _start() async {
    unawaited(_prune());
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    _server = server;
    state = server.port;
    unawaited(server.forEach(_answer));
  }

  Future<void> stop() async {
    await _server?.close(force: true);
    _client?.close(force: true);
    _server = null;
    _client = null;
    _starting = null;
  }

  /// Hands out a file of the server, from the device if it is known there.
  /// [gzipped]: the server sends the data compressed and it is kept that way.
  Future<void> _fromServer(
    HttpResponse response, {
    required String apiPath,
    required String cacheName,
    required ContentType type,
    bool gzipped = false,
    Duration freshFor = _freshFor,
  }) async {
    final baseUrl = ref.read(sessionProvider).baseUrl;
    final cached = await _cacheFile(cacheName);
    final known = cached != null && cached.existsSync();
    void send(List<int> bytes) {
      response.statusCode = bytes.isEmpty && gzipped
          ? HttpStatus.noContent
          : HttpStatus.ok;
      response.headers.contentType = type;
      if (gzipped && bytes.isNotEmpty) {
        response.headers.set(HttpHeaders.contentEncodingHeader, 'gzip');
      }
      response.add(bytes);
    }

    if (known &&
        DateTime.now().difference(cached.lastModifiedSync()) < freshFor) {
      send(cached.readAsBytesSync());
      return;
    }
    if (baseUrl.isEmpty) {
      response.statusCode = HttpStatus.notFound;
      return;
    }
    final trusted = ref.read(trustedCertificatesProvider.notifier);
    final client = _client ??= HttpClient()
      ..badCertificateCallback = trusted.accepts
      ..connectionTimeout = const Duration(seconds: 10)
      // Compressed tiles are passed on as they are.
      ..autoUncompress = false;
    final HttpClientResponse upstream;
    try {
      final request = await client.getUrl(Uri.parse('$baseUrl$apiPath'));
      // Tiles are stored compressed and passed on that way; everything else
      // must arrive as it is, or a proxy on the way would compress it.
      request.headers.set(
        HttpHeaders.acceptEncodingHeader,
        gzipped ? 'gzip' : 'identity',
      );
      upstream = await request.close();
    } on Exception {
      // No network: an older copy is better than no map.
      if (!known) rethrow;
      send(cached.readAsBytesSync());
      return;
    }
    final ok = upstream.statusCode == HttpStatus.ok;
    if (ok || upstream.statusCode == HttpStatus.noContent) {
      // "No content" (the map has nothing there) is remembered as an empty file.
      final bytes = await upstream.fold<List<int>>(
        [],
        (all, chunk) => all..addAll(chunk),
      );
      try {
        cached?.parent.createSync(recursive: true);
        cached?.writeAsBytesSync(bytes, flush: true);
      } on FileSystemException {
        // A full disk must not hide what just arrived.
      }
      final caching = upstream.headers.value(HttpHeaders.cacheControlHeader);
      if (caching != null) {
        response.headers.set(HttpHeaders.cacheControlHeader, caching);
      }
      send(bytes);
      return;
    }
    await upstream.drain<void>();
    if (upstream.statusCode >= 500 && known) {
      send(cached.readAsBytesSync());
      return;
    }
    response.statusCode = upstream.statusCode;
  }

  /// Answers from a layer pack on the device, if one has the tile; the zoom
  /// level is group [first] of the match, followed by column and row.
  Future<bool> _fromPack(
    HttpResponse response,
    String layer,
    RegExpMatch match,
    int first,
    ContentType type, {
    bool gzipped = false,
  }) async {
    final data = await ref
        .read(mapRegionStoreProvider)
        .layerTile(
          layer,
          int.parse(match[first]!),
          int.parse(match[first + 1]!),
          int.parse(match[first + 2]!),
        );
    if (data == null) return false;
    response.statusCode = HttpStatus.ok;
    response.headers.contentType = type;
    if (gzipped) {
      response.headers.set(HttpHeaders.contentEncodingHeader, 'gzip');
    }
    response.add(data);
    return true;
  }

  Future<void> _answer(HttpRequest request) async {
    final response = request.response;
    final path = request.uri.path;
    final query = request.uri.queryParameters;
    // A day in the past, for the layers that have a history. Such a day does
    // not change any more, so its files stay fresh.
    final day = _day.hasMatch(query['date'] ?? '') ? query['date'] : null;
    final dated = day == null ? '' : '?date=$day';
    final dayFolder = day == null ? '' : '@$day/';
    try {
      if (request.method != 'GET') {
        response.statusCode = HttpStatus.notFound;
        return;
      }
      if (_page.firstMatch(path) case final page?) {
        // The page of the 3D view and its map library come with the app.
        final List<int>? body = path == '/3d/scene.json'
            ? switch (scene3d) {
                final scene? => utf8.encode(scene),
                null => null,
              }
            : await ref.read(bundledPageProvider)('${page[1]}.${page[2]}');
        if (body == null) {
          response.statusCode = HttpStatus.notFound;
          return;
        }
        response.statusCode = HttpStatus.ok;
        response.headers.set(
          HttpHeaders.contentTypeHeader,
          '${_pageTypes[page[2]]}; charset=utf-8',
        );
        response.headers.set(HttpHeaders.cacheControlHeader, 'no-store');
        response.add(body);
        return;
      }
      if (_sprite.firstMatch(path) case final sprite?) {
        // The symbols of the map come with the app, like its fonts: single
        // resolution or double (also for screens that ask for the triple one).
        final name = 'sprite${sprite[1] == null ? '' : '@2x'}.${sprite[2]}';
        final bundled = await ref.read(bundledSpriteProvider)(name);
        if (bundled != null) {
          response.statusCode = HttpStatus.ok;
          response.headers.contentType = sprite[2] == 'png'
              ? _png
              : ContentType.json;
          response.add(bundled);
          return;
        }
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/$name',
          cacheName: 'sprite/$name',
          type: sprite[2] == 'png' ? _png : ContentType.json,
        );
        return;
      }
      final raster = _raster.firstMatch(path);
      final vector = _vector.firstMatch(path);
      final glyphs = _glyphs.firstMatch(path);
      if (raster != null) {
        await _fromServer(
          response,
          apiPath: AppConfig.serverTilePath
              .replaceFirst('{z}', raster[1]!)
              .replaceFirst('{x}', raster[2]!)
              .replaceFirst('{y}', raster[3]!),
          cacheName: '${raster[1]}/${raster[2]}/${raster[3]}.png',
          type: _png,
        );
      } else if (vector != null) {
        final z = int.parse(vector[1]!);
        final x = int.parse(vector[2]!);
        final y = int.parse(vector[3]!);
        // A map file on the device answers first: no network needed.
        final local = await ref.read(mapRegionStoreProvider).tile(z, x, y);
        if (local != null) {
          response.statusCode = HttpStatus.ok;
          response.headers.contentType = _protobuf;
          response.headers.set(HttpHeaders.contentEncodingHeader, 'gzip');
          response.add(local);
          return;
        }
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/vector/$z/$x/$y.pbf',
          cacheName: 'vector/$z/$x/$y.pbf',
          type: _protobuf,
          gzipped: true,
        );
      } else if (glyphs != null) {
        final font = Uri.decodeComponent(glyphs[1]!);
        // The fonts of the map come with the app: names never need the network.
        final bundled = await ref.read(bundledGlyphsProvider)(
          font.split(',').first,
          glyphs[2]!,
        );
        if (bundled != null) {
          response.statusCode = HttpStatus.ok;
          response.headers.contentType = _protobuf;
          response.add(bundled);
          return;
        }
        await _fromServer(
          response,
          apiPath:
              '/api/v1/maps/fonts/${Uri.encodeComponent(font)}/${glyphs[2]}.pbf',
          cacheName:
              'fonts/${font.replaceAll(RegExp(r'[^\w ,-]'), '_')}/${glyphs[2]}.pbf',
          type: _protobuf,
        );
      } else if (_layer.firstMatch(path) case final layer?) {
        final tile = '${layer[2]}/${layer[3]}/${layer[4]}';
        if (layer[1] == 'terrain' &&
            await _fromPack(response, 'terrain', layer, 2, _png)) {
          return;
        }
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/raster/${layer[1]}/$tile$dated',
          cacheName: 'raster/${layer[1]}/$dayFolder$tile',
          type: layer[1] == 'satellite' ? ContentType('image', 'jpeg') : _png,
          // Snow and precipitation of today change within hours.
          freshFor: switch (layer[1]) {
            'snow' when day == null => const Duration(hours: 6),
            'precipitation' when day == null => const Duration(minutes: 30),
            _ => _freshFor,
          },
        );
      } else if (path == '/avalanche.geojson') {
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/avalanche.geojson$dated',
          cacheName: '${dayFolder}avalanche.geojson',
          type: ContentType('application', 'geo+json'),
          // The bulletins change during the day; an old one is still shown offline.
          freshFor: day == null ? const Duration(minutes: 30) : _freshFor,
        );
      } else if (_contours.firstMatch(path) case final lines?) {
        final tile = '${lines[1]}/${lines[2]}/${lines[3]}.pbf';
        if (await _fromPack(
          response,
          'contours',
          lines,
          1,
          _protobuf,
          gzipped: true,
        )) {
          return;
        }
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/contours/$tile',
          cacheName: 'contours/$tile',
          type: _protobuf,
          gzipped: true,
        );
      } else if (_weather.firstMatch(path) case final forecast?) {
        final tile = '${forecast[1]}/${forecast[2]}/${forecast[3]}.pbf';
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/weather/$tile$dated',
          cacheName: 'weather/$dayFolder$tile',
          type: _protobuf,
          gzipped: true,
          // A forecast ages quickly; without network the last one is still shown.
          freshFor: day == null ? const Duration(hours: 1) : _freshFor,
        );
      } else if (_slope.firstMatch(path) case final slope?) {
        final tile = '${slope[1]}/${slope[2]}/${slope[3]}.png';
        // Angles chosen by the user: the layer pack only has the usual ones.
        final low = int.tryParse(query['low'] ?? '');
        final high = int.tryParse(query['high'] ?? '');
        final own = low != null && high != null;
        if (!own && await _fromPack(response, 'slope', slope, 1, _png)) return;
        await _fromServer(
          response,
          apiPath:
              '/api/v1/maps/slope/$tile${own ? '?low=$low&high=$high' : ''}',
          cacheName: 'slope/${own ? '$low-$high/' : ''}$tile',
          type: _png,
        );
      } else if (path == '/radar/frames') {
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/radar/frames',
          cacheName: 'radar/frames.json',
          type: ContentType.json,
          freshFor: const Duration(minutes: 2),
        );
      } else if (_radar.firstMatch(path) case final image?) {
        final tile =
            '${image[1]}/${image[2]}/${image[3]}/${image[4]}/${image[5]}.png';
        await _fromServer(
          response,
          apiPath: '/api/v1/maps/radar/$tile',
          cacheName: 'radar/$tile',
          type: _png,
        );
      } else {
        response.statusCode = HttpStatus.notFound;
      }
    } on Exception {
      response.statusCode = HttpStatus.badGateway;
    } finally {
      await response.close().catchError((_) {});
    }
  }
}

final tileProxyProvider = NotifierProvider<TileProxy, int?>(TileProxy.new);

/// Where the proxy keeps what it handed out; tests use a temporary folder.
final tileCacheDirectoryProvider = FutureProvider<Directory>((ref) async {
  final cache = await getApplicationCacheDirectory();
  return Directory('${cache.path}/map-tiles');
});

/// Reads a glyph file that comes with the app ("Noto Sans Regular", "0-255");
/// null if the app has none for that font or range.
typedef BundledGlyphs = Future<List<int>?> Function(String font, String range);

final bundledGlyphsProvider = Provider<BundledGlyphs>(
  (ref) => (font, range) async {
    final folder = font.toLowerCase().replaceAll(' ', '-');
    try {
      final data = await rootBundle.load('assets/fonts/$folder/$range.pbf');
      return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    } on Object {
      return null;
    }
  },
);

/// Reads a file of the map's symbols that comes with the app
/// (`assets/sprite/`); null if there is none of that name.
final bundledSpriteProvider =
    Provider<Future<List<int>?> Function(String name)>(
      (ref) => (name) async {
        try {
          final data = await rootBundle.load('assets/sprite/$name');
          return data.buffer.asUint8List(
            data.offsetInBytes,
            data.lengthInBytes,
          );
        } on Object {
          return null;
        }
      },
    );

/// Reads a file of the 3D view that comes with the app (`assets/map3d/`);
/// null if there is none of that name.
final bundledPageProvider = Provider<Future<List<int>?> Function(String name)>(
  (ref) => (name) async {
    try {
      final data = await rootBundle.load('assets/map3d/$name');
      return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    } on Object {
      return null;
    }
  },
);

/// False in tests, which have no network.
final tileProxyEnabledProvider = Provider<bool>((ref) => true);
