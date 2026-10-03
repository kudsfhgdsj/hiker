import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/db/app_database.dart';

void main() {
  late AppDatabase database;

  setUp(() => database = AppDatabase(NativeDatabase.memory()));
  tearDown(() => database.close());

  test('documents are stored per collection and can be updated', () async {
    await database.putDocument('gear_items', 'a', {'id': 'a', 'name': 'Zelt'});
    await database.putDocument('tours', 'a', {'id': 'a', 'title': 'Säntis'});
    await database.putDocument('gear_items', 'a', {
      'id': 'a',
      'name': 'Zelt neu',
    });

    expect(await database.getDocument('gear_items', 'a'), {
      'id': 'a',
      'name': 'Zelt neu',
    });
    expect(await database.getDocument('tours', 'a'), {
      'id': 'a',
      'title': 'Säntis',
    });
    expect(await database.getDocument('gear_items', 'b'), isNull);
    expect(await database.listDocuments('gear_items'), hasLength(1));
  });

  test('replaceCollection drops documents that are gone', () async {
    await database.putDocument('gear_items', 'old', {'id': 'old'});
    await database.putDocument('tours', 't', {'id': 't'});

    await database.replaceCollection('gear_items', [
      {'id': 'a', 'name': 'Zelt'},
      {'id': 'b', 'name': 'Kocher'},
    ]);

    final names = (await database.listDocuments('gear_items'))
        .map((d) => d['id']);
    expect(names, unorderedEquals(['a', 'b']));
    expect(await database.listDocuments('tours'), hasLength(1));
  });

  test('delete and clear', () async {
    await database.putDocument('gear_items', 'a', {'id': 'a'});
    await database.putDocument('tours', 't', {'id': 't'});

    await database.deleteDocument('gear_items', 'a');
    expect(await database.listDocuments('gear_items'), isEmpty);

    await database.clear();
    expect(await database.listDocuments('tours'), isEmpty);
  });
}
