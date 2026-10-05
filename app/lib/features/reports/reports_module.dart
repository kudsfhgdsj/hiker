import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'presentation/stats_screen.dart';

/// Statistics over all own tours. Not a page of the navigation: it is opened
/// from the list of tours and from the profile.
final reportsModule = FeatureModule(
  id: 'reports',
  rootPath: '/stats',
  icon: Icons.insights_outlined,
  label: (l10n) => l10n.statsTitle,
  inNavigation: false,
  routes: [
    GoRoute(path: '/stats', builder: (context, state) => const StatsScreen()),
  ],
);
