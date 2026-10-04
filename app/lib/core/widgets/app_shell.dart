import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../modules/feature_module.dart';
import '../theme/app_theme.dart';
import 'mountain_background.dart';

/// Frame around the feature screens: bottom navigation on phones, a navigation
/// rail on wide screens. Shows only the features that are active.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.location, required this.child});

  /// Current path, to highlight the matching destination.
  final String location;
  final Widget child;

  static const profilePath = '/profile';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final modules = ref.watch(activeModulesProvider);
    final destinations = [
      for (final module in modules)
        (path: module.rootPath, icon: module.icon, label: module.label(l10n)),
      (path: profilePath, icon: Icons.person_outline, label: l10n.profileTitle),
    ];
    final index = destinations.indexWhere(
      (d) => location == d.path || location.startsWith('${d.path}/'),
    );
    final selected = index < 0 ? 0 : index;
    void open(int i) => context.go(destinations[i].path);

    // A navigation with a single entry would only take up space.
    if (destinations.length < 2) return MountainBackground(child: child);

    final wide = MediaQuery.sizeOf(context).width >= AppSpacing.wideLayout;
    if (wide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: selected,
              onDestinationSelected: open,
              labelType: NavigationRailLabelType.all,
              destinations: [
                for (final d in destinations)
                  NavigationRailDestination(
                    icon: Icon(d.icon),
                    label: Text(d.label),
                  ),
              ],
            ),
            const VerticalDivider(width: 1),
            Expanded(child: MountainBackground(child: child)),
          ],
        ),
      );
    }
    return Scaffold(
      // The mountain stands on the navigation bar, not behind it.
      body: MountainBackground(child: child),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selected,
        onDestinationSelected: open,
        destinations: [
          for (final d in destinations)
            NavigationDestination(icon: Icon(d.icon), label: d.label),
        ],
      ),
    );
  }
}
