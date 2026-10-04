import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'presentation/map_screen.dart';

/// Map mode: look at the map and look things up, without planning anything.
final mapModule = FeatureModule(
  id: 'maps',
  rootPath: '/map',
  icon: Icons.map_outlined,
  label: (l10n) => l10n.mapTitle,
  routes: [
    GoRoute(path: '/map', builder: (context, state) => const MapScreen()),
  ],
);
