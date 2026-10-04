import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../modules/feature_module.dart';
import '../session/session.dart';
import '../widgets/app_shell.dart';
import '../widgets/mountain_background.dart';

/// Screens that core needs but that belong to the auth feature; set in `main.dart`.
class AuthScreens {
  const AuthScreens({
    required this.login,
    required this.register,
    required this.profile,
    required this.mfaSetup,
    required this.passwordChange,
  });

  final WidgetBuilder login;
  final WidgetBuilder register;
  final WidgetBuilder profile;
  final WidgetBuilder mfaSetup;
  final WidgetBuilder passwordChange;
}

/// The map shown before signing in; belongs to a feature, set in `app.dart`.
/// Null: the app has no such screen.
final openMapScreenProvider = Provider<WidgetBuilder?>((ref) => null);

final authScreensProvider = Provider<AuthScreens>(
  (ref) => throw UnimplementedError('authScreensProvider must be overridden'),
);

class AppRoutes {
  const AppRoutes._();

  static const splash = '/';
  static const login = '/login';
  static const register = '/register';

  /// The map on its own; reachable without signing in.
  static const openMap = '/open-map';
  static const mfaSetup = '/account/mfa';
  static const passwordChange = '/account/password';
  static const profile = AppShell.profilePath;
}

/// Where to go for the current session state, or null to stay.
String? redirectFor(
  SessionStatus status,
  String location,
  String home, {
  SessionPending pending = SessionPending.none,
}) {
  // Signing in, registering and looking at the map need no session.
  final onAuthScreen =
      location == AppRoutes.login ||
      location == AppRoutes.register ||
      location == AppRoutes.openMap;
  switch (status) {
    case SessionStatus.unknown:
      return location == AppRoutes.splash ? null : AppRoutes.splash;
    case SessionStatus.signedOut:
      return onAuthScreen ? null : AppRoutes.login;
    case SessionStatus.signedIn:
      // An incomplete sign-in only reaches the screen that completes it.
      final step = switch (pending) {
        SessionPending.passwordChange => AppRoutes.passwordChange,
        SessionPending.mfaSetup => AppRoutes.mfaSetup,
        SessionPending.none => null,
      };
      if (step != null) return location == step ? null : step;
      return onAuthScreen || location == AppRoutes.splash ? home : null;
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final screens = ref.watch(authScreensProvider);
  final openMap = ref.watch(openMapScreenProvider);
  final modules = ref.watch(featureModulesProvider);
  final refresh = ValueNotifier<int>(0);
  ref.listen(
    sessionProvider.select((s) => (s.status, s.pending)),
    (_, _) => refresh.value++,
  );
  ref.listen(activeModulesProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  final router = GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: refresh,
    redirect: (context, state) {
      final active = ref.read(activeModulesProvider);
      final home = active.isEmpty ? AppRoutes.profile : active.first.rootPath;
      final session = ref.read(sessionProvider);
      return redirectFor(
        session.status,
        state.matchedLocation,
        home,
        pending: session.pending,
      );
    },
    routes: [
      // Screens outside the navigation frame get the background themselves.
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) => const MountainBackground(
          child: Scaffold(body: Center(child: CircularProgressIndicator())),
        ),
      ),
      for (final (path, screen) in [
        (AppRoutes.login, screens.login),
        (AppRoutes.register, screens.register),
        (AppRoutes.mfaSetup, screens.mfaSetup),
        (AppRoutes.passwordChange, screens.passwordChange),
      ])
        GoRoute(
          path: path,
          builder: (context, state) =>
              MountainBackground(child: screen(context)),
        ),
      if (openMap != null)
        GoRoute(
          path: AppRoutes.openMap,
          builder: (context, state) => openMap(context),
        ),
      ShellRoute(
        builder: (context, state, child) =>
            AppShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(
            path: AppRoutes.profile,
            builder: (c, s) => screens.profile(c),
          ),
          for (final module in modules) ...module.routes,
        ],
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});
