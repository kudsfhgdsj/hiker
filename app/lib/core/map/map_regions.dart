import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sqlite3/sqlite3.dart';

import '../db/app_database.dart';
import '../network/api_client.dart';
import '../network/api_exception.dart';

/// The own map of a region as a file (MBTiles with vector tiles), on the
/// server or on the device. Unlike tiles of the OpenStreetMap servers these
/// maps may be taken along: the server builds them from the raw data.
class MapRegion {
  const MapRegion({required this.name, required this.sizeBytes, this.modified});

  factory MapRegion.fromJson(Map<String, dynamic> json) => MapRegion(
    name: json['name'] as String,
    sizeBytes: json['size_bytes'] as int,
    modified: DateTime.tryParse(json['modified'] as String? ?? ''),
  );

  final String name;
  final int sizeBytes;
  final DateTime? modified;
}

/// Where the app keeps the map files; tests use a temporary folder.
final mapRegionDirectoryProvider = FutureProvider<Directory>((ref) async {
  final support = await getApplicationSupportDirectory();
  return Directory('${support.path}/maps');
});

class MapRegionStore {
  MapRegionStore(this._dio, this._db, this._root);

  final Dio _dio;
  final AppDatabase _db;
  final Future<Directory> _root;

  static const _known = 'map_regions';
  static const _query =
      'SELECT tile_data FROM tiles '
      'WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?';

  /// Open map files, by path; closed when the files change.
  Map<String, Database>? _open;

  Future<Directory> get directory async {
    final folder = await _root;
    await folder.create(recursive: true);
    return folder;
  }

  Future<List<MapRegion>> installed() async {
    final files = (await directory).listSync().whereType<File>().where(
      (file) => file.path.endsWith('.mbtiles'),
    );
    return [
      for (final file in files)
        MapRegion(
          name: file.uri.pathSegments.last.replaceAll('.mbtiles', ''),
          sizeBytes: file.lengthSync(),
          modified: file.lastModifiedSync(),
        ),
    ]..sort((a, b) => a.name.compareTo(b.name));
  }

  /// What the server offers; offline the last known answer.
  Future<List<MapRegion>> available() async {
    try {
      final response = await apiCall(
        () => _dio.get<List<dynamic>>('/maps/regions'),
      );
      final items = (response.data ?? const []).cast<Map<String, dynamic>>();
      await _db.putDocument(_known, _known, {'items': items});
      return [for (final item in items) MapRegion.fromJson(item)];
    } on ApiException catch (error) {
      // A server without the own map simply offers nothing.
      if (error.statusCode == 404) return const [];
      if (error.code != ApiException.network) rethrow;
      final cached = await _db.getDocument(_known, _known);
      return [
        for (final item in cached?['items'] as List<dynamic>? ?? const [])
          MapRegion.fromJson(item as Map<String, dynamic>),
      ];
    }
  }

  void _closeAll() {
    for (final database in _open?.values ?? const <Database>[]) {
      database.close();
    }
    _open = null;
  }

  /// Downloads a map; [onProgress] gets the share that is done (0 to 1).
  /// The file only appears when it is complete.
  Future<void> download(
    String name, {
    void Function(double share)? onProgress,
    CancelToken? cancel,
  }) async {
    final target = File('${(await directory).path}/$name.mbtiles');
    final part = File('${target.path}.part');
    try {
      await apiCall(
        () => _dio.download(
          '/maps/regions/$name',
          part.path,
          cancelToken: cancel,
          // A map has some hundred megabytes: no limit for the whole download.
          options: Options(receiveTimeout: Duration.zero),
          onReceiveProgress: (received, total) {
            if (total > 0) onProgress?.call(received / total);
          },
        ),
      );
      _closeAll();
      await part.rename(target.path);
    } finally {
      if (part.existsSync()) part.deleteSync();
    }
  }

  Future<void> delete(String name) async {
    _closeAll();
    final file = File('${(await directory).path}/$name.mbtiles');
    if (file.existsSync()) await file.delete();
  }

  /// The gzip-compressed vector tile from a map on the device, if one has it.
  Future<Uint8List?> tile(int z, int x, int y) async {
    var open = _open;
    if (open == null) {
      open = _open = {};
      for (final region in await installed()) {
        final path = '${(await directory).path}/${region.name}.mbtiles';
        try {
          open[path] = sqlite3.open(path, mode: OpenMode.readOnly);
        } on SqliteException {
          // Not a map file: skip it.
        }
      }
    }
    for (final database in open.values) {
      try {
        // MBTiles count rows from the south.
        final rows = database.select(_query, [z, x, (1 << z) - 1 - y]);
        if (rows.isNotEmpty) return rows.first['tile_data'] as Uint8List;
      } on SqliteException {
        continue;
      }
    }
    return null;
  }
}

final mapRegionStoreProvider = Provider<MapRegionStore>((ref) {
  final store = MapRegionStore(
    ref.watch(dioProvider),
    ref.watch(appDatabaseProvider),
    ref.watch(mapRegionDirectoryProvider.future),
  );
  ref.onDispose(store._closeAll);
  return store;
});

/// Counts up when a map was loaded or removed.
class MapRegionGeneration extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final mapRegionGenerationProvider = NotifierProvider<MapRegionGeneration, int>(
  MapRegionGeneration.new,
);

final installedMapRegionsProvider = FutureProvider.autoDispose<List<MapRegion>>(
  (ref) {
    ref.watch(mapRegionGenerationProvider);
    return ref.watch(mapRegionStoreProvider).installed();
  },
);

final availableMapRegionsProvider = FutureProvider.autoDispose<List<MapRegion>>(
  (ref) => ref.watch(mapRegionStoreProvider).available(),
);
