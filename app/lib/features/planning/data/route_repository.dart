import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../core/db/app_database.dart';
import '../../../core/loaded.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/sync/sync_service.dart' hide Json;
import 'offline_routing.dart';
import 'route_models.dart';

/// Planned routes. The server computes every line; without network a route
/// is kept on the device as a draft of its waypoints and gets its line with
/// the next sync.
class RouteRepository {
  const RouteRepository(
    this._dio,
    this._db,
    this._sync,
    this._router,
    this._segments,
  );

  final Dio _dio;
  final AppDatabase _db;
  final SyncService _sync;

  /// Routing on the device, for planning without network.
  final DeviceRouter? _router;
  final SegmentStore _segments;

  /// Whole routes: synced, opened or drafted on this device.
  static const _routes = 'routes';

  /// The list as last loaded (without lines).
  static const _list = 'route_list';
  static const _info = 'planning_info';

  /// The paces saved under a name; the sync keeps them too.
  static const _paces = 'paces';
  static const _pageSize = 200;

  /// The fields a line follows from; if they differ the stored line is outdated.
  static const _course = [
    'profile',
    'max_difficulty',
    'via_ferrata',
    'waypoints',
  ];

  Future<Loaded<List<PlannedRoute>>> list({String query = ''}) async {
    try {
      final items = <Json>[];
      while (true) {
        final response = await apiCall(
          () => _dio.get<Json>(
            '/planning/routes',
            queryParameters: {
              if (query.isNotEmpty) 'q': query,
              'limit': _pageSize,
              'offset': items.length,
            },
          ),
        );
        final page = (response.data!['items'] as List<dynamic>).cast<Json>();
        items.addAll(page);
        if (page.length < _pageSize ||
            items.length >= (response.data!['total'] as int)) {
          break;
        }
      }
      if (query.isEmpty) await _db.replaceCollection(_list, items);
      return Loaded([for (final item in items) PlannedRoute(item)]);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final q = query.toLowerCase();
      // The list as last loaded, overlaid with what was synced or drafted here.
      final documents = <String, Json>{
        for (final d in await _db.listDocuments(_list)) d['id'] as String: d,
        for (final d in await _db.listDocuments(_routes)) d['id'] as String: d,
      };
      final cached =
          documents.values
              .map(PlannedRoute.new)
              .where((r) => q.isEmpty || r.title.toLowerCase().contains(q))
              .toList()
            ..sort(
              (a, b) => a.title.toLowerCase().compareTo(b.title.toLowerCase()),
            );
      return Loaded(cached, offline: true);
    }
  }

  Future<PlannedRoute> _stored(
    Future<Response<Json>> Function() request,
  ) async {
    final response = await apiCall(request);
    await _db.putDocument(
      _routes,
      response.data!['id'] as String,
      response.data!,
    );
    return PlannedRoute(response.data!);
  }

  Future<Loaded<PlannedRoute>> get(String id) async {
    try {
      return Loaded(
        await _stored(() => _dio.get<Json>('/planning/routes/$id')),
      );
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_routes, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return Loaded(PlannedRoute(cached), offline: true);
    }
  }

  /// Which profiles the server offers; offline the last known answer.
  Future<PlanningInfo> info() async {
    try {
      final response = await apiCall(() => _dio.get<Json>('/planning/info'));
      await _db.putDocument(_info, _info, response.data!);
      return PlanningInfo.fromJson(response.data!);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final cached = await _db.getDocument(_info, _info);
      // Never asked before: assume routing, the sync will tell.
      return cached == null
          ? const PlanningInfo(routingAvailable: true)
          : PlanningInfo.fromJson(cached);
    }
  }

  /// Line and key figures for a draft; nothing is stored. Without network
  /// the line is computed on the device from the path data loaded there.
  /// Throws an [ApiException] with `no_route`, `routing_unavailable` or, on
  /// the device, `offline_no_data`.
  Future<RouteResult> preview(RouteDraft draft) async {
    try {
      final response = await apiCall(
        () => _dio.post<Json>('/planning/preview', data: draft.courseJson()),
      );
      return RouteResult(response.data!);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      return computeOnDevice(draft, router: _router, hasSegment: _segments.has);
    }
  }

  /// Saves on the server. Without network the draft is kept on the device
  /// and sent with the next sync, which also computes its line.
  /// Throws `version_conflict` if the route was changed elsewhere meanwhile.
  /// [computed] is the line shown in the planner; a draft kept on the device
  /// takes it along, so that it has figures until the server answers.
  Future<PlannedRoute> save(
    RouteDraft draft, {
    PlannedRoute? existing,
    RouteResult? computed,
  }) async {
    final document = draft.toJson();
    try {
      final saved = await _stored(
        () => existing == null
            ? _dio.post<Json>('/planning/routes', data: document)
            : _dio.put<Json>(
                '/planning/routes/${existing.id}',
                data: {...document, 'version': existing.version},
              ),
      );
      return saved;
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final id = existing?.id ?? const Uuid().v4();
      final before = existing?.json;
      final sameCourse =
          before != null &&
          _course.every((key) => '${before[key]}' == '${document[key]}');
      final local = <String, dynamic>{
        // The old line and figures only stay if the course did not change.
        if (sameCourse) ...before else ...?computed?.json,
        // The pace only changes the walking time: that is computed here.
        if (sameCourse && before['distance_m'] != null)
          'duration_s': draft.pace.walkingTimeS(
            (before['distance_m'] as num).toDouble(),
            (before['ascent_m'] as num?)?.toDouble(),
            (before['descent_m'] as num?)?.toDouble(),
          ),
        ...document,
        'id': id,
        'version': existing?.version ?? 0,
      };
      await _db.putDocument(_routes, id, local);
      await _sync.enqueue(
        collection: _routes,
        id: id,
        data: document,
        baseVersion: existing?.version,
        base: before,
      );
      return PlannedRoute(local);
    }
  }

