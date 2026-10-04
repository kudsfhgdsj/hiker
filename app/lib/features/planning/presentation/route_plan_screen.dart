import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/map/elevation_profile.dart';
import '../../../core/map/geo.dart';
import '../../../core/map/map_view.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../core/widgets/file_pick.dart';
import '../../../l10n/app_localizations.dart';
import '../data/offline_routing.dart';
import '../data/route_models.dart';
import '../data/route_repository.dart';
import '../data/route_schedule.dart';

/// Plans a route: taps on the map set the waypoints, the server connects
/// them along paths or as straight lines and returns line and key figures.
class RoutePlanScreen extends ConsumerStatefulWidget {
  const RoutePlanScreen({super.key, this.routeId});

  /// null: a new route.
  final String? routeId;

  @override
  ConsumerState<RoutePlanScreen> createState() => _RoutePlanScreenState();
}

class _RoutePlanScreenState extends ConsumerState<RoutePlanScreen> {
  final _title = TextEditingController();
  final _description = TextEditingController();
  final _tags = TextEditingController();
  DateTime? _startTime;
  String _profile = 'hiking';
  int _difficulty = 3;
  bool _viaFerrata = false;
  Pace _pace = Pace.dav;
  List<RouteWaypoint> _waypoints = [];

  PlannedRoute? _existing;
  bool _loaded = false;
  Object? _loadError;

  RouteResult? _result;
  bool _computing = false;

  /// Why there is no line: an error code of the API, or null.
  String? _problem;
  int _request = 0;

