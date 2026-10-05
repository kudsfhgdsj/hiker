import 'package:flutter/material.dart';

/// Design tokens: fir green, rock grey, snow white, accent orange.
class AppColors {
  const AppColors._();

  static const firGreen = Color(0xFF1F5F45);
  static const rockGrey = Color(0xFF5E6770);
  static const snowWhite = Color(0xFFF7F9F8);
  static const accentOrange = Color(0xFFE8731A);
}

class AppSpacing {
  const AppSpacing._();

  static const double xs = 4;
  static const double s = 8;
  static const double m = 16;
  static const double l = 24;
  static const double xl = 32;

  /// From this width on the navigation moves from the bottom to a side rail.
  static const double wideLayout = 720;

  /// Forms and text columns do not grow wider than this.
  static const double maxContentWidth = 560;
}

class AppTheme {
  const AppTheme._();

  static ThemeData light() => _theme(Brightness.light);

  static ThemeData dark() => _theme(Brightness.dark);

  static ThemeData _theme(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.firGreen,
      secondary: AppColors.rockGrey,
      tertiary: AppColors.accentOrange,
      surface: brightness == Brightness.light ? AppColors.snowWhite : null,
      brightness: brightness,
    );
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      // Every screen stands on the painted background (MountainBackground), which the
      // navigation frame and the router put behind it.
      scaffoldBackgroundColor: Colors.transparent,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
    );
  }
}
