import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/db/app_database.dart';
import '../../../core/loaded.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import 'food_models.dart';

/// Foods of the user and the shared catalog. Everything the app has seen is
/// kept on the device, so that search and barcode lookup also work offline.
class FoodRepository {
  const FoodRepository(this._dio, this._db);

  final Dio _dio;
  final AppDatabase _db;

  /// The user's own foods (replaced as a whole when the list is loaded).
  static const _own = 'foods';

  /// Catalog entries the app came across (search results, scans).
  static const _seen = 'foods_seen';
  static const _pageSize = 200;

  Future<List<Map<String, dynamic>>> _allPages(
    String path,
    Map<String, dynamic> query,
  ) async {
    final result = <Map<String, dynamic>>[];
    while (true) {
      final response = await apiCall(
        () => _dio.get<Map<String, dynamic>>(
          path,
          queryParameters: {
            ...query,
            'limit': _pageSize,
            'offset': result.length,
          },
        ),
      );
      final items = (response.data!['items'] as List<dynamic>)
          .cast<Map<String, dynamic>>();
      result.addAll(items);
      if (items.length < _pageSize ||
          result.length >= (response.data!['total'] as int)) {
        return result;
      }
    }
  }

  Future<void> _remember(Map<String, dynamic> document) {
    final own = document['visibility'] == 'private';
    return _db.putDocument(
      own ? _own : _seen,
      document['id'] as String,
      document,
    );
  }

  Future<List<Food>> _cached(String query) async {
    final documents = [
      ...await _db.listDocuments(_own),
      ...await _db.listDocuments(_seen),
    ];
    final foods =
        documents.map(Food.fromJson).where((f) => f.matches(query)).toList()
          ..sort((a, b) {
            if (a.isOwn != b.isOwn) return a.isOwn ? -1 : 1;
            return a.name.toLowerCase().compareTo(b.name.toLowerCase());
          });
    return foods;
  }

  /// Own foods first, then the catalog.
  Future<Loaded<List<Food>>> search(String query) async {
    try {
      final documents = await _allPages('/nutrition/search', {
        if (query.isNotEmpty) 'q': query,
      });
      if (query.isEmpty) {
        await _db.replaceCollection(
          _own,
          documents.where((d) => d['visibility'] == 'private'),
        );
      }
      for (final document in documents) {
        await _remember(document);
      }
      return Loaded([for (final d in documents) Food.fromJson(d)]);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      return Loaded(await _cached(query), offline: true);
    }
  }

  /// Looks on the device first, then asks the server (own foods, catalog,
  /// Open Food Facts).
  Future<BarcodeResult> lookupBarcode(String barcode) async {
    try {
      final response = await apiCall(
        () => _dio.get<Map<String, dynamic>>('/nutrition/barcode/$barcode'),
      );
      await _remember(response.data!);
      return BarcodeFound(Food.fromJson(response.data!));
    } on ApiException catch (error) {
      if (error.code == 'product_not_found') return const BarcodeUnknown();
      if (error.code != ApiException.network &&
          error.code != 'source_unavailable') {
        rethrow;
      }
      final local = (await _cached(barcode))
          .where((food) => food.barcode == barcode);
      if (local.isNotEmpty) return BarcodeFound(local.first, offline: true);
      return const BarcodeUnavailable();
    }
  }

  Future<Food> save(Food food, {String? catalogId}) async {
    final response = await apiCall(
      () => food.id == null
          ? _dio.post<Map<String, dynamic>>(
              '/nutrition/foods',
              data: {...food.toJson(), 'catalog_id': ?catalogId},
            )
          : _dio.put<Map<String, dynamic>>(
              '/nutrition/foods/${food.id}',
              data: food.toJson(),
            ),
    );
    await _remember(response.data!);
    return Food.fromJson(response.data!);
  }

  Future<void> delete(String id) async {
    await apiCall(() => _dio.delete<void>('/nutrition/foods/$id'));
    await _db.deleteDocument(_own, id);
  }

  Future<void> propose(String id) =>
      apiCall(() => _dio.post<void>('/nutrition/foods/$id/propose-to-catalog'));

  Future<List<Food>> _list(String path) async => [
    for (final d in await _allPages(path, const {})) Food.fromJson(d),
  ];

  Future<List<Food>> myProposals() => _list('/nutrition/catalog/mine');

  Future<List<Food>> pendingProposals() => _list('/nutrition/catalog/pending');

  Future<void> moderate(String id, String visibility) => apiCall(
    () => _dio.patch<void>(
      '/nutrition/catalog/$id',
      data: {'visibility': visibility},
    ),
  );
}

final foodRepositoryProvider = Provider<FoodRepository>(
  (ref) =>
      FoodRepository(ref.watch(dioProvider), ref.watch(appDatabaseProvider)),
);

final foodSearchProvider = FutureProvider.autoDispose
    .family<Loaded<List<Food>>, String>(
      (ref, query) => ref.watch(foodRepositoryProvider).search(query),
    );
