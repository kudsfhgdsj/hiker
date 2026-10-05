import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/map/map_view.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/reports_repository.dart';

/// From how many metres of ascent a day gets the next darker colour.
const _levels = [400, 900, 1500];
const _shades = [
  Color(0xFFE4E9E6),
  Color(0xFFB9DCC4),
  Color(0xFF74B98B),
  Color(0xFF2F8A55),
  Color(0xFF14532D),
];

/// Colour level of a day out: 1 for any tour, more with the ascent.
int dayLevel(Json? day) => day == null
    ? 0
    : 1 +
          _levels
              .where((step) => ((day['ascent_m'] as num?) ?? 0) >= step)
              .length;

/// What all own tours add up to: totals, the days out as a calendar, all
/// tracks on one map, climbed peaks and the peaks wished for.
class StatsScreen extends ConsumerStatefulWidget {
  const StatsScreen({super.key});

  @override
  ConsumerState<StatsScreen> createState() => _StatsScreenState();
}

class _StatsScreenState extends ConsumerState<StatsScreen> {
  int? _year;

  Future<void> _addWish() async {
    final l10n = AppLocalizations.of(context);
    final name = TextEditingController();
    final elevation = TextEditingController();
    final note = TextEditingController();
    final save = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.statsWishNew),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                key: const ValueKey('wish-name'),
                controller: name,
                autofocus: true,
                maxLength: 200,
                decoration: InputDecoration(labelText: l10n.statsPeak),
              ),
              TextField(
                key: const ValueKey('wish-elevation'),
                controller: elevation,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(labelText: l10n.statsElevation),
              ),
              TextField(
                controller: note,
                maxLength: 2000,
                decoration: InputDecoration(
                  labelText: l10n.statsNote,
                  counterText: '',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.save),
          ),
        ],
      ),
    );
    if (save != true || name.text.trim().isEmpty || !mounted) return;
    try {
      await ref
          .read(reportsRepositoryProvider)
          .addWish(
            name: name.text.trim(),
            elevationM: int.tryParse(elevation.text.trim()),
            note: note.text.trim().isEmpty ? null : note.text.trim(),
          );
      ref.invalidate(reportProvider);
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Future<void> _deleteWish(Json wish) async {
    if (!await confirmDelete(context, wish['name'] as String)) return;
    try {
      await ref
          .read(reportsRepositoryProvider)
          .deleteWish(wish['id'] as String);
      ref.invalidate(reportProvider);
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.statsTitle)),
      body: AsyncBody<Report>(
        value: ref.watch(reportProvider(_year)),
        onRetry: () => ref.invalidate(reportProvider),
        builder: (report) => _content(context, report),
      ),
    );
  }

  Widget _content(BuildContext context, Report report) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final total = report.total;
    Widget heading(String text) => Padding(
      padding: const EdgeInsets.fromLTRB(0, AppSpacing.l, 0, AppSpacing.s),
      child: Text(text, style: theme.textTheme.titleMedium),
    );
    Widget figure(String label, String value) => SizedBox(
      width: 150,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: theme.textTheme.bodySmall),
          Text(value, style: theme.textTheme.titleMedium),
        ],
      ),
    );
    final withoutTrack =
        (total['tours'] as int) - (total['tours_with_track'] as int);
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.m),
      children: [
        if (report.offline)
          Text(l10n.offlineData, style: theme.textTheme.bodySmall),
        Text(l10n.statsTotals, style: theme.textTheme.titleMedium),
        const SizedBox(height: AppSpacing.s),
        Wrap(
          spacing: AppSpacing.m,
          runSpacing: AppSpacing.s,
          children: [
            figure(l10n.statsTours, '${total['tours']}'),
            figure(l10n.statsDays, '${total['days']}'),
            figure(
              l10n.planDistance,
              Format.distance(total['distance_m'] as num),
            ),
            figure(l10n.planAscent, Format.meters(total['ascent_m'] as num)),
            figure(l10n.planDescent, Format.meters(total['descent_m'] as num)),
            figure(
              l10n.statsMovingTime,
              Format.duration(((total['moving_time_s'] as num) / 60).round()),
            ),
            figure(l10n.statsPeaks, '${total['peaks']}'),
          ],
        ),
        if (withoutTrack > 0)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.s),
            child: Text(
              l10n.statsWithoutTrack(withoutTrack),
              style: theme.textTheme.bodySmall,
            ),
          ),
        for (final year in report.years)
          ListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            title: Text('${year['year']}'),
            subtitle: Text(
              [
                l10n.statsYearLine(year['tours'] as int, year['days'] as int),
                Format.distance(year['distance_m'] as num),
                '↑ ${Format.meters(year['ascent_m'] as num)}',
                '↓ ${Format.meters(year['descent_m'] as num)}',
              ].join(' · '),
            ),
          ),

        // --- The days out as a calendar ---
        heading(l10n.statsCalendar('${report.year}')),
        if (report.calendarYears.length > 1)
          Wrap(
            spacing: AppSpacing.s,
            children: [
              for (final year in report.calendarYears)
                ChoiceChip(
                  label: Text('$year'),
                  selected: year == report.year,
                  onSelected: (_) => setState(() => _year = year),
                ),
            ],
          ),
        const SizedBox(height: AppSpacing.s),
        _YearGrid(
          year: report.year,
          days: report.days,
          onDay: (day) => context.push(
            '/protocols/tour/${(day['tour_ids'] as List<dynamic>).first}',
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: AppSpacing.xs),
          child: Text(l10n.statsCalendarNote, style: theme.textTheme.bodySmall),
        ),

        // --- All tracks on one map ---
        heading(l10n.statsMap),
        if (report.tracks.isEmpty)
          Text(l10n.statsNoTracks, style: theme.textTheme.bodySmall)
        else ...[
          SizedBox(
            height: 320,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: HikerMap(content: MapContent(heatLines: report.tracks)),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xs),
            child: Text(l10n.statsMapNote, style: theme.textTheme.bodySmall),
          ),
        ],

        // --- Climbed peaks ---
        heading(l10n.statsClimbed(report.peaks.length)),
        if (report.peaks.isEmpty)
          Text(l10n.statsNoPeaks, style: theme.textTheme.bodySmall),
        for (final peak in report.peaks)
          ListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            leading: const Icon(Icons.terrain),
            title: Text(
              peak['elevation_m'] == null
                  ? peak['name'] as String
                  : '${peak['name']}, ${Format.meters(peak['elevation_m'] as num)}',
            ),
            subtitle: Text(
              [
                l10n.statsVisits(peak['count'] as int),
                if (DateTime.tryParse(peak['last'] as String? ?? '')
                    case final last?)
                  Format.date(last),
              ].join(' · '),
            ),
            onTap: () => context.push(
              '/protocols/tour/${((peak['visits'] as List<dynamic>).first as Json)['tour_id']}',
            ),
          ),

        // --- Wish peaks ---
        Row(
          children: [
            Expanded(child: heading(l10n.statsWishes)),
            IconButton(
              tooltip: l10n.statsWishNew,
              icon: const Icon(Icons.add),
              onPressed: _addWish,
            ),
          ],
        ),
        if (report.wishes.isEmpty)
          Text(l10n.statsNoWishes, style: theme.textTheme.bodySmall),
        for (final wish in report.wishes)
          ListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            leading: Icon(
              wish['climbed'] == true
                  ? Icons.check_circle
                  : Icons.flag_outlined,
              color: wish['climbed'] == true ? theme.colorScheme.primary : null,
            ),
            title: Text(
              wish['elevation_m'] == null
                  ? wish['name'] as String
                  : '${wish['name']}, ${Format.meters(wish['elevation_m'] as num)}',
            ),
            subtitle: switch ((wish['climbed'], wish['note'])) {
              (true, _) => Text(l10n.statsWishDone),
              (_, final String note) => Text(note),
              _ => null,
            },
            trailing: IconButton(
              tooltip: l10n.delete,
              icon: const Icon(Icons.delete_outline),
              onPressed: () => _deleteWish(wish),
            ),
          ),
        const SizedBox(height: AppSpacing.xl),
      ],
    );
  }
}

