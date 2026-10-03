import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/food_models.dart';
import '../data/food_repository.dart';

/// Creates or edits an own food. Opened with a catalog entry, it saves the
/// changes as the user's own copy and leaves the catalog entry untouched.
class FoodFormScreen extends ConsumerStatefulWidget {
  const FoodFormScreen({super.key, this.initial});

  final Food? initial;

  @override
  ConsumerState<FoodFormScreen> createState() => _FoodFormScreenState();
}

class _FoodFormScreenState extends ConsumerState<FoodFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final Food _food = widget.initial ?? const Food(name: '');
  late final _name = TextEditingController(text: _food.name);
  late final _brand = TextEditingController(text: _food.brand);
  late final _barcode = TextEditingController(text: _food.barcode);
  late final _kcal = TextEditingController(
    text: Format.input(_food.kcalPer100g),
  );
  late final _protein = TextEditingController(
    text: Format.input(_food.proteinG),
  );
  late final _carbs = TextEditingController(text: Format.input(_food.carbsG));
  late final _sugar = TextEditingController(text: Format.input(_food.sugarG));
  late final _fat = TextEditingController(text: Format.input(_food.fatG));
  late final _salt = TextEditingController(text: Format.input(_food.saltG));
  late final _serving = TextEditingController(
    text: Format.input(_food.servingSizeG),
  );
  bool _busy = false;
  Object? _error;

  /// An existing own food is updated; anything else becomes a new own food.
  bool get _isUpdate => _food.id != null && _food.isOwn;

  /// A catalog entry that gets an own corrected copy.
  bool get _isCorrection => _food.id != null && !_food.isOwn;

  @override
  void dispose() {
    for (final c in [
      _name,
      _brand,
      _barcode,
      _kcal,
      _protein,
      _carbs,
      _sugar,
      _fat,
      _salt,
      _serving,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  static String? _text(TextEditingController c) =>
      c.text.trim().isEmpty ? null : c.text.trim();

  double? _value(TextEditingController c) => Format.parseNumber(c.text);

  String? Function(String?) _per100g(AppLocalizations l10n) => (value) {
    if ((value ?? '').trim().isEmpty) return null;
    final number = Format.parseNumber(value!);
    return number == null || number < 0 || number > 100
        ? l10n.foodPer100gInvalid
        : null;
  };

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
    final router = GoRouter.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    final food = Food(
      id: _isUpdate ? _food.id : null,
      name: _name.text.trim(),
      brand: _text(_brand),
      barcode: _text(_barcode),
      kcalPer100g: _value(_kcal),
      proteinG: _value(_protein),
      carbsG: _value(_carbs),
      sugarG: _value(_sugar),
      fatG: _value(_fat),
      saltG: _value(_salt),
      servingSizeG: _value(_serving),
    );
    await _run(() async {
      await ref
          .read(foodRepositoryProvider)
          .save(food, catalogId: _isCorrection ? _food.id : null);
      ref.invalidate(foodSearchProvider);
      messenger.showSnackBar(SnackBar(content: Text(l10n.saved)));
      router.pop();
    });
  }

  Future<void> _delete() async {
    final router = GoRouter.of(context);
    if (!await confirmDelete(context, _food.name)) return;
    await _run(() async {
      await ref.read(foodRepositoryProvider).delete(_food.id!);
      ref.invalidate(foodSearchProvider);
      router.pop();
    });
  }

  Future<void> _propose() async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    await _run(() async {
      await ref.read(foodRepositoryProvider).propose(_food.id!);
      messenger.showSnackBar(SnackBar(content: Text(l10n.foodProposed)));
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    const gap = SizedBox(height: AppSpacing.m);
    const decimal = TextInputType.numberWithOptions(decimal: true);
    final per100g = _per100g(l10n);

    Widget pair(Widget left, Widget right) => Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: left),
        const SizedBox(width: AppSpacing.s),
        Expanded(child: right),
      ],
    );

    return Scaffold(
      appBar: AppBar(title: Text(_isUpdate ? l10n.foodEdit : l10n.foodNew)),
      body: Form(
        key: _formKey,
        child: CenteredForm(
          children: [
            if (_isCorrection) ...[
              Text(
                l10n.foodCorrectHint,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              gap,
            ],
            TextFormField(
              controller: _name,
              decoration: InputDecoration(labelText: l10n.name),
              validator: (v) =>
                  (v ?? '').trim().isEmpty ? l10n.requiredField : null,
            ),
            gap,
            TextFormField(
              controller: _brand,
              decoration: InputDecoration(labelText: l10n.foodBrand),
            ),
            gap,
            TextFormField(
              controller: _barcode,
              decoration: InputDecoration(labelText: l10n.foodBarcode),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (v) =>
                  (v ?? '').trim().isEmpty || isValidBarcode(v!.trim())
                  ? null
                  : l10n.foodBarcodeInvalid,
            ),
            gap,
            TextFormField(
              controller: _kcal,
              decoration: InputDecoration(labelText: l10n.foodKcal),
              keyboardType: decimal,
              validator: (value) {
                final number = Format.parseNumber(value ?? '');
                return number == null || number < 0 || number > 900
                    ? l10n.foodKcalInvalid
                    : null;
              },
            ),
            gap,
            pair(
              TextFormField(
                controller: _protein,
                decoration: InputDecoration(labelText: l10n.foodProtein),
                keyboardType: decimal,
                validator: (value) {
                  final basic = per100g(value);
                  if (basic != null) return basic;
                  final sum =
                      (_value(_protein) ?? 0) +
                      (_value(_carbs) ?? 0) +
                      (_value(_fat) ?? 0);
                  return sum > 100.5 ? l10n.foodMacrosAbove100 : null;
                },
              ),
              TextFormField(
                controller: _fat,
                decoration: InputDecoration(labelText: l10n.foodFat),
                keyboardType: decimal,
                validator: per100g,
              ),
            ),
            gap,
            pair(
              TextFormField(
                controller: _carbs,
                decoration: InputDecoration(labelText: l10n.foodCarbs),
                keyboardType: decimal,
                validator: per100g,
              ),
              TextFormField(
                controller: _sugar,
                decoration: InputDecoration(labelText: l10n.foodSugar),
                keyboardType: decimal,
                validator: (value) {
                  final basic = per100g(value);
                  if (basic != null) return basic;
                  final sugar = _value(_sugar);
                  final carbs = _value(_carbs);
                  return sugar != null && carbs != null && sugar > carbs
                      ? l10n.foodSugarAboveCarbs
                      : null;
                },
              ),
            ),
            gap,
            pair(
              TextFormField(
                controller: _salt,
                decoration: InputDecoration(labelText: l10n.foodSalt),
                keyboardType: decimal,
                validator: per100g,
              ),
              TextFormField(
                controller: _serving,
                decoration: InputDecoration(labelText: l10n.foodServing),
                keyboardType: decimal,
                validator: (value) {
                  if ((value ?? '').trim().isEmpty) return null;
                  final number = Format.parseNumber(value!);
                  return number == null || number <= 0 || number > 5000
                      ? l10n.invalidNumber
                      : null;
                },
              ),
            ),
            if (_error != null) ...[gap, ErrorText(_error!)],
            const SizedBox(height: AppSpacing.l),
            FilledButton(
              onPressed: _busy ? null : _save,
              child: Text(_isCorrection ? l10n.foodCorrect : l10n.save),
            ),
            if (_isUpdate) ...[
              const SizedBox(height: AppSpacing.s),
              OutlinedButton.icon(
                onPressed: _busy ? null : _propose,
                icon: const Icon(Icons.share_outlined),
                label: Text(l10n.foodProposeToCatalog),
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
      ),
    );
  }
}
