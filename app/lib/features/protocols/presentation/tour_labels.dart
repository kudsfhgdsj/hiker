import '../../../l10n/app_localizations.dart';

/// German names of the fields that appear in the history and in conflicts.
String fieldLabel(AppLocalizations l10n, String field) => switch (field) {
  'title' => l10n.fieldTitle,
  'summary' => l10n.fieldSummary,
  'start_time' => l10n.fieldStartTime,
  'end_time' => l10n.fieldEndTime,
  'duration_minutes' => l10n.fieldDuration,
  'pack_weight_start_g' => l10n.fieldPackWeight,
  'calories_burned' || 'calories_burned_source' => l10n.fieldCaloriesBurned,
  'gear' => l10n.fieldGear,
  'food' => l10n.fieldFood,
  'peaks' => l10n.fieldPeaks,
  'partners' => l10n.fieldPartners,
  'waypoints' => l10n.fieldWaypoints,
  'photos' ||
  'cover_photo_id' ||
  'photo_time_offset_seconds' => l10n.fieldPhotos,
  'gpx_file_id' ||
  'track_source' ||
  'points_source' ||
  'start_lat' ||
  'start_lon' ||
  'start_name' ||
  'end_lat' ||
  'end_lon' ||
  'end_name' => l10n.fieldTrack,
  _ => l10n.fieldOther,
};

/// The distinct field names of a comma separated change summary, in German.
String summaryLabel(AppLocalizations l10n, String summary) {
  final labels = <String>{
    for (final field
        in summary.split(',').map((f) => f.trim()).where((f) => f.isNotEmpty))
      fieldLabel(l10n, field),
  };
  return labels.join(', ');
}

String weatherPointLabel(AppLocalizations l10n, String point) =>
    switch (point) {
      'start' => l10n.weatherStart,
      'summit' => l10n.weatherSummit,
      'end' => l10n.weatherEnd,
      _ => l10n.weatherManual,
    };
