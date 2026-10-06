import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/map/elevation_profile.dart';
import '../../../core/map/geo.dart';
import '../../../core/map/map_view.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/api_image.dart';
import '../../../core/widgets/error_text.dart';
import '../../../core/widgets/file_pick.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_models.dart';
import '../data/tour_repository.dart';
import 'tour_labels.dart';
import 'tour_photo_gallery.dart';

class TourDetailScreen extends ConsumerStatefulWidget {
  const TourDetailScreen({super.key, required this.tourId});

  final String tourId;

  @override
  ConsumerState<TourDetailScreen> createState() => _TourDetailScreenState();
}

class _TourDetailScreenState extends ConsumerState<TourDetailScreen> {
  /// Distance along the track under the finger on the profile.
  double? _highlightDistance;

  /// A position to show on the map, e.g. of a photo chosen in the gallery.
  GeoPoint? _highlightPoint;

  String get _id => widget.tourId;

  void _refresh() {
    ref.invalidate(tourProvider(_id));
    ref.invalidate(tourTrackProvider(_id));
    ref.invalidate(tourPhotosProvider(_id));
    ref.invalidate(tourWaypointsProvider(_id));
    ref.invalidate(tourOverviewProvider(_id));
    ref.invalidate(tourListProvider);
  }

  /// Runs a change, reloads the tour and shows errors in German.
  Future<void> _run(
    Future<void> Function(TourRepository repository) action,
  ) async {
    try {
      await action(ref.read(tourRepositoryProvider));
      _refresh();
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  /// Tells the user that a file waits on the device for a connection.
  void _savedOffline(bool sent) {
    if (sent || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppLocalizations.of(context).syncSavedOffline)),
    );
  }

  Future<void> _uploadGpx() async {
    final files = await ref.read(filePickerProvider)(extensions: const ['gpx']);
    if (files.isEmpty) return;
    await _run((r) async => _savedOffline(await r.uploadGpx(_id, files.first)));
  }

  Future<void> _addPhotos() async {
    final files = await ref.read(filePickerProvider)(
      extensions: imageExtensions,
      multiple: true,
    );
    if (files.isEmpty) return;
    await _run((r) async => _savedOffline(await r.uploadPhotos(_id, files)));
  }

