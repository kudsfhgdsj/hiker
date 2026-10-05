import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/map/map_view.dart';
import '../../../core/router/app_router.dart';
import '../../../core/sun.dart';
import '../../../core/theme/app_theme.dart';
import '../../../l10n/app_localizations.dart';

/// What the map draws at a tapped place, in words: summit with its height,
/// path with its difficulty, or just a name. [summitM] is the height of the
/// first summit among them.
({List<String> lines, double? summitM}) describePlace(
  AppLocalizations l10n,
  MapPlace place,
) {
  final lines = <String>[];
  double? summit;
  for (final feature in place.features) {
    final properties = feature.properties;
    final name = properties['name']?.toString();
    final elevation = double.tryParse('${properties['ele'] ?? ''}');
    String? line;
    if (properties['sac_scale'] != null ||
        properties['highway'] == 'via_ferrata') {
      final grade = properties['highway'] == 'via_ferrata'
          ? l10n.mapViaFerrata
          : l10n.mapSacScale('${properties['sac_scale']}');
      line = name == null || name.isEmpty ? grade : '$name: $grade';
    } else if (name != null && name.isNotEmpty) {
      line = elevation == null ? name : '$name, ${Format.meters(elevation)}';
      if (elevation != null && properties['class'] == 'peak') {
        summit ??= elevation;
      }
    }
    if (line != null && !lines.contains(line)) lines.add(line);
  }
  return (lines: lines.take(6).toList(), summitM: summit);
}

/// The map on its own. [standalone]: opened from the sign-in screen, without
/// the navigation of the app.
class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key, this.standalone = false});

  final bool standalone;

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  MapPlace? _place;

  void _show(MapPlace place) {
    setState(() => _place = place);
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => PlaceSheet(
        place: place,
        // A day chosen for the layers also counts for the sun.
        day: DateTime.tryParse(ref.read(mapLayerChoiceProvider).day ?? ''),
      ),
    ).whenComplete(() {
      if (mounted) setState(() => _place = null);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final place = _place;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.mapTitle),
        leading: widget.standalone
            ? IconButton(
                tooltip: l10n.mapBackToLogin,
                icon: const Icon(Icons.arrow_back),
                onPressed: () => context.go(AppRoutes.login),
              )
            : null,
      ),
      body: HikerMap(
        content: MapContent(
          onPlace: _show,
          markers: [
            if (place != null)
              MapMarker(
                id: 'place',
                position: place.position,
                size: 30,
                child: IconMarker(icon: Icons.place, color: scheme.error),
              ),
          ],
        ),
      ),
    );
  }
}

/// What lies at a place and when the sun rises and sets there.
class PlaceSheet extends StatelessWidget {
  const PlaceSheet({super.key, required this.place, this.day});

  final MapPlace place;

  /// The day the sun is computed for; null: today.
  final DateTime? day;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final small = theme.textTheme.bodySmall;
    final found = describePlace(l10n, place);
    final position = place.position;
    final date = day ?? DateTime.now();
    final sun = sunTimes(position.lat, position.lon, date);
    final free = found.summitM == null
        ? null
        : sunTimes(
            position.lat,
            position.lon,
            date,
            elevationM: found.summitM!,
          );
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.m),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // A large red cross closes the sheet.
            Align(
              alignment: Alignment.topRight,
              child: IconButton(
                tooltip: l10n.close,
                iconSize: 32,
                color: const Color(0xFFC62828),
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ),
            for (final (index, line) in found.lines.indexed)
              Text(
                line,
                style: index == 0 ? theme.textTheme.titleMedium : null,
              ),
            Text(
              '${position.lat.toStringAsFixed(5)}° N, '
              '${position.lon.toStringAsFixed(5)}° O',
              style: small,
            ),
            const SizedBox(height: AppSpacing.s),
            if (sun.sunrise == null || sun.sunset == null)
              Text(l10n.mapSunNone)
            else ...[
              Text(
                l10n.mapSunTimes(
                  Format.date(date),
                  Format.time(sun.sunrise!),
                  Format.time(sun.sunset!),
                ),
              ),
              if (free?.sunrise != null && free?.sunset != null)
                Text(
                  l10n.mapSunSummit(
                    Format.time(free!.sunrise!),
                    Format.time(free.sunset!),
                  ),
                  style: small,
                ),
              if (sun.dawn != null && sun.dusk != null)
                Text(
                  l10n.mapSunLight(
                    Format.time(sun.dawn!),
                    Format.time(sun.dusk!),
                  ),
                  style: small,
                ),
            ],
          ],
        ),
      ),
    );
  }
}
