import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/map/maplibre_map_view.dart';

void main() {
  MapLibreMapView.configureWeb();
  runApp(ProviderScope(overrides: appOverrides(), child: const HikerApp()));
}
