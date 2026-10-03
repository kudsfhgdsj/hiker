/// Build-time configuration. Nothing here is a secret or a fixed domain:
/// the server address is entered at login and stored on the device.
class AppConfig {
  const AppConfig._();

  /// Optional default for the server address, e.g.
  /// `--dart-define=API_BASE_URL=https://hiker.example.org`.
  static const defaultBaseUrl = String.fromEnvironment('API_BASE_URL');

  static const apiPrefix = '/api/v1';

  /// Tile source of the map; replaceable until the licences are settled.
  static const mapTileUrl = String.fromEnvironment(
    'MAP_TILE_URL',
    defaultValue: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  );
}

/// Returns the address without trailing slash, or null if it is not usable.
String? normalizeBaseUrl(String input) {
  final text = input.trim().replaceAll(RegExp(r'/+$'), '');
  final uri = Uri.tryParse(text);
  if (uri == null || !uri.hasAuthority) return null;
  if (uri.scheme != 'http' && uri.scheme != 'https') return null;
  return text;
}
