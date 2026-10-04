import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class PickedFile {
  const PickedFile(this.name, this.bytes);

  final String name;
  final Uint8List bytes;
}

typedef PickFiles = Future<List<PickedFile>> Function({
  required List<String> extensions,
  bool multiple,
});

Future<List<PickedFile>> _pick({
  required List<String> extensions,
  bool multiple = false,
}) async {
  final List<PlatformFile> files;
  if (multiple) {
    files = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: extensions,
    );
  } else {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: extensions,
    );
    files = [?file];
  }
  return [
    for (final file in files) PickedFile(file.name, await file.readAsBytes()),
  ];
}

/// Lets the user choose files from the device; replaced in tests.
final filePickerProvider = Provider<PickFiles>((ref) => _pick);

const imageExtensions = ['jpg', 'jpeg', 'png', 'webp'];

typedef SaveFile = Future<bool> Function({
  required String name,
  required Uint8List bytes,
  required String mimeType,
});

Future<bool> _save({
  required String name,
  required Uint8List bytes,
  required String mimeType,
}) async =>
    await FilePicker.saveFile(
      fileName: name,
      bytes: bytes,
      mimeType: mimeType,
    ) !=
    null;

/// Lets the user choose where to store a file; false if they cancelled.
/// Replaced in tests.
final fileSaverProvider = Provider<SaveFile>((ref) => _save);