/// A year as columns of weeks, Monday on top: every day a small square,
/// coloured by what was done on it.
class _YearGrid extends StatelessWidget {
  const _YearGrid({
    required this.year,
    required this.days,
    required this.onDay,
  });

  final int year;
  final Map<String, Json> days;
  final ValueChanged<Json> onDay;

  @override
  Widget build(BuildContext context) {
    final first = DateTime.utc(year);
    var current = first.subtract(Duration(days: first.weekday - 1));
    final weeks = <List<DateTime?>>[];
    while (current.year <= year) {
      weeks.add([
        for (var i = 0; i < 7; i++)
          current.add(Duration(days: i)).year == year
              ? current.add(Duration(days: i))
              : null,
      ]);
      current = current.add(const Duration(days: 7));
    }
    const size = 12.0, gap = 2.0;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final week in weeks)
            Padding(
              padding: const EdgeInsets.only(right: gap),
              child: Column(
                children: [
                  for (final date in week)
                    Padding(
                      padding: const EdgeInsets.only(bottom: gap),
                      child: _cell(date, size),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _cell(DateTime? date, double size) {
    if (date == null) return SizedBox.square(dimension: size);
    final key = date.toIso8601String().substring(0, 10);
    final day = days[key];
    final box = Container(
      key: day == null ? null : ValueKey('day-$key'),
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _shades[dayLevel(day)],
        borderRadius: BorderRadius.circular(2),
      ),
    );
    return day == null
        ? box
        : GestureDetector(onTap: () => onDay(day), child: box);
  }
}
