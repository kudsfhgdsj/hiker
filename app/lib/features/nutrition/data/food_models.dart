final _barcodePattern = RegExp(r'^(\d{8}|\d{12,14})$');

/// EAN-8, UPC-A, EAN-13 or GTIN-14.
bool isValidBarcode(String text) => _barcodePattern.hasMatch(text);

class Food {
  const Food({
    this.id,
    this.catalogId,
    required this.name,
    this.brand,
    this.barcode,
    this.kcalPer100g,
    this.proteinG,
    this.carbsG,
    this.fatG,
    this.sugarG,
    this.saltG,
    this.servingSizeG,
    this.imageUrl,
    this.source = 'custom',
    this.visibility = 'private',
  });

  factory Food.fromJson(Map<String, dynamic> json) => Food(
    id: json['id'] as String?,
    catalogId: json['catalog_id'] as String?,
    name: json['name'] as String,
    brand: json['brand'] as String?,
    barcode: json['barcode'] as String?,
    kcalPer100g: (json['kcal_per_100g'] as num?)?.toDouble(),
    proteinG: (json['protein_g'] as num?)?.toDouble(),
    carbsG: (json['carbs_g'] as num?)?.toDouble(),
    fatG: (json['fat_g'] as num?)?.toDouble(),
    sugarG: (json['sugar_g'] as num?)?.toDouble(),
    saltG: (json['salt_g'] as num?)?.toDouble(),
    servingSizeG: (json['serving_size_g'] as num?)?.toDouble(),
    imageUrl: json['image_url'] as String?,
    source: json['source'] as String? ?? 'custom',
    visibility: json['visibility'] as String? ?? 'private',
  );

  final String? id;

  /// For an own food: the catalog entry it is a copy of or was proposed as.
  final String? catalogId;
  final String name;
  final String? brand;
  final String? barcode;
  final double? kcalPer100g;
  final double? proteinG;
  final double? carbsG;
  final double? fatG;
  final double? sugarG;
  final double? saltG;
  final double? servingSizeG;
  final String? imageUrl;

  /// `openfoodfacts` data is under the ODbL; the source must be named.
  final String source;

  /// `private`, `catalog_pending`, `catalog_rejected` or `catalog`.
  final String visibility;

  bool get isOwn => visibility == 'private';

  bool get isFromOpenFoodFacts => source == 'openfoodfacts';

  /// Calories of an amount in grams; null if the food has no calorie value.
  double? kcalFor(double grams) =>
      kcalPer100g == null ? null : kcalPer100g! * grams / 100;

  bool matches(String query) {
    final q = query.toLowerCase();
    return q.isEmpty ||
        name.toLowerCase().contains(q) ||
        (brand ?? '').toLowerCase().contains(q) ||
        barcode == query;
  }

  /// The fields the user edits.
  Map<String, dynamic> toJson() => {
    'name': name,
    'brand': brand,
    'barcode': barcode,
    'kcal_per_100g': kcalPer100g,
    'protein_g': proteinG,
    'carbs_g': carbsG,
    'fat_g': fatG,
    'sugar_g': sugarG,
    'salt_g': saltG,
    'serving_size_g': servingSizeG,
  };
}

/// Result of a barcode lookup.
sealed class BarcodeResult {
  const BarcodeResult();
}

class BarcodeFound extends BarcodeResult {
  const BarcodeFound(this.food, {this.offline = false});

  final Food food;
  final bool offline;
}

/// Nobody knows the product: offer the form for an own product.
class BarcodeUnknown extends BarcodeResult {
  const BarcodeUnknown();
}

/// The product database (or the server) cannot be reached right now.
class BarcodeUnavailable extends BarcodeResult {
  const BarcodeUnavailable();
}
