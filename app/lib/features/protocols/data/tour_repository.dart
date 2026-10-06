import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../core/db/app_database.dart';
import '../../../core/loaded.dart';
import '../../../core/map/geo.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/sync/sync_service.dart' hide Json;
import '../../../core/widgets/file_pick.dart';
import 'tour_models.dart';

typedef Json = Map<String, dynamic>;

/// Tours of the user and tours shared with them. Reads fall back to the copy
/// on the device when the server cannot be reached; changes need the server.
class TourRepository {
  const TourRepository(this._dio, this._db, this._sync);

  final Dio _dio;
  final AppDatabase _db;
  final SyncService _sync;

  static const _tours = 'tours';
  static const _list = 'tour_list';
  static const _tracks = 'tour_tracks';
  static const _lines = 'tour_lines';
  static const _photos = 'tour_photos';
  static const _overviews = 'tour_overviews';

  Future<Tour> _stored(Future<Response<Json>> Function() request) async {
    final response = await apiCall(request);
    await _db.putDocument(
      _tours,
      response.data!['id'] as String,
      response.data!,
    );
    return Tour(response.data!);
  }

  // --- Tours ---

  Future<Loaded<List<Tour>>> list({
    required String scope,
    String query = '',
  }) async {
    try {
      final items = <Json>[];
      while (true) {
        final response = await apiCall(
          () => _dio.get<Json>(
            '/tours',
            queryParameters: {
              'scope': scope,
              if (query.isNotEmpty) 'q': query,
              'limit': 200,
              'offset': items.length,
            },
          ),
        );
        final page = (response.data!['items'] as List<dynamic>).cast<Json>();
        items.addAll(page);
        if (page.length < 200 ||
            items.length >= (response.data!['total'] as int)) {
          break;
        }
      }
      if (query.isEmpty) {
        await _db.replaceCollection('$_list:$scope', items);
      }
      return Loaded([for (final item in items) Tour(item)]);
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final q = query.toLowerCase();
      // The list as last loaded, plus tours opened, synced or created offline.
      final documents = <String, Json>{
        for (final d in await _db.listDocuments('$_list:$scope'))
          d['id'] as String: d,
        for (final d in await _db.listDocuments(_tours))
          if ((d['permission'] == 'owner') == (scope == 'mine'))
            d['id'] as String: d,
      };
      final cached =
          documents.values
              .map(Tour.new)
              .where((t) => q.isEmpty || t.title.toLowerCase().contains(q))
              .toList()
            ..sort(
              (a, b) => (b.startTime ?? DateTime(0)).compareTo(
                a.startTime ?? DateTime(0),
              ),
            );
      return Loaded(cached, offline: true);
    }
  }

