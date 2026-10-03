import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';
import 'gear_list_screen.dart';

/// Count, weight and purchase value of the gear that matches the list filter.
class GearSummaryScreen extends ConsumerStatefulWidget {
  const GearSummaryScreen({super.key});

  @override
  ConsumerState<GearSummaryScreen> createState() => _GearSummaryScreenState();
}

class _GearSummaryScreenState extends ConsumerState<GearSummaryScreen> {
  String? _groupBy;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final request = (filter: ref.watch(gearFilterProvider), groupBy: _groupBy);
    final groupings = {
      null: l10n.gearGroupNone,
      'type': l10n.gearGroupType,
      'tag': l10n.gearGroupTag,
      'status': l10n.gearGroupStatus,
      'brand': l10n.gearGroupBrand,
    };
    return Scaffold(
      appBar: AppBar(title: Text(l10n.gearSummaryTitle)),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(AppSpacing.m),
            child: Row(
              spacing: AppSpacing.s,
              children: [
                for (final entry in groupings.entries)
                  ChoiceChip(
                    label: Text(entry.value),
                    selected: _groupBy == entry.key,
                    onSelected: (_) => setState(() => _groupBy = entry.key),
                  ),
              ],
            ),
          ),
          Expanded(
            child: AsyncBody(
              value: ref.watch(gearSummaryProvider(request)),
              onRetry: () => ref.invalidate(gearSummaryProvider(request)),
              builder: (summary) => ListView(
                padding: const EdgeInsets.all(AppSpacing.m),
                children: [
                  _TotalsCard(
                    title: l10n.gearGroupNone,
                    totals: summary.total,
                    emphasized: true,
                  ),
                  if (_groupBy == 'tag') ...[
                    const SizedBox(height: AppSpacing.s),
                    Text(
                      l10n.gearTagGroupHint,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  for (final group in summary.groups) ...[
                    const SizedBox(height: AppSpacing.s),
                    _TotalsCard(title: _groupLabel(l10n, group), totals: group),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _groupLabel(AppLocalizations l10n, GearTotals group) {
    if (group.label == null) return l10n.gearUnassigned;
    if (_groupBy != 'status') return group.label!;
    return group.label == 'retired'
        ? l10n.gearStatusRetired
        : l10n.gearStatusActive;
  }
}

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({
    required this.title,
    required this.totals,
    this.emphasized = false,
  });

  final String title;
  final GearTotals totals;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final value = totals.value.isEmpty
        ? '–'
        : totals.value
              .map((v) => Format.money(v.amount, v.currency))
              .join(' + ');
    final hints = [
      if (totals.itemsWithoutWeight > 0)
        l10n.gearWithoutWeight(totals.itemsWithoutWeight),
      if (totals.itemsWithoutPrice > 0)
        l10n.gearWithoutPrice(totals.itemsWithoutPrice),
    ].join(' · ');
    return Card(
      color: emphasized ? theme.colorScheme.primaryContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: theme.textTheme.titleMedium),
            Text(
              l10n.gearItemCount(totals.itemCount),
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                Expanded(
                  child: _Figure(
                    label: l10n.gearTotalWeight,
                    value: Format.weight(totals.weightG),
                  ),
                ),
                Expanded(
                  child: _Figure(label: l10n.gearTotalValue, value: value),
                ),
              ],
            ),
            if (hints.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(hints, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

class _Figure extends StatelessWidget {
  const _Figure({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: theme.textTheme.labelMedium),
        Text(value, style: theme.textTheme.titleLarge),
      ],
    );
  }
}
