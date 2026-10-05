import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

part 'app_database.g.dart';

/// Local copy of the records the app has seen, so that it works without network.
/// One row per record: `collection` names the kind (e.g. `gear_items`), the
/// record itself is kept as the JSON document the API delivered.
class CachedDocuments extends Table {
  TextColumn get collection => text()();
  TextColumn get id => text()();
  TextColumn get json => text()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {collection, id};
}

/// A change made while the server could not be reached, waiting to be pushed.
class PendingChanges extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get collection => text()();

  /// `upsert` or `delete`.
  TextColumn get op => text()();
  TextColumn get recordId => text()();
  IntColumn get baseVersion => integer().nullable()();
  TextColumn get baseUpdatedAt => text().nullable()();

  /// The record as JSON, for upsert.
  TextColumn get data => text().nullable()();

  /// The record before the first offline change, for merging after a conflict.
  TextColumn get base => text().nullable()();

  /// The server's record, set when the push ended in a conflict.
  TextColumn get conflict => text().nullable()();

  /// Error code of the server, set when the push was rejected.
  TextColumn get error => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
}

/// A file (GPX or photo) waiting to be uploaded.
class PendingUploads extends Table {
  IntColumn get id => integer().autoIncrement()();

  /// `gpx` or `photo`.
  TextColumn get kind => text()();
  TextColumn get tourId => text()();
  TextColumn get filename => text()();
  BlobColumn get bytes => blob()();
  TextColumn get error => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
}

@DriftDatabase(tables: [CachedDocuments, PendingChanges, PendingUploads])
class AppDatabase extends _$AppDatabase {
  AppDatabase([QueryExecutor? executor])
    : super(executor ?? driftDatabase(name: 'hiker'));

  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onUpgrade: (migrator, from, to) async {
      if (from < 2) {
        await migrator.createTable(pendingChanges);
        await migrator.createTable(pendingUploads);
      }
    },
  );

  Future<void> putDocument(
    String collection,
    String id,
    Map<String, dynamic> document,
  ) => into(cachedDocuments).insertOnConflictUpdate(
    CachedDocumentsCompanion.insert(
      collection: collection,
      id: id,
      json: jsonEncode(document),
      updatedAt: DateTime.now().toUtc(),
    ),
  );

  /// Replaces all documents of a collection, e.g. after loading a full list.
  Future<void> replaceCollection(
    String collection,
    Iterable<Map<String, dynamic>> documents, {
    String idField = 'id',
  }) => transaction(() async {
    await (delete(
      cachedDocuments,
    )..where((row) => row.collection.equals(collection))).go();
    for (final document in documents) {
      await putDocument(collection, document[idField] as String, document);
    }
  });

  Future<Map<String, dynamic>?> getDocument(
    String collection,
    String id,
  ) async {
    final row =
        await (select(cachedDocuments)
              ..where((r) => r.collection.equals(collection) & r.id.equals(id)))
            .getSingleOrNull();
    return row == null ? null : jsonDecode(row.json) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> listDocuments(String collection) async {
    final rows = await (select(
      cachedDocuments,
    )..where((row) => row.collection.equals(collection))).get();
    return [
      for (final row in rows) jsonDecode(row.json) as Map<String, dynamic>,
    ];
  }

  Future<void> deleteDocument(String collection, String id) => (delete(
    cachedDocuments,
  )..where((r) => r.collection.equals(collection) & r.id.equals(id))).go();

  /// Removes everything, e.g. when the user signs out. Changes that were not
  /// synced yet are lost.
  Future<void> clear() => transaction(() async {
    await delete(cachedDocuments).go();
    await delete(pendingChanges).go();
    await delete(pendingUploads).go();
  });
}

final appDatabaseProvider = Provider<AppDatabase>((ref) {
  final database = AppDatabase();
  ref.onDispose(database.close);
  return database;
});
