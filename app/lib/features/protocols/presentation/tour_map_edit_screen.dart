import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/map/geo.dart';
import '../../../core/map/map_view.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_repository.dart';

/// Draw a track by tapping points on the map, or set start and end.
class TourMapEditScreen extends ConsumerStatefulWidget {
  const TourMapEditScreen({
    super.key,
    required this.tourId,
    required this.drawTrack,
  });

  final String tourId;

  /// true: any number of points become a track. false: two points, start and end.
  final bool drawTrack;

  @override
  ConsumerState<TourMapEditScreen> createState() => _TourMapEditScreenState();
}

class _TourMapEditScreenState extends ConsumerState<TourMapEditScreen> {
  final _points = <GeoPoint>[];
  bool _busy = false;

  void _add(GeoPoint point) => setState(() {
    // For start and end a third tap starts over.
    if (!widget.drawTrack && _points.length >= 2) _points.clear();
    _points.add(point);
  });

  bool get _canSave =>
      widget.drawTrack ? _points.length >= 2 : _points.isNotEmpty;

  Future<void> _save() async {
    setState(() => _busy = true);
    final router = GoRouter.of(context);
    final repository = ref.read(tourRepositoryProvider);
    Map<String, dynamic> point(GeoPoint p) => {'lat': p.lat, 'lon': p.lon};
    try {
      if (widget.drawTrack) {
        await repository.saveDrawnTrack(widget.tourId, _points);
      } else {
        await repository.setPoints(
          widget.tourId,
          start: point(_points.first),
          end: _points.length > 1 ? point(_points.last) : null,
        );
      }
      ref.invalidate(tourProvider(widget.tourId));
      ref.invalidate(tourTrackProvider(widget.tourId));
      router.pop();
    } catch (error) {
      if (mounted) {
        showError(context, error);
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.drawTrack ? l10n.tourDrawTrack : l10n.tourSetPoints),
        actions: [
          IconButton(
            tooltip: l10n.tourDrawUndo,
            icon: const Icon(Icons.undo),
            onPressed: _points.isEmpty
                ? null
                : () => setState(_points.removeLast),
          ),
          TextButton(
            onPressed: _busy || !_canSave ? null : _save,
            child: Text(l10n.save),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.s),
            child: Text(
              widget.drawTrack
                  ? '${l10n.tourDrawHint} ${l10n.tourDrawPoints(_points.length)}'
                  : l10n.tourPointsHint,
            ),
          ),
          Expanded(
            child: HikerMap(
              content: MapContent(
                track: widget.drawTrack ? List.of(_points) : const [],
                onTap: _add,
                markers: [
                  for (var i = 0; i < _points.length; i++)
                    MapMarker(
                      id: 'point-$i',
                      position: _points[i],
                      size: 26,
                      child: IconMarker(
                        icon: i == 0
                            ? Icons.play_arrow
                            : (i == _points.length - 1
                                  ? Icons.flag
                                  : Icons.circle),
                        color: i == 0 ? scheme.primary : scheme.secondary,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
