import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../session/session.dart';

/// Adds the access token to every request and renews it once when the server
/// answers 401. If the refresh token is no longer valid the user is signed out.
class AuthInterceptor extends QueuedInterceptor {
  AuthInterceptor({
    required this.readSession,
    required this.onTokens,
    required this.onSessionExpired,
    required this.plainDio,
  });

  final SessionState Function() readSession;
  final Future<void> Function(Tokens tokens) onTokens;
  final Future<void> Function() onSessionExpired;

  /// Without this interceptor; used for the refresh call and the retry.
  final Dio plainDio;

  static const _retried = 'auth_retried';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final tokens = readSession().tokens;
    if (tokens != null && !_isAuthPath(options.path)) {
      options.headers['Authorization'] = 'Bearer ${tokens.access}';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final options = err.requestOptions;
    final tokens = readSession().tokens;
    final canRenew =
        err.response?.statusCode == 401 &&
        tokens != null &&
        !_isAuthPath(options.path) &&
        options.extra[_retried] != true;
    if (!canRenew) return handler.next(err);

    final Tokens renewed;
    try {
      final response = await plainDio.post<Map<String, dynamic>>(
        '${options.baseUrl}/auth/refresh',
        data: {'refresh_token': tokens.refresh},
      );
      renewed = Tokens(
        access: response.data!['access_token'] as String,
        refresh: response.data!['refresh_token'] as String,
      );
    } on DioException catch (refreshError) {
      // Only a rejected refresh token ends the session; without network the
      // user stays signed in and can keep working offline.
      if (refreshError.response != null) await onSessionExpired();
      return handler.next(err);
    }
    await onTokens(renewed);
    try {
      options.extra[_retried] = true;
      options.headers['Authorization'] = 'Bearer ${renewed.access}';
      handler.resolve(await plainDio.fetch<dynamic>(options));
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  bool _isAuthPath(String path) => path.startsWith('/auth/');
}

/// Used until a server address is known; requests to it fail as network errors.
const _noServer = 'http://server.invalid';

BaseOptions _options(String baseUrl) => BaseOptions(
  baseUrl: '${baseUrl.isEmpty ? _noServer : baseUrl}${AppConfig.apiPrefix}',
  connectTimeout: const Duration(seconds: 10),
  receiveTimeout: const Duration(seconds: 30),
  contentType: Headers.jsonContentType,
);

/// Replaceable in tests to answer requests without a server.
final httpClientAdapterProvider = Provider<HttpClientAdapter?>((ref) => null);

/// The HTTP client for the API of the server the user is signed in to.
final dioProvider = Provider<Dio>((ref) {
  final baseUrl = ref.watch(sessionProvider.select((s) => s.baseUrl));
  final adapter = ref.watch(httpClientAdapterProvider);
  final session = ref.read(sessionProvider.notifier);

  final plain = Dio(_options(baseUrl));
  final dio = Dio(_options(baseUrl));
  if (adapter != null) {
    plain.httpClientAdapter = adapter;
    dio.httpClientAdapter = adapter;
  }
  dio.interceptors.add(
    AuthInterceptor(
      readSession: () => ref.read(sessionProvider),
      onTokens: session.updateTokens,
      onSessionExpired: session.signOut,
      plainDio: plain,
    ),
  );
  ref.onDispose(() {
    dio.close();
    plain.close();
  });
  return dio;
});
