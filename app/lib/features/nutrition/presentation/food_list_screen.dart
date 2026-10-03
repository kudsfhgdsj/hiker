import 'dart:async';

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
import 'barcode_scanner.dart';
import 'food_widgets.dart';

class FoodListScreen extends ConsumerStatefulWidget {
  const FoodListScreen({super.key});

  @override
  ConsumerState<FoodListScreen> createState() => _FoodListScreenState();
}

class _FoodListScreenState extends ConsumerState<FoodListScreen> {
  Timer? _debounce;
  String _query = '';

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _search(String text) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _query = text.trim());
    });
  }

  Future<void> _scan() async {
    final scan = ref.read(barcodeScannerProvider);
    final barcode = scan == null ? await _typeBarcode() : await scan(context);
    if (barcode != null && mounted) await _lookup(barcode);
  }

  Future<String?> _typeBarcode() => showDialog<String>(
    context: context,
    builder: (context) => const _BarcodeDialog(),
  );

  /// Barcode → own food, catalog or Open Food Facts; otherwise offer the form.
  Future<void> _lookup(String barcode) async {
    final l10n = AppLocalizations.of(context);
    final BarcodeResult result;
    try {
      result = await ref.read(foodRepositoryProvider).lookupBarcode(barcode);
    } catch (error) {
      if (mounted) showError(context, error);
      return;
    }
    if (!mounted) return;
    switch (result) {
      case BarcodeFound(:final food):
        await showFoodSheet(context, food);
      case BarcodeUnknown() || BarcodeUnavailable():
        final create = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(l10n.foodNotFoundTitle),
            content: Text(
              result is BarcodeUnknown
                  ? l10n.foodNotFoundBody
                  : l10n.foodSourceUnavailable,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: Text(l10n.cancel),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: Text(l10n.foodCreateOwn),
              ),
            ],
          ),
        );
        if ((create ?? false) && mounted) {
          await context.push(
            '/nutrition/new',
            extra: Food(name: '', barcode: barcode),
          );
        }
    }
    ref.invalidate(foodSearchProvider);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final hasCamera = ref.watch(barcodeScannerProvider) != null;
    final results = ref.watch(foodSearchProvider(_query));
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.foodTitle),
        actions: [
          if (hasCamera)
            IconButton(
              tooltip: l10n.foodEnterBarcode,
              icon: const Icon(Icons.dialpad),
              onPressed: () async {
                final barcode = await _typeBarcode();
                if (barcode != null && mounted) await _lookup(barcode);
              },
            ),
          IconButton(
            tooltip: l10n.foodCatalogTitle,
            icon: const Icon(Icons.library_books_outlined),
            onPressed: () => context.push('/nutrition/catalog'),
          ),
          IconButton(
            tooltip: l10n.foodNew,
            icon: const Icon(Icons.add),
            onPressed: () => context.push('/nutrition/new'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _scan,
        icon: const Icon(Icons.qr_code_scanner),
        label: Text(hasCamera ? l10n.foodScan : l10n.foodEnterBarcode),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.m),
            child: TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                labelText: l10n.search,
                hintText: l10n.foodSearchHint,
              ),
              textInputAction: TextInputAction.search,
              onChanged: _search,
            ),
          ),
          Expanded(
            child: AsyncBody(
              value: results,
              onRetry: () => ref.invalidate(foodSearchProvider(_query)),
              builder: (loaded) => Column(
                children: [
                  if (loaded.offline) const OfflineBanner(),
                  Expanded(
                    child: loaded.value.isEmpty
                        ? Center(child: Text(l10n.foodEmpty))
                        : ListView.builder(
                            padding: const EdgeInsets.only(bottom: 88),
                            itemCount: loaded.value.length,
                            itemBuilder: (context, index) {
                              final food = loaded.value[index];
                              return ListTile(
                                leading: FoodImage(food: food),
                                title: Text(food.name),
                                subtitle: Text(
                                  [
                                    if (food.brand != null) food.brand!,
                                    food.isOwn
                                        ? l10n.foodOwn
                                        : l10n.foodCatalog,
                                  ].join(' · '),
                                ),
                                trailing: food.kcalPer100g == null
                                    ? null
                                    : Text(
                                        l10n.foodKcalValue(
                                          Format.number(food.kcalPer100g!),
                                        ),
                                      ),
                                onTap: () async {
                                  await showFoodSheet(context, food);
                                  ref.invalidate(foodSearchProvider);
                                },
                              );
                            },
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

class _BarcodeDialog extends StatefulWidget {
  const _BarcodeDialog();

  @override
  State<_BarcodeDialog> createState() => _BarcodeDialogState();
}

class _BarcodeDialogState extends State<_BarcodeDialog> {
  final _formKey = GlobalKey<FormState>();
  final _barcode = TextEditingController();

  @override
  void dispose() {
    _barcode.dispose();
    super.dispose();
  }

  void _submit() {
    if (_formKey.currentState!.validate()) {
      Navigator.pop(context, _barcode.text.trim());
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.foodEnterBarcode),
      content: Form(
        key: _formKey,
        child: TextFormField(
          controller: _barcode,
          autofocus: true,
          decoration: InputDecoration(labelText: l10n.foodBarcode),
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          validator: (v) =>
              isValidBarcode((v ?? '').trim()) ? null : l10n.foodBarcodeInvalid,
          onFieldSubmitted: (_) => _submit(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(onPressed: _submit, child: Text(l10n.search)),
      ],
    );
  }
}
