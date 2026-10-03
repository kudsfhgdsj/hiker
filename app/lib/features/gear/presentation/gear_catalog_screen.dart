import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/session/session.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';

final _myProposalsProvider = FutureProvider.autoDispose<List<CatalogItem>>(
  (ref) => ref.watch(gearRepositoryProvider).myProposals(),
);

final _pendingProvider = FutureProvider.autoDispose<List<CatalogItem>>(
  (ref) => ref.watch(gearRepositoryProvider).pendingProposals(),
);

/// The user's own catalog proposals with their status; admins also moderate.
class GearCatalogScreen extends ConsumerWidget {
  const GearCatalogScreen({super.key});

  Future<void> _moderate(
    BuildContext context,
    WidgetRef ref,
    CatalogItem entry,
    String status,
  ) async {
    try {
      await ref.read(gearRepositoryProvider).moderate(entry.id, status);
      ref.invalidate(_pendingProvider);
      ref.invalidate(_myProposalsProvider);
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
      'pending': l10n.catalogPending,
      'approved': l10n.catalogApproved,
      'rejected': l10n.catalogRejected,
    };

    Widget subtitle(CatalogItem entry) => Text(
      [
        if (entry.brand != null) entry.brand!,
        Format.weight(entry.nominalWeightG),
      ].join(' · '),
    );

    final mine = AsyncBody(
      value: ref.watch(_myProposalsProvider),
      onRetry: () => ref.invalidate(_myProposalsProvider),
      builder: (entries) => entries.isEmpty
          ? Center(child: Text(l10n.gearNoProposals))
          : ListView(
              children: [
                for (final entry in entries)
                  ListTile(
                    title: Text(entry.name),
                    subtitle: subtitle(entry),
                    trailing: Chip(
                      label: Text(statusLabels[entry.status] ?? entry.status),
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
          title: Text(l10n.gearCatalogTitle),
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
              builder: (entries) => entries.isEmpty
                  ? Center(child: Text(l10n.gearNoProposals))
                  : ListView(
                      children: [
                        for (final entry in entries)
                          ListTile(
                            title: Text(entry.name),
                            subtitle: subtitle(entry),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: l10n.catalogReject,
                                  icon: const Icon(Icons.close),
                                  onPressed: () => _moderate(
                                    context,
                                    ref,
                                    entry,
                                    'rejected',
                                  ),
                                ),
                                IconButton(
                                  tooltip: l10n.catalogApprove,
                                  icon: const Icon(Icons.check),
                                  onPressed: () => _moderate(
                                    context,
                                    ref,
                                    entry,
                                    'approved',
                                  ),
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