  Future<void> _waypointsFromPhotos() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    await _run((r) async {
      final count = await r.waypointsFromPhotos(_id);
      messenger.showSnackBar(
        SnackBar(content: Text(l10n.tourWaypointsCreated(count))),
      );
    });
  }

  Future<void> _photoOffset(Tour tour) async {
    final minutes = await showDialog<int>(
      context: context,
      builder: (context) =>
          _OffsetDialog(initialMinutes: tour.photoTimeOffsetSeconds ~/ 60),
    );
    if (minutes != null) {
      await _run((r) => r.setPhotoTimeOffset(_id, minutes * 60));
    }
  }

  Future<void> _delete(Tour tour) async {
    final router = GoRouter.of(context);
    if (!await confirmDelete(context, tour.title)) return;
    await _run((r) => r.delete(_id));
    router.pop();
  }

  Future<void> _openGallery(
    List<Json> photos,
    String photoId,
    Tour tour,
  ) async {
    final shown = await showPhotoGallery(
      context,
      tourId: _id,
      photos: photos,
      initialId: photoId,
      canEdit: tour.canEdit,
      onChanged: _refresh,
    );
    if (shown != null && mounted) setState(() => _highlightPoint = shown);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final loaded = ref.watch(tourProvider(_id));
    final tour = loaded.asData?.value.value;
    return Scaffold(
      appBar: AppBar(
        title: Text(tour?.title ?? l10n.toursTitle),
        actions: tour == null
            ? null
            : [
                if (tour.canEdit)
                  IconButton(
                    tooltip: l10n.edit,
                    icon: const Icon(Icons.edit_outlined),
                    onPressed: () async {
                      await context.push('/protocols/tour/$_id/edit');
                      _refresh();
                    },
                  ),
                IconButton(
                  tooltip: l10n.tourHistory,
                  icon: const Icon(Icons.history),
                  onPressed: () async {
                    await context.push('/protocols/tour/$_id/history');
                    _refresh();
                  },
                ),
                if (tour.isOwner)
                  IconButton(
                    tooltip: l10n.tourShare,
                    icon: const Icon(Icons.share_outlined),
                    onPressed: () => context.push('/protocols/tour/$_id/share'),
                  ),
                if (tour.canEdit)
                  PopupMenuButton<VoidCallback>(
                    onSelected: (action) => action(),
                    itemBuilder: (context) => [
                      PopupMenuItem(
                        value: _addPhotos,
                        child: Text(l10n.tourAddPhotos),
                      ),
                      PopupMenuItem(
                        value: _waypointsFromPhotos,
                        child: Text(l10n.tourWaypointsFromPhotos),
                      ),
                      PopupMenuItem(
                        value: () => _photoOffset(tour),
                        child: Text(l10n.tourPhotoOffset),
                      ),
                      if (tour.isOwner) ...[
                        const PopupMenuDivider(),
                        PopupMenuItem(
                          value: _uploadGpx,
                          child: Text(l10n.tourUploadGpx),
                        ),
                        PopupMenuItem(
                          value: () async {
                            await context.push('/protocols/tour/$_id/draw');
                            _refresh();
                          },
                          child: Text(l10n.tourDrawTrack),
                        ),
                        if (tour.hasTrack)
                          PopupMenuItem(
                            value: () => _run((r) => r.removeTrack(_id)),
                            child: Text(l10n.tourRemoveTrack),
                          )
                        else
                          PopupMenuItem(
                            value: () async {
                              await context.push('/protocols/tour/$_id/points');
                              _refresh();
                            },
                            child: Text(l10n.tourSetPoints),
                          ),
                        if (tour.hasTrack)
                          PopupMenuItem(
                            value: () => _run((r) => r.detectPlaces(_id)),
                            child: Text(l10n.tourDetectPlaces),
                          ),
                        PopupMenuItem(
                          value: () => _run((r) => r.fetchWeather(_id)),
                          child: Text(l10n.tourWeatherRefresh),
                        ),
                        const PopupMenuDivider(),
                        PopupMenuItem(
                          value: () => _delete(tour),
                          child: Text(l10n.delete),
                        ),
                      ],
                    ],
                  ),
              ],
      ),
      body: AsyncBody(
        value: loaded,
        onRetry: _refresh,
        builder: (data) => _body(context, data.value, data.offline),
      ),
    );
  }

  Widget _body(BuildContext context, Tour tour, bool offline) {
    final l10n = AppLocalizations.of(context);
    final track = ref.watch(tourTrackProvider(_id)).asData?.value;
    final photos =
        ref.watch(tourPhotosProvider(_id)).asData?.value ?? const <Json>[];
    final waypoints =
        ref.watch(tourWaypointsProvider(_id)).asData?.value ?? const <Json>[];
    final scheme = Theme.of(context).colorScheme;

    GeoPoint? position(Json item) => item['lat'] == null
        ? null
        : GeoPoint(
            (item['lat'] as num).toDouble(),
            (item['lon'] as num).toDouble(),
          );

    final markers = <MapMarker>[
      if (tour.startPoint != null)
        MapMarker(
          id: 'start',
          position: tour.startPoint!,
          size: 30,
          child: IconMarker(
            icon: Icons.play_arrow,
            color: scheme.primary,
            tooltip: l10n.tourStart,
          ),
        ),
      if (tour.endPoint != null)
        MapMarker(
          id: 'end',
          position: tour.endPoint!,
          size: 30,
          child: IconMarker(
            icon: Icons.flag,
            color: scheme.secondary,
            tooltip: l10n.tourEnd,
          ),
        ),
      for (final peak in tour.peaks)
        if (position(peak) != null)
          MapMarker(
            id: 'peak-${peak['id']}',
            position: position(peak)!,
            size: 30,
            child: IconMarker(
              icon: Icons.terrain,
              color: scheme.tertiary,
              tooltip: peak['name'] as String,
            ),
          ),
      for (final waypoint in waypoints)
        MapMarker(
          id: 'waypoint-${waypoint['id']}',
          position: position(waypoint)!,
          size: 28,
          child: IconMarker(
            icon: Icons.place,
            color: scheme.secondary,
            tooltip: waypoint['name'] as String,
          ),
        ),
      // Photos as small round previews; close ones merge into a counter.
      for (final photo in photos)
        if (position(photo) != null)
          MapMarker(
            id: photo['id'] as String,
            position: position(photo)!,
            clusters: true,
            size: 44,
            onTap: () => _openGallery(photos, photo['id'] as String, tour),
            child: PhotoThumbnail(
              tourId: _id,
              photo: photo,
              size: 44,
              round: true,
            ),
          ),
    ];
    final highlight = _highlightDistance != null && track != null
        ? track.pointAt(_highlightDistance!)
        : _highlightPoint;
    final hasMap = (track != null && !track.isEmpty) || markers.isNotEmpty;
    final elevations = track?.elevations;

    return ListView(
      padding: const EdgeInsets.only(bottom: AppSpacing.xl),
      children: [
        if (offline) const OfflineBanner(),
        if (hasMap)
          SizedBox(
            height: 300,
            child: HikerMap(
              content: MapContent(
                track: track?.points ?? const [],
                markers: markers,
                highlight: highlight,
                onClusterTap: (ids) => _openGallery(photos, ids.first, tour),
              ),
            ),
          ),
        if (track != null && elevations != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s),
            child: ElevationProfile(
              distancesM: track.distances,
              elevationsM: elevations,
              heartRates: track.heartRates,
              highlightDistanceM: _highlightDistance,
              markers: [
                for (final photo in photos)
                  if (photo['track_distance_m'] != null)
                    ProfileMarker(
                      id: photo['id'] as String,
                      distanceM: (photo['track_distance_m'] as num).toDouble(),
                    ),
              ],
              onDistanceChanged: (distance) => setState(() {
                _highlightDistance = distance;
                _highlightPoint = null;
              }),
              onMarkerTap: (id) => _openGallery(photos, id, tour),
            ),
          ),
        if (photos.isNotEmpty)
          SizedBox(
            height: 84,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.all(AppSpacing.s),
              itemCount: photos.length,
              separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.s),
              itemBuilder: (context, index) => GestureDetector(
                onTap: () =>
                    _openGallery(photos, photos[index]['id'] as String, tour),
                child: PhotoThumbnail(
                  tourId: _id,
                  photo: photos[index],
                  size: 68,
                ),
              ),
            ),
          ),
        _FactsSection(tour: tour),
        if (tour.trackStats != null) _TrackSection(stats: tour.trackStats!),
        _RouteSection(
          overview: ref.watch(tourOverviewProvider(_id)).asData?.value,
        ),
        _ListSection(
          title: l10n.tourGear,
          trailing: Format.weight(tour.packWeightG),
          rows: [
            for (final entry in tour.gear)
              (
                '${entry['quantity'] == 1 ? '' : '${entry['quantity']} × '}${entry['name']}',
                Format.weight(entry['weight_g'] as int?),
              ),
          ],
        ),
        _ListSection(
          title: l10n.tourFood,
          trailing: tour.caloriesEaten == null
              ? null
              : l10n.tourKcal(Format.number(tour.caloriesEaten!.round())),
          rows: [
            for (final entry in tour.food)
              (
                '${entry['name']} · ${Format.number(entry['amount_g'] as num)} g',
                entry['kcal'] == null
                    ? ''
                    : l10n.tourKcal(
                        Format.number((entry['kcal'] as num).round()),
                      ),
              ),
          ],
        ),
        _WeatherSection(
          tour: tour,
          onRefresh: tour.isOwner
              ? () => _run((r) => r.fetchWeather(_id))
              : null,
        ),
        _ListSection(
          title: l10n.tourPeaks,
          rows: [
            for (final peak in tour.peaks)
              (
                peak['name'] as String,
                Format.meters(peak['elevation_m'] as num?),
              ),
          ],
        ),
        _ListSection(
          title: l10n.tourPartners,
          rows: [
            for (final partner in tour.partners)
              (partner['display_name'] as String, ''),
          ],
        ),
        if (tour.summary != null)
          _Section(title: l10n.tourSummary, children: [Text(tour.summary!)]),
        if (tour.tags.isNotEmpty)
          _Section(
            title: l10n.tourTags,
            children: [
              Wrap(
                spacing: AppSpacing.xs,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final tag in tour.tags)
                    Chip(
                      label: Text(tag),
                      visualDensity: VisualDensity.compact,
                    ),
                ],
              ),
            ],
          ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children, this.trailing});

  final String title;
  final String? trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.m,
        AppSpacing.m,
        AppSpacing.m,
        0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: Text(title, style: theme.textTheme.titleMedium)),
              if (trailing != null)
                Text(trailing!, style: theme.textTheme.titleMedium),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          ...children,
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value, {this.extra});

  final String label;
  final String value;
  final Widget? extra;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      children: [
        Flexible(child: Text(label)),
        const SizedBox(width: AppSpacing.s),
        ?extra,
        // Long values wrap instead of running out of the screen.
        Expanded(child: Text(value, textAlign: TextAlign.end)),
      ],
    ),
  );
}