  /// All tours of a scope as lines for one map; without network the lines
  /// as last loaded.
  Future<Loaded<List<TourLine>>> lines({required String scope}) async {
    List<TourLine> parse(Json document) => [
      for (final feature
          in (document['features'] as List<dynamic>).cast<Json>())
        TourLine.fromFeature(feature),
    ];
    try {
      final response = await apiCall(
        () =>
            _dio.get<Json>('/tours/tracks', queryParameters: {'scope': scope}),
      );
      await _db.putDocument(_lines, scope, response.data!);
      return Loaded(parse(response.data!));
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_lines, scope);
      if (error.code != ApiException.network || cached == null) rethrow;
      return Loaded(parse(cached), offline: true);
    }
  }

  Future<Loaded<Tour>> get(String id) async {
    try {
      return Loaded(await _stored(() => _dio.get<Json>('/tours/$id')));
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_tours, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return Loaded(Tour(cached), offline: true);
    }
  }

  /// Without network the tour is created on the device and sent with the
  /// next sync; it then has version 0 until the server answers.
  Future<Tour> create(Json document) async {
    try {
      return await _stored(() => _dio.post<Json>('/tours', data: document));
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final id = const Uuid().v4();
      final tour = {
        ...document,
        'id': id,
        'permission': 'owner',
        'version': 0,
        'computed': <String, dynamic>{},
        'track_source': 'none',
        'weather': <Json>[],
      };
      await _db.putDocument(_tours, id, tour);
      await _sync.enqueue(collection: _tours, id: id, data: document);
      return Tour(tour);
    }
  }

  /// Throws an [ApiException] with code `version_conflict` and the current
  /// tour in `body['current']` if the tour was changed in the meantime.
  /// Without network the change is kept on the device and sent with the next
  /// sync, where a conflict is merged field by field.
  Future<Tour> update(String id, Json document, int version) async {
    try {
      return await _stored(
        () => _dio.put<Json>(
          '/tours/$id',
          data: {...document, 'version': version},
        ),
      );
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      final before = await _db.getDocument(_tours, id) ?? <String, dynamic>{};
      final tour = {...before, ...document};
      await _db.putDocument(_tours, id, tour);
      await _sync.enqueue(
        collection: _tours,
        id: id,
        data: document,
        baseVersion: version,
        base: documentOf(before),
      );
      return Tour(tour);
    }
  }

  Future<void> delete(String id) async {
    try {
      await apiCall(() => _dio.delete<void>('/tours/$id'));
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      await _sync.enqueue(collection: _tours, id: id);
    }
    await _db.deleteDocument(_tours, id);
  }

  // --- Track, points, weather, calories ---

  Future<TrackData> track(String id) async {
    try {
      final response = await apiCall(() => _dio.get<Json>('/tours/$id/track'));
      await _db.putDocument(_tracks, id, response.data!);
      return TrackData(response.data!);
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_tracks, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return TrackData(cached);
    }
  }

  /// Sends a GPX file; used directly and by the upload queue.
  Future<Tour> sendGpx(String id, String filename, Uint8List bytes) => _stored(
    () => _dio.put<Json>(
      '/tours/$id/gpx',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: filename),
      }),
    ),
  );

  /// Uploads a GPX file. Without network it waits in the upload queue;
  /// returns false in that case.
  Future<bool> uploadGpx(String id, PickedFile file) async {
    try {
      await sendGpx(id, file.name, file.bytes);
      return true;
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      await _sync.enqueueUpload(
        kind: 'gpx',
        tourId: id,
        filename: file.name,
        bytes: file.bytes,
      );
      return false;
    }
  }

  Future<Tour> saveDrawnTrack(String id, List<GeoPoint> points) => _stored(
    () => _dio.post<Json>(
      '/tours/$id/track/drawn',
      data: {
        'points': [
          for (final point in points) {'lat': point.lat, 'lon': point.lon},
        ],
      },
    ),
  );

  /// Key figures and the places on the way, in the order along the track.
  Future<Json> overview(String id) async {
    try {
      final response = await apiCall(
        () => _dio.get<Json>('/tours/$id/overview'),
      );
      await _db.putDocument(_overviews, id, response.data!);
      return response.data!;
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_overviews, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return cached;
    }
  }

  Future<Tour> detectPlaces(String id) =>
      _stored(() => _dio.post<Json>('/tours/$id/track/places'));

  Future<Tour> removeTrack(String id) =>
      _stored(() => _dio.delete<Json>('/tours/$id/track'));

  Future<Tour> setPoints(String id, {Json? start, Json? end}) => _stored(
    () =>
        _dio.put<Json>('/tours/$id/points', data: {'start': start, 'end': end}),
  );

  Future<Tour> fetchWeather(String id) =>
      _stored(() => _dio.post<Json>('/tours/$id/weather/fetch'));

  Future<Tour> useCalorieEstimate(String id) =>
      _stored(() => _dio.post<Json>('/tours/$id/calories/estimate'));

  // --- Photos and waypoints ---

  Future<List<Json>> _jsonList(String path) async {
    final response = await apiCall(() => _dio.get<List<dynamic>>(path));
    return response.data!.cast<Json>();
  }

  Future<List<Json>> photos(String id) async {
    try {
      final photos = await _jsonList('/tours/$id/photos');
      await _db.putDocument(_photos, id, {'photos': photos});
      return photos;
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_photos, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return (cached['photos'] as List<dynamic>).cast<Json>();
    }
  }

  /// Sends photos; used directly and by the upload queue.
  Future<void> sendPhotos(String id, List<PickedFile> files) => apiCall(
    () => _dio.post<void>(
      '/tours/$id/photos',
      data: FormData.fromMap({
        'files': [
          for (final file in files)
            MultipartFile.fromBytes(file.bytes, filename: file.name),
        ],
      }),
    ),
  );

  /// Uploads photos. Without network they wait in the upload queue; returns
  /// false in that case.
  Future<bool> uploadPhotos(String id, List<PickedFile> files) async {
    try {
      await sendPhotos(id, files);
      return true;
    } on ApiException catch (error) {
      if (error.code != ApiException.network) rethrow;
      for (final file in files) {
        await _sync.enqueueUpload(
          kind: 'photo',
          tourId: id,
          filename: file.name,
          bytes: file.bytes,
        );
      }
      return false;
    }
  }

  Future<void> updatePhoto(String id, String photoId, Json changes) => apiCall(
    () => _dio.patch<void>('/tours/$id/photos/$photoId', data: changes),
  );

  Future<void> deletePhoto(String id, String photoId) =>
      apiCall(() => _dio.delete<void>('/tours/$id/photos/$photoId'));

  Future<void> setPhotoTimeOffset(String id, int seconds) => apiCall(
    () => _dio.put<void>(
      '/tours/$id/photos/time-offset',
      data: {'seconds': seconds},
    ),
  );

  Future<List<Json>> waypoints(String id) => _jsonList('/tours/$id/waypoints');

  Future<void> addWaypoint(String id, Json waypoint) =>
      apiCall(() => _dio.post<void>('/tours/$id/waypoints', data: waypoint));

  Future<void> deleteWaypoint(String id, String waypointId) =>
      apiCall(() => _dio.delete<void>('/tours/$id/waypoints/$waypointId'));

  Future<int> waypointsFromPhotos(String id) async {
    final response = await apiCall(
      () => _dio.post<List<dynamic>>('/tours/$id/waypoints/from-photos'),
    );
    return response.data!.length;
  }

  // --- History ---

  Future<List<Json>> revisions(String id) async {
    final response = await apiCall(
      () => _dio.get<Json>(
        '/tours/$id/revisions',
        queryParameters: {'limit': 200},
      ),
    );
    return (response.data!['items'] as List<dynamic>).cast<Json>();
  }

  Future<Json> revision(String id, int version) async {
    final response = await apiCall(
      () => _dio.get<Json>('/tours/$id/revisions/$version'),
    );
    return response.data!;
  }

  Future<Tour> restore(String id, int version) =>
      _stored(() => _dio.post<Json>('/tours/$id/revisions/$version/restore'));

  // --- Sharing ---

  Future<List<Json>> shares(String id) => _jsonList('/tours/$id/shares');

  /// The user with exactly this e-mail address, or null.
  Future<Json?> lookupUser(String email) async {
    try {
      final response = await apiCall(
        () =>
            _dio.get<Json>('/users/lookup', queryParameters: {'email': email}),
      );
      return response.data;
    } on ApiException catch (error) {
      if (error.statusCode == 404 || error.statusCode == 422) return null;
      rethrow;
    }
  }

  Future<void> share(String id, String userId, String permission) => apiCall(
    () => _dio.post<void>(
      '/tours/$id/shares',
      data: {'user_id': userId, 'permission': permission},
    ),
  );

  Future<void> updateShare(String id, String userId, String permission) =>
      apiCall(
        () => _dio.patch<void>(
          '/tours/$id/shares/$userId',
          data: {'permission': permission},
        ),
      );

  Future<void> removeShare(String id, String userId) =>
      apiCall(() => _dio.delete<void>('/tours/$id/shares/$userId'));

  Future<List<Json>> publicLinks(String id) =>
      _jsonList('/tours/$id/public-link');

  Future<Json> createPublicLink(String id, Json options) async {
    final response = await apiCall(
      () => _dio.post<Json>('/tours/$id/public-link', data: options),
    );
    return response.data!;
  }

  Future<void> revokePublicLink(String id, String linkId) =>
      apiCall(() => _dio.delete<void>('/tours/$id/public-link/$linkId'));

  // --- Contacts ---

  Future<List<Json>> contacts() => _jsonList('/contacts');

  Future<Json> createContact(String name) async {
    final response = await apiCall(
      () => _dio.post<Json>('/contacts', data: {'display_name': name}),
    );
    return response.data!;
  }

  /// Bytes of the export file, for saving or sharing.
  Future<Uint8List> export(String id) async {
    final response = await apiCall(
      () => _dio.get<List<int>>(
        '/tours/$id/export',
        options: Options(responseType: ResponseType.bytes),
      ),
    );
    return Uint8List.fromList(response.data!);
  }
}

