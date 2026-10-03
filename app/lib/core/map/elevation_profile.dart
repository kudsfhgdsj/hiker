import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'geo.dart';

/// A marker on the profile, e.g. a photo, at a distance along the track.
class ProfileMarker {
  const ProfileMarker({required this.id, required this.distanceM});

  final String id;
  final double distanceM;
}

/// Elevation over distance, optionally with the heart rate. Moving a finger
/// (or the mouse) over it reports the distance, so that the map can follow.
class ElevationProfile extends StatelessWidget {
  const ElevationProfile({
    super.key,
    required this.distancesM,
    required this.elevationsM,
    this.heartRates,
    this.markers = const [],
    this.highlightDistanceM,
    this.onDistanceChanged,
    this.onMarkerTap,
    this.height = 160,
  });

  final List<double> distancesM;
  final List<double?> elevationsM;
  final List<int?>? heartRates;
  final List<ProfileMarker> markers;
  final double? highlightDistanceM;

  /// The distance under the pointer; null when the pointer leaves.
  final ValueChanged<double?>? onDistanceChanged;
  final ValueChanged<String>? onMarkerTap;
  final double height;

  static const _padding = EdgeInsets.fromLTRB(8, 12, 8, 20);

  double get _total => distancesM.isEmpty ? 0 : distancesM.last;

  double _distanceAt(double dx, double width) {
    final inner = width - _padding.horizontal;
    final share = ((dx - _padding.left) / inner).clamp(0.0, 1.0);
    return share * _total;
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        void report(Offset position) =>
            onDistanceChanged?.call(_distanceAt(position.dx, width));
        void tap(Offset position) {
          final inner = width - _padding.horizontal;
          for (final marker in markers) {
            final x =
                _padding.left +
                (_total == 0 ? 0 : marker.distanceM / _total * inner);
            if ((x - position.dx).abs() <= 16) {
              onMarkerTap?.call(marker.id);
              return;
            }
          }
          report(position);
        }

        return MouseRegion(
          onHover: (event) => report(event.localPosition),
          onExit: (_) => onDistanceChanged?.call(null),
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapUp: (details) => tap(details.localPosition),
            // Report at once when the finger touches down, not only after it moved.
            onHorizontalDragDown: (details) => report(details.localPosition),
            onHorizontalDragStart: (details) => report(details.localPosition),
            onHorizontalDragUpdate: (details) => report(details.localPosition),
            onHorizontalDragEnd: (_) => onDistanceChanged?.call(null),
            child: CustomPaint(
              size: Size(width, height),
              painter: _ProfilePainter(
                distances: distancesM,
                elevations: elevationsM,
                heartRates: heartRates,
                markers: markers,
                highlight: highlightDistanceM,
                padding: _padding,
                line: scheme.primary,
                fill: scheme.primary.withValues(alpha: 0.18),
                heart: scheme.error,
                marker: scheme.tertiary,
                axis: scheme.onSurfaceVariant,
                textStyle: Theme.of(context).textTheme.labelSmall!,
              ),
            ),
          ),
        );
      },
    );
  }
}

class _ProfilePainter extends CustomPainter {
  _ProfilePainter({
    required this.distances,
    required this.elevations,
    required this.heartRates,
    required this.markers,
    required this.highlight,
    required this.padding,
    required this.line,
    required this.fill,
    required this.heart,
    required this.marker,
    required this.axis,
    required this.textStyle,
  });

  final List<double> distances;
  final List<double?> elevations;
  final List<int?>? heartRates;
  final List<ProfileMarker> markers;
  final double? highlight;
  final EdgeInsets padding;
  final Color line;
  final Color fill;
  final Color heart;
  final Color marker;
  final Color axis;
  final TextStyle textStyle;

  void _label(
    Canvas canvas,
    String text,
    Offset position, {
    bool alignRight = false,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: textStyle.copyWith(color: axis),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(
      canvas,
      alignRight ? position - Offset(painter.width, 0) : position,
    );
  }

  @override
  void paint(Canvas canvas, Size size) {
    final area = padding.deflateRect(Offset.zero & size);
    final known = [for (final e in elevations) ?e];
    if (distances.length < 2 || known.isEmpty) return;
    final total = distances.last;
    final low = known.reduce(math.min);
    final high = known.reduce(math.max);
    final span = math.max(high - low, 1);

    double x(double distance) =>
        area.left + (total == 0 ? 0 : distance / total * area.width);
    double y(double elevation) =>
        area.bottom - (elevation - low) / span * area.height;

    final path = Path();
    var started = false;
    double? lastX;
    for (var i = 0; i < distances.length; i++) {
      final elevation = elevations[i];
      if (elevation == null) continue;
      final point = Offset(x(distances[i]), y(elevation));
      if (started) {
        path.lineTo(point.dx, point.dy);
      } else {
        path.moveTo(point.dx, point.dy);
        started = true;
      }
      lastX = point.dx;
    }
    final area2 = Path.from(path)
      ..lineTo(lastX!, area.bottom)
      ..lineTo(area.left, area.bottom)
      ..close();
    canvas.drawPath(area2, Paint()..color = fill);
    canvas.drawPath(
      path,
      Paint()
        ..color = line
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );

    final rates = heartRates;
    if (rates != null && rates.any((r) => r != null)) {
      final present = [for (final r in rates) ?r];
      final minRate = present.reduce(math.min);
      final rateSpan = math.max(present.reduce(math.max) - minRate, 1);
      final heartPath = Path();
      var first = true;
      for (var i = 0; i < distances.length && i < rates.length; i++) {
        final rate = rates[i];
        if (rate == null) continue;
        final point = Offset(
          x(distances[i]),
          area.bottom - (rate - minRate) / rateSpan * area.height,
        );
        first
            ? heartPath.moveTo(point.dx, point.dy)
            : heartPath.lineTo(point.dx, point.dy);
        first = false;
      }
      canvas.drawPath(
        heartPath,
        Paint()
          ..color = heart.withValues(alpha: 0.7)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2,
      );
    }

    for (final item in markers) {
      final index = nearestIndex(distances, item.distanceM);
      final elevation = elevations[index] ?? low;
      canvas.drawCircle(
        Offset(x(item.distanceM), y(elevation)),
        5,
        Paint()..color = marker,
      );
    }

    final at = highlight;
    if (at != null) {
      final px = x(at.clamp(0, total));
      canvas.drawLine(
        Offset(px, area.top),
        Offset(px, area.bottom),
        Paint()
          ..color = axis
          ..strokeWidth = 1,
      );
    }

    _label(canvas, '${high.round()} m', Offset(area.left, 0));
    _label(canvas, '${low.round()} m', Offset(area.left, area.bottom + 4));
    _label(
      canvas,
      '${(total / 1000).toStringAsFixed(1).replaceAll('.', ',')} km',
      Offset(area.right, area.bottom + 4),
      alignRight: true,
    );
  }

  @override
  bool shouldRepaint(_ProfilePainter old) =>
      old.distances != distances ||
      old.elevations != elevations ||
      old.heartRates != heartRates ||
      old.markers != markers ||
      old.highlight != highlight;
}
