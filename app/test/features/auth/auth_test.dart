import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/network/api_exception.dart';
import 'package:hiker/core/network/trusted_certificates.dart';
import 'package:hiker/core/router/app_router.dart';
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
      Future<void> submit() async {
        final button = find.widgetWithText(FilledButton, 'Konto anlegen');
        await tester.ensureVisible(button);
        await tester.tap(button);
        await tester.pumpAndSettle();
      }

      await tester.enterText(field('Passwort'), 'short');
      await submit();
      expect(find.text('Mindestens 8 Zeichen'), findsOneWidget);

      await tester.enterText(field('Passwort'), 'nurkleinbuchstaben');
      await submit();
      expect(find.textContaining('Zu einfach'), findsOneWidget);

      // The password has to be typed twice.
      await tester.enterText(field('Passwort'), 'Correct-Horse-7');
      await tester.enterText(field('Passwort wiederholen'), 'Correct-Horse-8');
      await submit();
      expect(
        find.text('Die beiden Passwörter stimmen nicht überein'),
        findsOneWidget,
      );
      expect(api.calls, isEmpty);

      await tester.enterText(field('Passwort wiederholen'), 'Correct-Horse-7');
      await submit();

      expect(api.calls.first.body, {
        'email': 'anna@example.org',
        'display_name': 'Anna',
        'password': 'Correct-Horse-7',
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
      await tester.enterText(field('Passwort'), 'Correct-Horse-7');
      await tester.enterText(field('Passwort wiederholen'), 'Correct-Horse-7');
      final button = find.widgetWithText(FilledButton, 'Konto anlegen');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Auf diesem Server können keine neuen Konten angelegt werden.',
        ),
        findsOneWidget,
      );
    });
  });

  group('self-signed certificate', () {
    const fingerprint = 'AB:CD:EF:01';

    testWidgets('is trusted after the user confirmed its fingerprint', (
      tester,
    ) async {
      final api = FakeApi({
        'POST /auth/login': (_, _) => ok(authJson()),
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      })..offline = true;
      final asked = <Uri>[];
      final container = await pumpApp(
        tester,
        api: api,
        certificateProbe: (server) async {
          asked.add(server);
          // Once trusted, the connection works.
          api.offline = false;
          return (
            host: server.host,
            port: 443,
            fingerprint: fingerprint,
            subject: 'CN=hiker.test',
            validUntil: DateTime(2030),
          );
        },
      );

      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Passwort'), 'Correct-Horse-7');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      // The button keeps spinning while the dialog waits for the decision.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      expect(find.text('Unbekanntes Zertifikat'), findsOneWidget);
      expect(find.text(fingerprint), findsOneWidget);
      expect(container.read(sessionProvider).isSignedIn, isFalse);

      await tester.tap(find.widgetWithText(FilledButton, 'Vertrauen'));
      await tester.pumpAndSettle();

      expect(asked.single.host, 'hiker.test');
      expect(container.read(trustedCertificatesProvider), {
        'hiker.test:443': fingerprint,
      });
      expect(container.read(sessionProvider).isSignedIn, isTrue);
    });

    testWidgets('is not trusted if the user declines', (tester) async {
      final api = FakeApi()..offline = true;
      final container = await pumpApp(
        tester,
        api: api,
        certificateProbe: (server) async => (
          host: server.host,
          port: 443,
          fingerprint: fingerprint,
          subject: 'CN=hiker.test',
          validUntil: DateTime(2030),
        ),
      );

      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Passwort'), 'Correct-Horse-7');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      // The button keeps spinning while the dialog waits for the decision.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      await tester.tap(find.widgetWithText(TextButton, 'Abbrechen'));
      await tester.pumpAndSettle();

      expect(container.read(trustedCertificatesProvider), isEmpty);
      expect(
        find.textContaining('Der Server ist nicht erreichbar'),
        findsOneWidget,
      );
    });

    test('decisions are stored and restored per server', () async {
      final store = MemoryKeyValueStore();
      final first = createContainer(api: FakeApi(), store: store);
      await first
          .read(trustedCertificatesProvider.notifier)
          .trust('hiker.test', 8443, fingerprint);

      final second = createContainer(api: FakeApi(), store: store);
      await second.read(trustedCertificatesProvider.notifier).load();

      expect(second.read(trustedCertificatesProvider), {
        'hiker.test:8443': fingerprint,
      });
      await second
          .read(trustedCertificatesProvider.notifier)
          .forget('hiker.test:8443');
      expect(second.read(trustedCertificatesProvider), isEmpty);
    });
  });

  group('second factor and password change', () {
    Future<void> signIn(WidgetTester tester) async {
      await tester.enterText(field('Server-Adresse'), 'https://hiker.test');
      await tester.enterText(field('E-Mail'), 'anna@example.org');
      await tester.enterText(field('Passwort'), 'Correct-Horse-7');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();
    }

    testWidgets('login asks for the code when the account has one', (
      tester,
    ) async {
      final api = FakeApi({
        'POST /auth/login': (_, body) =>
            (body! as Map<String, dynamic>)['code'] == '123456'
            ? ok(authJson())
            : apiError(401, 'mfa_required'),
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      });
      final container = await pumpApp(tester, api: api);

      expect(find.text('Code der Authenticator-App'), findsNothing);
      await signIn(tester);
      expect(
        find.text('Bitte auch den Code der Authenticator-App eingeben.'),
        findsOneWidget,
      );
      await tester.enterText(field('Code der Authenticator-App'), '123456');
      await tester.tap(find.widgetWithText(FilledButton, 'Anmelden'));
      await tester.pumpAndSettle();

      final logins = api.calls.where((c) => c.path == '/auth/login');
      expect((logins.last.body! as Map)['code'], '123456');
      expect(container.read(sessionProvider).isSignedIn, isTrue);
    });

    testWidgets('a session without second factor has to set it up first', (
      tester,
    ) async {
      final api = FakeApi({
        'POST /auth/login': (_, _) =>
            ok({...authJson(), 'mfa_setup_required': true}),
        'POST /auth/mfa/setup': (_, _) => ok({
          'secret': 'JBSWY3DPEHPK3PXP',
          'otpauth_uri': 'otpauth://totp/hiker:anna?secret=JBSWY3DPEHPK3PXP',
        }),
        'POST /auth/mfa/enable': (_, body) =>
            (body! as Map<String, dynamic>)['code'] == '654321'
            ? ok({
                ...authJson(access: 'access-mfa', refresh: 'refresh-mfa'),
                'mfa_setup_required': false,
                'recovery_codes': ['abcde-12345', 'fghij-67890'],
              })
            : apiError(422, 'invalid_mfa_code'),
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      });
      final container = await pumpApp(tester, api: api);

      await signIn(tester);

      expect(find.text('Zweiten Faktor einrichten'), findsOneWidget);
      expect(find.textContaining('zweiter Faktor Pflicht'), findsOneWidget);
      expect(find.text('JBSWY3DPEHPK3PXP'), findsOneWidget);
      expect(container.read(sessionProvider).pending, SessionPending.mfaSetup);
      // The setup is sent with the token although the path starts with /auth/.
      expect(
        api.calls
            .firstWhere((c) => c.path == '/auth/mfa/setup')
            .headers['Authorization'],
        'Bearer access-1',
      );

      await tester.enterText(find.byType(TextField).last, '000000');
      await tester.tap(find.widgetWithText(FilledButton, 'Einrichten'));
      await tester.pumpAndSettle();
      expect(
        find.text('Der Code stimmt nicht oder wurde schon benutzt.'),
        findsOneWidget,
      );

      await tester.enterText(find.byType(TextField).last, '654321');
      final enable = find.widgetWithText(FilledButton, 'Einrichten');
      await tester.ensureVisible(enable);
      await tester.tap(enable);
      await tester.pumpAndSettle();
      expect(find.text('abcde-12345'), findsOneWidget);
      expect(find.textContaining('nur dieses eine Mal'), findsOneWidget);

      final done = find.widgetWithText(
        FilledButton,
        'Ich habe die Codes gesichert',
      );
      await tester.ensureVisible(done);
      await tester.tap(done);
      await tester.pumpAndSettle();

      final session = container.read(sessionProvider);
      expect(session.pending, SessionPending.none);
      expect(session.tokens!.access, 'access-mfa');
      // The app moves on to its first screen.
      expect(find.text('Wiederherstellungscodes'), findsNothing);
      expect(find.text('abcde-12345'), findsNothing);
      expect(find.text('Profil'), findsWidgets);
    });

    testWidgets('a reset password has to be replaced first', (tester) async {
      Object? sent;
      final api = FakeApi({
        'POST /auth/login': (_, _) =>
            ok({...authJson(), 'password_change_required': true}),
        'POST /auth/password': (_, body) {
          sent = body;
          return ok(authJson(access: 'access-2', refresh: 'refresh-2'));
        },
        'GET /modules': (_, _) => ok([]),
        'GET /me/profile': (_, _) => ok(<String, dynamic>{}),
      });
      final container = await pumpApp(tester, api: api);

      await signIn(tester);
      expect(find.textContaining('wurde zurückgesetzt'), findsOneWidget);

      await tester.enterText(field('Bisheriges Passwort'), 'Temp-Pass-1');
      await tester.enterText(field('Neues Passwort'), 'Ganz-Neu-9');
      await tester.enterText(field('Passwort wiederholen'), 'Ganz-Neu-8');
      final save = find.widgetWithText(FilledButton, 'Speichern');
      await tester.ensureVisible(save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(sent, isNull);

      await tester.enterText(field('Passwort wiederholen'), 'Ganz-Neu-9');
      await tester.tap(save);
      await tester.pumpAndSettle();

      expect(sent, {
        'current_password': 'Temp-Pass-1',
        'new_password': 'Ganz-Neu-9',
      });
      expect(container.read(sessionProvider).pending, SessionPending.none);
      expect(container.read(sessionProvider).tokens!.access, 'access-2');
      // The app moves on to its first screen.
      expect(find.text('Bisheriges Passwort'), findsNothing);
      expect(find.text('Profil'), findsWidgets);
    });

    test('a refusal of the server leads to the screen that resolves it', () {
      const home = '/tours';
      String? go(String location, SessionPending pending) =>
          redirectFor(SessionStatus.signedIn, location, home, pending: pending);

      expect(go('/tours', SessionPending.mfaSetup), '/account/mfa');
      expect(go('/account/mfa', SessionPending.mfaSetup), isNull);
      expect(
        go('/profile', SessionPending.passwordChange),
        '/account/password',
      );
      expect(go('/account/password', SessionPending.none), isNull);
    });

    test('a 403 of the API marks the session as incomplete', () async {
      final api = FakeApi({
        'GET /me/profile': (_, _) => apiError(403, 'mfa_setup_required'),
      });
      final container = createContainer(
        api: api,
        store: MemoryKeyValueStore(signedInStore),
      );
      await container.read(sessionProvider.notifier).restore();

      await expectLater(
        container.read(authRepositoryProvider).fetchProfile(),
        throwsA(isA<ApiException>()),
      );

      expect(container.read(sessionProvider).pending, SessionPending.mfaSetup);
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
