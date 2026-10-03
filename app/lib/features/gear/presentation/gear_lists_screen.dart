import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';

/// Packing list templates.
class GearListsScreen extends ConsumerWidget {
  const GearListsScreen({super.key});

  Future<void> _edit(
    BuildContext context,
    WidgetRef ref,
    GearPackList? list,
  ) async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => _PackListDialog(initial: list),
    );
    if (saved == true) ref.invalidate(gearPackListsProvider);
  }

  Future<void> _delete(
    BuildContext context,
    WidgetRef ref,
    GearPackList list,
  ) async {
    if (!await confirmDelete(context, list.name)) return;
    try {
      await ref.read(gearRepositoryProvider).deletePackList(list.id!);
      ref.invalidate(gearPackListsProvider);
    } catch (error) {
      if (context.mounted) showError(context, error);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.gearListsTitle)),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _edit(context, ref, null),
        icon: const Icon(Icons.add),
        label: Text(l10n.gearListNew),
      ),
      body: AsyncBody(
        value: ref.watch(gearPackListsProvider),
        onRetry: () => ref.invalidate(gearPackListsProvider),
        builder: (loaded) => Column(
          children: [
            if (loaded.offline) const OfflineBanner(),
            Expanded(
              child: loaded.value.isEmpty
                  ? Center(child: Text(l10n.gearListsEmpty))
                  : ListView(
                      padding: const EdgeInsets.only(bottom: 88),
                      children: [
                        for (final list in loaded.value)
                          ListTile(
                            title: Text(list.name),
                            subtitle: Text(
                              '${l10n.gearItemCount(list.entries.length)} · '
                              '${Format.weight(list.totalWeightG)}',
                            ),
                            trailing: IconButton(
                              tooltip: l10n.delete,
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () => _delete(context, ref, list),
                            ),
                            onTap: () => _edit(context, ref, list),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PackListDialog extends ConsumerStatefulWidget {
  const _PackListDialog({this.initial});

  final GearPackList? initial;

  @override
  ConsumerState<_PackListDialog> createState() => _PackListDialogState();
}

class _PackListDialogState extends ConsumerState<_PackListDialog> {
  late final _name = TextEditingController(text: widget.initial?.name);
  late final Map<String, int> _quantities = {
    for (final entry in widget.initial?.entries ?? const <GearListEntry>[])
      entry.gearItemId: entry.quantity,
  };
  Object? _error;
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) return;
    setState(() => _busy = true);
    final navigator = Navigator.of(context);
    try {
      await ref
          .read(gearRepositoryProvider)
          .savePackList(
            GearPackList(
              id: widget.initial?.id,
              name: _name.text.trim(),
              description: widget.initial?.description,
              entries: [
                for (final entry in _quantities.entries)
                  GearListEntry(gearItemId: entry.key, quantity: entry.value),
              ],
            ),
          );
      navigator.pop(true);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error;
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final items = ref.watch(
      gearItemsProvider(const GearFilter(status: 'active')),
    );
    final all = items.asData?.value.value ?? const <GearItem>[];
    final weight = all.fold<int>(
      0,
      (sum, item) => sum + (item.weightG ?? 0) * (_quantities[item.id] ?? 0),
    );
    return AlertDialog(
      title: Text(
        widget.initial == null ? l10n.gearListNew : l10n.gearListEdit,
      ),
      content: SizedBox(
        width: AppSpacing.maxContentWidth,
        height: 440,
        child: Column(
          children: [
            TextField(
              controller: _name,
              decoration: InputDecoration(labelText: l10n.name),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: AppSpacing.s),
            Align(
              alignment: Alignment.centerLeft,
              child: Text('${l10n.gearTotalWeight}: ${Format.weight(weight)}'),
            ),
            if (_error != null) ErrorText(_error!),
            Expanded(
              child: items.isLoading && all.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : ListView(
                      children: [
                        for (final item in all)
                          CheckboxListTile(
                            dense: true,
                            value: _quantities.containsKey(item.id),
                            title: Text(item.name),
                            subtitle: Text(Format.weight(item.weightG)),
                            secondary: _quantities.containsKey(item.id)
                                ? _QuantityStepper(
                                    value: _quantities[item.id]!,
                                    onChanged: (value) => setState(
                                      () => _quantities[item.id!] = value,
                                    ),
                                  )
                                : null,
                            onChanged: (selected) => setState(() {
                              if (selected ?? false) {
                                _quantities[item.id!] = 1;
                              } else {
                                _quantities.remove(item.id);
                              }
                            }),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: _busy || _name.text.trim().isEmpty ? null : _save,
          child: Text(l10n.save),
        ),
      ],
    );
  }
}

class _QuantityStepper extends StatelessWidget {
  const _QuantityStepper({required this.value, required this.onChanged});

  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          tooltip: '${l10n.gearQuantity} −',
          icon: const Icon(Icons.remove_circle_outline),
          onPressed: value > 1 ? () => onChanged(value - 1) : null,
        ),
        Text('$value'),
        IconButton(
          tooltip: '${l10n.gearQuantity} +',
          icon: const Icon(Icons.add_circle_outline),
          onPressed: value < 999 ? () => onChanged(value + 1) : null,
        ),
      ],
    );
  }
}
