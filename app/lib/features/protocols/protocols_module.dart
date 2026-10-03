import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/modules/feature_module.dart';
import 'presentation/tour_detail_screen.dart';
import 'presentation/tour_edit_screen.dart';
import 'presentation/tour_history_screen.dart';
import 'presentation/tour_list_screen.dart';
import 'presentation/tour_map_edit_screen.dart';
import 'presentation/tour_share_screen.dart';

final protocolsModule = FeatureModule(
  id: 'protocols',
  rootPath: '/protocols',
  icon: Icons.terrain_outlined,
  label: (l10n) => l10n.toursTitle,
  routes: [
    GoRoute(
      path: '/protocols',
      builder: (context, state) => const TourListScreen(),
      routes: [
        GoRoute(
          path: 'new',
          builder: (context, state) => const TourEditScreen(),
        ),
        GoRoute(
          path: 'tour/:id',
          builder: (context, state) =>
              TourDetailScreen(tourId: state.pathParameters['id']!),
          routes: [
            GoRoute(
              path: 'edit',
              builder: (context, state) =>
                  TourEditScreen(tourId: state.pathParameters['id']),
            ),
            GoRoute(
              path: 'history',
              builder: (context, state) =>
                  TourHistoryScreen(tourId: state.pathParameters['id']!),
            ),
            GoRoute(
              path: 'share',
              builder: (context, state) =>
                  TourShareScreen(tourId: state.pathParameters['id']!),
            ),
            GoRoute(
              path: 'draw',
              builder: (context, state) => TourMapEditScreen(
                tourId: state.pathParameters['id']!,
                drawTrack: true,
              ),
            ),
            GoRoute(
              path: 'points',
              builder: (context, state) => TourMapEditScreen(
                tourId: state.pathParameters['id']!,
                drawTrack: false,
              ),
            ),
          ],
        ),
      ],
    ),
  ],
);
