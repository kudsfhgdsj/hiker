import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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
                children: [
                  _TourList(
                    scope: 'mine',
                    query: _query,
                    empty: l10n.toursEmpty,
                  ),
                  _TourList(
                    scope: 'shared',
                    query: _query,
                    empty: l10n.toursSharedEmpty,
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
  });

  final String scope;
  final String query;
  final String empty;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final request = (scope: scope, query: query);
    return AsyncBody(
      value: ref.watch(tourListProvider(request)),
      onRetry: () => ref.invalidate(tourListProvider(request)),
      builder: (loaded) => Column(
        children: [
          if (loaded.offline) const OfflineBanner(),
          Expanded(
            child: loaded.value.isEmpty
                ? EmptyList(
                    text: empty,
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
                      itemCount: loaded.value.length,
                      itemBuilder: (context, index) =>
                          _TourCard(tour: loaded.value[index]),
                    ),
                  ),
          ),
        ],
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