  /// The waypoint the next tap on the map moves, if any.
  int? _moving;
  double? _highlightDistance;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _tags.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final repository = ref.read(routeRepositoryProvider);
    try {
      final info = await repository.info();
      final id = widget.routeId;
      final route = id == null ? null : (await repository.get(id)).value;
      if (!mounted) return;
      setState(() {
        _loaded = true;
        _existing = route;
        if (route != null) {
          final draft = route.draft;
          _title.text = draft.title;
          _description.text = draft.description ?? '';
          _tags.text = draft.tags.join(', ');
          _startTime = draft.startTime;
          _profile = draft.profile;
          _difficulty = draft.maxDifficulty;
          _viaFerrata = draft.viaFerrata;
          _pace = draft.pace;
          _waypoints = List.of(draft.waypoints);
          _result = route.result;
        } else if (!info.routingAvailable) {
          _profile = 'direct';
        }
      });
      // Drafted offline: ask for the line now, if the server can be reached.
      if (route != null && route.result == null) _compute();
    } catch (error) {
      if (mounted) setState(() => _loadError = error);
    }
  }

  RouteDraft get _draft => RouteDraft(
    title: _title.text.trim(),
    description: _description.text.trim().isEmpty
        ? null
        : _description.text.trim(),
    tags: [
      for (final tag in _tags.text.split(','))
        if (tag.trim().isNotEmpty) tag.trim(),
    ],
    startTime: _startTime,
    profile: _profile,
    maxDifficulty: _difficulty,
    viaFerrata: _viaFerrata,
    pace: _pace,
    waypoints: _waypoints,
  );

  /// Asks the server for the line after a change of the course.
  Future<void> _compute() async {
    final current = ++_request;
    if (_waypoints.length < 2) {
      setState(() {
        _result = null;
        _problem = null;
        _computing = false;
      });
      return;
    }
    setState(() => _computing = true);
    RouteResult? result;
    String? problem;
    try {
      result = await ref.read(routeRepositoryProvider).preview(_draft);
    } on ApiException catch (error) {
      problem = error.code;
    }
    // A newer change is already on its way: this answer is outdated.
    if (!mounted || current != _request) return;
    setState(() {
      _result = result;
      _problem = problem;
      _computing = false;
      _highlightDistance = null;
    });
  }

  void _change(VoidCallback change) {
    setState(change);
    _compute();
  }

  void _tapMap(GeoPoint point) {
    final moving = _moving;
    final position = GeoPoint(
      double.parse(point.lat.toStringAsFixed(6)),
      double.parse(point.lon.toStringAsFixed(6)),
    );
    _change(() {
      if (moving != null) {
        _waypoints[moving] = _waypoints[moving].copyWith(position: position);
        _moving = null;
      } else {
        _waypoints.add(RouteWaypoint(position: position));
      }
    });
  }

  Future<void> _rename(int index) async {
    final l10n = AppLocalizations.of(context);
    final controller = TextEditingController(text: _waypoints[index].name);
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.planWaypointName),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 200,
          decoration: InputDecoration(labelText: l10n.name),
          onSubmitted: (text) => Navigator.pop(context, text),
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
    if (name == null || !mounted) return;
    // A name does not change the course: no new line needed.
    setState(
      () => _waypoints[index] = _waypoints[index].copyWith(name: name.trim()),
    );
  }

  void _reverse() => _change(() {
    // The mark for a straight leg belongs to the leg: it moves to its other end.
    final marks = [for (final point in _waypoints) point.direct];
    final reversed = _waypoints.reversed.toList();
    _waypoints = [
      for (var i = 0; i < reversed.length; i++)
        reversed[i].copyWith(direct: i > 0 && marks[reversed.length - i]),
    ];
    _moving = null;
  });

  /// Day and time of the start, in the time of the device.
  Future<void> _pickStart() async {
    final now = DateTime.now();
    final before = _startTime?.toLocal();
    final day = await showDatePicker(
      context: context,
      initialDate: before ?? now,
      firstDate: DateTime(now.year - 1),
      lastDate: DateTime(now.year + 10),
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: before == null
          ? const TimeOfDay(hour: 7, minute: 0)
          : TimeOfDay.fromDateTime(before),
    );
    if (time == null || !mounted) return;
    // The line does not depend on the start: nothing to compute anew.
    setState(
      () => _startTime = DateTime(
        day.year,
        day.month,
        day.day,
        time.hour,
        time.minute,
      ).toUtc(),
    );
  }

  Future<void> _save() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    if (_title.text.trim().isEmpty) {
      messenger.showSnackBar(SnackBar(content: Text(l10n.planTitleMissing)));
      return;
    }
    setState(() => _busy = true);
    try {
      final saved = await ref
          .read(routeRepositoryProvider)
          .save(_draft, existing: _existing, computed: _result);
      ref.invalidate(routeListProvider);
      if (!mounted) return;
      setState(() {
        _existing = saved;
        _result = saved.result ?? _result;
        _busy = false;
      });
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            saved.result == null ? l10n.planSavedOffline : l10n.saved,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      showError(context, error);
      setState(() => _busy = false);
    }
  }

  /// Writes the line shown as a GPX file; works without network too.
  Future<void> _exportGpx() async {
    final result = _result;
    if (result == null) return;
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final title = _title.text.trim().isEmpty
        ? l10n.planNew
        : _title.text.trim();
    final name = title.replaceAll(RegExp(r'[^\w\-äöüÄÖÜß ]'), '').trim();
    try {
      final saved = await ref.read(fileSaverProvider)(
        name: '${name.isEmpty ? 'route' : name}.gpx',
        bytes: Uint8List.fromList(utf8.encode(routeGpx(title, result))),
        mimeType: 'application/gpx+xml',
      );
      if (saved) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.planGpxSaved)));
      }
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Future<void> _delete() async {
    final existing = _existing;
    if (existing == null || !await confirmDelete(context, existing.title)) {
      return;
    }
    if (!mounted) return;
    final router = GoRouter.of(context);
    try {
      await ref.read(routeRepositoryProvider).delete(existing.id);
      ref.invalidate(routeListProvider);
      router.pop();
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  String _problemText(AppLocalizations l10n, String code) => switch (code) {
    'no_route' => l10n.errorNoRoute,
    'routing_unavailable' => l10n.errorRoutingUnavailable,
    offlineNoData => l10n.planOfflineNoData,
    ApiException.network => l10n.planOffline,
    _ => l10n.planFailed,
  };

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final title = _existing?.title ?? l10n.planNew;
    if (_loadError != null) {
      return Scaffold(
        appBar: AppBar(title: Text(title)),
        body: CenteredForm(children: [ErrorText(_loadError!)]),
      );
    }
    if (!_loaded) {
      return Scaffold(
        appBar: AppBar(title: Text(title)),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    final scheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final info = ref.watch(planningInfoProvider).asData?.value;
    final routing = info?.routingAvailable ?? true;
    final result = _result;
    // Without a line from the server the waypoints are joined directly, as a sketch.
    final line =
        result?.points ?? [for (final point in _waypoints) point.position];
    final highlight = _highlightDistance != null && result != null
        ? result.pointAt(_highlightDistance!)
        : null;
    final elevations = result?.elevations;
    // The pace only changes the times: they are computed here, so that a new
    // start needs no new line.
    final sun = sunReport(result, _startTime, _pace);
    final timeHere =
        result != null && _startTime != null && _highlightDistance != null
        ? _startTime!.add(
            Duration(
              seconds: timesAlong(
                result,
                _pace,
              )[nearestIndex(result.distances, _highlightDistance!)],
            ),
          )
        : null;
    final canSave = !_busy && _waypoints.length >= 2;

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            tooltip: l10n.planUndo,
            icon: const Icon(Icons.undo),
            onPressed: _waypoints.isEmpty
                ? null
                : () => _change(() {
                    _waypoints.removeLast();
                    _moving = null;
                  }),
          ),
          TextButton(onPressed: canSave ? _save : null, child: Text(l10n.save)),
          PopupMenuButton<VoidCallback>(
            key: const ValueKey('plan-menu'),
            onSelected: (action) => action(),
            itemBuilder: (context) => [
              PopupMenuItem(
                enabled: _waypoints.length > 1,
                value: _reverse,
                child: Text(l10n.planReverse),
              ),
              PopupMenuItem(
                enabled: _waypoints.isNotEmpty,
                value: () => _change(() {
                  _waypoints = [];
                  _moving = null;
                }),
                child: Text(l10n.planClear),
              ),
              PopupMenuItem(
                enabled: _result != null,
                value: _exportGpx,
                child: Text(l10n.planGpx),
              ),
              if (_existing != null)
                PopupMenuItem(value: _delete, child: Text(l10n.delete)),
            ],
          ),
        ],
      ),
      // The map fills the screen; everything else lies in a sheet that is
      // pulled up over it.
      body: Stack(
        children: [
          Positioned.fill(
            child: HikerMap(
              content: MapContent(
                track: line,
                highlight: highlight,
                onTap: _tapMap,
                controls: [
                  MapControl(
                    label: l10n.planDifficultyField,
                    builder: (context) => _PathSheet(
                      routing: routing,
                      profile: _profile,
                      difficulty: _difficulty,
                      viaFerrata: _viaFerrata,
                      pace: _pace,
                      onChanged: (profile, difficulty, viaFerrata, pace) =>
                          _change(() {
                            _profile = profile;
                            _difficulty = difficulty;
                            _viaFerrata = viaFerrata;
                            _pace = pace;
                          }),
                    ),
                  ),
                ],
                markers: [
                  for (var i = 0; i < _waypoints.length; i++)
                    MapMarker(
                      id: 'waypoint-$i',
                      position: _waypoints[i].position,
                      size: 28,
                      onTap: () =>
                          setState(() => _moving = _moving == i ? null : i),
                      child: _NumberMarker(
                        label: i == 0 ? 'S' : '${i + 1}',
                        color: _moving == i ? scheme.tertiary : scheme.error,
                      ),
                    ),
                ],
              ),
            ),
          ),
          DraggableScrollableSheet(
            initialChildSize: 0.3,
            minChildSize: 0.12,
            maxChildSize: 0.92,
            snap: true,
            snapSizes: const [0.3, 0.6],
            builder: (context, scroll) => Material(
              elevation: 8,
              color: scheme.surface,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(16),
              ),
              clipBehavior: Clip.antiAlias,
              child: SingleChildScrollView(
                controller: scroll,
                padding: const EdgeInsets.only(bottom: AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 36,
                        height: 4,
                        margin: const EdgeInsets.symmetric(vertical: 8),
                        decoration: BoxDecoration(
                          color: scheme.outlineVariant,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.m,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            _moving != null
                                ? l10n.planMoveHint(
                                    _moving == 0 ? 'S' : '${_moving! + 1}',
                                  )
                                : _waypoints.isEmpty
                                ? l10n.planHintStart
                                : l10n.planHint,
                            style: theme.textTheme.bodySmall,
                          ),
                          if (_computing) ...[
                            const SizedBox(height: AppSpacing.s),
                            const LinearProgressIndicator(),
                          ],
                          if (_problem != null && !_computing) ...[
                            const SizedBox(height: AppSpacing.s),
                            Text(
                              _problemText(l10n, _problem!),
                              style: TextStyle(color: scheme.error),
                            ),
                          ],
                          if (!routing)
                            Padding(
                              padding: const EdgeInsets.only(
                                top: AppSpacing.xs,
                              ),
                              child: Text(
                                l10n.planNoRouting,
                                style: theme.textTheme.bodySmall,
                              ),
                            ),
                          if (result != null) ...[
                            const SizedBox(height: AppSpacing.s),
                            _Figures(result: result, pace: _pace),
                            if (result.onDevice)
                              Padding(
                                padding: const EdgeInsets.only(
                                  top: AppSpacing.xs,
                                ),
                                child: Text(
                                  l10n.planOnDevice,
                                  style: theme.textTheme.bodySmall,
                                ),
                              ),
                            if (sun != null) _SunCard(report: sun),
                          ],
                        ],
                      ),
                    ),
                    if (result != null && elevations != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.s,
                        ),
                        child: ElevationProfile(
                          distancesM: result.distances,
                          elevationsM: elevations,
                          highlightDistanceM: _highlightDistance,
                          onDistanceChanged: (distance) =>
                              setState(() => _highlightDistance = distance),
                        ),
                      ),
                    if (timeHere != null)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.m,
                        ),
                        child: Text(
                          l10n.planTimeHere(Format.time(timeHere)),
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.all(AppSpacing.m),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            l10n.planWaypoints,
                            style: theme.textTheme.titleSmall,
                          ),
                          for (var i = 0; i < _waypoints.length; i++)
                            _WaypointTile(
                              index: i,
                              waypoint: _waypoints[i],
                              moving: _moving == i,
                              onRename: () => _rename(i),
                              onMove: () => setState(() => _moving = i),
                              onDirect: (value) => _change(
                                () => _waypoints[i] = _waypoints[i].copyWith(
                                  direct: value,
                                ),
                              ),
                              onRemove: () => _change(() {
                                _waypoints.removeAt(i);
                                _moving = null;
                              }),
                            ),
                          const Divider(),
                          TextField(
                            controller: _title,
                            maxLength: 200,
                            decoration: InputDecoration(
                              labelText: l10n.planRouteTitle,
                            ),
                          ),
                          TextField(
                            controller: _description,
                            maxLength: 5000,
                            minLines: 2,
                            maxLines: 5,
                            decoration: InputDecoration(
                              labelText: l10n.planDescription,
                            ),
                          ),
                          TextField(
                            key: const ValueKey('plan-tags'),
                            controller: _tags,
                            decoration: InputDecoration(
                              labelText: l10n.planTags,
                              helperText: l10n.planTagsHint,
                            ),
                          ),
                          ListTile(
                            key: const ValueKey('plan-start'),
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.schedule),
                            title: Text(l10n.planStart),
                            subtitle: Text(
                              _startTime == null
                                  ? l10n.planStartHint
                                  : Format.dateTime(_startTime!),
                            ),
                            trailing: _startTime == null
                                ? null
                                : IconButton(
                                    tooltip: l10n.delete,
                                    icon: const Icon(Icons.clear),
                                    onPressed: () =>
                                        setState(() => _startTime = null),
                                  ),
                            onTap: _pickStart,
                          ),
                          const SizedBox(height: AppSpacing.s),
                          FilledButton(
                            onPressed: canSave ? _save : null,
                            child: Text(l10n.save),
                          ),
                          if (info?.attribution != null) ...[
                            const SizedBox(height: AppSpacing.m),
                            Text(
                              info!.attribution!,
                              style: theme.textTheme.bodySmall,
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// How the points are connected, which paths may be used and how fast the
/// walker is: the field "Schwierigkeit" on the map.
class _PathSheet extends ConsumerStatefulWidget {
  const _PathSheet({
    required this.routing,
    required this.profile,
    required this.difficulty,
    required this.viaFerrata,
    required this.pace,
    required this.onChanged,
  });

  final bool routing;
  final String profile;
  final int difficulty;
  final bool viaFerrata;
  final Pace pace;
  final void Function(
    String profile,
    int difficulty,
    bool viaFerrata,
    Pace pace,
  )
  onChanged;

  @override
  ConsumerState<_PathSheet> createState() => _PathSheetState();
}

class _PathSheetState extends ConsumerState<_PathSheet> {
  late String _profile = widget.profile;
  late int _difficulty = widget.difficulty;
  late bool _viaFerrata = widget.viaFerrata;
  late Pace _pace = widget.pace;
  late final _ascent = TextEditingController(
    text: Format.input(widget.pace.ascentMPerH),
  );
  late final _descent = TextEditingController(
    text: Format.input(widget.pace.descentMPerH),
  );
  late final _distance = TextEditingController(
    text: Format.input(widget.pace.distanceKmPerH),
  );
  final _name = TextEditingController();

  @override
  void dispose() {
    _ascent.dispose();
    _descent.dispose();
    _distance.dispose();
    _name.dispose();
    super.dispose();
  }

  void _tell() => widget.onChanged(_profile, _difficulty, _viaFerrata, _pace);

  void _setPace(Pace pace) {
    setState(() {
      _pace = pace;
      _ascent.text = Format.input(pace.ascentMPerH);
      _descent.text = Format.input(pace.descentMPerH);
      _distance.text = Format.input(pace.distanceKmPerH);
    });
    _tell();
  }

  /// The typed values, if they are numbers the server accepts.
  Pace? _typed() {
    double? read(TextEditingController field, double min, double max) {
      final value = double.tryParse(field.text.trim().replaceAll(',', '.'));
      return value == null || value < min || value > max ? null : value;
    }

    final ascent = read(_ascent, 50, 3000);
    final descent = read(_descent, 50, 5000);
    final distance = read(_distance, 0.5, 20);
    if (ascent == null || descent == null || distance == null) return null;
    return Pace.custom(
      ascentMPerH: ascent,
      descentMPerH: descent,
      distanceKmPerH: distance,
    );
  }

  void _valuesChanged() {
    final pace = _typed();
    if (pace == null) return;
    setState(() => _pace = pace);
    _tell();
  }

  Future<void> _store() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final name = _name.text.trim();
    final pace = _typed();
    if (name.isEmpty || pace == null) {
      messenger.showSnackBar(SnackBar(content: Text(l10n.planPaceNameMissing)));
      return;
    }
    try {
      final saved = await ref
          .read(routeRepositoryProvider)
          .savePace(name, pace);
      ref.invalidate(savedPacesProvider);
      if (!mounted) return;
      _name.clear();
      _setPace(saved.pace);
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Future<void> _remove(SavedPace saved) async {
    try {
      await ref.read(routeRepositoryProvider).deletePace(saved.id);
      ref.invalidate(savedPacesProvider);
      if (!mounted) return;
      // The route keeps the values; only the saved entry is gone.
      _setPace(
        Pace.custom(
          ascentMPerH: _pace.ascentMPerH,
          descentMPerH: _pace.descentMPerH,
          distanceKmPerH: _pace.distanceKmPerH,
        ),
      );
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final saved = ref.watch(savedPacesProvider).asData?.value ?? const [];
    final direct = _profile == 'direct';
    SavedPace? chosen;
    for (final entry in saved) {
      if (_pace.isCustom && entry.name == _pace.name) chosen = entry;
    }
    // What the list shows as chosen: a preset, a saved pace, or own values.
    final selected = !_pace.isCustom
        ? _pace.preset
        : chosen != null
        ? 'saved:${chosen.id}'
        : Pace.customPreset;
    final own = selected == Pace.customPreset;
    Widget value(String label, TextEditingController controller) => Expanded(
      child: TextField(
        controller: controller,
        enabled: own,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(labelText: label),
        onChanged: (_) => _valuesChanged(),
      ),
    );
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          AppSpacing.m,
          AppSpacing.m,
          AppSpacing.m,
          AppSpacing.m + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(l10n.planConnection, style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(
                  value: 'hiking',
                  enabled: widget.routing,
                  label: Text(l10n.planProfileHiking),
                  icon: const Icon(Icons.hiking),
                ),
                ButtonSegment(
                  value: 'direct',
                  label: Text(l10n.planProfileDirect),
                  icon: const Icon(Icons.straight),
                ),
              ],
              selected: {_profile},
              onSelectionChanged: (selection) {
                setState(() => _profile = selection.first);
                _tell();
              },
            ),
            const SizedBox(height: AppSpacing.m),
            DropdownButtonFormField<int>(
              key: const ValueKey('plan-difficulty'),
              initialValue: _difficulty,
              isExpanded: true,
              decoration: InputDecoration(
                labelText: l10n.planDifficulty,
                helperText: l10n.planDifficultyHint,
                helperMaxLines: 2,
              ),
              items: [
                for (var level = 1; level <= 6; level++)
                  DropdownMenuItem(
                    value: level,
                    child: Text(
                      l10n.planDifficultyLevel('$level'),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: direct
                  ? null
                  : (level) {
                      setState(() => _difficulty = level!);
                      _tell();
                    },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l10n.planViaFerrata),
              value: _viaFerrata,
              onChanged: direct
                  ? null
                  : (value) {
                      setState(() => _viaFerrata = value);
                      _tell();
                    },
            ),
            const Divider(),
            DropdownButtonFormField<String>(
              // Another choice is another field: it shows the new value.
              key: ValueKey('plan-pace-$selected'),
              initialValue: selected,
              isExpanded: true,
              decoration: InputDecoration(labelText: l10n.planPace),
              items: [
                for (final preset in Pace.presets.keys)
                  DropdownMenuItem(
                    value: preset,
                    child: Text(
                      l10n.planPacePreset(preset),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                DropdownMenuItem(
                  value: Pace.customPreset,
                  child: Text(l10n.planPaceCustom),
                ),
                for (final entry in saved)
                  DropdownMenuItem(
                    value: 'saved:${entry.id}',
                    child: Text(entry.name, overflow: TextOverflow.ellipsis),
                  ),
              ],
              onChanged: (choice) {
                if (choice == null) return;
                if (Pace.presets[choice] case final preset?) {
                  _setPace(preset);
                } else if (choice == Pace.customPreset) {
                  _setPace(
                    Pace.custom(
                      ascentMPerH: _pace.ascentMPerH,
                      descentMPerH: _pace.descentMPerH,
                      distanceKmPerH: _pace.distanceKmPerH,
                    ),
                  );
                } else {
                  _setPace(
                    saved
                        .firstWhere((entry) => 'saved:${entry.id}' == choice)
                        .pace,
                  );
                }
              },
            ),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                value(l10n.planPaceAscent, _ascent),
                const SizedBox(width: AppSpacing.s),
                value(l10n.planPaceDescent, _descent),
                const SizedBox(width: AppSpacing.s),
                value(l10n.planPaceDistance, _distance),
              ],
            ),
            if (own)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.s),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        key: const ValueKey('plan-pace-name'),
                        controller: _name,
                        maxLength: 100,
                        decoration: InputDecoration(
                          labelText: l10n.planPaceName,
                          counterText: '',
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.s),
                    OutlinedButton(onPressed: _store, child: Text(l10n.save)),
                  ],
                ),
              ),
            if (chosen != null)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  icon: const Icon(Icons.delete_outline),
                  label: Text(l10n.planPaceDelete(chosen.name)),
                  onPressed: () => _remove(chosen!),
                ),
              ),
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.planPaceNote, style: theme.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

/// Sunrise, sunset and how the tour lies between them.
class _SunCard extends StatelessWidget {
  const _SunCard({required this.report});

  final SunReport report;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final warn = TextStyle(
      color: theme.colorScheme.error,
      fontWeight: FontWeight.w600,
    );
    String span(Duration time) => Format.duration(time.inMinutes.abs());
    final summit = report.summit;
    // The moments of the day in the order they happen.
    final moments = <(DateTime, String)>[
      if (report.sun.sunrise case final sunrise?)
        (sunrise, '${l10n.planSunrise}: ${Format.time(sunrise)}'),
      if (summit != null)
        (
          summit.time,
          '${l10n.planSummit(Format.meters(summit.elevationM))}: '
              '${Format.time(summit.time)}'
              '${summit.sunHeightDeg > 0 ? ' – ${l10n.planSunAtSummit('${summit.sunHeightDeg.round()}', l10n.compassDirection('${(summit.sunDirectionDeg / 45).round() % 8}'))}' : ''}',
        ),
      (report.end, '${l10n.planEnd}: ${Format.time(report.end)}'),
      if (report.sun.sunset case final sunset?)
        (sunset, '${l10n.planSunset}: ${Format.time(sunset)}'),
    ]..sort((a, b) => a.$1.compareTo(b.$1));
    final left = report.daylightLeft;
    return Card(
      margin: const EdgeInsets.only(top: AppSpacing.s),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.s),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final (_, text) in moments) Text(text),
            if (left != null)
              left.isNegative
                  ? Text(l10n.planAfterSunset(span(left)), style: warn)
                  : Text(l10n.planDaylightLeft(span(left))),
            if (report.startsInDark) Text(l10n.planStartsInDark, style: warn),
            if (report.endsInDark) Text(l10n.planEndsInDark, style: warn),
          ],
        ),
      ),
    );
  }
}

