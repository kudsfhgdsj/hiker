import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/network/api_client.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';

import '../helpers.dart';

Future<ProviderContainer> signedIn(FakeApi api) async {
  final container = createContainer(
    api: api,
    store: MemoryKeyValueStore(signedInStore),
  );
  await container.read(sessionProvider.notifier).restore();
  return container;
}

void main() {
  test('requests go to the stored server with the access token', () async {
    final api = FakeApi({'GET /me': (_, _) => ok(userJson)});
    final container = await signedIn(api);

    final response = await container
        .read(dioProvider)
        .get<Map<String, dynamic>>('/me');

    expect(
      response.requestOptions.uri.toString(),
      'https://hiker.test/api/v1/me',
    );
    expect(api.calls.single.headers['Authorization'], 'Bearer access-1');
    expect(response.data!['email'], 'anna@example.org');
  });

  test('auth endpoints are called without a token', () async {
    final api = FakeApi({'POST /auth/login': (_, _) => ok(authJson())});
    final container = await signedIn(api);

    await container.read(dioProvider).post<dynamic>('/auth/login', data: {});

    expect(api.calls.single.headers.containsKey('Authorization'), isFalse);
  });

  test(
    'an expired access token is renewed once and the request repeated',
    () async {
      final api = FakeApi();
      api.routes['GET /me'] = (request, _) =>
          request.headers['Authorization'] == 'Bearer access-2'
          ? ok(userJson)
          : apiError(401, 'invalid_token');
      api.routes['POST /auth/refresh'] = (_, body) {
        expect(body, {'refresh_token': 'refresh-1'});
        return ok({'access_token': 'access-2', 'refresh_token': 'refresh-2'});
      };
      final container = await signedIn(api);

      final response = await container
          .read(dioProvider)
          .get<Map<String, dynamic>>('/me');

      expect(response.statusCode, 200);
      expect(api.requested, ['GET /me', 'POST /auth/refresh', 'GET /me']);
      final session = container.read(sessionProvider);
      expect(session.tokens!.access, 'access-2');
      expect(session.tokens!.refresh, 'refresh-2');
      expect(session.isSignedIn, isTrue);
    },
  );

  test('a rejected refresh token signs the user out', () async {
    final api = FakeApi({
      'GET /me': (_, _) => apiError(401, 'invalid_token'),
      'POST /auth/refresh': (_, _) => apiError(401, 'invalid_refresh_token'),
    });
    final container = await signedIn(api);

    await expectLater(
      apiCall(() => container.read(dioProvider).get<dynamic>('/me')),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', 'invalid_token'),
      ),
    );

    expect(container.read(sessionProvider).status, SessionStatus.signedOut);
  });

  test('a still failing request is not retried again', () async {
    final api = FakeApi({
      'GET /me': (_, _) => apiError(401, 'invalid_token'),
      'POST /auth/refresh': (_, _) =>
          ok({'access_token': 'access-2', 'refresh_token': 'refresh-2'}),
    });
    final container = await signedIn(api);

    await expectLater(
      container.read(dioProvider).get<dynamic>('/me'),
      throwsA(isA<DioException>()),
    );

    expect(api.requested, ['GET /me', 'POST /auth/refresh', 'GET /me']);
  });

  test('without network the user stays signed in', () async {
    final api = FakeApi()..offline = true;
    final container = await signedIn(api);

    await expectLater(
      apiCall(() => container.read(dioProvider).get<dynamic>('/me')),
      throwsA(
        isA<ApiException>().having((e) => e.code, 'code', ApiException.network),
      ),
    );

    expect(container.read(sessionProvider).isSignedIn, isTrue);
  });

  test('error answers are parsed into code, message and body', () async {
    final api = FakeApi({
      'PUT /tours/1': (_, _) => (
        status: 409,
        body: {
          'error': {'code': 'version_conflict', 'message': 'changed'},
          'current': {'version': 3},
        },
      ),
      'POST /gear/items': (_, _) => (status: 422, body: {'detail': []}),
    });
    final dio = (await signedIn(api)).read(dioProvider);

    final conflict = await apiCall(
      () => dio.put<dynamic>('/tours/1'),
    ).then<Object?>((_) => null, onError: (Object e) => e) as ApiException;
    final invalid = await apiCall(
      () => dio.post<dynamic>('/gear/items'),
    ).then<Object?>((_) => null, onError: (Object e) => e) as ApiException;

    expect(conflict.code, 'version_conflict');
    expect(conflict.statusCode, 409);
    expect(conflict.body!['current'], {'version': 3});
    expect(invalid.code, ApiException.validation);
  });
}
