import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';

/// Hands map tiles of the user's server to the map.
///
/// The map is drawn by a native library with its own network code, which knows
/// nothing about a self-signed certificate the user chose to trust in the app.
/// For such a server the map asks this small server on the loopback address
/// instead; it fetches the tile over the connection the app trusts.
class TileProxy extends Notifier<int?> {
  static final _tilePath = RegExp(r'^/(\d{1,2})/(\d{1,7})/(\d{1,7})\.png$');

  HttpServer? _server;
  HttpClient? _client;

  /// The port it listens on, or null while it is not running.
  @override
  int? build() {
    ref.onDispose(stop);
    return null;
  }

  Future<void> start() async {
    if (_server != null) return;
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
      final trusted = ref.read(trustedCertificatesProvider.notifier);
      final client = _client ??= HttpClient()
        ..badCertificateCallback = trusted.accepts
        ..connectionTimeout = const Duration(seconds: 10);
      final path = AppConfig.serverTilePath
          .replaceFirst('{z}', tile[1]!)
          .replaceFirst('{x}', tile[2]!)
          .replaceFirst('{y}', tile[3]!);
      final upstream = await (await client.getUrl(Uri.parse('$baseUrl$path')))
          .close();
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

/// False in tests, which have no network.
final tileProxyEnabledProvider = Provider<bool>((ref) => true);
