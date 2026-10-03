import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart';

import 'core/modules/feature_module.dart';
import 'core/router/app_router.dart';
import 'core/session/session.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/auth_form_screen.dart';
import 'features/auth/presentation/profile_screen.dart';
import 'features/gear/gear_module.dart';
import 'l10n/app_localizations.dart';

/// The features built into the app. A feature is added or removed here only.
final List<FeatureModule> builtInModules = [gearModule];

/// Wires the features into core. Tests pass their own list of modules.
List<Override> appOverrides({List<FeatureModule>? modules}) => [
  featureModulesProvider.overrideWithValue(modules ?? builtInModules),
  authScreensProvider.overrideWithValue(
    AuthScreens(
      login: (_) => const AuthFormScreen(register: false),
      register: (_) => const AuthFormScreen(register: true),
      profile: (_) => const ProfileScreen(),
    ),
  ),
];

class HikerApp extends ConsumerStatefulWidget {
  const HikerApp({super.key});

  @override
  ConsumerState<HikerApp> createState() => _HikerAppState();
}

class _HikerAppState extends ConsumerState<HikerApp> {
  @override
  void initState() {
    super.initState();
    // Load the stored session; the router leaves the splash screen afterwards.
    Future.microtask(() => ref.read(sessionProvider.notifier).restore());
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      routerConfig: ref.watch(routerProvider),
      locale: const Locale('de'),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    );
  }
}
