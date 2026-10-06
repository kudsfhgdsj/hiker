import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/map/map_regions.dart';
import '../../../core/map/map_view.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/offline_routing.dart';

/// Everything the app can take along for use without network: the map of a
/// region and the path data for planning, both from the user's own server.
class OfflineDataScreen extends ConsumerStatefulWidget {
  const OfflineDataScreen({super.key});

  @override
  ConsumerState<OfflineDataScreen> createState() => _OfflineDataScreenState();
}

class _OfflineDataScreenState extends ConsumerState<OfflineDataScreen> {
  /// Share that is done, per download that is running right now.
  final _progress = <String, double>{};
  final _cancel = <String, CancelToken>{};

  @override
  void dispose() {
    for (final token in _cancel.values) {
      token.cancel();
    }
    super.dispose();
  }

  /// Runs a download and shows its progress under [key].
  Future<void> _load(
    String key,
    Future<void> Function(CancelToken cancel, void Function(double) progress)
    download,
  ) async {
    final token = _cancel[key] = CancelToken();
    setState(() => _progress[key] = 0);
    try {
      await download(token, (share) {
        if (mounted) setState(() => _progress[key] = share);
      });
    } catch (error) {
      if (mounted && !token.isCancelled) showError(context, error);
    } finally {
      _cancel.remove(key);
      if (mounted) setState(() => _progress.remove(key));
    }
  }

  /// Loads the map; where the server offers finer elevation, asks first how
  /// fine it should be without network. [loaded] is what the device has.
  Future<void> _chooseAndLoadMap(MapRegion region, MapRegion? loaded) async {
    var detail = 0;
    if (region.layersSizeBytes != null && region.detailSizes.isNotEmpty) {
      final chosen = await showDialog<int>(
        context: context,
        builder: (context) =>
            _DetailDialog(region: region, current: loaded?.detail),
      );
      if (chosen == null) return;
      detail = chosen;
    }
    await _loadMap(region, detail);
  }

  Future<void> _loadMap(MapRegion region, int detail) =>
      _load('map:${region.name}', (cancel, progress) async {
        await ref
            .read(mapRegionStoreProvider)
            .download(
              region,
              detail: detail,
              cancel: cancel,
              onProgress: progress,
            );
        // Style and fonts too, so that the map is complete without network.
        await prepareOfflineMap(ref);
        ref.read(mapRegionGenerationProvider.notifier).bump();
      });

  Future<void> _removeMap(String name) async {
    await ref.read(mapRegionStoreProvider).delete(name);
    ref.read(mapRegionGenerationProvider.notifier).bump();
  }

  Future<void> _loadSegment(String name) =>
      _load('segment:$name', (cancel, progress) async {
        await ref
            .read(segmentStoreProvider)
            .download(name, cancel: cancel, onProgress: progress);
        ref.read(segmentGenerationProvider.notifier).bump();
      });

  Future<void> _removeSegment(String name) async {
    await ref.read(segmentStoreProvider).delete(name);
    ref.read(segmentGenerationProvider.notifier).bump();
  }

  /// "5°–10° Ost, 45°–50° Nord", with the name of the region where it is known.
  String _area(AppLocalizations l10n, SegmentInfo segment) {
    final (lon, lat) = segment.corner;
    final region = switch (segment.name) {
      'E5_N45' => l10n.offlineRegionE5N45,
      'E10_N45' => l10n.offlineRegionE10N45,
      'E15_N45' => l10n.offlineRegionE15N45,
      'E5_N40' => l10n.offlineRegionE5N40,
      'E10_N40' => l10n.offlineRegionE10N40,
      _ => null,
    };
    String span(int from, String positive, String negative) => from < 0
        ? '${-from}°–${-(from + 5)}° $negative'
        : '$from°–${from + 5}° $positive';
    final extent =
        '${span(lon, l10n.offlineEast, l10n.offlineWest)}, '
        '${span(lat, l10n.offlineNorth, l10n.offlineSouth)}';
    return region == null ? extent : '$region\n$extent';
  }

  String _megabytes(int bytes) => '${Format.number((bytes / 1e6).round())} MB';

