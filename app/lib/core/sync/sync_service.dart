import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../db/app_database.dart';
import '../network/api_client.dart';
import '../network/api_exception.dart';
import '../session/session.dart';
import '../storage/key_value_store.dart';

typedef Json = Map<String, dynamic>;

/// Merges an offline change with the server's newer record after a conflict.
/// Returns the record to push again, or null if the user has to decide.
typedef ConflictResolver = Json? Function(Json? base, Json mine, Json current);

/// Resolvers per collection; set in `app.dart` by the features that can merge.
final conflictResolversProvider = Provider<Map<String, ConflictResolver>>(
  (ref) => const {},
);

/// Uploads a queued file; set in `app.dart`, because uploading is a feature's job.
typedef UploadHandler = Future<void> Function(PendingUpload upload);

final uploadHandlerProvider = Provider<UploadHandler?>((ref) => null);

/// Counts up after every sync, so that lists on screen load again.
class SyncGeneration extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final syncGenerationProvider = NotifierProvider<SyncGeneration, int>(
  SyncGeneration.new,
);

class SyncStatus {
  const SyncStatus({
    this.pending = const [],
    this.uploads = 0,
    this.running = false,
  });

  final List<PendingChange> pending;
  final int uploads;
  final bool running;

  List<PendingChange> get conflicts => [
    for (final change in pending)
      if (change.conflict != null) change,
  ];

  List<PendingChange> get failed => [
    for (final change in pending)
      if (change.error != null) change,
  ];

  /// Changes and files that simply wait for a connection.
  int get waiting =>
      pending.length - conflicts.length - failed.length + uploads;

  bool get isClean => pending.isEmpty && uploads == 0;
}

/// Offline sync: keeps local changes in a queue, pushes them when the server
/// is reachable and pulls what changed there.
class SyncService extends Notifier<SyncStatus> {
  AppDatabase get _db => ref.read(appDatabaseProvider);
  Dio get _dio => ref.read(dioProvider);

  @override
  SyncStatus build() => const SyncStatus();

  Future<void> _refreshStatus({bool? running}) async {
    final pending = await (_db.select(
      _db.pendingChanges,
    )..orderBy([(row) => OrderingTerm.asc(row.id)])).get();
    final uploads = await _db.select(_db.pendingUploads).get();
    state = SyncStatus(
      pending: pending,
      uploads: uploads.length,
      running: running ?? state.running,
    );
  }

  /// Loads the queue from the device; call once at start.
  Future<void> load() => _refreshStatus();

  /// Remembers a change that could not be sent. Several changes of the same
  /// record become one: the newest data on the oldest base.
  Future<void> enqueue({
    required String collection,
    required String id,
    Json? data,
    int? baseVersion,
    String? baseUpdatedAt,
    Json? base,
  }) async {
    final existing =
        await (_db.select(_db.pendingChanges)..where(
              (row) =>
                  row.collection.equals(collection) & row.recordId.equals(id),
            ))
            .getSingleOrNull();
    final isDelete = data == null;
    if (existing != null) {
      final createdOffline =
          existing.op == 'upsert' &&
          existing.baseVersion == null &&
          existing.baseUpdatedAt == null &&
          existing.base == null;
      if (isDelete && createdOffline) {
        // Created and deleted offline: the server never needs to know.
        await (_db.delete(
          _db.pendingChanges,
        )..where((row) => row.id.equals(existing.id))).go();
      } else {
        await (_db.update(
          _db.pendingChanges,
        )..where((row) => row.id.equals(existing.id))).write(
          PendingChangesCompanion(
            op: Value(isDelete ? 'delete' : 'upsert'),
            data: Value(isDelete ? null : jsonEncode(data)),
            conflict: const Value(null),
            error: const Value(null),
          ),
        );
      }
    } else {
      await _db
          .into(_db.pendingChanges)
          .insert(
            PendingChangesCompanion.insert(
              collection: collection,
              op: isDelete ? 'delete' : 'upsert',
              recordId: id,
              baseVersion: Value(baseVersion),
              baseUpdatedAt: Value(baseUpdatedAt),
              data: Value(isDelete ? null : jsonEncode(data)),
              base: Value(base == null ? null : jsonEncode(base)),
              createdAt: DateTime.now().toUtc(),
            ),
          );
    }
    await _refreshStatus();
  }

  Future<void> enqueueUpload({
    required String kind,
    required String tourId,
    required String filename,
    required Uint8List bytes,
  }) async {
    await _db
        .into(_db.pendingUploads)
        .insert(
          PendingUploadsCompanion.insert(
            kind: kind,
            tourId: tourId,
            filename: filename,
            bytes: bytes,
            createdAt: DateTime.now().toUtc(),
          ),
        );
    await _refreshStatus();
  }

  Future<void> _remove(int id) =>
      (_db.delete(_db.pendingChanges)..where((row) => row.id.equals(id))).go();

  /// Gives up a local change; the server's state stays.
  Future<void> discard(PendingChange change) async {
    final current = change.conflict;
    if (current != null) {
      await _db.putDocument(
        change.collection,
        change.recordId,
        jsonDecode(current) as Json,
      );
    }
    await _remove(change.id);
    await _refreshStatus();
    ref.read(syncGenerationProvider.notifier).bump();
  }

  /// Pushes the local change over the server's newer state.
  Future<void> keepMine(PendingChange change) async {
    final current = jsonDecode(change.conflict!) as Json;
    await (_db.update(
      _db.pendingChanges,
    )..where((row) => row.id.equals(change.id))).write(
      PendingChangesCompanion(
        baseVersion: Value(current['version'] as int?),
        baseUpdatedAt: Value(current['updated_at'] as String?),
        base: Value(jsonEncode(current)),
        conflict: const Value(null),
      ),
    );
    await sync();
  }

