import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hiker/core/map/elevation_profile.dart';
import 'package:hiker/core/map/geo.dart';

void main() {
  group('geo', () {
    test('bounds around points', () {
      final bounds = GeoBounds.around(const [
        GeoPoint(47.2, 9.4),
        GeoPoint(47.0, 9.1),
        GeoPoint(47.3, 9.2),
      ])!;

      expect(bounds.southWest, const GeoPoint(47.0, 9.1));
      expect(bounds.northEast, const GeoPoint(47.3, 9.4));
      expect(GeoBounds.around(const []), isNull);
    });

    test('distance between two points', () {
      // 0.001° of latitude is about 111.2 m.
      expect(
        distanceMeters(const GeoPoint(47.0, 9.0), const GeoPoint(47.001, 9.0)),
        closeTo(111.2, 0.1),
      );
      expect(distanceMeters(const GeoPoint(47, 9), const GeoPoint(47, 9)), 0);
    });

    test('markers close together on screen form one group', () {
      final groups = clusterByDistance(const [
        math.Point(100, 100),
        math.Point(120, 110),
        math.Point(300, 300),
        math.Point(95, 130),
        math.Point(310, 290),
      ], 44);

      expect(groups, [
        [0, 1, 3],
        [2, 4],
      ]);
      expect(clusterByDistance(const [], 44), isEmpty);
    });

    test('nearest index in an ascending list', () {
      const distances = [0.0, 100.0, 250.0, 400.0];

      expect(nearestIndex(distances, -5), 0);
      expect(nearestIndex(distances, 60), 1);
      expect(nearestIndex(distances, 170), 1);
      expect(nearestIndex(distances, 180), 2);
      expect(nearestIndex(distances, 999), 3);
      expect(nearestIndex(const [], 1), -1);
    });
  });

  group('ElevationProfile', () {
    const distances = [0.0, 250.0, 500.0, 750.0, 1000.0];
    const elevations = <double?>[1000, 1050, null, 1100, 1080];

    Future<List<double?>> pumpProfile(
      WidgetTester tester, {
      List<String>? tapped,
      List<ProfileMarker> markers = const [],
    }) async {
      final reported = <double?>[];
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Center(
              child: SizedBox(
                width: 416,
                child: ElevationProfile(
                  distancesM: distances,
                  elevationsM: elevations,
                  heartRates: const [100, 120, null, 150, 140],
                  markers: markers,
                  highlightDistanceM: 500,
                  onDistanceChanged: reported.add,
                  onMarkerTap: tapped?.add,
                ),
              ),
            ),
          ),
        ),
      );
      return reported;
    }

    testWidgets('dragging reports the distance under the finger', (
      tester,
    ) async {
      final reported = await pumpProfile(tester);
      final box = tester.getRect(find.byType(ElevationProfile));

      // The chart is 400 px wide inside 8 px of padding on both sides.
      final gesture = await tester.startGesture(
        Offset(box.left + 8, box.center.dy),
      );
      await gesture.moveTo(Offset(box.left + 108, box.center.dy));
      await gesture.moveTo(Offset(box.left + 208, box.center.dy));
      await gesture.moveTo(Offset(box.right + 50, box.center.dy));
      await gesture.up();
      await tester.pump();

      expect(reported.first, 0);
      expect(reported, contains(closeTo(500, 30)));
      expect(reported.whereType<double>().last, 1000);
      expect(reported.last, isNull);
      expect(tester.takeException(), isNull);
    });

    testWidgets('tapping a marker reports it, tapping elsewhere the distance', (
      tester,
    ) async {
      final tapped = <String>[];
      final reported = await pumpProfile(
        tester,
        tapped: tapped,
        markers: const [ProfileMarker(id: 'photo-1', distanceM: 250)],
      );
      final box = tester.getRect(find.byType(ElevationProfile));

      await tester.tapAt(Offset(box.left + 8 + 100, box.center.dy));
      await tester.tapAt(Offset(box.left + 8 + 300, box.center.dy));
      await tester.pump();

      expect(tapped, ['photo-1']);
      // Touching the profile always moves the highlight, also on a marker.
      expect(reported.first, 250);
      expect(reported.last, 750);
    });

    testWidgets('paints nothing for a track without elevation', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: ElevationProfile(
            distancesM: [0, 100],
            elevationsM: [null, null],
          ),
        ),
      );

      expect(tester.takeException(), isNull);
    });
  });
}
