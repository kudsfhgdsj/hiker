import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/db/app_database.dart';
import '../../../core/loaded.dart';
import '../../../core/map/geo.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/widgets/file_pick.dart';
import 'tour_models.dart';

typedef Json = Map<String, dynamic>;

/// Tours of the user and tours shared with them. Reads fall back to the copy
/// on the device when the server cannot be reached; changes need the server.
class TourRepository {
  const TourRepository(this._dio, this._db);

  final Dio _dio;
  final AppDatabase _db;

  static const _tours = 'tours';
  static const _list = 'tour_list';
  static const _tracks = 'tour_tracks';
  static const _photos = 'tour_photos';

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
      final cached =
          (await _db.listDocuments('$_list:$scope'))
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

  Future<Loaded<Tour>> get(String id) async {
    try {
      return Loaded(await _stored(() => _dio.get<Json>('/tours/$id')));
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_tours, id);
      if (error.code != ApiException.network || cached == null) rethrow;
      return Loaded(Tour(cached), offline: true);
    }
  }

  Future<Tour> create(Json document) =>
      _stored(() => _dio.post<Json>('/tours', data: document));

  /// Throws an [ApiException] with code `version_conflict` and the current
  /// tour in `body['current']` if the tour was changed in the meantime.
  Future<Tour> update(String id, Json document, int version) => _stored(
    () => _dio.put<Json>('/tours/$id', data: {...document, 'version': version}),
  );

  Future<void> delete(String id) async {
    await apiCall(() => _dio.delete<void>('/tours/$id'));
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

  Future<Tour> uploadGpx(String id, PickedFile file) => _stored(
    () => _dio.put<Json>(
      '/tours/$id/gpx',
      data: FormData.fromMap({
        'file': MultipartFile.fromBytes(file.bytes, filename: file.name),
      }),
    ),
  );

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

  Future<void> uploadPhotos(String id, List<PickedFile> files) => apiCall(
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
  (ref) =>
      TourRepository(ref.watch(dioProvider), ref.watch(appDatabaseProvider)),
);

typedef TourListRequest = ({String scope, String query});

final tourListProvider = FutureProvider.autoDispose
    .family<Loaded<List<Tour>>, TourListRequest>(
      (ref, request) => ref
          .watch(tourRepositoryProvider)
          .list(scope: request.scope, query: request.query),
    );

final tourProvider = FutureProvider.autoDispose.family<Loaded<Tour>, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).get(id),
);

final tourTrackProvider = FutureProvider.autoDispose.family<TrackData, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).track(id),
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
