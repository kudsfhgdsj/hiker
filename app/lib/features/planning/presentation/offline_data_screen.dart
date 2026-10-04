import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/offline_routing.dart';

/// Path data for planning without network: load tiles from the own server
/// onto the device, or remove them again.
class OfflineDataScreen extends ConsumerStatefulWidget {
  const OfflineDataScreen({super.key});

  @override
  ConsumerState<OfflineDataScreen> createState() => _OfflineDataScreenState();
}

class _OfflineDataScreenState extends ConsumerState<OfflineDataScreen> {
  /// Share that is done, per tile that is loading right now.
  final _progress = <String, double>{};
  final _cancel = <String, CancelToken>{};

  @override
  void dispose() {
    for (final token in _cancel.values) {
      token.cancel();
    }
    super.dispose();
  }

  Future<void> _download(String name) async {
    final token = _cancel[name] = CancelToken();
    setState(() => _progress[name] = 0);
    try {
      await ref
          .read(segmentStoreProvider)
          .download(
            name,
            cancel: token,
            onProgress: (share) {
              if (mounted) setState(() => _progress[name] = share);
            },
          );
      ref.read(segmentGenerationProvider.notifier).bump();
    } catch (error) {
      if (mounted && !token.isCancelled) showError(context, error);
    } finally {
      _cancel.remove(name);
      if (mounted) setState(() => _progress.remove(name));
    }
  }

  Future<void> _delete(String name) async {
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

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final installed = {
      for (final segment
          in ref.watch(installedSegmentsProvider).asData?.value ??
              const <SegmentInfo>[])
        segment.name: segment,
    };
    return Scaffold(
      appBar: AppBar(title: Text(l10n.offlineTitle)),
      body: AsyncBody(
        value: ref.watch(availableSegmentsProvider),
        onRetry: () => ref.invalidate(availableSegmentsProvider),
        builder: (available) {
          // What the server offers, and what is on the device but no longer offered.
          final segments = {
            for (final segment in available) segment.name: segment,
            for (final segment in installed.values)
              if (!available.any((a) => a.name == segment.name))
                segment.name: segment,
          }.values.toList();
          return ListView(
            padding: const EdgeInsets.all(AppSpacing.m),
            children: [
              Text(l10n.offlineIntro),
              const SizedBox(height: AppSpacing.s),
              Text(l10n.offlineMapNote, style: theme.textTheme.bodySmall),
              const SizedBox(height: AppSpacing.m),
              if (segments.isEmpty) Text(l10n.offlineNone),
              for (final segment in segments)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.m),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(segment.name, style: theme.textTheme.titleMedium),
                        Text(_area(l10n, segment)),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          [
                            _megabytes(segment.sizeBytes),
                            if (installed[segment.name] case final local?)
                              l10n.offlineLoaded(
                                Format.date(local.modified ?? DateTime.now()),
                              ),
                          ].join(' · '),
                          style: theme.textTheme.bodySmall,
                        ),
                        const SizedBox(height: AppSpacing.s),
                        if (_progress[segment.name] case final share?) ...[
                          LinearProgressIndicator(value: share),
                          const SizedBox(height: AppSpacing.xs),
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  l10n.offlineLoading(
                                    '${(share * 100).round()}',
                                  ),
                                ),
                              ),
                              TextButton(
                                onPressed: () =>
                                    _cancel[segment.name]?.cancel(),
                                child: Text(l10n.cancel),
                              ),
                            ],
                          ),
                        ] else
                          Wrap(
                            spacing: AppSpacing.s,
                            children: [
                              if (available.any((a) => a.name == segment.name))
                                FilledButton.tonalIcon(
                                  onPressed: () => _download(segment.name),
                                  icon: const Icon(Icons.download),
                                  label: Text(
                                    installed.containsKey(segment.name)
                                        ? l10n.offlineUpdate
                                        : l10n.offlineDownload,
                                  ),
                                ),
                              if (installed.containsKey(segment.name))
                                OutlinedButton(
                                  onPressed: () => _delete(segment.name),
                                  child: Text(l10n.offlineRemove),
                                ),
                            ],
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
