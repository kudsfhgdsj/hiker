import 'dart:math' as math;

class GeoPoint {
  const GeoPoint(this.lat, this.lon);

  final double lat;
  final double lon;

  @override
  bool operator ==(Object other) =>
      other is GeoPoint && other.lat == lat && other.lon == lon;

  @override
  int get hashCode => Object.hash(lat, lon);

  @override
  String toString() => 'GeoPoint($lat, $lon)';
}

class GeoBounds {
  const GeoBounds(this.southWest, this.northEast);

  /// The smallest box around the points; null without points.
  static GeoBounds? around(Iterable<GeoPoint> points) {
    if (points.isEmpty) return null;
    var south = 90.0, north = -90.0, west = 180.0, east = -180.0;
    for (final point in points) {
      south = math.min(south, point.lat);
      north = math.max(north, point.lat);
      west = math.min(west, point.lon);
      east = math.max(east, point.lon);
    }
    return GeoBounds(GeoPoint(south, west), GeoPoint(north, east));
  }

  final GeoPoint southWest;
  final GeoPoint northEast;
}

/// Great-circle distance in metres.
double distanceMeters(GeoPoint a, GeoPoint b) {
  const radius = 6371000.0;
  double rad(double degrees) => degrees * math.pi / 180;
  final dLat = rad(b.lat - a.lat) / 2;
  final dLon = rad(b.lon - a.lon) / 2;
  final h =
      math.sin(dLat) * math.sin(dLat) +
      math.cos(rad(a.lat)) *
          math.cos(rad(b.lat)) *
          math.sin(dLon) *
          math.sin(dLon);
  return 2 * radius * math.asin(math.min(1, math.sqrt(h)));
}

/// Groups screen positions that are closer than [radius] to the first member
/// of a group. Returns the indexes of each group, in input order.
List<List<int>> clusterByDistance(
  List<math.Point<double>> positions,
  double radius,
) {
  final groups = <List<int>>[];
  for (var index = 0; index < positions.length; index++) {
    final position = positions[index];
    final group = groups.where(
      (g) => positions[g.first].distanceTo(position) <= radius,
    );
    if (group.isEmpty) {
      groups.add([index]);
    } else {
      group.first.add(index);
    }
  }
  return groups;
}

/// The index of the value in the ascending list that is closest to [target].
int nearestIndex(List<double> ascending, double target) {
  if (ascending.isEmpty) return -1;
  var low = 0, high = ascending.length - 1;
  while (low < high) {
    final middle = (low + high) ~/ 2;
    if (ascending[middle] < target) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  if (low > 0 &&
      (target - ascending[low - 1]).abs() <= (ascending[low] - target).abs()) {
    return low - 1;
  }
  return low;
}
