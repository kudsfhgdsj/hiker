import 'package:flutter/material.dart';

/// A mountain in the manner of the Matterhorn, drawn for hiker in flat grey
/// shapes behind every screen. The same drawing as `background.svg` of the web
/// frontend, on a canvas of 1200 x 600.
class MountainBackground extends StatelessWidget {
  const MountainBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ColoredBox(
      color: scheme.surface,
      child: CustomPaint(
        painter: _MountainPainter(
          rock: const Color(0xFF808890),
          snow: Colors.white,
        ),
        child: child,
      ),
    );
  }
}

class _MountainPainter extends CustomPainter {
  const _MountainPainter({required this.rock, required this.snow});

  final Color rock;
  final Color snow;

  static const _width = 1200.0;
  static const _height = 600.0;

  /// Shapes as (opacity, points); the first three are rock, the rest snow.
  static const _rock = <(double, List<double>)>[
    // far ranges
    (
      0.07,
      [
        0,
        600,
        0,
        455,
        95,
        385,
        165,
        430,
        250,
        350,
        345,
        445,
        405,
        405,
        520,
        600,
      ],
    ),
    (
      0.07,
      [
        760,
        600,
        870,
        425,
        945,
        480,
        1040,
        375,
        1120,
        460,
        1200,
        410,
        1200,
        600,
      ],
    ),
    // the peak
    (
      0.13,
      [
        300,
        600,
        450,
        395,
        505,
        350,
        550,
        240,
        590,
        185,
        620,
        105,
        644,
        83,
        670,
        117,
        692,
        195,
        736,
        287,
        788,
        347,
        866,
        469,
        970,
        600,
      ],
    ),
    // its shaded east face
    (
      0.10,
      [
        644,
        83,
        670,
        117,
        692,
        195,
        736,
        287,
        788,
        347,
        866,
        469,
        970,
        600,
        690,
        600,
        660,
        410,
        638,
        290,
      ],
    ),
    // foreground
    (
      0.09,
      [
        0,
        600,
        0,
        530,
        140,
        485,
        290,
        535,
        460,
        475,
        640,
        550,
        800,
        495,
        990,
        555,
        1200,
        505,
        1200,
        600,
      ],
    ),
  ];
  static const _snow = <List<double>>[
    [644, 83, 620, 105, 602, 153, 624, 139, 638, 159, 654, 135, 670, 153],
    [550, 240, 532, 284, 558, 272, 578, 298, 592, 262],
    [736, 287, 730, 321, 756, 313, 788, 347],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    // As wide as the screen, standing on its lower edge.
    final scale = size.width / _width;
    final dy = size.height - _height * scale;
    Path path(List<double> points) {
      final path = Path()..moveTo(points[0] * scale, points[1] * scale + dy);
      for (var i = 2; i < points.length; i += 2) {
        path.lineTo(points[i] * scale, points[i + 1] * scale + dy);
      }
      return path..close();
    }

    for (final (opacity, points) in _rock) {
      canvas.drawPath(
        path(points),
        Paint()..color = rock.withValues(alpha: opacity),
      );
    }
    for (final points in _snow) {
      canvas.drawPath(
        path(points),
        Paint()..color = snow.withValues(alpha: 0.16),
      );
    }
  }

  @override
  bool shouldRepaint(_MountainPainter oldDelegate) =>
      oldDelegate.rock != rock || oldDelegate.snow != snow;
}
