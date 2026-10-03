import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/app.dart';
import 'package:hiker/core/db/app_database.dart';
import 'package:hiker/core/modules/feature_module.dart';
import 'package:hiker/core/network/api_client.dart';
import 'package:hiker/core/storage/key_value_store.dart';

typedef FakeResponse = ({int status, Object? body});
typedef FakeHandler = FakeResponse Function(
  RequestOptions request,
  Object? body,
);

FakeResponse ok(Object? body, [int status = 200]) =>
    (status: status, body: body);

FakeResponse apiError(int status, String code) => (
  status: status,
  body: {
    'error': {'code': code, 'message': code},
  },
);

/// Answers requests from a table of `METHOD /path` → handler, without a server.
class FakeApi implements HttpClientAdapter {
  FakeApi([Map<String, FakeHandler>? routes]) : routes = {...?routes};

  final Map<String, FakeHandler> routes;
  final List<
    ({String method, String path, Object? body, Map<String, dynamic> headers})
  >
  calls = [];
  bool offline = false;

  Iterable<String> get requested => calls.map((c) => '${c.method} ${c.path}');

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.uri.path.replaceFirst('/api/v1', '');
    final data = options.data;
    final body = data is String && data.isNotEmpty ? jsonDecode(data) : data;
    calls.add((
      method: options.method,
      path: path,
      body: body,
      headers: options.headers,
    ));
    if (offline) {
      throw DioException.connectionError(
        requestOptions: options,
        reason: 'offline',
      );
    }
    final handler = routes['${options.method} $path'];
    final response = handler == null
        ? apiError(404, 'not_found')
        : handler(options, body);
    return ResponseBody.fromString(
      response.body == null ? '' : jsonEncode(response.body),
      response.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

const userJson = {
  'id': '11111111-1111-4111-8111-111111111111',
  'email': 'anna@example.org',
  'display_name': 'Anna',
  'role': 'user',
};

const signedInStore = {
  'base_url': 'https://hiker.test',
  'access_token': 'access-1',
  'refresh_token': 'refresh-1',
  'user': '{"id":"11111111-1111-4111-8111-111111111111","email":"anna@example.org","display_name":"Anna","role":"user"}',
};

Map<String, dynamic> authJson({
  String access = 'access-1',
  String refresh = 'refresh-1',
}) => {
  'access_token': access,
  'refresh_token': refresh,
  'token_type': 'bearer',
  'expires_in': 900,
  'user': userJson,
};

/// A container wired like the app, with a fake server and in-memory storage.
ProviderContainer createContainer({
  required FakeApi api,
  MemoryKeyValueStore? store,
  List<Override> overrides = const [],
  List<FeatureModule>? modules,
}) {
  final container = ProviderContainer(
    // Riverpod retries failed providers with a delay; tests want the first answer.
    retry: (_, _) => null,
    overrides: [
      ...appOverrides(modules: modules ?? builtInModules),
      httpClientAdapterProvider.overrideWithValue(api),
      keyValueStoreProvider.overrideWithValue(store ?? MemoryKeyValueStore()),
      appDatabaseProvider.overrideWith((ref) {
        final database = AppDatabase(NativeDatabase.memory());
        ref.onDispose(database.close);
        return database;
      }),
      ...overrides,
    ],
  );
  addTearDown(container.dispose);
  return container;
}

/// Starts the whole app against a fake server.
Future<ProviderContainer> pumpApp(
  WidgetTester tester, {
  required FakeApi api,
  MemoryKeyValueStore? store,
  List<Override> overrides = const [],
  List<FeatureModule>? modules,
  Size size = const Size(400, 800),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final container = createContainer(
    api: api,
    store: store,
    overrides: overrides,
    modules: modules,
  );
  await tester.pumpWidget(
    UncontrolledProviderScope(container: container, child: const HikerApp()),
  );
  await tester.pumpAndSettle();
  return container;
}

Finder field(String label) => find.widgetWithText(TextFormField, label);
