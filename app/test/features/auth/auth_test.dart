import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/session/session.dart';
import 'package:hiker/core/storage/key_value_store.dart';
import 'package:hiker/features/auth/data/auth_repository.dart';

import '../../helpers.dart';

const fullProfile = {
  'weight_kg': 72.5,
  'birth_year': 1988,
  'sex': 'female',
  'max_heart_rate': 186,
  'resting_heart_rate': 52,
};

void main() {
  group('AuthRepository', () {
    test('login returns tokens and user', () async {
      final api = FakeApi({'POST /auth/login': (_, _) => ok(authJson())});
      final container = createContainer(api: api);

      final result = await container
          .read(authRepositoryProvider)
          .login(email: 'anna@example.org', password: 'secret-password');

      expect(api.calls.single.body, {
        'email': 'anna@example.org',
        'password': 'secret-password',
      });
      expect(result.tokens.refresh, 'refresh-1');
      expect(result.user.displayName, 'Anna');
    });

    test('errors carry the code of the server', () async {
      final api = FakeApi({
        'POST /auth/login': (_, _) => apiError(401, 'invalid_credentials'),
      });
      final repository = createContainer(api: api).read(authRepositoryProvider);

      expect(
        repository.login(email: 'a@b.ch', password: 'x'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'invalid_credentials',
          ),
        ),
      );
    });

    test('profile round trip keeps empty fields empty', () async {
      Object? sent;
      final api = FakeApi({
        'GET /me/profile': (_, _) => ok({...fullProfile, 'sex': null}),
        'PUT /me/profile': (_, body) {
          sent = body;
          return ok(body);
        },
      });
      final repository = createContainer(api: api).read(authRepositoryProvider);

      final profile = await repository.fetchProfile();
      await repository.saveProfile(profile);

      expect(profile.weightKg, 72.5);
      expect(profile.sex, isNull);
      expect(sent, {...fullProfile, 'sex': null});
    });

    test('logout ignores a server that cannot be reached', () async {
      final repository = createContainer(api: FakeApi()..offline = true)
          .read(authRepositoryProvider);

      await repository.logout('refresh-1');
    });
  });

  group('login screen', () {
    testWidgets('validates the input before asking the server', (tester) async {
      final api = FakeApi();
      await pumpApp(tester, api: api);

      expect(find.text('Anmelden'), findsWidgets);
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();

      expect(
        find.text('Bitte eine Adresse mit http:// oder https:// eingeben'),
        findsOneWidget,
      );
      expect(
        find.text('Bitte eine gültige E-Mail-Adresse eingeben'),
        findsOneWidget,
      );
      expect(find.text('Pflichtfeld'), findsOneWidget);
      expect(api.calls, isEmpty);
    });

    testWidgets('signs in and opens the app', (tester) async {
      final api = FakeApi({
        'POST /auth/login': (_, _) => ok(authJson()),
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      });
      final store = MemoryKeyValueStore();
      final container = await pumpApp(tester, api: api, store: store);

      await tester.enterText(field('Server-Adresse'), 'https://hiker.test/');
      await tester.enterText(field('E-Mail'), ' anna@example.org ');
      await tester.enterText(field('Passwort'), 'correct-horse-battery');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();

      expect(api.calls.first.body, {
        'email': 'anna@example.org',
        'password': 'correct-horse-battery',
      });
      expect(container.read(sessionProvider).isSignedIn, isTrue);
      expect(store.values['base_url'], 'https://hiker.test');
      expect(store.values['refresh_token'], 'refresh-1');
      expect(find.text('Angemeldet als Anna'), findsOneWidget);
    });

    testWidgets('shows a German message for wrong credentials', (tester) async {
      final api = FakeApi({
        'POST /auth/login': (_, _) => apiError(401, 'invalid_credentials'),
      });
      final container = await pumpApp(tester, api: api);

      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Passwort'), 'wrong');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();

      expect(find.text('E-Mail oder Passwort ist falsch.'), findsOneWidget);
      expect(container.read(sessionProvider).isSignedIn, isFalse);
    });

    testWidgets('shows a message when the server cannot be reached', (
      tester,
    ) async {
      await pumpApp(tester, api: FakeApi()..offline = true);

      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Passwort'), 'whatever');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('Der Server ist nicht erreichbar'),
        findsOneWidget,
      );
    });
  });

  group('registration', () {
    testWidgets('creates an account', (tester) async {
      final api = FakeApi({
        'POST /auth/register': (_, _) => ok(authJson(), 201),
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      });
      final container = await pumpApp(tester, api: api);

      await tester.tap(find.text('Noch kein Konto? Konto anlegen'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Anzeigename'), 'Anna');
      await tester.enterText(field('Passwort'), 'short');
      await tester.tap(find.widgetWithText(FilledButton, 'Konto anlegen'));
      await tester.pumpAndSettle();
      expect(find.text('Mindestens 10 Zeichen'), findsOneWidget);
      expect(api.calls, isEmpty);

      await tester.enterText(field('Passwort'), 'correct-horse-battery');
      await tester.tap(find.widgetWithText(FilledButton, 'Konto anlegen'));
      await tester.pumpAndSettle();

      expect(api.calls.first.body, {
        'email': 'anna@example.org',
        'display_name': 'Anna',
        'password': 'correct-horse-battery',
      });
      expect(container.read(sessionProvider).isSignedIn, isTrue);
    });

    testWidgets('explains a closed registration', (tester) async {
      final api = FakeApi({
        'POST /auth/register': (_, _) => apiError(403, 'registration_closed'),
      });
      await pumpApp(tester, api: api);

      await tester.tap(find.text('Noch kein Konto? Konto anlegen'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Anzeigename'), 'Anna');
      await tester.enterText(field('Passwort'), 'correct-horse-battery');
      await tester.tap(find.widgetWithText(FilledButton, 'Konto anlegen'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Auf diesem Server können keine neuen Konten angelegt werden.',
        ),
        findsOneWidget,
      );
    });
  });

  group('profile screen', () {
    FakeApi profileApi(List<Object?> saved) => FakeApi({
      'GET /modules': (_, _) => ok([]),
      'GET /me/profile': (_, _) => ok(fullProfile),
      'PUT /me/profile': (_, body) {
        saved.add(body);
        return ok(body);
      },
      'POST /auth/logout': (_, _) => ok(null, 204),
    });

    testWidgets('shows the stored values and saves changes', (tester) async {
      final saved = <Object?>[];
      await pumpApp(
        tester,
        api: profileApi(saved),
        store: MemoryKeyValueStore(signedInStore),
      );

      expect(find.text('72.5'), findsOneWidget);
      expect(find.text('1988'), findsOneWidget);
      expect(find.text('weiblich'), findsOneWidget);

      await tester.enterText(field('Gewicht (kg)'), '70,5');
      await tester.enterText(field('Ruheherzfrequenz'), '');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      expect(saved.single, {
        ...fullProfile,
        'weight_kg': 70.5,
        'resting_heart_rate': null,
      });
      expect(find.text('Gespeichert'), findsOneWidget);
    });

    testWidgets('rejects values outside the allowed range', (tester) async {
      final saved = <Object?>[];
      await pumpApp(
        tester,
        api: profileApi(saved),
        store: MemoryKeyValueStore(signedInStore),
      );

      await tester.enterText(field('Gewicht (kg)'), '5');
      await tester.enterText(field('Geburtsjahr'), '1800');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Speichern'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Speichern'));
      await tester.pumpAndSettle();

      expect(find.text('Bitte eine gültige Zahl eingeben'), findsNWidgets(2));
      expect(saved, isEmpty);
    });

    testWidgets('logout revokes the token and returns to the login', (
      tester,
    ) async {
      final api = profileApi([]);
      final store = MemoryKeyValueStore(signedInStore);
      final container = await pumpApp(tester, api: api, store: store);

      await tester.tap(find.text('Abmelden'));
      await tester.pumpAndSettle();

      expect(api.calls.last.path, '/auth/logout');
      expect(api.calls.last.body, {'refresh_token': 'refresh-1'});
      expect(container.read(sessionProvider).status, SessionStatus.signedOut);
      expect(store.values.keys, ['base_url']);
      expect(find.widgetWithText(FilledButton, 'Anmelden'), findsOneWidget);
      // The server address is kept for the next login.
      expect(find.text('https://hiker.test'), findsOneWidget);
    });
  });
}