class _ListSection extends StatelessWidget {
  const _ListSection({required this.title, required this.rows, this.trailing});

  final String title;
  final String? trailing;
  final List<(String, String)> rows;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return _Section(
      title: title,
      trailing: trailing,
      children: [for (final (label, value) in rows) _Row(label, value)],
    );
  }
}

class _FactsSection extends StatelessWidget {
  const _FactsSection({required this.tour});

  final Tour tour;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final estimate = tour.caloriesEstimate;
    final burned = tour.caloriesBurned;
    // How the estimate was made, or why there is none (owner only).
    final explanation = switch ((estimate?['method'], estimate?['reason'])) {
      ('heart_rate', _) => l10n.tourEstimateHeartRate,
      ('acsm_walking', _) => l10n.tourEstimateWalking,
      (_, 'no_profile') => l10n.tourNoEstimateProfile,
      (_, 'no_track') => l10n.tourNoEstimateTrack,
      (_, 'no_duration') => l10n.tourNoEstimateDuration,
      _ => null,
    };
    return _Section(
      title: l10n.tourFacts,
      children: [
        if (!tour.isOwner && tour.ownerName != null)
          _Row(l10n.tourSharedBy(tour.ownerName!), ''),
        if (tour.startTime != null)
          _Row(l10n.tourStart, Format.dateTime(tour.startTime!)),
        if (tour.endTime != null)
          _Row(l10n.tourEnd, Format.dateTime(tour.endTime!)),
        _Row(l10n.tourDuration, Format.duration(tour.durationMinutes)),
        _Row(l10n.tourPackWeight, Format.weight(tour.packWeightG)),
        _Row(
          l10n.tourCaloriesBurned,
          burned == null ? '–' : l10n.tourKcal(Format.number(burned.round())),
          // An estimate is always marked as such.
          extra: burned != null && tour.caloriesBurnedEstimated
              ? Tooltip(
                  message: explanation ?? l10n.tourEstimated,
                  triggerMode: TooltipTriggerMode.tap,
                  child: Chip(
                    label: Text(l10n.tourEstimated),
                    visualDensity: VisualDensity.compact,
                  ),
                )
              : null,
        ),
        if (burned == null && explanation != null)
          Text(explanation, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _TrackSection extends StatelessWidget {
  const _TrackSection({required this.stats});

  final Json stats;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final heart = stats['heart_rate'] as Json?;
    final moving = stats['moving_time_s'] as int?;
    return _Section(
      title: l10n.tourTrack,
      children: [
        _Row(l10n.tourDistance, Format.distance(stats['distance_m'] as num?)),
        if (stats['ascent_m'] != null) ...[
          _Row(l10n.tourAscent, Format.meters(stats['ascent_m'] as num?)),
          _Row(l10n.tourDescent, Format.meters(stats['descent_m'] as num?)),
          _Row(
            l10n.tourHighest,
            Format.meters(stats['max_elevation_m'] as num?),
          ),
        ],
        if (moving != null)
          _Row(l10n.tourMovingTime, Format.duration(moving ~/ 60)),
        // Only present for the owner: heart rate is health data.
        if (heart != null)
          _Row(
            l10n.tourHeartRate,
            l10n.tourHeartRateValue('${heart['avg']}', '${heart['max']}'),
          ),
      ],
    );
  }
}

/// The course of the tour: start, peaks, passes, waypoints and end in track order.
class _RouteSection extends StatelessWidget {
  const _RouteSection({required this.overview});

  final Json? overview;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final stations = [
      ...?(overview?['stations'] as List<dynamic>?)?.cast<Json>(),
    ];
    // Start and end alone are no course worth showing.
    if (stations.length < 3) return const SizedBox.shrink();
    final kinds = {
      'start': (l10n.stationStart, Icons.play_arrow),
      'end': (l10n.stationEnd, Icons.flag),
      'peak': (l10n.stationPeak, Icons.terrain),
      'saddle': (l10n.stationSaddle, Icons.compare_arrows),
      'high_point': (l10n.stationHighPoint, Icons.vertical_align_top),
      'photo': (l10n.tourPhotos, Icons.photo_outlined),
    };
    final theme = Theme.of(context);
    return _Section(
      title: l10n.tourRoute,
      children: [
        for (final station in stations)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              children: [
                Icon(kinds[station['kind']]?.$2 ?? Icons.place, size: 18),
                const SizedBox(width: AppSpacing.s),
                Expanded(
                  child: Text(
                    (station['name'] as String?) ??
                        kinds[station['kind']]?.$1 ??
                        l10n.stationWaypoint,
                  ),
                ),
                Text(
                  [
                    if (station['elevation_m'] != null)
                      Format.meters(station['elevation_m'] as num),
                    if (station['time'] != null)
                      Format.time(DateTime.parse(station['time'] as String)),
                  ].join(' · '),
                ),
              ],
            ),
          ),
        if (overview?['attribution'] != null)
          // OpenStreetMap data is under the ODbL: the source must be named.
          Text(l10n.osmAttribution, style: theme.textTheme.bodySmall),
      ],
    );
  }
}

