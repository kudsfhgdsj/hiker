import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../network/api_client.dart';
import '../network/api_exception.dart';
import '../session/session.dart';

/// A feature of the app. Features register themselves with their routes and
/// their entry in the navigation; core does not know any feature.
class FeatureModule {
  const FeatureModule({
    required this.id,
    required this.rootPath,
    required this.icon,
    required this.label,
    required this.routes,
  });

  /// Name of the backend module; the feature is shown only if it is enabled there.
  final String id;

  /// Path of the first screen, e.g. `/gear`.
  final String rootPath;
  final IconData icon;
  final String Function(AppLocalizations l10n) label;

  /// Routes below the navigation shell.
  final List<RouteBase> routes;
}

/// All features built into the app; set in `main.dart`.
final featureModulesProvider = Provider<List<FeatureModule>>((ref) => const []);

/// Names of the modules the server has enabled.
final backendModulesProvider = FutureProvider<Set<String>>((ref) async {
  if (!ref.watch(sessionProvider.select((s) => s.isSignedIn))) return {};
  final dio = ref.watch(dioProvider);
  final response = await apiCall(() => dio.get<List<dynamic>>('/modules'));
  return {
    for (final module in response.data ?? const <dynamic>[])
      (module as Map<String, dynamic>)['name'] as String,
  };
});

/// The features to show: built into the app and enabled on the server.
/// While the server cannot be asked (offline), all built-in features are shown.
final activeModulesProvider = Provider<List<FeatureModule>>((ref) {
  final modules = ref.watch(featureModulesProvider);
  // No answer yet or no network: asData is null.
  final enabled = ref.watch(backendModulesProvider).asData?.value;
  if (enabled == null) return modules;
  return [
    for (final module in modules)
      if (enabled.contains(module.id)) module,
  ];
});
