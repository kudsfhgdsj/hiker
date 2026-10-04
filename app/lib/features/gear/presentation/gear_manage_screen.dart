import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/session/session.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';

/// `#RRGGBB` → colour, or null.
Color? parseTagColor(String? hex) {
  if (hex == null || !RegExp(r'^#[0-9a-fA-F]{6}$').hasMatch(hex)) return null;
  return Color(int.parse(hex.substring(1), radix: 16) | 0xFF000000);
}

/// Tags and gear types of the user.
class GearManageScreen extends ConsumerWidget {
  const GearManageScreen({super.key});

  Future<void> _guard(
    BuildContext context,
    WidgetRef ref,
    Future<void> Function() action,
  ) async {
    try {
      await action();
      ref.invalidate(gearTagsProvider);
      ref.invalidate(gearTypesProvider);
      ref.invalidate(gearItemsProvider);
    } catch (error) {
      if (context.mounted) showError(context, error);
    }
  }

  Future<void> _editTag(
    BuildContext context,
    WidgetRef ref,
    GearTag? tag,
  ) async {
    final result = await showDialog<({String name, String? color})>(
      context: context,
      builder: (context) => _NameDialog(
        title: tag == null ? AppLocalizations.of(context).gearTagNew : tag.name,
        name: tag?.name,
        color: tag?.color,
        withColor: true,
      ),
    );
    if (result == null || !context.mounted) return;
    await _guard(
      context,
      ref,
      () => ref
          .read(gearRepositoryProvider)
          .saveTag(id: tag?.id, name: result.name, color: result.color),
    );
  }

  Future<void> _editType(
    BuildContext context,
    WidgetRef ref,
    GearType? type,
  ) async {
    final result = await showDialog<({String name, String? color})>(
      context: context,
      builder: (context) => _NameDialog(
        title: type == null
            ? AppLocalizations.of(context).gearTypeNew
            : type.name,
        name: type?.name,
      ),
    );
    if (result == null || !context.mounted) return;
    await _guard(
      context,
      ref,
      () => ref
          .read(gearRepositoryProvider)
          .saveType(id: type?.id, name: result.name),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final isAdmin = ref.watch(
      sessionProvider.select((s) => s.user?.isAdmin ?? false),
    );
    final repository = ref.read(gearRepositoryProvider);
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.gearManageTitle),
          bottom: TabBar(
            tabs: [
              Tab(text: l10n.gearTags),
              Tab(text: l10n.gearType),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            AsyncBody(
              value: ref.watch(gearTagsProvider),
              onRetry: () => ref.invalidate(gearTagsProvider),
              builder: (loaded) => ListView(
                children: [
                  if (loaded.offline) const OfflineBanner(),
                  if (loaded.value.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(l10n.gearTagsEmpty),
                    ),
                  for (final tag in loaded.value)
                    ListTile(
                      leading: CircleAvatar(
                        radius: 10,
                        backgroundColor:
                            parseTagColor(tag.color) ??
                            Theme.of(context)
                                .colorScheme
                                .surfaceContainerHighest,
                      ),
                      title: Text(tag.name),
                      onTap: () => _editTag(context, ref, tag),
                      subtitle: tag.system == null
                          ? null
                          : Text(l10n.gearTagSystem),
                      // The tags of the app itself stay.
                      trailing: tag.system != null
                          ? null
                          : IconButton(
                              tooltip: l10n.delete,
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () async {
                                if (await confirmDelete(context, tag.name) &&
                                    context.mounted) {
                                  await _guard(
                                    context,
                                    ref,
                                    () => repository.deleteTag(tag.id),
                                  );
                                }
                              },
                            ),
                    ),
                  ListTile(
                    leading: const Icon(Icons.add),
                    title: Text(l10n.gearTagNew),
                    onTap: () => _editTag(context, ref, null),
                  ),
                ],
              ),
            ),
            AsyncBody(
              value: ref.watch(gearTypesProvider),
              onRetry: () => ref.invalidate(gearTypesProvider),
              builder: (loaded) => ListView(
                children: [
                  if (loaded.offline) const OfflineBanner(),
                  for (final type in loaded.value)
                    ListTile(
                      title: Text(type.name),
                      subtitle: Text(
                        type.standard
                            ? l10n.gearStandardType
                            : l10n.gearOwnType,
                      ),
                      // The standard list is shared by all users; only admins change it.
                      enabled: !type.standard || isAdmin,
                      onTap: () => _editType(context, ref, type),
                      trailing: type.standard && !isAdmin
                          ? null
                          : IconButton(
                              tooltip: l10n.delete,
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () async {
                                if (await confirmDelete(context, type.name) &&
                                    context.mounted) {
                                  await _guard(
                                    context,
                                    ref,
                                    () => repository.deleteType(type.id),
                                  );
                                }
                              },
                            ),
                    ),
                  ListTile(
                    leading: const Icon(Icons.add),
                    title: Text(l10n.gearTypeNew),
                    onTap: () => _editType(context, ref, null),
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

class _NameDialog extends StatefulWidget {
  const _NameDialog({
    required this.title,
    this.name,
    this.color,
    this.withColor = false,
  });

  final String title;
  final String? name;
  final String? color;
  final bool withColor;

  @override
  State<_NameDialog> createState() => _NameDialogState();
}

class _NameDialogState extends State<_NameDialog> {
  final _formKey = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.name);
  late final _color = TextEditingController(text: widget.color);

  @override
  void dispose() {
    _name.dispose();
    _color.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final color = _color.text.trim();
    Navigator.pop(context, (
      name: _name.text.trim(),
      color: color.isEmpty ? null : color,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(widget.title),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: _name,
              autofocus: true,
              decoration: InputDecoration(labelText: l10n.name),
              validator: (v) =>
                  (v ?? '').trim().isEmpty ? l10n.requiredField : null,
              onFieldSubmitted: (_) => _submit(),
            ),
            if (widget.withColor) ...[
              const SizedBox(height: 16),
              TextFormField(
                controller: _color,
                decoration: InputDecoration(
                  labelText: l10n.gearColorHex,
                  hintText: '#3366CC',
                ),
                validator: (v) =>
                    (v ?? '').trim().isEmpty || parseTagColor(v!.trim()) != null
                    ? null
                    : l10n.gearColorInvalid,
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(onPressed: _submit, child: Text(l10n.save)),
      ],
    );
  }
}
