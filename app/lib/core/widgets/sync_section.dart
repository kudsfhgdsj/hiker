import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../db/app_database.dart';
import '../sync/sync_service.dart';
import '../theme/app_theme.dart';
import 'error_text.dart';

/// State of the offline sync: what waits for a connection, what needs a
/// decision, and a button to sync now.
class SyncSection extends ConsumerWidget {
  const SyncSection({super.key});

  String _label(AppLocalizations l10n, PendingChange change) {
    final kind = switch (change.collection) {
      'gear_items' => l10n.syncCollectionGear,
      'foods' => l10n.syncCollectionFood,
      'tours' => l10n.syncCollectionTour,
      'routes' => l10n.syncCollectionRoute,
      _ => change.collection,
    };
    if (change.data == null) return '$kind (${l10n.syncDeleted})';
    final data = jsonDecode(change.data!) as Map<String, dynamic>;
    return '$kind: ${data['title'] ?? data['name'] ?? ''}';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final status = ref.watch(syncProvider);
    final service = ref.read(syncProvider.notifier);
    final theme = Theme.of(context);

    Future<void> syncNow() async {
      final messenger = ScaffoldMessenger.of(context);
      final reached = await service.sync();
      messenger.showSnackBar(
        SnackBar(
          content: Text(reached ? l10n.syncDone : l10n.syncNoConnection),
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l10n.syncTitle, style: theme.textTheme.titleMedium),
            const SizedBox(height: AppSpacing.xs),
            Text(
              status.isClean
                  ? l10n.syncClean
                  : status.waiting > 0
                  ? l10n.syncWaiting(status.waiting)
                  : '',
            ),
            for (final change in status.conflicts) ...[
              const Divider(),
              Text(_label(l10n, change), style: theme.textTheme.titleSmall),
              Text(l10n.syncConflict),
              Wrap(
                spacing: AppSpacing.s,
                children: [
                  OutlinedButton(
                    onPressed: () => service.keepMine(change),
                    child: Text(l10n.syncKeepMine),
                  ),
                  OutlinedButton(
                    onPressed: () => service.discard(change),
                    child: Text(l10n.syncTakeServer),
                  ),
                ],
              ),
            ],
            for (final change in status.failed) ...[
              const Divider(),
              Text(_label(l10n, change), style: theme.textTheme.titleSmall),
              Text(
                '${l10n.syncFailed}: ${describeErrorCode(l10n, change.error!)}',
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: () => service.discard(change),
                  child: Text(l10n.syncDiscard),
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.s),
            FilledButton.tonalIcon(
              onPressed: status.running ? null : syncNow,
              icon: const Icon(Icons.sync),
              label: Text(l10n.syncNow),
            ),
          ],
        ),
      ),
    );
  }
}
