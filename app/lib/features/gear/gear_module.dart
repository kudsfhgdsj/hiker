import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'presentation/gear_catalog_screen.dart';
import 'presentation/gear_item_screen.dart';
import 'presentation/gear_list_screen.dart';
import 'presentation/gear_lists_screen.dart';
import 'presentation/gear_manage_screen.dart';
import 'presentation/gear_summary_screen.dart';

final gearModule = FeatureModule(
  id: 'gear',
  rootPath: '/gear',
  icon: Icons.backpack_outlined,
  label: (l10n) => l10n.gearTitle,
  routes: [
    GoRoute(
      path: '/gear',
      builder: (context, state) => const GearListScreen(),
      routes: [
        GoRoute(
          path: 'new',
          builder: (context, state) => const GearItemScreen(),
        ),
        GoRoute(
          path: 'item/:id',
          builder: (context, state) =>
              GearItemScreen(itemId: state.pathParameters['id']),
        ),
        GoRoute(
          path: 'summary',
          builder: (context, state) => const GearSummaryScreen(),
        ),
        GoRoute(
          path: 'lists',
          builder: (context, state) => const GearListsScreen(),
        ),
        GoRoute(
          path: 'manage',
          builder: (context, state) => const GearManageScreen(),
        ),
        GoRoute(
          path: 'catalog',
          builder: (context, state) => const GearCatalogScreen(),
        ),
      ],
    ),
  ],
);