/// Distance, ascent, descent and the estimated walking time of a route.
class _Figures extends StatelessWidget {
  const _Figures({required this.result, required this.pace});

  final RouteResult result;
  final Pace pace;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    Widget figure(String label, String value) => Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.bodySmall),
          Text(value, style: theme.textTheme.titleMedium),
        ],
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            figure(l10n.planDistance, Format.distance(result.distanceM)),
            figure(l10n.planAscent, Format.meters(result.ascentM)),
            figure(l10n.planDescent, Format.meters(result.descentM)),
            figure(
              l10n.planDuration,
              // For the pace chosen now, also before the server answered.
              Format.duration(
                (pace.walkingTimeS(
                          result.distanceM,
                          result.ascentM,
                          result.descentM,
                        ) /
                        60)
                    .round(),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        // The walking time is always an estimate and is named as one.
        Text(
          l10n.planDurationNote(
            Format.number(pace.ascentMPerH),
            Format.number(pace.descentMPerH),
            Format.input(pace.distanceKmPerH),
          ),
          style: theme.textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _NumberMarker extends StatelessWidget {
  const _NumberMarker({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: color,
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white, width: 2),
      boxShadow: const [BoxShadow(blurRadius: 3, color: Colors.black38)],
    ),
    child: Center(
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    ),
  );
}

class _WaypointTile extends StatelessWidget {
  const _WaypointTile({
    required this.index,
    required this.waypoint,
    required this.moving,
    required this.onRename,
    required this.onMove,
    required this.onDirect,
    required this.onRemove,
  });

  final int index;
  final RouteWaypoint waypoint;
  final bool moving;
  final VoidCallback onRename;
  final VoidCallback onMove;
  final ValueChanged<bool> onDirect;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final position = waypoint.position;
    final coordinates =
        '${position.lat.toStringAsFixed(5)}, ${position.lon.toStringAsFixed(5)}';
    return ListTile(
      contentPadding: EdgeInsets.zero,
      selected: moving,
      leading: CircleAvatar(
        radius: 14,
        child: Text(index == 0 ? 'S' : '${index + 1}'),
      ),
      title: Text(waypoint.name.isEmpty ? coordinates : waypoint.name),
      subtitle: index > 0 && waypoint.direct ? Text(l10n.planDirectLeg) : null,
      onTap: onRename,
      trailing: PopupMenuButton<VoidCallback>(
        tooltip: l10n.planWaypointMenu('${index + 1}'),
        onSelected: (action) => action(),
        itemBuilder: (context) => [
          PopupMenuItem(value: onRename, child: Text(l10n.planWaypointName)),
          PopupMenuItem(value: onMove, child: Text(l10n.planWaypointMove)),
          if (index > 0)
            CheckedPopupMenuItem(
              checked: waypoint.direct,
              value: () => onDirect(!waypoint.direct),
              child: Text(l10n.planDirectLeg),
            ),
          PopupMenuItem(value: onRemove, child: Text(l10n.planWaypointRemove)),
        ],
      ),
    );
  }
}
