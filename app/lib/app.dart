import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart';

import 'core/map/tile_proxy.dart';
import 'core/modules/feature_module.dart';
import 'core/network/trusted_certificates.dart';
import 'core/router/app_router.dart';
import 'core/session/session.dart';
import 'core/sync/sync_service.dart';
import 'core/theme/app_theme.dart';
import 'core/widgets/certificate_dialog.dart';
import 'features/auth/presentation/account_security_screens.dart';
import 'features/auth/presentation/auth_form_screen.dart';
import 'features/auth/presentation/profile_screen.dart';
import 'features/gear/gear_module.dart';
import 'features/nutrition/nutrition_module.dart';
import 'features/planning/planning_module.dart';
import 'features/protocols/data/tour_repository.dart';
import 'features/protocols/protocols_module.dart';
import 'l10n/app_localizations.dart';

/// The features built into the app. A feature is added or removed here only.
final List<FeatureModule> builtInModules = [
  protocolsModule,
  planningModule,
  gearModule,
  nutritionModule,
];

/// Wires the features into core. Tests pass their own list of modules.
List<Override> appOverrides({List<FeatureModule>? modules}) => [
  featureModulesProvider.overrideWithValue(modules ?? builtInModules),
  authScreensProvider.overrideWithValue(
    AuthScreens(
      login: (_) => const AuthFormScreen(register: false),
      register: (_) => const AuthFormScreen(register: true),
      profile: (_) => const ProfileScreen(),
      mfaSetup: (_) => const MfaSetupScreen(),
      passwordChange: (_) => const PasswordChangeScreen(),
    ),
  ),
  // Offline sync: tours merge field by field; files go through the tour API.
  conflictResolversProvider.overrideWithValue({'tours': resolveTourConflict}),
  uploadHandlerProvider.overrideWith(tourUploadHandler),
];

/// Whether the app syncs by itself at start, after sign-in and when it comes
/// back to the foreground. Tests switch it off.
final autoSyncProvider = Provider<bool>((ref) => true);

class HikerApp extends ConsumerStatefulWidget {
  const HikerApp({super.key});

  @override
  ConsumerState<HikerApp> createState() => _HikerAppState();
}

class _HikerAppState extends ConsumerState<HikerApp>
    with WidgetsBindingObserver {
  /// The map asks the app's own map server: it knows the maps on the device
  /// and reaches a server whose certificate was trusted by hand.
  void _startTileProxyIfNeeded() {
    if (!ref.read(tileProxyEnabledProvider)) return;
    ref.read(tileProxyProvider.notifier).start();
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Load the stored session; the router leaves the splash screen afterwards.
    Future.microtask(() async {
      await ref.read(trustedCertificatesProvider.notifier).load();
      _startTileProxyIfNeeded();
      await ref.read(sessionProvider.notifier).restore();
      await ref.read(syncProvider.notifier).load();
      _sync();
    });
    // Changes made without a connection go out by themselves once it is back.
    if (ref.read(autoSyncProvider)) {
      _retry = Timer.periodic(const Duration(minutes: 1), (_) {
        if (mounted && ref.read(sessionProvider).isSignedIn) {
          ref.read(syncProvider.notifier).retryIfWaiting();
        }
      });
    }
  }

  Timer? _retry;

  @override
  void dispose() {
    _retry?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _sync();
  }

  void _sync() {
    if (mounted && ref.read(autoSyncProvider)) {
      ref.read(syncProvider.notifier).sync();
    }
  }

  @override
  Widget build(BuildContext context) {
    // Sync right after signing in.
    ref.listen(sessionProvider.select((s) => s.isSignedIn), (_, signedIn) {
      if (signedIn) _sync();
    });
    ref.listen(
      trustedCertificatesProvider,
      (_, _) => _startTileProxyIfNeeded(),
    );
    // A renewed certificate was accepted: the server is reachable again.
    ref.listen(certificateChangedProvider, (_, _) => _sync());
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
