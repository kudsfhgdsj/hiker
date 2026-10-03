import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/api_image.dart';
import '../../../core/widgets/error_text.dart';
import '../../../core/widgets/file_pick.dart';
import '../../../l10n/app_localizations.dart';
import '../data/gear_models.dart';
import '../data/gear_repository.dart';

/// Loads the item to edit; a new item starts empty.
final _itemProvider = FutureProvider.autoDispose.family<GearItem, String?>(
  (ref, id) async => id == null
      ? const GearItem(name: '')
      : ref.watch(gearRepositoryProvider).getItem(id),
);

class GearItemScreen extends ConsumerWidget {
  const GearItemScreen({super.key, this.itemId});

  final String? itemId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(itemId == null ? l10n.gearNew : l10n.gearEdit),
      ),
      body: AsyncBody(
        value: ref.watch(_itemProvider(itemId)),
        onRetry: () => ref.invalidate(_itemProvider(itemId)),
        builder: (item) => _GearItemForm(initial: item),
      ),
    );
  }
}

class _GearItemForm extends ConsumerStatefulWidget {
  const _GearItemForm({required this.initial});

  final GearItem initial;

  @override
  ConsumerState<_GearItemForm> createState() => _GearItemFormState();
}

class _GearItemFormState extends ConsumerState<_GearItemForm> {
  final _formKey = GlobalKey<FormState>();
  late GearItem _item = widget.initial;
  late final _name = TextEditingController(text: _item.name);
  late final _brand = TextEditingController(text: _item.brand);
  late final _weight = TextEditingController(text: Format.input(_item.weightG));
  late final _price = TextEditingController(
    text: Format.input(_item.purchasePrice),
  );
  late final _currency = TextEditingController(text: _item.currency);
  late final _description = TextEditingController(text: _item.description);
  late final _notes = TextEditingController(text: _item.notes);
  late final _website = TextEditingController(text: _item.websiteUrl);
  late final _serial = TextEditingController(text: _item.serialNumber);
  late final _size = TextEditingController(text: _item.size);
  late final _color = TextEditingController(text: _item.color);
  late String? _typeId = _item.typeId;
  late String _status = _item.status;
  late String? _purchaseDate = _item.purchaseDate;
  late Set<String> _tagIds = {..._item.tagIds};
  String? _catalogId;
  bool _busy = false;
  Object? _error;

  List<TextEditingController> get _controllers => [
    _name,
    _brand,
    _weight,
    _price,
    _currency,
    _description,
    _notes,
    _website,
    _serial,
    _size,
    _color, //
  ];

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  static String? _text(TextEditingController controller) {
    final text = controller.text.trim();
    return text.isEmpty ? null : text;
  }

  GearItem _collect() => GearItem(
    id: _item.id,
    name: _name.text.trim(),
    brand: _text(_brand),
    typeId: _typeId,
    weightG: Format.parseNumber(_weight.text)?.round(),
    purchaseDate: _purchaseDate,
    purchasePrice: Format.parseNumber(_price.text),
    currency: _text(_currency)?.toUpperCase(),
    description: _text(_description),
    notes: _text(_notes),
    websiteUrl: _text(_website),
    status: _status,
    serialNumber: _text(_serial),
    size: _text(_size),
    color: _text(_color),
    tagIds: _tagIds.toList(),
  );

