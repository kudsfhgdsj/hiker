import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'geo.dart';

/// A marker on the profile, e.g. a photo, at a distance along the track.
class ProfileMarker {
  const ProfileMarker({required this.id, required this.distanceM});

  final String id;
  final double distanceM;
}

/// A step of 1, 2 or 5 times a power of ten that gives about [wanted] steps.
double niceStep(double span, int wanted) {
  final rough = span / wanted;
  final power = math.pow(10, (math.log(rough) / math.ln10).floor()).toDouble();
  final share = rough / power;
  return (share <= 1
          ? 1
          : share <= 2
          ? 2
          : share <= 5
          ? 5
          : 10) *
      power;
}

/// The slope in percent over about 100 m around [distanceM]; from one point
/// to the next it would be too noisy. Null where the elevation is unknown.
double? slopePercent(
  List<double> distancesM,
  List<double?> elevationsM,
  double distanceM,
) {
  if (distancesM.length < 2) return null;
  final from = nearestIndex(distancesM, distanceM - 50);
  final to = nearestIndex(distancesM, distanceM + 50);
  final start = elevationsM[from];
  final end = elevationsM[to];
  final run = distancesM[to] - distancesM[from];
  if (start == null || end == null || run <= 0) return null;
  return (end - start) / run * 100;
}

/// Elevation over distance with axes, optionally with the heart rate. Moving
/// a finger (or the mouse) over it reports the distance, so that the map can
/// follow, and names distance, elevation and slope of that place.
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
    this.height = 190,
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

  /// Room around the chart for the axis labels and the box of the highlight.
  static const padding = EdgeInsets.fromLTRB(46, 30, 12, 22);

  double get _total => distancesM.isEmpty ? 0 : distancesM.last;

  double _distanceAt(double dx, double width) {
    final inner = width - padding.horizontal;
    final share = ((dx - padding.left) / inner).clamp(0.0, 1.0);
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
          final inner = width - padding.horizontal;
          for (final marker in markers) {
            final x =
                padding.left +
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
                padding: padding,
                surface: scheme.surfaceContainerHighest,
                onSurface: scheme.onSurface,
                line: scheme.primary,
                fill: scheme.primary,
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
    required this.surface,
    required this.onSurface,
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
  final Color surface;
  final Color onSurface;
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
    bool centered = false,
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
      alignRight
          ? position - Offset(painter.width, 0)
          : centered
          ? position - Offset(painter.width / 2, 0)
          : position,
    );
  }

  @override
  void paint(Canvas canvas, Size size) {
    final area = padding.deflateRect(Offset.zero & size);
    final known = [for (final e in elevations) ?e];
    if (distances.length < 2 || known.isEmpty) return;
    final total = distances.last;
    final lowest = known.reduce(math.min);
    final highest = known.reduce(math.max);
    // The scale runs between round values, so that the labels are easy to read.
    final stepY = niceStep(math.max(highest - lowest, 10), 3);
    final low = (lowest / stepY).floor() * stepY;
    final high = math.max((highest / stepY).ceil() * stepY, low + stepY);
    final span = high - low;

    double x(double distance) =>
        area.left + (total == 0 ? 0 : distance / total * area.width);
    double y(double elevation) =>
        area.bottom - (elevation - low) / span * area.height;

    final grid = Paint()
      ..color = axis.withValues(alpha: 0.25)
      ..strokeWidth = 1;
    for (var value = low; value <= high + stepY / 2; value += stepY) {
      canvas.drawLine(
        Offset(area.left, y(value)),
        Offset(area.right, y(value)),
        grid,
      );
      _label(
        canvas,
        '${value.round()} m',
        Offset(area.left - 6, y(value) - 7),
        alignRight: true,
      );
    }
    if (total > 0) {
      final stepX = niceStep(total / 1000, 4);
      final digits = stepX < 0.1
          ? 2
          : stepX < 1
          ? 1
          : 0;
      for (var km = 0.0; km * 1000 <= total + 1; km += stepX) {
        canvas.drawLine(
          Offset(x(km * 1000), area.bottom),
          Offset(x(km * 1000), area.bottom + 4),
          grid,
        );
        _label(
          canvas,
          '${km.toStringAsFixed(digits).replaceAll('.', ',')} km',
          Offset(x(km * 1000), area.bottom + 6),
          centered: true,
        );
      }
    }

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
    canvas.drawPath(
      area2,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [fill.withValues(alpha: 0.45), fill.withValues(alpha: 0.04)],
        ).createShader(area),
    );
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
    if (at != null) _paintHighlight(canvas, area, at.clamp(0, total), x, y);
  }

  /// The place under the finger: a line, a dot on the curve and a box that
  /// names distance, elevation and slope.
  void _paintHighlight(
    Canvas canvas,
    Rect area,
    double at,
    double Function(double) x,
    double Function(double) y,
  ) {
    final px = x(at);
    canvas.drawLine(
      Offset(px, area.top),
      Offset(px, area.bottom),
      Paint()
        ..color = heart
        ..strokeWidth = 1.5,
    );
    final elevation = elevations[nearestIndex(distances, at)];
    if (elevation != null) {
      final point = Offset(px, y(elevation));
      canvas.drawCircle(point, 7, Paint()..color = Colors.white);
      canvas.drawCircle(point, 5, Paint()..color = heart);
    }

    final slope = slopePercent(distances, elevations, at)?.round();
    final text = TextPainter(
      text: TextSpan(
        text: [
          '${(at / 1000).toStringAsFixed(1).replaceAll('.', ',')} km',
          if (elevation != null) '${elevation.round()} m',
          if (slope != null) '${slope > 0 ? '+' : ''}$slope %',
        ].join('  ·  '),
        style: textStyle.copyWith(
          color: onSurface,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    // The box stays above the chart, where the finger does not cover it.
    final width = text.width + 16;
    final double left = (px - width / 2)
        .clamp(0.0, math.max(0.0, area.right - width))
        .toDouble();
    final box = RRect.fromRectAndRadius(
      Rect.fromLTWH(left, 2, width, text.height + 8),
      const Radius.circular(8),
    );
    canvas.drawRRect(box, Paint()..color = surface);
    text.paint(canvas, Offset(left + 8, 6));
  }

  @override
  bool shouldRepaint(_ProfilePainter old) =>
      old.distances != distances ||
      old.elevations != elevations ||
      old.heartRates != heartRates ||
      old.markers != markers ||
      old.highlight != highlight ||
      old.line != line ||
      old.surface != surface;
}
