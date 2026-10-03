import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/app_localizations.dart';
import '../data/food_models.dart';

/// Product image from Open Food Facts, or a placeholder.
class FoodImage extends StatelessWidget {
  const FoodImage({super.key, required this.food, this.size = 48});

  final Food food;
  final double size;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final placeholder = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(Icons.restaurant, color: scheme.onSurfaceVariant),
    );
    final url = food.imageUrl;
    if (url == null) return placeholder;
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Image.network(
        url,
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stack) => placeholder,
      ),
    );
  }
}

/// Nutrition values of a food per 100 g.
class NutritionTable extends StatelessWidget {
  const NutritionTable({super.key, required this.food});

  final Food food;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    String grams(double? value) =>
        value == null ? '–' : '${Format.number(value)} g';
    final rows = [
      (
        l10n.foodKcal,
        food.kcalPer100g == null
            ? '–'
            : l10n.foodKcalValue(Format.number(food.kcalPer100g!)),
      ),
      (l10n.foodProtein, grams(food.proteinG)),
      (l10n.foodCarbs, grams(food.carbsG)),
      (l10n.foodSugar, grams(food.sugarG)),
      (l10n.foodFat, grams(food.fatG)),
      (l10n.foodSalt, grams(food.saltG)),
      if (food.servingSizeG != null)
        (l10n.foodServing, grams(food.servingSizeG)),
    ];
    return Column(
      children: [
        for (final (label, value) in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              children: [
                Expanded(child: Text(label)),
                const SizedBox(width: AppSpacing.s),
                Text(value),
              ],
            ),
          ),
      ],
    );
  }
}

/// Card with the details of a food; own foods can be edited, catalog entries
/// can be saved as an own corrected copy.
Future<void> showFoodSheet(BuildContext context, Food food) =>
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) {
        final l10n = AppLocalizations.of(sheetContext);
        final theme = Theme.of(sheetContext);
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.l,
              0,
              AppSpacing.l,
              AppSpacing.l,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    FoodImage(food: food, size: 72),
                    const SizedBox(width: AppSpacing.m),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(food.name, style: theme.textTheme.titleLarge),
                          if (food.brand != null) Text(food.brand!),
                          if (food.barcode != null)
                            Text(
                              food.barcode!,
                              style: theme.textTheme.bodySmall,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.m),
                Text(l10n.foodPer100g, style: theme.textTheme.labelLarge),
                NutritionTable(food: food),
                if (food.isFromOpenFoodFacts) ...[
                  const SizedBox(height: AppSpacing.s),
                  // Open Food Facts data is licensed under the ODbL: name the source.
                  Text(l10n.foodSourceOff, style: theme.textTheme.bodySmall),
                ],
                const SizedBox(height: AppSpacing.m),
                FilledButton.tonal(
                  onPressed: () {
                    Navigator.pop(sheetContext);
                    context.push('/nutrition/edit', extra: food);
                  },
                  child: Text(food.isOwn ? l10n.edit : l10n.foodCorrect),
                ),
              ],
            ),
          ),
        );
      },
    );
