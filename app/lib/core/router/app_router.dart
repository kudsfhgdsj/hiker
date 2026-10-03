import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../modules/feature_module.dart';
import '../session/session.dart';
import '../widgets/app_shell.dart';

/// Screens that core needs but that belong to the auth feature; set in `main.dart`.
class AuthScreens {
  const AuthScreens({
    required this.login,
    required this.register,
    required this.profile,
  });

  final WidgetBuilder login;
  final WidgetBuilder register;
  final WidgetBuilder profile;
}

final authScreensProvider = Provider<AuthScreens>(
  (ref) => throw UnimplementedError('authScreensProvider must be overridden'),
);

class AppRoutes {
  const AppRoutes._();

  static const splash = '/';
  static const login = '/login';
  static const register = '/register';
  static const profile = AppShell.profilePath;
}

/// Where to go for the current session state, or null to stay.
String? redirectFor(SessionStatus status, String location, String home) {
  final onAuthScreen =
      location == AppRoutes.login || location == AppRoutes.register;
  switch (status) {
    case SessionStatus.unknown:
      return location == AppRoutes.splash ? null : AppRoutes.splash;
    case SessionStatus.signedOut:
      return onAuthScreen ? null : AppRoutes.login;
    case SessionStatus.signedIn:
      return onAuthScreen || location == AppRoutes.splash ? home : null;
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final screens = ref.watch(authScreensProvider);
  final modules = ref.watch(featureModulesProvider);
  final refresh = ValueNotifier<int>(0);
  ref.listen(
    sessionProvider.select((s) => s.status),
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
      return redirectFor(
        ref.read(sessionProvider).status,
        state.matchedLocation,
        home,
      );
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) =>
            const Scaffold(body: Center(child: CircularProgressIndicator())),
      ),
      GoRoute(path: AppRoutes.login, builder: (c, s) => screens.login(c)),
      GoRoute(path: AppRoutes.register, builder: (c, s) => screens.register(c)),
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
