/// Build-time configuration. Nothing here is a secret or a fixed domain:
/// the server address is entered at login and stored on the device.
class AppConfig {
  const AppConfig._();

  /// Optional default for the server address, e.g.
  /// `--dart-define=API_BASE_URL=https://hiker.example.org`.
  static const defaultBaseUrl = String.fromEnvironment('API_BASE_URL');

  static const apiPrefix = '/api/v1';

  /// Optional fixed tile source of the map (`--dart-define=MAP_TILE_URL=...`).
  /// Empty: the tiles come from the user's server (module `maps`).
  static const mapTileUrl = String.fromEnvironment('MAP_TILE_URL');

  /// Tiles the server keeps a copy of, below its address.
  static const serverTilePath = '$apiPrefix/maps/tiles/{z}/{x}/{y}.png';

  /// Used only if the server has no module `maps`.
  static const fallbackTileUrl =
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
}

/// Returns the address without trailing slash, or null if it is not usable.
String? normalizeBaseUrl(String input) {
  final text = input.trim().replaceAll(RegExp(r'/+$'), '');
  final uri = Uri.tryParse(text);
  if (uri == null || !uri.hasAuthority) return null;
  if (uri.scheme != 'http' && uri.scheme != 'https') return null;
  return text;
}