class _WeatherSection extends StatelessWidget {
  const _WeatherSection({required this.tour, this.onRefresh});

  final Tour tour;
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    if (tour.weather.isEmpty && !tour.weatherOutdated) {
      return const SizedBox.shrink();
    }
    String number(Object? value) =>
        value == null ? '–' : Format.number((value as num).round());
    return _Section(
      title: l10n.tourWeather,
      children: [
        for (final sample in tour.weather)
          _Row(
            weatherPointLabel(l10n, sample['sample_point'] as String),
            l10n.weatherLine(
              number(sample['temperature_c']),
              number(sample['wind_speed_kmh']),
              number(sample['cloud_cover_pct']),
            ),
          ),
        if (tour.weatherOutdated) ...[
          Text(
            l10n.tourWeatherOutdated,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (onRefresh != null)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh),
                label: Text(l10n.tourWeatherRefresh),
              ),
            ),
        ],
      ],
    );
  }
}

class _OffsetDialog extends StatefulWidget {
  const _OffsetDialog({required this.initialMinutes});

  final int initialMinutes;

  @override
  State<_OffsetDialog> createState() => _OffsetDialogState();
}

class _OffsetDialogState extends State<_OffsetDialog> {
  late final _minutes = TextEditingController(text: '${widget.initialMinutes}');