  Widget _card({
    required String progressKey,
    required String title,
    String? description,
    required int sizeBytes,
    required DateTime? loaded,
    required bool isLoaded,
    required bool offered,
    required VoidCallback onLoad,
    required VoidCallback onRemove,
  }) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: theme.textTheme.titleMedium),
            if (description != null) Text(description),
            const SizedBox(height: AppSpacing.xs),
            Text(
              [
                _megabytes(sizeBytes),
                if (isLoaded)
                  l10n.offlineLoaded(Format.date(loaded ?? DateTime.now())),
              ].join(' · '),
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: AppSpacing.s),
            if (_progress[progressKey] case final share?) ...[
              LinearProgressIndicator(value: share),
              const SizedBox(height: AppSpacing.xs),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      l10n.offlineLoading('${(share * 100).round()}'),
                    ),
                  ),
                  TextButton(
                    onPressed: () => _cancel[progressKey]?.cancel(),
                    child: Text(l10n.cancel),
                  ),
                ],
              ),
            ] else
              Wrap(
                spacing: AppSpacing.s,
                children: [
                  if (offered)
                    FilledButton.tonalIcon(
                      onPressed: onLoad,
                      icon: const Icon(Icons.download),
                      label: Text(
                        isLoaded ? l10n.offlineUpdate : l10n.offlineDownload,
                      ),
                    ),
                  if (isLoaded)
                    OutlinedButton(
                      onPressed: onRemove,
                      child: Text(l10n.offlineRemove),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  /// What the server offers, and what is on the device but no longer offered.
  List<T> _merged<T>(
    List<T> offered,
    Iterable<T> local,
    String Function(T) name,
  ) => {
    for (final item in offered) name(item): item,
    for (final item in local)
      if (!offered.any((o) => name(o) == name(item))) name(item): item,
  }.values.toList();

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final localMaps = {
      for (final region
          in ref.watch(installedMapRegionsProvider).asData?.value ??
              const <MapRegion>[])
        region.name: region,
    };
    final localSegments = {
      for (final segment
          in ref.watch(installedSegmentsProvider).asData?.value ??
              const <SegmentInfo>[])
        segment.name: segment,
    };
    final maps = ref.watch(availableMapRegionsProvider);
    final segments = ref.watch(availableSegmentsProvider);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.offlineTitle)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.m),
        children: [
          Text(l10n.offlineMaps, style: theme.textTheme.titleLarge),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.offlineMapsIntro),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.offlineMapNote, style: theme.textTheme.bodySmall),
          const SizedBox(height: AppSpacing.s),
          AsyncBody(
            value: maps,
            onRetry: () => ref.invalidate(availableMapRegionsProvider),
            builder: (offered) {
              final all = _merged(offered, localMaps.values, (m) => m.name);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (all.isEmpty) Text(l10n.offlineMapsNone),
                  for (final region in all)
                    _card(
                      progressKey: 'map:${region.name}',
                      title: region.name,
                      description: [
                        region.layersSizeBytes == null
                            ? l10n.offlineMapOnly
                            : l10n.offlineMapWithLayers,
                        if (localMaps[region.name] case final local?
                            when region.detailSizes.isNotEmpty ||
                                local.detail > 0)
                          l10n.offlineDetailLoaded(
                            detailName(l10n, local.detail),
                          ),
                      ].join('\n'),
                      // What is on the device, else the map with its layer pack.
                      sizeBytes: switch (localMaps[region.name]) {
                        final local? => local.bytesWith(local.detail),
                        null => region.totalBytes,
                      },
                      loaded: localMaps[region.name]?.modified,
                      isLoaded: localMaps.containsKey(region.name),
                      offered: offered.any((o) => o.name == region.name),
                      onLoad: () => _chooseAndLoadMap(
                        offered.firstWhere((o) => o.name == region.name),
                        localMaps[region.name],
                      ),
                      onRemove: () => _removeMap(region.name),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: AppSpacing.l),
          Text(l10n.offlineSegments, style: theme.textTheme.titleLarge),
          const SizedBox(height: AppSpacing.xs),
          Text(l10n.offlineIntro),
          const SizedBox(height: AppSpacing.s),
          AsyncBody(
            value: segments,
            onRetry: () => ref.invalidate(availableSegmentsProvider),
            builder: (offered) {
              final all = _merged(offered, localSegments.values, (s) => s.name);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (all.isEmpty) Text(l10n.offlineNone),
                  for (final segment in all)
                    _card(
                      progressKey: 'segment:${segment.name}',
                      title: segment.name,
                      description: _area(l10n, segment),
                      sizeBytes: segment.sizeBytes,
                      loaded: localSegments[segment.name]?.modified,
                      isLoaded: localSegments.containsKey(segment.name),
                      offered: offered.any((o) => o.name == segment.name),
                      onLoad: () => _loadSegment(segment.name),
                      onRemove: () => _removeSegment(segment.name),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// The name of a level of detail: 0 is the layer pack alone.
String detailName(AppLocalizations l10n, int level) => switch (level) {
  0 => l10n.offlineDetailBase,
  1 => l10n.offlineDetailSmall,
  2 => l10n.offlineDetailMedium,
  3 => l10n.offlineDetailFull,
  _ => '$level',
};

/// Asks how fine elevation, slope and contour lines of a map should be
/// without network; answers with the level, or nothing when it is closed.
class _DetailDialog extends StatefulWidget {
  const _DetailDialog({required this.region, this.current});

  final MapRegion region;

  /// The level that is on the device; null if the map is not loaded yet.
  final int? current;

  @override
  State<_DetailDialog> createState() => _DetailDialogState();
}

class _DetailDialogState extends State<_DetailDialog> {
  // Medium by default: close to what the map shows with network.
  late int _level =
      widget.current ??
      (widget.region.detailSizes.length >= 2
          ? 2
          : widget.region.detailSizes.length);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final region = widget.region;
    String note(int level) => switch (level) {
      0 => l10n.offlineDetailBaseNote,
      1 => l10n.offlineDetailSmallNote,
      2 => l10n.offlineDetailMediumNote,
      3 => l10n.offlineDetailFullNote,
      _ => '',
    };
    return AlertDialog(
      title: Text(l10n.offlineDetailTitle),
      contentPadding: const EdgeInsets.only(top: AppSpacing.s),
      content: SingleChildScrollView(
        child: RadioGroup<int>(
          groupValue: _level,
          onChanged: (level) => setState(() => _level = level ?? _level),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var level = 0; level <= region.detailSizes.length; level++)
                RadioListTile<int>(
                  key: ValueKey('detail-$level'),
                  value: level,
                  title: Text(
                    '${detailName(l10n, level)} · '
                    '${Format.number((region.bytesWith(level) / 1e6).round())} MB',
                  ),
                  subtitle: Text(note(level)),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_level),
          child: Text(l10n.offlineDownload),
        ),
      ],
    );
  }
}
