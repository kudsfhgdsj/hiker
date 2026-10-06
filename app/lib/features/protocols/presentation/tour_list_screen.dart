import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/map/map_view.dart';
import '../../../core/modules/feature_module.dart';
import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/api_image.dart';
import '../../../core/widgets/empty_list.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_models.dart';
import '../data/tour_repository.dart';

class TourListScreen extends ConsumerStatefulWidget {
  const TourListScreen({super.key});

  @override
  ConsumerState<TourListScreen> createState() => _TourListScreenState();
}

class _TourListScreenState extends ConsumerState<TourListScreen> {
  Timer? _debounce;
  String _query = '';

  /// Only tours with this tag are shown; null: all.
  String? _tag;

  /// All tours on one map instead of the list.
  bool _onMap = false;

  void _chooseTag(String? tag) => setState(() => _tag = tag);

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  void _search(String text) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _query = text.trim());
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l10n.toursTitle),
          actions: [
            IconButton(
              tooltip: _onMap ? l10n.toursShowList : l10n.toursShowMap,
              icon: Icon(_onMap ? Icons.view_list : Icons.map_outlined),
              onPressed: () => setState(() => _onMap = !_onMap),
            ),
            // Totals, climbed peaks and where the user has been.
            if (ref.watch(activeModulesProvider).any((m) => m.id == 'reports'))
              IconButton(
                tooltip: l10n.statsTitle,
                icon: const Icon(Icons.insights_outlined),
                onPressed: () => context.push('/stats'),
              ),
          ],
          bottom: TabBar(
            tabs: [
              Tab(text: l10n.toursMine),
              Tab(text: l10n.toursShared),
            ],
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => context.push('/protocols/new'),
          icon: const Icon(Icons.add),
          label: Text(l10n.tourNew),
        ),
        body: Column(
          children: [
            // The search is for the list; the map shows all tours of the choice.
            if (!_onMap)
              Padding(
                padding: const EdgeInsets.all(AppSpacing.m),
                child: TextField(
                  decoration: InputDecoration(
                    prefixIcon: const Icon(Icons.search),
                    labelText: l10n.search,
                    hintText: l10n.tourSearchHint,
                  ),
                  textInputAction: TextInputAction.search,
                  onChanged: _search,
                ),
              ),
            Expanded(
              child: TabBarView(
                // The map takes the gestures that would change the tab.
                physics: _onMap ? const NeverScrollableScrollPhysics() : null,
                children: [
                  for (final (scope, empty) in [
                    ('mine', l10n.toursEmpty),
                    ('shared', l10n.toursSharedEmpty),
                  ])
                    _onMap
                        ? _TourMap(scope: scope, tag: _tag, onTag: _chooseTag)
                        : _TourList(
                            scope: scope,
                            query: _query,
                            empty: empty,
                            tag: _tag,
                            onTag: _chooseTag,
                          ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TourList extends ConsumerWidget {
  const _TourList({
    required this.scope,
    required this.query,
    required this.empty,
    required this.tag,
    required this.onTag,
  });

  final String scope;
  final String query;
  final String empty;
  final String? tag;
  final ValueChanged<String?> onTag;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final request = (scope: scope, query: query);
    return AsyncBody(
      value: ref.watch(tourListProvider(request)),
      onRetry: () => ref.invalidate(tourListProvider(request)),
      builder: (loaded) {
        final tours = [
          for (final tour in loaded.value)
            if (tag == null || tour.hasTag(tag!)) tour,
        ];
        return Column(
          children: [
            if (loaded.offline) const OfflineBanner(),
            _TagBar(
              tags: countTags(loaded.value.map((tour) => tour.tags)),
              chosen: tag,
              onTag: onTag,
            ),
            Expanded(
              child: tours.isEmpty
                  ? EmptyList(
                      text: tag != null && loaded.value.isNotEmpty
                          ? AppLocalizations.of(context).toursTagEmpty(tag!)
                          : empty,
                      onRefresh: () =>
                          ref.refresh(tourListProvider(request).future),
                    )
                  : RefreshIndicator(
                      onRefresh: () =>
                          ref.refresh(tourListProvider(request).future),
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(
                          AppSpacing.m,
                          0,
                          AppSpacing.m,
                          88,
                        ),
                        itemCount: tours.length,
                        itemBuilder: (context, index) =>
                            _TourCard(tour: tours[index]),
                      ),
                    ),
            ),
          ],
        );
      },
    );
  }
}

/// The tags in use as a row of choices; a tap on the chosen one shows all
/// tours again. Nothing where no tour has a tag.
class _TagBar extends StatelessWidget {
  const _TagBar({
    required this.tags,
    required this.chosen,
    required this.onTag,
  });

  final List<(String, int)> tags;
  final String? chosen;
  final ValueChanged<String?> onTag;

  @override
  Widget build(BuildContext context) {
    if (tags.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: 48,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.m),
        children: [
          for (final (tag, count) in tags)
            Padding(
              padding: const EdgeInsets.only(right: AppSpacing.xs),
              child: FilterChip(
                key: ValueKey('tag-$tag'),
                label: Text('$tag · $count'),
                selected: chosen?.toLowerCase() == tag.toLowerCase(),
                onSelected: (on) => onTag(on ? tag : null),
              ),
            ),
        ],
      ),
    );
  }
}

/// All tours of a scope on one map: each track as a line and a marker at its
/// start that opens the tour.
class _TourMap extends ConsumerWidget {
  const _TourMap({required this.scope, required this.tag, required this.onTag});

  final String scope;
  final String? tag;
  final ValueChanged<String?> onTag;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return AsyncBody(
      value: ref.watch(tourLinesProvider(scope)),
      onRetry: () => ref.invalidate(tourLinesProvider(scope)),
      builder: (loaded) {
        final lines = [
          for (final line in loaded.value)
            if (tag == null || line.hasTag(tag!)) line,
        ];
        return Column(
          children: [
            if (loaded.offline) const OfflineBanner(),
            _TagBar(
              tags: countTags(loaded.value.map((line) => line.tags)),
              chosen: tag,
              onTag: onTag,
            ),
            Expanded(
              child: lines.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.l),
                        child: Text(
                          l10n.toursMapEmpty,
                          textAlign: TextAlign.center,
                        ),
                      ),
                    )
                  : HikerMap(
                      content: MapContent(
                        heatLines: [
                          for (final line in lines)
                            if (line.points.length > 1) line.points,
                        ],
                        markers: [
                          for (final line in lines)
                            MapMarker(
                              id: line.tourId,
                              position: line.points.first,
                              clusters: true,
                              onTap: () => context.push(
                                '/protocols/tour/${line.tourId}',
                              ),
                              child: Tooltip(
                                message: line.title,
                                child: Icon(
                                  Icons.location_on,
                                  color: theme.colorScheme.error,
                                  size: 36,
                                ),
                              ),
                            ),
                        ],
                        // A group of tours that lie close together: choose one.
                        onClusterTap: (ids) => _choose(context, lines, ids),
                      ),
                    ),
            ),
            if (lines.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.m,
                  AppSpacing.xs,
                  AppSpacing.m,
                  88,
                ),
                child: Text(
                  l10n.toursMapHint,
                  style: theme.textTheme.bodySmall,
                ),
              ),
          ],
        );
      },
    );
  }

  void _choose(BuildContext context, List<TourLine> lines, List<String> ids) {
    final chosen = [
      for (final line in lines)
        if (ids.contains(line.tourId)) line,
    ];
    showModalBottomSheet<void>(
      context: context,
      builder: (sheet) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (final line in chosen)
              ListTile(
                title: Text(line.title),
                subtitle: line.date == null
                    ? null
                    : Text(Format.date(line.date!)),
                onTap: () {
                  Navigator.of(sheet).pop();
                  context.push('/protocols/tour/${line.tourId}');
                },
              ),
          ],
        ),
      ),
    );
  }
}

class _TourCard extends StatelessWidget {
  const _TourCard({required this.tour});

  final Tour tour;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final details = [
      if (tour.startTime != null) Format.date(tour.startTime!),
      if (tour.peakNames.isNotEmpty) tour.peakNames.join(', '),
      if (!tour.isOwner && tour.ownerName != null)
        l10n.tourSharedBy(tour.ownerName!),
    ];
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/protocols/tour/${tour.id}'),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.m),
          child: Row(
            children: [
              ApiImage(
                path:
                    '/tours/${tour.id}/photos/${tour.coverPhotoId}/image?size=thumb',
                version: tour.coverPhotoId,
                size: 64,
                placeholder: Icons.terrain,
              ),
              const SizedBox(width: AppSpacing.m),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(tour.title, style: theme.textTheme.titleMedium),
                    for (final line in details)
                      Text(line, style: theme.textTheme.bodySmall),
                    if (tour.tags.isNotEmpty)
                      Text(
                        tour.tags.map((tag) => '#$tag').join('  '),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.primary,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
