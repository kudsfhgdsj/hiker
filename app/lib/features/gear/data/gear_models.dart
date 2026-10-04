class GearType {
  const GearType({
    required this.id,
    required this.name,
    this.sortOrder = 0,
    this.standard = false,
    this.kind,
  });

  factory GearType.fromJson(Map<String, dynamic> json) => GearType(
    id: json['id'] as String,
    name: json['name'] as String,
    sortOrder: json['sort_order'] as int? ?? 0,
    standard: json['standard'] as bool? ?? false,
    kind: json['kind'] as String?,
  );

  final String id;
  final String name;
  final int sortOrder;

  /// Standard types are shared by all users and changed by admins only.
  final bool standard;

  /// Gives the items of this type extra fields, see [gearKinds].
  final String? kind;
}

/// An extra field of gear that depends on the kind of its type.
class GearAttribute {
  const GearAttribute(this.key, {this.options = const []});

  final String key;

  /// Empty: a number. Otherwise one of these values.
  final List<String> options;
}

/// The same definitions as on the server (`GET /gear/meta`), kept in the app
/// so that the form works offline.
const gearKinds = <String, List<GearAttribute>>{
  'backpack': [GearAttribute('volume_l')],
  'shoes': [
    GearAttribute('shoe_category', options: ['A', 'B', 'B/C', 'C', 'D']),
  ],
};

class GearTag {
  const GearTag({
    required this.id,
    required this.name,
    this.color,
    this.system,
  });

  static const favorite = 'favorite';

  factory GearTag.fromJson(Map<String, dynamic> json) => GearTag(
    id: json['id'] as String,
    name: json['name'] as String,
    color: json['color'] as String?,
    system: json['system'] as String?,
  );

  final String id;
  final String name;

  /// `#RRGGBB` or null.
  final String? color;

  /// Set for tags every user has and cannot delete, e.g. [favorite].
  final String? system;
}

class GearItem {
  const GearItem({
    this.id,
    required this.name,
    this.brand,
    this.typeId,
    this.weightG,
    this.purchaseDate,
    this.purchasePrice,
    this.currency,
    this.description,
    this.notes,
    this.websiteUrl,
    this.status = 'active',
    this.serialNumber,
    this.size,
    this.color,
    this.tagIds = const [],
    this.catalogId,
    this.imageFileId,
    this.attributes = const {},
  });

  factory GearItem.fromJson(Map<String, dynamic> json) => GearItem(
    id: json['id'] as String?,
    name: json['name'] as String,
    brand: json['brand'] as String?,
    typeId: json['type_id'] as String?,
    weightG: json['weight_g'] as int?,
    purchaseDate: json['purchase_date'] as String?,
    purchasePrice: (json['purchase_price'] as num?)?.toDouble(),
    currency: json['currency'] as String?,
    description: json['description'] as String?,
    notes: json['notes'] as String?,
    websiteUrl: json['website_url'] as String?,
    status: json['status'] as String? ?? 'active',
    serialNumber: json['serial_number'] as String?,
    size: json['size'] as String?,
    color: json['color'] as String?,
    tagIds: [...?(json['tag_ids'] as List<dynamic>?)?.cast<String>()],
    catalogId: json['catalog_id'] as String?,
    imageFileId: json['image_file_id'] as String?,
    attributes: {...?(json['attributes'] as Map<String, dynamic>?)},
  );

  final String? id;
  final String name;
  final String? brand;
  final String? typeId;
  final int? weightG;

  /// ISO date `yyyy-MM-dd`.
  final String? purchaseDate;

  /// Always in EUR.
  final double? purchasePrice;
  final String? currency;
  final String? description;
  final String? notes;
  final String? websiteUrl;
  final String status;
  final String? serialNumber;
  final String? size;
  final String? color;
  final List<String> tagIds;
  final String? catalogId;
  final String? imageFileId;

  /// Extra fields by kind of the type, e.g. `volume_l`.
  final Map<String, dynamic> attributes;

  /// The item with other tags, e.g. after the favourite star was tapped.
  GearItem withTags(List<String> tagIds) => GearItem(
    id: id,
    name: name,
    brand: brand,
    typeId: typeId,
    weightG: weightG,
    purchaseDate: purchaseDate,
    purchasePrice: purchasePrice,
    currency: currency,
    description: description,
    notes: notes,
    websiteUrl: websiteUrl,
    status: status,
    serialNumber: serialNumber,
    size: size,
    color: color,
    tagIds: tagIds,
    catalogId: catalogId,
    imageFileId: imageFileId,
    attributes: attributes,
  );

  /// The fields the user edits; `id`, catalog link and image are handled apart.
  Map<String, dynamic> toJson() => {
    'name': name,
    'brand': brand,
    'type_id': typeId,
    'weight_g': weightG,
    'purchase_date': purchaseDate,
    'purchase_price': purchasePrice,
    'description': description,
    'notes': notes,
    'website_url': websiteUrl,
    'status': status,
    'serial_number': serialNumber,
    'size': size,
    'color': color,
    'tag_ids': tagIds,
    'attributes': attributes,
  };
}

class GearFilter {
  const GearFilter({
    this.query = '',
    this.typeId,
    this.status,
    this.tagIds = const {},
  });

