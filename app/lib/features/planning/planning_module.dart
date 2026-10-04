import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'presentation/offline_data_screen.dart';
import 'presentation/route_list_screen.dart';
import 'presentation/route_plan_screen.dart';

final planningModule = FeatureModule(
  id: 'planning',
  rootPath: '/planning',
  icon: Icons.route_outlined,
  label: (l10n) => l10n.planTitle,
  routes: [
    GoRoute(
      path: '/planning',
      builder: (context, state) => const RouteListScreen(),
      routes: [
        GoRoute(
          path: 'new',
          builder: (context, state) => const RoutePlanScreen(),
        ),
        GoRoute(
          path: 'offline',
          builder: (context, state) => const OfflineDataScreen(),
        ),
        GoRoute(
          path: 'route/:id',
          builder: (context, state) =>
              RoutePlanScreen(routeId: state.pathParameters['id']),
        ),
      ],
    ),
  ],
);
