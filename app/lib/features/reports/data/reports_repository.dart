import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/db/app_database.dart';
import '../../../core/map/geo.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/sync/sync_service.dart' hide Json;

typedef Json = Map<String, dynamic>;

/// What all own tours add up to: totals, climbed peaks, the days out, all
/// tracks and the peaks wished for. The server computes it; without network
/// the answer seen last is shown.
class Report {
  const Report({
    required this.summary,
    required this.peaks,
    required this.calendar,
    required this.wishes,
    required this.tracks,
    this.offline = false,
  });

  final Json summary;
  final List<Json> peaks;
  final Json calendar;
  final List<Json> wishes;

  /// Every own track as a thinned-out line.
  final List<List<GeoPoint>> tracks;
  final bool offline;

  Json get total => summary['total'] as Json;
  List<Json> get years => (summary['years'] as List<dynamic>).cast<Json>();
  int get year => calendar['year'] as int;
  List<int> get calendarYears =>
      (calendar['years'] as List<dynamic>).cast<int>();

  /// The days with tours of [year], by ISO date.
  Map<String, Json> get days => {
    for (final day in (calendar['days'] as List<dynamic>).cast<Json>())
      day['date'] as String: day,
  };
}

class ReportsRepository {
  const ReportsRepository(this._dio, this._db);

  final Dio _dio;
  final AppDatabase _db;

  static const _cache = 'reports';

  Future<Report> load({int? year}) async {
    final key = 'report-${year ?? 'latest'}';
    Json document;
    var offline = false;
    try {
      final answers = await Future.wait([
        apiCall(() => _dio.get<Json>('/reports/summary')),
        apiCall(() => _dio.get<List<dynamic>>('/reports/peaks')),
        apiCall(
          () => _dio.get<Json>(
            '/reports/calendar',
            queryParameters: {'year': ?year},
          ),
        ),
        apiCall(() => _dio.get<List<dynamic>>('/reports/wishes')),
        apiCall(() => _dio.get<Json>('/reports/tracks')),
      ]);
      document = {
        'summary': answers[0].data,
        'peaks': answers[1].data,
        'calendar': answers[2].data,
        'wishes': answers[3].data,
        'tracks': answers[4].data,
      };
      await _db.putDocument(_cache, key, document);
    } on ApiException catch (error) {
      final cached = await _db.getDocument(_cache, key);
      if (error.code != ApiException.network || cached == null) rethrow;
      document = cached;
      offline = true;
    }
    return Report(
      summary: document['summary'] as Json,
      peaks: (document['peaks'] as List<dynamic>).cast<Json>(),
      calendar: document['calendar'] as Json,
      wishes: (document['wishes'] as List<dynamic>).cast<Json>(),
      tracks: [
        for (final feature
            in ((document['tracks'] as Json)['features'] as List<dynamic>)
                .cast<Json>())
          [
            for (final point
                in ((feature['geometry'] as Json)['coordinates']
                    as List<dynamic>))
              GeoPoint(
                ((point as List<dynamic>)[1] as num).toDouble(),
                (point[0] as num).toDouble(),
              ),
          ],
      ],
      offline: offline,
    );
  }

  /// Puts a peak on the list of wishes. Needs the server.
  Future<void> addWish({
    required String name,
    int? elevationM,
    double? lat,
    double? lon,
    String? note,
  }) => apiCall(
    () => _dio.post<Json>(
      '/reports/wishes',
      data: {
        'name': name,
        'elevation_m': elevationM,
        'lat': lat,
        'lon': lon,
        'note': note,
      },
    ),
  );

  Future<void> deleteWish(String id) =>
      apiCall(() => _dio.delete<void>('/reports/wishes/$id'));
}

final reportsRepositoryProvider = Provider<ReportsRepository>(
  (ref) =>
      ReportsRepository(ref.watch(dioProvider), ref.watch(appDatabaseProvider)),
);

/// The report for a year of the calendar (null: the newest year with tours).
final reportProvider = FutureProvider.autoDispose.family<Report, int?>((
  ref,
  year,
) {
  ref.watch(syncGenerationProvider);
  return ref.watch(reportsRepositoryProvider).load(year: year);
});
