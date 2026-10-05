import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_repository.dart';
import 'tour_labels.dart';

final _revisionsProvider = FutureProvider.autoDispose
    .family<List<Json>, String>(
      (ref, id) => ref.watch(tourRepositoryProvider).revisions(id),
    );

/// Readable lines for the diff of a revision.
List<String> describeDiff(AppLocalizations l10n, Json diff) {
  String text(Object? value) => value == null ? '–' : '$value';
  final lines = <String>[];
  for (final entry in diff.entries) {
    final label = fieldLabel(l10n, entry.key);
    final change = entry.value as Json;
    if (change.containsKey('added')) {
      String names(String key) => (change[key] as List<dynamic>)
          .map((e) => (e as Json)['name'] ?? '?')
          .join(', ');
      if ((change['added'] as List<dynamic>).isNotEmpty) {
        lines.add('$label ${l10n.historyAdded}: ${names('added')}');
      }
      if ((change['removed'] as List<dynamic>).isNotEmpty) {
        lines.add('$label ${l10n.historyRemoved}: ${names('removed')}');
      }
      if ((change['changed'] as List<dynamic>).isNotEmpty) {
        lines.add('$label ${l10n.historyChanged}: ${names('changed')}');
      }
    } else {
      lines.add('$label: ${text(change['old'])} → ${text(change['new'])}');
    }
  }
  return lines;
}

class TourHistoryScreen extends ConsumerWidget {
  const TourHistoryScreen({super.key, required this.tourId});

  final String tourId;

  Future<void> _open(
    BuildContext context,
    WidgetRef ref,
    Json item,
    bool canRestore,
  ) async {
    final l10n = AppLocalizations.of(context);
    final repository = ref.read(tourRepositoryProvider);
    final version = item['version'] as int;
    final Json revision;
    try {
      revision = await repository.revision(tourId, version);
    } catch (error) {
      if (context.mounted) showError(context, error);
      return;
    }
    if (!context.mounted) return;
    final lines = describeDiff(l10n, revision['diff'] as Json);
    final restore = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.historyVersion(version)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.historyChanges,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: AppSpacing.s),
              if (lines.isEmpty) Text(l10n.historyNoChanges),
              for (final line in lines) Text(line),
              if (canRestore) ...[
                const SizedBox(height: AppSpacing.m),
                Text(
                  l10n.historyRestoreConfirm,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.close),
          ),
          if (canRestore)
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(l10n.historyRestore),
            ),
        ],
      ),
    );
    if (restore != true) return;
    try {
      await repository.restore(tourId, version);
      ref.invalidate(_revisionsProvider(tourId));
      ref.invalidate(tourProvider(tourId));
    } catch (error) {
      if (context.mounted) showError(context, error);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final tour = ref.watch(tourProvider(tourId)).asData?.value.value;
    final kinds = {
      'created': (l10n.historyCreated, Icons.add_circle_outline),
      'updated': (l10n.historyUpdated, Icons.edit_outlined),
      'restored': (l10n.historyRestored, Icons.restore),
      'deleted': (l10n.historyDeleted, Icons.delete_outline),
    };
    return Scaffold(
      appBar: AppBar(title: Text(l10n.tourHistory)),
      body: AsyncBody(
        value: ref.watch(_revisionsProvider(tourId)),
        onRetry: () => ref.invalidate(_revisionsProvider(tourId)),
        builder: (revisions) => ListView(
          children: [
            for (final (index, item) in revisions.indexed)
              ListTile(
                leading: Icon(kinds[item['kind']]?.$2 ?? Icons.edit_outlined),
                title: Text(
                  [
                    kinds[item['kind']]?.$1 ?? '',
                    if (item['kind'] == 'updated')
                      summaryLabel(l10n, item['change_summary'] as String),
                  ].where((part) => part.isNotEmpty).join(': '),
                ),
                subtitle: Text(
                  '${Format.dateTime(DateTime.parse(item['created_at'] as String))} · '
                  '${(item['author'] as Json?)?['display_name'] ?? l10n.historyUnknownAuthor}',
                ),
                trailing: Text('${item['version']}'),
                // The newest revision is the current state: nothing to restore.
                onTap: () => _open(
                  context,
                  ref,
                  item,
                  index > 0 && (tour?.canEdit ?? false),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
