import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_client.dart';

/// Bytes of an image behind the API. The key is `path?version`; the version
/// (e.g. the file id) changes when the image changes.
final apiImageProvider = FutureProvider.family<Uint8List, String>((
  ref,
  key,
) async {
  final dio = ref.watch(dioProvider);
  final response = await dio.get<List<int>>(
    key.split('#').first,
    options: Options(responseType: ResponseType.bytes),
  );
  return Uint8List.fromList(response.data!);
});

/// Shows an image that needs the access token, with a placeholder while it
/// loads or when it cannot be loaded.
class ApiImage extends ConsumerWidget {
  const ApiImage({
    super.key,
    required this.path,
    required this.version,
    this.size = 48,
    this.placeholder = Icons.image_outlined,
  });

  final String path;

  /// Null means "there is no image".
  final String? version;
  final double size;
  final IconData placeholder;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final empty = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(placeholder, color: scheme.onSurfaceVariant),
    );
    if (version == null) return empty;
    final image = ref.watch(apiImageProvider('$path#$version'));
    return image.when(
      loading: () => empty,
      error: (_, _) => empty,
      data: (bytes) => ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.memory(
          bytes,
          width: size,
          height: size,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        ),
      ),
    );
  }
}