  void _refreshLists() {
    ref.invalidate(gearItemsProvider);
    ref.invalidate(gearSummaryProvider);
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);
    await _run(() async {
      await ref
          .read(gearRepositoryProvider)
          .saveItem(_collect(), catalogId: _catalogId);
      _refreshLists();
      messenger.showSnackBar(SnackBar(content: Text(l10n.saved)));
      router.pop();
    });
  }

  Future<void> _delete() async {
    final router = GoRouter.of(context);
    if (!await confirmDelete(context, _item.name)) return;
    await _run(() async {
      await ref.read(gearRepositoryProvider).deleteItem(_item.id!);
      _refreshLists();
      router.pop();
    });
  }

  Future<void> _chooseImage() async {
    final files = await ref.read(filePickerProvider)(
      extensions: imageExtensions,
    );
    if (files.isEmpty) return;
    await _run(() async {
      final updated = await ref
          .read(gearRepositoryProvider)
          .uploadImage(_item.id!, files.first.bytes, files.first.name);
      _refreshLists();
      setState(() => _item = updated);
    });
  }

  Future<void> _removeImage() => _run(() async {
    await ref.read(gearRepositoryProvider).removeImage(_item.id!);
    _refreshLists();
    setState(
      () => _item = GearItem.fromJson({..._item.toJson(), 'id': _item.id}),
    );
  });

  Future<void> _propose() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    await _run(() async {
      await ref.read(gearRepositoryProvider).propose(_item.id!);
      messenger.showSnackBar(SnackBar(content: Text(l10n.gearProposed)));
    });
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.tryParse(_purchaseDate ?? '') ?? now,
      firstDate: DateTime(1970),
      lastDate: now,
    );
    if (picked != null) {
      setState(() => _purchaseDate = picked.toIso8601String().substring(0, 10));
    }
  }

  Future<void> _useCatalogEntry() async {
    final entry = await showDialog<CatalogItem>(
      context: context,
      builder: (context) => const _CatalogSearchDialog(),
    );
    if (entry == null) return;
    setState(() {
      // A copy: the fields can be changed, later catalog changes do not reach the item.
      _catalogId = entry.id;
      _name.text = entry.name;
      _brand.text = entry.brand ?? '';
      _weight.text = Format.input(entry.nominalWeightG);
      _website.text = entry.websiteUrl ?? '';
      _typeId = entry.typeId;
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final types =
        ref.watch(gearTypesProvider).asData?.value.value ?? const <GearType>[];
    final tags =
        ref.watch(gearTagsProvider).asData?.value.value ?? const <GearTag>[];
    final isNew = _item.id == null;
    const gap = SizedBox(height: AppSpacing.m);
    final date = DateTime.tryParse(_purchaseDate ?? '');

    return Form(
      key: _formKey,
      child: CenteredForm(
        children: [
          if (isNew)
            OutlinedButton.icon(
              onPressed: _useCatalogEntry,
              icon: const Icon(Icons.library_books_outlined),
              label: Text(l10n.gearFromCatalog),
            )
          else
            Row(
              children: [
                ApiImage(
                  path: '/gear/items/${_item.id}/image',
                  version: _item.imageFileId,
                  size: 96,
                  placeholder: Icons.backpack_outlined,
                ),
                const SizedBox(width: AppSpacing.m),
                Expanded(
                  child: Wrap(
                    spacing: AppSpacing.s,
                    children: [
                      OutlinedButton(
                        onPressed: _busy ? null : _chooseImage,
                        child: Text(l10n.gearImageChoose),
                      ),
                      if (_item.imageFileId != null)
                        TextButton(
                          onPressed: _busy ? null : _removeImage,
                          child: Text(l10n.gearImageRemove),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          gap,
          TextFormField(
            controller: _name,
            decoration: InputDecoration(labelText: l10n.name),
            validator: (v) =>
                (v ?? '').trim().isEmpty ? l10n.requiredField : null,
          ),
          gap,
          TextFormField(
            controller: _brand,
            decoration: InputDecoration(labelText: l10n.gearBrand),
          ),
          gap,
          DropdownButtonFormField<String?>(
            initialValue: types.any((t) => t.id == _typeId) ? _typeId : null,
            decoration: InputDecoration(labelText: l10n.gearType),
            items: [
              DropdownMenuItem(child: Text(l10n.gearNoType)),
              for (final type in types)
                DropdownMenuItem(value: type.id, child: Text(type.name)),
            ],
            onChanged: (value) => setState(() => _typeId = value),
          ),
          gap,
          TextFormField(
            controller: _weight,
            decoration: InputDecoration(labelText: l10n.gearWeight),
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          ),
          gap,
          if (tags.isNotEmpty) ...[
            InputDecorator(
              decoration: InputDecoration(labelText: l10n.gearTags),
              child: Wrap(
                spacing: AppSpacing.s,
                children: [
                  for (final tag in tags)
                    FilterChip(
                      label: Text(tag.name),
                      selected: _tagIds.contains(tag.id),
                      onSelected: (selected) => setState(
                        () => _tagIds = selected
                            ? {..._tagIds, tag.id}
                            : _tagIds.difference({tag.id}),
                      ),
                    ),
                ],
              ),
            ),
            gap,
          ],
          SegmentedButton<String>(
            segments: [
              ButtonSegment(
                value: 'active',
                label: Text(l10n.gearStatusActive),
              ),
              ButtonSegment(
                value: 'retired',
                label: Text(l10n.gearStatusRetired),
              ),
            ],
            selected: {_status},
            onSelectionChanged: (value) =>
                setState(() => _status = value.first),
          ),
          gap,
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 2,
                child: TextFormField(
                  controller: _price,
                  decoration: InputDecoration(
                    labelText: l10n.gearPurchasePrice,
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  validator: (value) {
                    if ((value ?? '').trim().isEmpty) return null;
                    final number = Format.parseNumber(value!);
                    final cents = number == null ? null : number * 100;
                    final valid =
                        number != null &&
                        number >= 0 &&
                        number <= 1000000 &&
                        (cents! - cents.round()).abs() < 1e-6;
                    return valid ? null : l10n.gearPriceInvalid;
                  },
                ),
              ),
              const SizedBox(width: AppSpacing.s),
              Expanded(
                child: TextFormField(
                  controller: _currency,
                  decoration: InputDecoration(
                    labelText: l10n.gearCurrency,
                    hintText: 'CHF',
                  ),
                  textCapitalization: TextCapitalization.characters,
                  validator: (value) {
                    final text = (value ?? '').trim().toUpperCase();
                    if (text.isEmpty) {
                      return _price.text.trim().isEmpty
                          ? null
                          : l10n.gearCurrencyRequired;
                    }
                    return RegExp(r'^[A-Z]{3}$').hasMatch(text)
                        ? null
                        : l10n.gearCurrencyInvalid;
                  },
                ),
              ),
            ],
          ),
          gap,
          InkWell(
            onTap: _pickDate,
            child: InputDecorator(
              decoration: InputDecoration(
                labelText: l10n.gearPurchaseDate,
                suffixIcon: _purchaseDate == null
                    ? const Icon(Icons.calendar_today)
                    : IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () => setState(() => _purchaseDate = null),
                      ),
              ),
              child: Text(date == null ? '' : Format.date(date)),
            ),
          ),
          gap,
          TextFormField(
            controller: _description,
            decoration: InputDecoration(labelText: l10n.gearDescription),
            maxLines: null,
          ),
          gap,
          TextFormField(
            controller: _notes,
            decoration: InputDecoration(labelText: l10n.gearNotes),
            maxLines: null,
          ),
          gap,
          TextFormField(
            controller: _website,
            decoration: InputDecoration(labelText: l10n.gearWebsite),
            keyboardType: TextInputType.url,
            validator: (value) {
              final text = (value ?? '').trim();
              return text.isEmpty || RegExp(r'^https?://\S+$').hasMatch(text)
                  ? null
                  : l10n.gearWebsiteInvalid;
            },
          ),
          gap,
          TextFormField(
            controller: _serial,
            decoration: InputDecoration(labelText: l10n.gearSerialNumber),
          ),
          gap,
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _size,
                  decoration: InputDecoration(labelText: l10n.gearSize),
                ),
              ),
              const SizedBox(width: AppSpacing.s),
              Expanded(
                child: TextFormField(
                  controller: _color,
                  decoration: InputDecoration(labelText: l10n.gearColor),
                ),
              ),
            ],
          ),
          if (_error != null) ...[gap, ErrorText(_error!)],
          const SizedBox(height: AppSpacing.l),
          FilledButton(onPressed: _busy ? null : _save, child: Text(l10n.save)),
          if (!isNew) ...[
            const SizedBox(height: AppSpacing.s),
            OutlinedButton.icon(
              onPressed: _busy ? null : _propose,
              icon: const Icon(Icons.share_outlined),
              label: Text(l10n.gearProposeToCatalog),
            ),
            const SizedBox(height: AppSpacing.s),
            TextButton.icon(
              onPressed: _busy ? null : _delete,
              icon: const Icon(Icons.delete_outline),
              label: Text(l10n.delete),
            ),
          ],
        ],
      ),
    );
  }
}

