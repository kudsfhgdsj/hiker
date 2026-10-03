import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/map/geo.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/api_image.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_repository.dart';

/// Full-screen gallery in the order along the track. Returns the position of
/// a photo if the user wants to see it on the map.
Future<GeoPoint?> showPhotoGallery(
  BuildContext context, {
  required String tourId,
  required List<Json> photos,
  required String initialId,
  required bool canEdit,
  required VoidCallback onChanged,
}) => Navigator.of(context).push<GeoPoint>(
  MaterialPageRoute(
    fullscreenDialog: true,
    builder: (context) => _Gallery(
      tourId: tourId,
      photos: photos,
      initialId: initialId,
      canEdit: canEdit,
      onChanged: onChanged,
    ),
  ),
);

class _Gallery extends ConsumerStatefulWidget {
  const _Gallery({
    required this.tourId,
    required this.photos,
    required this.initialId,
    required this.canEdit,
    required this.onChanged,
  });

  final String tourId;
  final List<Json> photos;
  final String initialId;
  final bool canEdit;
  final VoidCallback onChanged;

  @override
  ConsumerState<_Gallery> createState() => _GalleryState();
}

class _GalleryState extends ConsumerState<_Gallery> {
  late int _index = widget.photos
      .indexWhere((p) => p['id'] == widget.initialId)
      .clamp(0, widget.photos.length - 1);
  late final _controller = PageController(initialPage: _index);

  Json get _photo => widget.photos[_index];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _change(
    Future<void> Function(TourRepository r) action, {
    bool close = true,
  }) async {
    final navigator = Navigator.of(context);
    try {
      await action(ref.read(tourRepositoryProvider));
      widget.onChanged();
      if (close) navigator.pop();
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Future<void> _editCaption() async {
    final controller = TextEditingController(
      text: _photo['caption'] as String?,
    );
    final l10n = AppLocalizations.of(context);
    final caption = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.tourPhotoCaption),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 500,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: Text(l10n.save),
          ),
        ],
      ),
    );
    if (caption != null) {
      await _change(
        (r) => r.updatePhoto(widget.tourId, _photo['id'] as String, {
          'caption': caption,
        }),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final photo = _photo;
    final id = photo['id'] as String;
    final hasPosition = photo['lat'] != null;
    final details = [
      if (photo['taken_at'] != null)
        Format.dateTime(DateTime.parse(photo['taken_at'] as String)),
      if (photo['elevation_m'] != null)
        Format.meters(photo['elevation_m'] as num),
      if (!hasPosition) l10n.tourPhotoNoPosition,
      if (photo['is_cover'] == true) l10n.tourPhotoIsCover,
    ].join(' · ');
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text('${_index + 1} / ${widget.photos.length}'),
        actions: [
          if (hasPosition)
            IconButton(
              tooltip: l10n.tourPhotoShowOnMap,
              icon: const Icon(Icons.map_outlined),
              onPressed: () => Navigator.pop(
                context,
                GeoPoint(
                  (photo['lat'] as num).toDouble(),
                  (photo['lon'] as num).toDouble(),
                ),
              ),
            ),
          if (widget.canEdit)
            PopupMenuButton<VoidCallback>(
              onSelected: (action) => action(),
              itemBuilder: (context) => [
                PopupMenuItem(
                  value: _editCaption,
                  child: Text(l10n.tourPhotoCaption),
                ),
                PopupMenuItem(
                  value: () => _change(
                    (r) => r.updatePhoto(widget.tourId, id, {'is_cover': true}),
                  ),
                  child: Text(l10n.tourPhotoCover),
                ),
                PopupMenuItem(
                  value: () => _change((r) => r.deletePhoto(widget.tourId, id)),
                  child: Text(l10n.delete),
                ),
              ],
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: PageView.builder(
              controller: _controller,
              itemCount: widget.photos.length,
              onPageChanged: (index) => setState(() => _index = index),
              itemBuilder: (context, index) {
                final item = widget.photos[index];
                final image = ref.watch(
                  apiImageProvider(
                    '/tours/${widget.tourId}/photos/${item['id']}/image#${item['id']}',
                  ),
                );
                return image.when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (_, _) => const Center(
                    child: Icon(
                      Icons.broken_image_outlined,
                      color: Colors.white54,
                      size: 48,
                    ),
                  ),
                  data: (bytes) => InteractiveViewer(
                    child: Image.memory(
                      bytes,
                      fit: BoxFit.contain,
                      gaplessPlayback: true,
                    ),
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.m),
            child: Column(
              children: [
                if ((photo['caption'] as String?)?.isNotEmpty ?? false)
                  Text(
                    photo['caption'] as String,
                    style: const TextStyle(color: Colors.white, fontSize: 16),
                    textAlign: TextAlign.center,
                  ),
                Text(details, style: const TextStyle(color: Colors.white70)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