  Future<void> _push() async {
    final ready = [
      for (final change in state.pending)
        if (change.conflict == null && change.error == null) change,
    ];
    if (ready.isEmpty) return;
    final response = await apiCall(
      () => _dio.post<Json>(
        '/sync/push',
        data: {
          'operations': [
            for (final change in ready)
              {
                'collection': change.collection,
                'op': change.op,
                'id': change.recordId,
                'base_version': change.baseVersion,
                'base_updated_at': change.baseUpdatedAt,
                'data': change.data == null ? null : jsonDecode(change.data!),
              },
          ],
        },
      ),
    );
    final results = (response.data!['results'] as List<dynamic>).cast<Json>();
    final resolvers = ref.read(conflictResolversProvider);
    var merged = false;
    for (var i = 0; i < ready.length && i < results.length; i++) {
      final change = ready[i];
      final result = results[i];
      final row = _db.update(_db.pendingChanges)
        ..where((r) => r.id.equals(change.id));
      switch (result['status']) {
        case 'ok':
          final record = result['record'] as Json?;
          if (record != null) {
            await _db.putDocument(change.collection, change.recordId, record);
          }
          await _remove(change.id);
        case 'conflict':
          final current = result['current'] as Json;
          final mine = jsonDecode(change.data ?? '{}') as Json;
          final base = change.base == null
              ? null
              : jsonDecode(change.base!) as Json;
          final resolved = resolvers[change.collection]?.call(
            base,
            mine,
            current,
          );
          if (resolved != null) {
            // Both sides changed different fields: push the merged record again.
            await row.write(
              PendingChangesCompanion(
                data: Value(jsonEncode(resolved)),
                base: Value(jsonEncode(current)),
                baseVersion: Value(current['version'] as int?),
                baseUpdatedAt: Value(current['updated_at'] as String?),
              ),
            );
            merged = true;
          } else {
            await row.write(
              PendingChangesCompanion(conflict: Value(jsonEncode(current))),
            );
          }
        default:
          await row.write(
            PendingChangesCompanion(
              error: Value(result['code'] as String? ?? 'unknown'),
            ),
          );
      }
    }
    await _refreshStatus();
    if (merged) await _push();
  }

  Future<void> _upload() async {
    final handler = ref.read(uploadHandlerProvider);
    if (handler == null) return;
    final uploads = await (_db.select(
      _db.pendingUploads,
    )..orderBy([(row) => OrderingTerm.asc(row.id)])).get();
    for (final upload in uploads) {
      final row = _db.update(_db.pendingUploads)
        ..where((r) => r.id.equals(upload.id));
      try {
        await handler(upload);
        await (_db.delete(
          _db.pendingUploads,
        )..where((r) => r.id.equals(upload.id))).go();
      } on ApiException catch (error) {
        // Without network the file simply waits; a rejected file is marked.
        if (error.code == ApiException.network) rethrow;
        await row.write(PendingUploadsCompanion(error: Value(error.code)));
      }
    }
  }

  Future<void> _pull() async {
    final store = ref.read(keyValueStoreProvider);
    final since = await store.read(lastSyncStorageKey);
    final response = await apiCall(
      () => _dio.get<Json>('/sync/changes', queryParameters: {'since': ?since}),
    );
    final collections = response.data!['collections'] as Json;
    // Records with a change that still waits are not overwritten by the server's state.
    final waiting = {
      for (final change in state.pending) (change.collection, change.recordId),
    };
    for (final entry in collections.entries) {
      final name = entry.key;
      final changes = entry.value as Json;
      final changed = (changes['changed'] as List<dynamic>).cast<Json>();
      if (changes['full'] == true) {
        await _db.replaceCollection(name, changed);
        continue;
      }
      for (final record in changed) {
        final id = record['id'] as String;
        if (!waiting.contains((name, id))) {
          await _db.putDocument(name, id, record);
        }
      }
      for (final id in (changes['deleted'] as List<dynamic>).cast<String>()) {
        await _db.deleteDocument(name, id);
      }
      final ids = (changes['ids'] as List<dynamic>?)?.cast<String>().toSet();
      if (ids != null) {
        for (final record in await _db.listDocuments(name)) {
          final id = record['id'] as String;
          // Access was taken away; local records still waiting to be pushed stay.
          if (!ids.contains(id) && !waiting.contains((name, id))) {
            await _db.deleteDocument(name, id);
          }
        }
      }
    }
    await store.write(
      lastSyncStorageKey,
      response.data!['server_time'] as String,
    );
  }

  /// Push, upload, pull. Returns false if the server could not be reached.
  /// Tries again if changes are still waiting, e.g. after the connection came
  /// back. Does nothing, and asks the server nothing, if all is in sync.
  Future<void> retryIfWaiting() async {
    if (state.waiting > 0 && !state.running) await sync();
  }

  Future<bool> sync() async {
    if (state.running || !ref.read(sessionProvider).isSignedIn) return false;
    await _refreshStatus(running: true);
    try {
      await _push();
      await _upload();
      await _pull();
      return true;
    } on ApiException {
      return false;
    } finally {
      await _refreshStatus(running: false);
      ref.read(syncGenerationProvider.notifier).bump();
    }
  }
}

final syncProvider = NotifierProvider<SyncService, SyncStatus>(SyncService.new);