final tourRepositoryProvider = Provider<TourRepository>(
  (ref) => TourRepository(
    ref.watch(dioProvider),
    ref.watch(appDatabaseProvider),
    ref.read(syncProvider.notifier),
  ),
);

typedef TourListRequest = ({String scope, String query});

final tourListProvider = FutureProvider.autoDispose
    .family<Loaded<List<Tour>>, TourListRequest>((ref, request) {
      // Load again after every sync.
      ref.watch(syncGenerationProvider);
      return ref
          .watch(tourRepositoryProvider)
          .list(scope: request.scope, query: request.query);
    });

final tourLinesProvider = FutureProvider.autoDispose
    .family<Loaded<List<TourLine>>, String>((ref, scope) {
      ref.watch(syncGenerationProvider);
      return ref.watch(tourRepositoryProvider).lines(scope: scope);
    });

final tourProvider = FutureProvider.autoDispose.family<Loaded<Tour>, String>((
  ref,
  id,
) {
  ref.watch(syncGenerationProvider);
  return ref.watch(tourRepositoryProvider).get(id);
});

/// Sends a queued GPX file or photo; wired into the sync in `app.dart`.
UploadHandler tourUploadHandler(Ref ref) => (upload) {
  final repository = ref.read(tourRepositoryProvider);
  return upload.kind == 'gpx'
      ? repository.sendGpx(upload.tourId, upload.filename, upload.bytes)
      : repository.sendPhotos(upload.tourId, [
          PickedFile(upload.filename, upload.bytes),
        ]);
};

/// After a version conflict in the sync: merge field by field; null if both
/// sides changed the same field and the user has to decide.
Json? resolveTourConflict(Json? base, Json mine, Json current) {
  if (base == null) return null;
  final result = mergeDocuments(base, mine, documentOf(current));
  return result.conflicts.isEmpty ? result.merged : null;
}

final tourTrackProvider = FutureProvider.autoDispose.family<TrackData, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).track(id),
);

final tourOverviewProvider = FutureProvider.autoDispose.family<Json, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).overview(id),
);

final tourPhotosProvider = FutureProvider.autoDispose
    .family<List<Json>, String>(
      (ref, id) => ref.watch(tourRepositoryProvider).photos(id),
    );

final tourWaypointsProvider = FutureProvider.autoDispose
    .family<List<Json>, String>(
      (ref, id) => ref.watch(tourRepositoryProvider).waypoints(id),
    );

final contactsProvider = FutureProvider.autoDispose<List<Json>>(
  (ref) => ref.watch(tourRepositoryProvider).contacts(),
);
