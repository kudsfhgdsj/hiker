import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'data/food_models.dart';
import 'presentation/food_catalog_screen.dart';
import 'presentation/food_form_screen.dart';
import 'presentation/food_list_screen.dart';

final nutritionModule = FeatureModule(
  id: 'nutrition',
  rootPath: '/nutrition',
  icon: Icons.restaurant_outlined,
  label: (l10n) => l10n.foodTitle,
  routes: [
    GoRoute(
      path: '/nutrition',
      builder: (context, state) => const FoodListScreen(),
      routes: [
        GoRoute(
          path: 'new',
          builder: (context, state) =>
              FoodFormScreen(initial: state.extra as Food?),
        ),
        GoRoute(
          path: 'edit',
          builder: (context, state) =>
              FoodFormScreen(initial: state.extra as Food?),
        ),
        GoRoute(
          path: 'catalog',
          builder: (context, state) => const FoodCatalogScreen(),
        ),
      ],
    ),
  ],
);