class _CatalogSearchDialog extends ConsumerStatefulWidget {
  const _CatalogSearchDialog();

  @override
  ConsumerState<_CatalogSearchDialog> createState() =>
      _CatalogSearchDialogState();
}

class _CatalogSearchDialogState extends ConsumerState<_CatalogSearchDialog> {
  late Future<List<CatalogItem>> _results = _search('');

  Future<List<CatalogItem>> _search(String query) =>
      ref.read(gearRepositoryProvider).searchCatalog(query.trim());

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.gearFromCatalog),
      content: SizedBox(
        width: AppSpacing.maxContentWidth,
        height: 360,
        child: Column(
          children: [
            TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                hintText: l10n.gearCatalogSearchHint,
              ),
              textInputAction: TextInputAction.search,
              onSubmitted: (text) => setState(() => _results = _search(text)),
            ),
            Expanded(
              child: FutureBuilder(
                future: _results,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return Center(child: ErrorText(snapshot.error!));
                  }
                  if (!snapshot.hasData) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final entries = snapshot.data!;
                  if (entries.isEmpty) {
                    return Center(child: Text(l10n.gearCatalogEmpty));
                  }
                  return ListView(
                    children: [
                      for (final entry in entries)
                        ListTile(
                          title: Text(entry.name),
                          subtitle: entry.brand == null
                              ? null
                              : Text(entry.brand!),
                          trailing: Text(Format.weight(entry.nominalWeightG)),
                          onTap: () => Navigator.pop(context, entry),
                        ),
                    ],
                  );
                },
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
      ],
    );
  }
}