  @override
  void dispose() {
    _minutes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.tourPhotoOffset),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(l10n.tourPhotoOffsetHint),
          const SizedBox(height: AppSpacing.m),
          TextField(
            controller: _minutes,
            decoration: InputDecoration(labelText: l10n.tourPhotoOffsetField),
            keyboardType: const TextInputType.numberWithOptions(signed: true),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () {
            final minutes = int.tryParse(
              _minutes.text.trim().replaceAll('−', '-'),
            );
            if (minutes != null && minutes.abs() <= 2880) {
              Navigator.pop(context, minutes);
            }
          },
          child: Text(l10n.save),
        ),
      ],
    );
  }
}

/// Preview of a tour photo, loaded with the access token.
class PhotoThumbnail extends StatelessWidget {
  const PhotoThumbnail({
    super.key,
    required this.tourId,
    required this.photo,
    required this.size,
    this.round = false,
  });

  final String tourId;
  final Json photo;
  final double size;
  final bool round;

  @override
  Widget build(BuildContext context) {
    final image = ApiImage(
      path: '/tours/$tourId/photos/${photo['id']}/image?size=thumb',
      version: photo['id'] as String,
      size: size,
      placeholder: Icons.photo_outlined,
    );
    if (!round) return image;
    return DecoratedBox(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: const [BoxShadow(blurRadius: 3, color: Colors.black38)],
      ),
      child: ClipOval(child: image),
    );
  }
}
