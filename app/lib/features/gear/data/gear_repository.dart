import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../core/db/app_database.dart';
import '../../../core/loaded.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/sync/sync_service.dart';
import 'gear_models.dart';

/// Gear of the signed-in user. Reads fall back to the copy on the device when
/// the server cannot be reached; changes need the server.
class GearRepository {
  const GearRepository(this._dio, this._db, this._sync);

  final Dio _dio;
  final AppDatabase _db;
  final SyncService _sync;

  static const _items = 'gear_items';
  static const _types = 'gear_types';
  static const _tags = 'gear_tags';
  static const _lists = 'gear_lists';
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

  /// Loads a plain list and keeps a copy; offline, returns the copy.
  Future<Loaded<List<Map<String, dynamic>>>> _cachedList(
    String path,
    String collection,
  ) async {
    try {
      final response = await apiCall(() => _dio.get<List<dynamic>>(path));
      final documents = response.data!.cast<Map<String, dynamic>>();
      await _db.replaceCollection(collection, documents);
      return Loaded(documents);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      return Loaded(await _db.listDocuments(collection), offline: true);
    }
  }

  // --- Items ---

  Future<Loaded<List<GearItem>>> listItems(GearFilter filter) async {
    try {
      final documents = await _allPages('/gear/items', filter.toQuery());
      // Only the unfiltered list is the full picture worth keeping.
      if (filter.isEmpty) await _db.replaceCollection(_items, documents);
      return Loaded([for (final d in documents) GearItem.fromJson(d)]);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final cached =
          (await _db.listDocuments(_items))
              .map(GearItem.fromJson)
              .where(filter.matches)
              .toList()
            ..sort(
              (a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()),
            );
      return Loaded(cached, offline: true);
    }
  }

  Future<GearItem> getItem(String id) async {
    try {
      final response = await apiCall(
        () => _dio.get<Map<String, dynamic>>('/gear/items/$id'),
      );
      await _db.putDocument(_items, id, response.data!);
      return GearItem.fromJson(response.data!);
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_items, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return GearItem.fromJson(cached);
    }
  }

  /// Saves on the server; without network the change is kept on the device
  /// and sent with the next sync.
  Future<GearItem> saveItem(GearItem item, {String? catalogId}) async {
    try {
      final response = await apiCall(
        () => item.id == null
            ? _dio.post<Map<String, dynamic>>(
                '/gear/items',
                data: {...item.toJson(), 'catalog_id': ?catalogId},
              )
            : _dio.put<Map<String, dynamic>>(
                '/gear/items/${item.id}',
                data: item.toJson(),
              ),
      );
      final saved = GearItem.fromJson(response.data!);
      await _db.putDocument(_items, saved.id!, response.data!);
      return saved;
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final id = item.id ?? const Uuid().v4();
      final before = await _db.getDocument(_items, id);
      final document = {
        ...?before,
        ...item.toJson(),
        'id': id,
        'catalog_id': ?catalogId,
      };
      await _db.putDocument(_items, id, document);
      await _sync.enqueue(
        collection: _items,
        id: id,
        data: document,
        baseUpdatedAt: before?['updated_at'] as String?,
        base: before,
      );
      return GearItem.fromJson(document);
    }
  }

  Future<void> deleteItem(String id) async {
    try {
      await apiCall(() => _dio.delete<void>('/gear/items/$id'));
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      await _sync.enqueue(collection: _items, id: id);
    }
    await _db.deleteDocument(_items, id);
  }

