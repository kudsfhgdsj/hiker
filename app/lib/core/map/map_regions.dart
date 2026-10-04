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
  const MapRegion({
    required this.name,
    required this.sizeBytes,
    this.modified,
    this.layersSizeBytes,
  });

  factory MapRegion.fromJson(Map<String, dynamic> json) => MapRegion(
    name: json['name'] as String,
    sizeBytes: json['size_bytes'] as int,
    modified: DateTime.tryParse(json['modified'] as String? ?? ''),
    layersSizeBytes: json['layers_size_bytes'] as int?,
  );

  final String name;
  final int sizeBytes;
  final DateTime? modified;

  /// Size of the layer pack that belongs to the map (elevation, slope and
  /// contour lines to take along); null if there is none.
  final int? layersSizeBytes;

  /// Map and layer pack together.
  int get totalBytes => sizeBytes + (layersSizeBytes ?? 0);
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
  static const _packSuffix = '.layers.sqlite';
  static const _packQuery =
      'SELECT data FROM layer_tiles '
      'WHERE layer = ? AND z = ? AND x = ? AND y = ?';
  static const _query =
      'SELECT tile_data FROM tiles '
      'WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?';

  /// Open map files, by path; closed when the files change.
  Map<String, Database>? _open;

  /// Open layer packs, by path.
  Map<String, Database>? _openPacks;

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
          layersSizeBytes: switch (File(
            file.path.replaceAll('.mbtiles', _packSuffix),
          )) {
            final pack when pack.existsSync() => pack.lengthSync(),
            _ => null,
          },
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
    for (final database in _openPacks?.values ?? const <Database>[]) {
      database.close();
    }
    _openPacks = null;
  }

  /// Downloads a map and, if the server has one, its layer pack;
  /// [onProgress] gets the share of both that is done (0 to 1). A file only
  /// appears when it is complete.
  Future<void> download(
    MapRegion region, {
    void Function(double share)? onProgress,
    CancelToken? cancel,
  }) async {
    final folder = (await directory).path;
    final total = region.totalBytes;
    var done = 0;
    Future<void> fetch(String path, String fileName, int size) async {
      final target = File('$folder/$fileName');
      final part = File('${target.path}.part');
      try {
        await apiCall(
          () => _dio.download(
            path,
            part.path,
            cancelToken: cancel,
            // Some hundred megabytes: no limit for the whole download.
            options: Options(receiveTimeout: Duration.zero),
            onReceiveProgress: (received, _) {
              if (total > 0) onProgress?.call((done + received) / total);
            },
          ),
        );
        _closeAll();
        await part.rename(target.path);
        done += size;
      } finally {
        if (part.existsSync()) part.deleteSync();
      }
    }

    final name = region.name;
    await fetch('/maps/regions/$name', '$name.mbtiles', region.sizeBytes);
    final pack = region.layersSizeBytes;
    if (pack != null) {
      await fetch('/maps/regions/$name/layers', '$name$_packSuffix', pack);
    }
  }

  Future<void> delete(String name) async {
    _closeAll();
    final folder = (await directory).path;
    for (final file in [
      File('$folder/$name.mbtiles'),
      File('$folder/$name$_packSuffix'),
    ]) {
      if (file.existsSync()) await file.delete();
    }
  }

  /// A tile of a layer pack on the device: `terrain`, `slope` or `contours`.
  Future<Uint8List?> layerTile(String layer, int z, int x, int y) async {
    var open = _openPacks;
    if (open == null) {
      open = _openPacks = {};
      final files = (await directory).listSync().whereType<File>().where(
        (file) => file.path.endsWith(_packSuffix),
      );
      for (final file in files) {
        try {
          open[file.path] = sqlite3.open(file.path, mode: OpenMode.readOnly);
        } on SqliteException {
          // Not a layer pack: skip it.
        }
      }
    }
    for (final database in open.values) {
      try {
        final rows = database.select(_packQuery, [layer, z, x, y]);
        if (rows.isNotEmpty) return rows.first['data'] as Uint8List;
      } on SqliteException {
        continue;
      }
    }
    return null;
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
