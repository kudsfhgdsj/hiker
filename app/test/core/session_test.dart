import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/config/app_config.dart';
import 'package:hiker/core/router/app_router.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/shared/models/user.dart';

import '../helpers.dart';

void main() {
  test('restore without stored data ends signed out', () async {
    final container = createContainer(api: FakeApi());

    await container.read(sessionProvider.notifier).restore();

    final state = container.read(sessionProvider);
    expect(state.status, SessionStatus.signedOut);
    expect(state.user, isNull);
  });

  test('sign in is persisted and restored, sign out removes it', () async {
    final store = MemoryKeyValueStore();
    final first = createContainer(api: FakeApi(), store: store);
    final session = first.read(sessionProvider.notifier);
    await session.setBaseUrl('https://hiker.test');
    await session.signIn(
      const Tokens(access: 'a', refresh: 'r'),
      User.fromJson(userJson),
    );

    final second = createContainer(api: FakeApi(), store: store);
    await second.read(sessionProvider.notifier).restore();

    final restored = second.read(sessionProvider);
    expect(restored.isSignedIn, isTrue);
    expect(restored.baseUrl, 'https://hiker.test');
    expect(restored.tokens!.refresh, 'r');
    expect(restored.user!.displayName, 'Anna');

    await second.read(sessionProvider.notifier).signOut();

    expect(second.read(sessionProvider).status, SessionStatus.signedOut);
    expect(store.values.keys, ['base_url']);
  });

  test('server address is normalised or rejected', () {
    expect(normalizeBaseUrl(' https://hiker.test/ '), 'https://hiker.test');
    expect(normalizeBaseUrl('http://10.0.2.2:8010'), 'http://10.0.2.2:8010');
    expect(normalizeBaseUrl('hiker.test'), isNull);
    expect(normalizeBaseUrl('ftp://hiker.test'), isNull);
    expect(normalizeBaseUrl(''), isNull);
  });

  test('redirects follow the session state', () {
    const home = '/gear';
    expect(redirectFor(SessionStatus.unknown, '/gear', home), '/');
    expect(redirectFor(SessionStatus.unknown, '/', home), isNull);
    expect(redirectFor(SessionStatus.signedOut, '/gear', home), '/login');
    expect(redirectFor(SessionStatus.signedOut, '/register', home), isNull);
    expect(redirectFor(SessionStatus.signedIn, '/login', home), home);
    expect(redirectFor(SessionStatus.signedIn, '/', home), home);
    expect(redirectFor(SessionStatus.signedIn, '/profile', home), isNull);
  });
}
