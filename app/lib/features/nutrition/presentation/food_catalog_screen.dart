import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/session/session.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/food_models.dart';
import '../data/food_repository.dart';

final _mineProvider = FutureProvider.autoDispose<List<Food>>(
  (ref) => ref.watch(foodRepositoryProvider).myProposals(),
);

final _pendingProvider = FutureProvider.autoDispose<List<Food>>(
  (ref) => ref.watch(foodRepositoryProvider).pendingProposals(),
);

/// The user's own catalog proposals with their status; admins also moderate.
class FoodCatalogScreen extends ConsumerWidget {
  const FoodCatalogScreen({super.key});

  Future<void> _moderate(
    BuildContext context,
    WidgetRef ref,
    Food food,
    String visibility,
  ) async {
    try {
      await ref.read(foodRepositoryProvider).moderate(food.id!, visibility);
      ref.invalidate(_pendingProvider);
      ref.invalidate(_mineProvider);
    } catch (error) {
      if (context.mounted) showError(context, error);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final isAdmin = ref.watch(
      sessionProvider.select((s) => s.user?.isAdmin ?? false),
    );
    final statusLabels = {
      'catalog_pending': l10n.catalogPending,
      'catalog': l10n.catalogApproved,
      'catalog_rejected': l10n.catalogRejected,
    };

    Widget subtitle(Food food) => Text(
      [
        if (food.brand != null) food.brand!,
        if (food.kcalPer100g != null)
          l10n.foodKcalValue(Format.number(food.kcalPer100g!)),
      ].join(' · '),
    );

    final mine = AsyncBody(
      value: ref.watch(_mineProvider),
      onRetry: () => ref.invalidate(_mineProvider),
      builder: (foods) => foods.isEmpty
          ? Center(child: Text(l10n.gearNoProposals))
          : ListView(
              children: [
                for (final food in foods)
                  ListTile(
                    title: Text(food.name),
                    subtitle: subtitle(food),
                    trailing: Chip(
                      label: Text(
                        statusLabels[food.visibility] ?? food.visibility,
                      ),
                    ),
                  ),
              ],
            ),
    );
    if (!isAdmin) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.gearMyProposals)),
        body: mine,
      );
    }
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.foodCatalogTitle),
          bottom: TabBar(
            tabs: [
              Tab(text: l10n.gearPendingProposals),
              Tab(text: l10n.gearMyProposals),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            AsyncBody(
              value: ref.watch(_pendingProvider),
              onRetry: () => ref.invalidate(_pendingProvider),
              builder: (foods) => foods.isEmpty
                  ? Center(child: Text(l10n.gearNoProposals))
                  : ListView(
                      children: [
                        for (final food in foods)
                          ListTile(
                            title: Text(food.name),
                            subtitle: subtitle(food),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: l10n.catalogReject,
                                  icon: const Icon(Icons.close),
                                  onPressed: () => _moderate(
                                    context,
                                    ref,
                                    food,
                                    'catalog_rejected',
                                  ),
                                ),
                                IconButton(
                                  tooltip: l10n.catalogApprove,
                                  icon: const Icon(Icons.check),
                                  onPressed: () =>
                                      _moderate(context, ref, food, 'catalog'),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
            ),
            mine,
          ],
        ),
      ),
    );
  }
}
