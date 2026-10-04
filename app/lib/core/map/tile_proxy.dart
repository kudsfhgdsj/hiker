import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../config/app_config.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';

/// Hands map tiles of the user's server to the map.
///
/// The map is drawn by a native library with its own network code, which knows
/// nothing about a self-signed certificate the user chose to trust in the app.
/// For such a server the map asks this small server on the loopback address
/// instead; it fetches the tile over the connection the app trusts.
///
/// It keeps every tile it handed out as a file. A tile seen before is shown at
/// once and also without network; after [_freshFor] the server is asked again.
/// Only tiles the user looked at are kept, never tiles in advance.
class TileProxy extends Notifier<int?> {
  static const _freshFor = Duration(days: 7);

  /// Above this size the tiles not used for the longest time are removed.
  static const _maxCacheBytes = 300 * 1024 * 1024;

  static final _tilePath = RegExp(r'^/(\d{1,2})/(\d{1,7})/(\d{1,7})\.png$');

  HttpServer? _server;
  HttpClient? _client;

  /// The port it listens on, or null while it is not running.
  @override
  int? build() {
    ref.onDispose(stop);
    return null;
  }

  Future<File?> _cached(RegExpMatch tile) async {
    try {
      final folder = await ref.read(tileCacheDirectoryProvider.future);
      return File('${folder.path}/${tile[1]}/${tile[2]}/${tile[3]}.png');
    } on Object {
      // No place to keep tiles: the map still works with the server.
      return null;
    }
  }

  /// Removes the tiles used least recently once the cache is too large.
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

  Future<void> start() async {
    if (_server != null) return;
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
  }

  Future<void> _answer(HttpRequest request) async {
    final response = request.response;
    final tile = _tilePath.firstMatch(request.uri.path);
    final baseUrl = ref.read(sessionProvider).baseUrl;
    try {
      if (request.method != 'GET' || tile == null || baseUrl.isEmpty) {
        response.statusCode = HttpStatus.notFound;
        return;
      }
      final cached = await _cached(tile);
      final known = cached != null && cached.existsSync();
      void sendCached() {
        response.statusCode = HttpStatus.ok;
        response.headers.contentType = ContentType('image', 'png');
        response.add(cached!.readAsBytesSync());
      }

      if (known &&
          DateTime.now().difference(cached.lastModifiedSync()) < _freshFor) {
        sendCached();
        return;
      }
      final trusted = ref.read(trustedCertificatesProvider.notifier);
      final client = _client ??= HttpClient()
        ..badCertificateCallback = trusted.accepts
        ..connectionTimeout = const Duration(seconds: 10);
      final path = AppConfig.serverTilePath
          .replaceFirst('{z}', tile[1]!)
          .replaceFirst('{x}', tile[2]!)
          .replaceFirst('{y}', tile[3]!);
      final HttpClientResponse upstream;
      try {
        upstream = await (await client.getUrl(Uri.parse('$baseUrl$path')))
            .close();
      } on Exception {
        // No network: an older copy is better than no map.
        if (!known) rethrow;
        sendCached();
        return;
      }
      if (upstream.statusCode == HttpStatus.ok && cached != null) {
        final bytes = await upstream.fold<List<int>>(
          [],
          (all, chunk) => all..addAll(chunk),
        );
        try {
          cached.parent.createSync(recursive: true);
          cached.writeAsBytesSync(bytes, flush: true);
        } on FileSystemException {
          // A full disk must not hide the tile that just arrived.
        }
        response.statusCode = HttpStatus.ok;
        response.headers.contentType =
            upstream.headers.contentType ?? ContentType('image', 'png');
        final caching = upstream.headers.value(HttpHeaders.cacheControlHeader);
        if (caching != null) {
          response.headers.set(HttpHeaders.cacheControlHeader, caching);
        }
        response.add(bytes);
        return;
      }
      if (upstream.statusCode >= 500 && known) {
        await upstream.drain<void>();
        sendCached();
        return;
      }
      response.statusCode = upstream.statusCode;
      response.headers.contentType =
          upstream.headers.contentType ?? ContentType('image', 'png');
      final caching = upstream.headers.value(HttpHeaders.cacheControlHeader);
      if (caching != null) {
        response.headers.set(HttpHeaders.cacheControlHeader, caching);
      }
      await upstream.pipe(response);
    } on Exception {
      response.statusCode = HttpStatus.badGateway;
    } finally {
      await response.close().catchError((_) {});
    }
  }
}

final tileProxyProvider = NotifierProvider<TileProxy, int?>(TileProxy.new);

/// Where the proxy keeps the tiles it handed out; tests use a temporary folder.
final tileCacheDirectoryProvider = FutureProvider<Directory>((ref) async {
  final cache = await getApplicationCacheDirectory();
  return Directory('${cache.path}/map-tiles');
});

/// False in tests, which have no network.
final tileProxyEnabledProvider = Provider<bool>((ref) => true);