  Future<GearItem> uploadImage(
    String id,
    Uint8List bytes,
    String filename,
  ) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(bytes, filename: filename),
    });
    final response = await apiCall(
      () =>
          _dio.post<Map<String, dynamic>>('/gear/items/$id/image', data: form),
    );
    await _db.putDocument(_items, id, response.data!);
    return GearItem.fromJson(response.data!);
  }

  Future<void> removeImage(String id) =>
      apiCall(() => _dio.delete<void>('/gear/items/$id/image'));

  Future<GearSummary> summary(GearFilter filter, String? groupBy) async {
    final response = await apiCall(
      () => _dio.get<Map<String, dynamic>>(
        '/gear/summary',
        queryParameters: {...filter.toQuery(), 'group_by': ?groupBy},
      ),
    );
    return GearSummary.fromJson(response.data!);
  }

  // --- Types and tags ---

  Future<Loaded<List<GearType>>> listTypes() async {
    final loaded = await _cachedList('/gear/types', _types);
    return Loaded([
      for (final d in loaded.value) GearType.fromJson(d),
    ], offline: loaded.offline);
  }

  /// [kind] gives the items of the type extra fields, see [gearKinds].
  Future<void> saveType({
    String? id,
    required String name,
    String? kind,
    int sortOrder = 0,
  }) {
    final data = {'name': name, 'kind': kind, 'sort_order': sortOrder};
    return apiCall(
      () => id == null
          ? _dio.post<void>('/gear/types', data: data)
          : _dio.put<void>('/gear/types/$id', data: data),
    );
  }

  Future<void> deleteType(String id) =>
      apiCall(() => _dio.delete<void>('/gear/types/$id'));

  Future<Loaded<List<GearTag>>> listTags() async {
    final loaded = await _cachedList('/gear/tags', _tags);
    return Loaded([
      for (final d in loaded.value) GearTag.fromJson(d),
    ], offline: loaded.offline);
  }

  Future<void> saveTag({String? id, required String name, String? color}) {
    final data = {'name': name, 'color': color};
    return apiCall(
      () => id == null
          ? _dio.post<void>('/gear/tags', data: data)
          : _dio.put<void>('/gear/tags/$id', data: data),
    );
  }

  Future<void> deleteTag(String id) =>
      apiCall(() => _dio.delete<void>('/gear/tags/$id'));

  // --- Packing lists ---

  Future<Loaded<List<GearPackList>>> listPackLists() async {
    final loaded = await _cachedList('/gear/lists', _lists);
    return Loaded([
      for (final d in loaded.value) GearPackList.fromJson(d),
    ], offline: loaded.offline);
  }

  Future<void> savePackList(GearPackList list) => apiCall(
    () => list.id == null
        ? _dio.post<void>('/gear/lists', data: list.toJson())
        : _dio.put<void>('/gear/lists/${list.id}', data: list.toJson()),
  );

  Future<void> deletePackList(String id) =>
      apiCall(() => _dio.delete<void>('/gear/lists/$id'));

  // --- Catalog ---

  Future<List<CatalogItem>> _catalog(
    String path, [
    Map<String, dynamic> query = const {},
  ]) async {
    final documents = await _allPages(path, query);
    return [for (final d in documents) CatalogItem.fromJson(d)];
  }

  Future<List<CatalogItem>> searchCatalog(String query) =>
      _catalog('/gear/catalog', {if (query.isNotEmpty) 'q': query});

  Future<List<CatalogItem>> myProposals() => _catalog('/gear/catalog/mine');

  Future<List<CatalogItem>> pendingProposals() =>
      _catalog('/gear/catalog/pending');

  Future<void> propose(String itemId) =>
      apiCall(() => _dio.post<void>('/gear/items/$itemId/propose-to-catalog'));

  Future<void> moderate(String catalogId, String status) => apiCall(
    () =>
        _dio.patch<void>('/gear/catalog/$catalogId', data: {'status': status}),
  );
}

final gearRepositoryProvider = Provider<GearRepository>(
  (ref) => GearRepository(
    ref.watch(dioProvider),
    ref.watch(appDatabaseProvider),
    ref.read(syncProvider.notifier),
  ),
);

final gearItemsProvider = FutureProvider.autoDispose
    .family<Loaded<List<GearItem>>, GearFilter>((ref, filter) {
      // Load again after every sync.
      ref.watch(syncGenerationProvider);
      return ref.watch(gearRepositoryProvider).listItems(filter);
    });

final gearTypesProvider = FutureProvider.autoDispose<Loaded<List<GearType>>>(
  (ref) => ref.watch(gearRepositoryProvider).listTypes(),
);

final gearTagsProvider = FutureProvider.autoDispose<Loaded<List<GearTag>>>(
  (ref) => ref.watch(gearRepositoryProvider).listTags(),
);

final gearPackListsProvider =
    FutureProvider.autoDispose<Loaded<List<GearPackList>>>(
      (ref) => ref.watch(gearRepositoryProvider).listPackLists(),
    );

typedef SummaryRequest = ({GearFilter filter, String? groupBy});

final gearSummaryProvider = FutureProvider.autoDispose
    .family<GearSummary, SummaryRequest>(
      (ref, request) => ref
          .watch(gearRepositoryProvider)
          .summary(request.filter, request.groupBy),
    );
