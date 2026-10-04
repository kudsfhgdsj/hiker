import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/empty_list.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/route_models.dart';
import '../data/route_repository.dart';

class RouteListScreen extends ConsumerStatefulWidget {
  const RouteListScreen({super.key});

  @override
  ConsumerState<RouteListScreen> createState() => _RouteListScreenState();
}

class _RouteListScreenState extends ConsumerState<RouteListScreen> {
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
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.planTitle),
        actions: [
          IconButton(
            tooltip: l10n.offlineTitle,
            icon: const Icon(Icons.download_for_offline_outlined),
            onPressed: () => context.push('/planning/offline'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/planning/new'),
        icon: const Icon(Icons.add),
        label: Text(l10n.planNew),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.m),
            child: TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(Icons.search),
                labelText: l10n.search,
              ),
              textInputAction: TextInputAction.search,
              onChanged: _search,
            ),
          ),
          Expanded(
            child: AsyncBody(
              value: ref.watch(routeListProvider(_query)),
              onRetry: () => ref.invalidate(routeListProvider(_query)),
              builder: (loaded) => Column(
                children: [
                  if (loaded.offline) const OfflineBanner(),
                  Expanded(
                    child: loaded.value.isEmpty
                        ? EmptyList(
                            text: l10n.planEmpty,
                            onRefresh: () =>
                                ref.refresh(routeListProvider(_query).future),
                          )
                        : RefreshIndicator(
                            onRefresh: () =>
                                ref.refresh(routeListProvider(_query).future),
                            child: ListView.builder(
                              padding: const EdgeInsets.fromLTRB(
                                AppSpacing.m,
                                0,
                                AppSpacing.m,
                                88,
                              ),
                              itemCount: loaded.value.length,
                              itemBuilder: (context, index) =>
                                  _RouteCard(route: loaded.value[index]),
                            ),
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

class _RouteCard extends StatelessWidget {
  const _RouteCard({required this.route});

  final PlannedRoute route;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final figures = route.distanceM == null
        // Drafted offline: the server computes the line with the next sync.
        ? l10n.planPending
        : [
            Format.distance(route.distanceM),
            '↑ ${Format.meters(route.ascentM)}',
            Format.duration((route.durationS! / 60).round()),
          ].join(' · ');
    return Card(
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        leading: const Icon(Icons.route_outlined),
        title: Text(route.title),
        subtitle: Text(
          [
            if (route.startTime != null) Format.dateTime(route.startTime!),
            if (route.tags.isNotEmpty) route.tags.join(' · '),
            figures,
          ].join('\n'),
          style: theme.textTheme.bodySmall,
        ),
        onTap: () => context.push('/planning/route/${route.id}'),
      ),
    );
  }
}