  final String query;
  final String? typeId;
  final String? status;
  final Set<String> tagIds;

  bool get isEmpty =>
      query.isEmpty && typeId == null && status == null && tagIds.isEmpty;

  Map<String, dynamic> toQuery() => {
    if (query.isNotEmpty) 'q': query,
    'type_id': ?typeId,
    'status': ?status,
    if (tagIds.isNotEmpty) 'tag_id': tagIds.toList(),
  };

  /// The same rule as on the server, for the offline copy.
  bool matches(GearItem item) {
    final q = query.toLowerCase();
    final inText =
        q.isEmpty ||
        item.name.toLowerCase().contains(q) ||
        (item.brand ?? '').toLowerCase().contains(q);
    return inText &&
        (typeId == null || item.typeId == typeId) &&
        (status == null || item.status == status) &&
        tagIds.every(item.tagIds.contains);
  }

  GearFilter copyWith({
    String? query,
    String? Function()? typeId,
    String? Function()? status,
    Set<String>? tagIds,
  }) => GearFilter(
    query: query ?? this.query,
    typeId: typeId == null ? this.typeId : typeId(),
    status: status == null ? this.status : status(),
    tagIds: tagIds ?? this.tagIds,
  );

  @override
  bool operator ==(Object other) =>
      other is GearFilter &&
      other.query == query &&
      other.typeId == typeId &&
      other.status == status &&
      other.tagIds.length == tagIds.length &&
      other.tagIds.containsAll(tagIds);

  @override
  int get hashCode =>
      Object.hash(query, typeId, status, Object.hashAllUnordered(tagIds));
}

class MoneyTotal {
  const MoneyTotal(this.currency, this.amount);

  final String currency;
  final double amount;
}

class GearTotals {
  const GearTotals({
    required this.itemCount,
    required this.weightG,
    required this.itemsWithoutWeight,
    required this.value,
    required this.itemsWithoutPrice,
    this.key,
    this.label,
  });

  factory GearTotals.fromJson(Map<String, dynamic> json) => GearTotals(
    itemCount: json['item_count'] as int,
    weightG: json['weight_g'] as int,
    itemsWithoutWeight: json['items_without_weight'] as int,
    value: [
      for (final v in json['value'] as List<dynamic>)
        MoneyTotal(
          (v as Map<String, dynamic>)['currency'] as String,
          (v['amount'] as num).toDouble(),
        ),
    ],
    itemsWithoutPrice: json['items_without_price'] as int,
    key: json['key'] as String?,
    label: json['label'] as String?,
  );

  final int itemCount;
  final int weightG;
  final int itemsWithoutWeight;

  /// One sum per currency; currencies are never converted.
  final List<MoneyTotal> value;
  final int itemsWithoutPrice;
  final String? key;
  final String? label;
}

class GearSummary {
  const GearSummary({required this.total, required this.groups});

  factory GearSummary.fromJson(Map<String, dynamic> json) => GearSummary(
    total: GearTotals.fromJson(json['total'] as Map<String, dynamic>),
    groups: [
      for (final g in json['groups'] as List<dynamic>)
        GearTotals.fromJson(g as Map<String, dynamic>),
    ],
  );

  final GearTotals total;
  final List<GearTotals> groups;
}

class GearListEntry {
  const GearListEntry({required this.gearItemId, this.quantity = 1});

  final String gearItemId;
  final int quantity;

  Map<String, dynamic> toJson() => {
    'gear_item_id': gearItemId,
    'quantity': quantity,
  };
}

class GearPackList {
  const GearPackList({
    this.id,
    required this.name,
    this.description,
    this.entries = const [],
    this.totalWeightG = 0,
  });

  factory GearPackList.fromJson(Map<String, dynamic> json) => GearPackList(
    id: json['id'] as String?,
    name: json['name'] as String,
    description: json['description'] as String?,
    entries: [
      for (final e in json['entries'] as List<dynamic>)
        GearListEntry(
          gearItemId: (e as Map<String, dynamic>)['gear_item_id'] as String,
          quantity: e['quantity'] as int,
        ),
    ],
    totalWeightG: json['total_weight_g'] as int? ?? 0,
  );

  final String? id;
  final String name;
  final String? description;
  final List<GearListEntry> entries;
  final int totalWeightG;

  Map<String, dynamic> toJson() => {
    'name': name,
    'description': description,
    'entries': [for (final entry in entries) entry.toJson()],
  };
}

class CatalogItem {
  const CatalogItem({
    required this.id,
    required this.name,
    this.brand,
    this.typeId,
    this.nominalWeightG,
    this.websiteUrl,
    this.imageFileId,
    required this.status,
  });

  factory CatalogItem.fromJson(Map<String, dynamic> json) => CatalogItem(
    id: json['id'] as String,
    name: json['name'] as String,
    brand: json['brand'] as String?,
    typeId: json['type_id'] as String?,
    nominalWeightG: json['nominal_weight_g'] as int?,
    websiteUrl: json['website_url'] as String?,
    imageFileId: json['image_file_id'] as String?,
    status: json['status'] as String,
  );

  final String id;
  final String name;
  final String? brand;
  final String? typeId;
  final int? nominalWeightG;
  final String? websiteUrl;
  final String? imageFileId;
  final String status;
}