  /// A GPX file as a new route; the server reduces the track to waypoints.
  /// Needs the server: throws `network` without a connection.
  Future<PlannedRoute> importGpx(List<int> bytes, String filename) => _stored(
    () => _dio.post<Json>(
      '/planning/routes/import',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: filename),
      }),
    ),
  );

  /// Starts a tour from the route and returns its id. Needs the server.
  Future<String> tourFromRoute(String routeId) async {
    final response = await apiCall(
      () => _dio.post<Json>('/planning/routes/$routeId/tour'),
    );
    return response.data!['tour_id'] as String;
  }

  /// The tours started from the route; without network none are known.
  Future<List<Json>> routeTours(String routeId) async {
    try {
      final response = await apiCall(
        () => _dio.get<List<dynamic>>('/planning/routes/$routeId/tours'),
      );
      return response.data!.cast<Json>();
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      return const [];
    }
  }

  /// Plan and walked track of a tour side by side.
  Future<Json> comparison(String routeId, String tourId) async {
    final response = await apiCall(
      () => _dio.get<Json>('/planning/routes/$routeId/comparison/$tourId'),
    );
    return response.data!;
  }

  /// The paces the user saved under a name; offline the last known ones.
  Future<List<SavedPace>> paces() async {
    List<Json> documents;
    try {
      final response = await apiCall(
        () => _dio.get<List<dynamic>>('/planning/paces'),
      );
      documents = response.data!.cast<Json>();
      await _db.replaceCollection(_paces, documents);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      documents = await _db.listDocuments(_paces);
    }
    return [for (final document in documents) SavedPace(document)]
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }

  /// Saves a pace under a name. A name stands for one pace: saving it again
  /// replaces the earlier one. Without network it is sent with the next sync.
  Future<SavedPace> savePace(String name, Pace pace) async {
    for (final earlier in await paces()) {
      if (earlier.name == name) await deletePace(earlier.id);
    }
    final document = <String, dynamic>{
      'id': const Uuid().v4(),
      'name': name,
      'ascent_m_per_h': pace.ascentMPerH,
      'descent_m_per_h': pace.descentMPerH,
      'distance_km_per_h': pace.distanceKmPerH,
    };
    try {
      final response = await apiCall(
        () => _dio.post<Json>('/planning/paces', data: document),
      );
      await _db.putDocument(
        _paces,
        response.data!['id'] as String,
        response.data!,
      );
      return SavedPace(response.data!);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final id = document['id'] as String;
      await _db.putDocument(_paces, id, document);
      await _sync.enqueue(collection: _paces, id: id, data: document);
      return SavedPace(document);
    }
  }

  Future<void> deletePace(String id) async {
    try {
      await apiCall(() => _dio.delete<void>('/planning/paces/$id'));
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      await _sync.enqueue(collection: _paces, id: id);
    }
    await _db.deleteDocument(_paces, id);
  }

  Future<void> delete(String id) async {
    try {
      await apiCall(() => _dio.delete<void>('/planning/routes/$id'));
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      await _sync.enqueue(collection: _routes, id: id);
    }
    await _db.deleteDocument(_routes, id);
    await _db.deleteDocument(_list, id);
  }
}

final routeRepositoryProvider = Provider<RouteRepository>(
  (ref) => RouteRepository(
    ref.watch(dioProvider),
    ref.watch(appDatabaseProvider),
    ref.read(syncProvider.notifier),
    ref.watch(deviceRouterProvider),
    ref.watch(segmentStoreProvider),
  ),
);

final routeListProvider = FutureProvider.autoDispose
    .family<Loaded<List<PlannedRoute>>, String>((ref, query) {
      // Load again after every sync.
      ref.watch(syncGenerationProvider);
      return ref.watch(routeRepositoryProvider).list(query: query);
    });

final plannedRouteProvider = FutureProvider.autoDispose
    .family<Loaded<PlannedRoute>, String>((ref, id) {
      ref.watch(syncGenerationProvider);
      return ref.watch(routeRepositoryProvider).get(id);
    });

final savedPacesProvider = FutureProvider.autoDispose<List<SavedPace>>((ref) {
  ref.watch(syncGenerationProvider);
  return ref.watch(routeRepositoryProvider).paces();
});

final routeToursProvider = FutureProvider.autoDispose
    .family<List<Json>, String>((ref, routeId) {
      ref.watch(syncGenerationProvider);
      return ref.watch(routeRepositoryProvider).routeTours(routeId);
    });

final planningInfoProvider = FutureProvider.autoDispose<PlanningInfo>(
  (ref) => ref.watch(routeRepositoryProvider).info(),
);
