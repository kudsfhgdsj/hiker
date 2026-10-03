import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/api_image.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';

/// The current filter of the gear list; shared with the summary screen.
class GearFilterController extends Notifier<GearFilter> {
  @override
  GearFilter build() => const GearFilter();

  void set(GearFilter filter) => state = filter;
}

final gearFilterProvider = NotifierProvider<GearFilterController, GearFilter>(
  GearFilterController.new,
);

class GearListScreen extends ConsumerStatefulWidget {
  const GearListScreen({super.key});

  @override
  ConsumerState<GearListScreen> createState() => _GearListScreenState();
}

class _GearListScreenState extends ConsumerState<GearListScreen> {
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _update(GearFilter filter) =>
      ref.read(gearFilterProvider.notifier).set(filter);

  void _search(String text) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      _update(ref.read(gearFilterProvider).copyWith(query: text.trim()));
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final filter = ref.watch(gearFilterProvider);
    final items = ref.watch(gearItemsProvider(filter));
    final types =
        ref.watch(gearTypesProvider).asData?.value.value ?? const <GearType>[];
    final tags =
        ref.watch(gearTagsProvider).asData?.value.value ?? const <GearTag>[];
    final typeNames = {for (final type in types) type.id: type.name};

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.gearTitle),
        actions: [
          IconButton(
            tooltip: l10n.gearSummaryTitle,
            icon: const Icon(Icons.functions),
            onPressed: () => context.push('/gear/summary'),
          ),
          IconButton(
            tooltip: l10n.gearListsTitle,
            icon: const Icon(Icons.checklist),
            onPressed: () => context.push('/gear/lists'),
          ),
          PopupMenuButton<String>(
            onSelected: (path) => context.push(path),
            itemBuilder: (context) => [
              PopupMenuItem(
                value: '/gear/manage',
                child: Text(l10n.gearManageTitle),
              ),
              PopupMenuItem(
                value: '/gear/catalog',
                child: Text(l10n.gearCatalogTitle),
              ),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/gear/new'),
        icon: const Icon(Icons.add),
        label: Text(l10n.gearNew),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.m,
              AppSpacing.s,
              AppSpacing.m,
              0,
            ),
            child: TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                labelText: l10n.search,
                hintText: l10n.gearSearchHint,
              ),
              textInputAction: TextInputAction.search,
              onChanged: _search,
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.m,
              vertical: AppSpacing.s,
            ),
            child: Row(
              spacing: AppSpacing.s,
              children: [
                for (final (value, label) in [
                  (null, l10n.all),
                  ('active', l10n.gearStatusActive),
                  ('retired', l10n.gearStatusRetired),
                ])
                  ChoiceChip(
                    label: Text(label),
                    selected: filter.status == value,
                    onSelected: (_) =>
                        _update(filter.copyWith(status: () => value)),
                  ),
                if (types.isNotEmpty)
                  DropdownButton<String?>(
                    value: filter.typeId,
                    hint: Text(l10n.gearType),
                    underline: const SizedBox.shrink(),
                    items: [
                      DropdownMenuItem(
                        child: Text('${l10n.gearType}: ${l10n.all}'),
                      ),
                      for (final type in types)
                        DropdownMenuItem(
                          value: type.id,
                          child: Text(type.name),
                        ),
                    ],
                    onChanged: (value) =>
                        _update(filter.copyWith(typeId: () => value)),
                  ),
                for (final tag in tags)
                  FilterChip(
                    label: Text(tag.name),
                    selected: filter.tagIds.contains(tag.id),
                    onSelected: (selected) => _update(
                      filter.copyWith(
                        tagIds: selected
                            ? {...filter.tagIds, tag.id}
                            : filter.tagIds.difference({tag.id}),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: AsyncBody(
              value: items,
              onRetry: () => ref.invalidate(gearItemsProvider(filter)),
              builder: (loaded) => Column(
                children: [
                  if (loaded.offline) const OfflineBanner(),
                  Expanded(
                    child: loaded.value.isEmpty
                        ? Center(child: Text(l10n.gearEmpty))
                        : RefreshIndicator(
                            onRefresh: () =>
                                ref.refresh(gearItemsProvider(filter).future),
                            child: ListView.builder(
                              padding: const EdgeInsets.only(bottom: 88),
                              itemCount: loaded.value.length,
                              itemBuilder: (context, index) {
                                final item = loaded.value[index];
                                final details = [
                                  if (item.brand != null) item.brand!,
                                  if (typeNames[item.typeId] != null)
                                    typeNames[item.typeId]!,
                                ].join(' · ');
                                return ListTile(
                                  leading: ApiImage(
                                    path: '/gear/items/${item.id}/image',
                                    version: item.imageFileId,
                                    placeholder: Icons.backpack_outlined,
                                  ),
                                  title: Text(item.name),
                                  subtitle: details.isEmpty
                                      ? null
                                      : Text(details),
                                  trailing: Text(Format.weight(item.weightG)),
                                  onTap: () =>
                                      context.push('/gear/item/${item.id}'),
                                );
                              },
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
