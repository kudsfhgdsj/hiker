import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/key_value_store.dart';

/// SHA-256 of the certificate as pairs of hex digits, the way browsers and
/// `openssl x509 -fingerprint -sha256` show it.
String certificateFingerprint(X509Certificate certificate) => sha256
    .convert(certificate.der)
    .bytes
    .map((byte) => byte.toRadixString(16).padLeft(2, '0').toUpperCase())
    .join(':');

String _endpoint(String host, int port) => '$host:$port';

/// Certificates the user decided to trust although no known authority issued
/// them (self-signed). Kept per server as a fingerprint: the app only accepts
/// exactly that certificate, so a different one is refused again.
class TrustedCertificates extends Notifier<Map<String, String>> {
  static const _key = 'trusted_certificates';

  KeyValueStore get _store => ref.read(keyValueStoreProvider);

  @override
  Map<String, String> build() => const {};

  /// Loads the stored decisions; call once at start.
  Future<void> load() async {
    final stored = await _store.read(_key);
    if (stored == null) return;
    state = (jsonDecode(stored) as Map<String, dynamic>).cast<String, String>();
  }

  Future<void> trust(String host, int port, String fingerprint) async {
    state = {...state, _endpoint(host, port): fingerprint};
    await _store.write(_key, jsonEncode(state));
  }

  Future<void> forget(String endpoint) async {
    state = {...state}..remove(endpoint);
    await _store.write(_key, jsonEncode(state));
  }

  bool accepts(X509Certificate certificate, String host, int port) =>
      state[_endpoint(host, port)] == certificateFingerprint(certificate);
}

final trustedCertificatesProvider =
    NotifierProvider<TrustedCertificates, Map<String, String>>(
      TrustedCertificates.new,
    );

/// A certificate the system does not trust, as found when asking a server.
typedef UntrustedCertificate = ({
  String host,
  int port,
  String fingerprint,
  String subject,
  DateTime validUntil,
});

typedef CertificateProbe = Future<UntrustedCertificate?> Function(Uri server);

/// Connects to the server once to see its certificate. Returns it if the system
/// does not trust it, otherwise null (trusted, not HTTPS or not reachable).
Future<UntrustedCertificate?> probeCertificate(Uri server) async {
  if (server.scheme != 'https') return null;
  final port = server.hasPort ? server.port : 443;
  UntrustedCertificate? found;
  try {
    final socket = await SecureSocket.connect(
      server.host,
      port,
      timeout: const Duration(seconds: 10),
      onBadCertificate: (certificate) {
        found = (
          host: server.host,
          port: port,
          fingerprint: certificateFingerprint(certificate),
          subject: certificate.subject,
          validUntil: certificate.endValidity,
        );
        // Only to look at it: the connection is closed right away.
        return true;
      },
    );
    socket.destroy();
  } on Exception {
    return null;
  }
  return found;
}

/// Replaceable in tests, which have no network.
final certificateProbeProvider = Provider<CertificateProbe>(
  (ref) => probeCertificate,
);
