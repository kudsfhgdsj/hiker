import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../network/trusted_certificates.dart';
import '../session/session.dart';
import '../theme/app_theme.dart';

/// Looks at the certificate of [server]. If the system does not trust it and the
/// user has not confirmed exactly this one yet, shows its fingerprint and asks.
/// Returns true if the user now trusts it.
Future<bool> offerToTrustCertificate(
  BuildContext context,
  WidgetRef ref,
  Uri server,
) async {
  final found = await ref.read(certificateProbeProvider)(server);
  if (found == null || !context.mounted) return false;
  final endpoint = '${found.host}:${found.port}';
  final known = ref.read(trustedCertificatesProvider);
  if (known[endpoint] == found.fingerprint) return false;
  final trusted = ref.read(trustedCertificatesProvider.notifier);
  final l10n = AppLocalizations.of(context);
  // Another certificate than the one confirmed before: renewed, or not the server.
  final changed = known.containsKey(endpoint);
  final accepted = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(l10n.certificateTitle),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(changed ? l10n.certificateChanged : l10n.certificateUnknown),
            const SizedBox(height: AppSpacing.m),
            Text(l10n.certificateFingerprint),
            SelectableText(
              found.fingerprint,
              style: const TextStyle(fontFamily: 'monospace'),
            ),
            const SizedBox(height: AppSpacing.m),
            Text(found.subject),
            const SizedBox(height: AppSpacing.m),
            Text(l10n.certificateAdvice),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(l10n.certificateTrust),
        ),
      ],
    ),
  );
  if (accepted != true) return false;
  await trusted.trust(found.host, found.port, found.fingerprint);
  return true;
}

/// Notices when the server of a signed-in user shows another certificate than
/// the one trusted by hand, e.g. after it was renewed. Without this the app
/// would just look offline. Asks once per start of the app.
class CertificateWatcher extends ConsumerStatefulWidget {
  const CertificateWatcher({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<CertificateWatcher> createState() => _CertificateWatcherState();
}

class _CertificateWatcherState extends ConsumerState<CertificateWatcher> {
  bool _asked = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _check());
  }

  Future<void> _check() async {
    if (_asked || !mounted) return;
    final server = Uri.tryParse(ref.read(sessionProvider).baseUrl);
    if (server == null || server.scheme != 'https') return;
    final endpoint = '${server.host}:${server.hasPort ? server.port : 443}';
    // Only servers whose certificate was confirmed by hand can change that way.
    if (!ref.read(trustedCertificatesProvider).containsKey(endpoint)) return;
    _asked = true;
    final accepted = await offerToTrustCertificate(context, ref, server);
    if (accepted && mounted) {
      ref.read(certificateChangedProvider.notifier).bump();
    }
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// Counts the certificates accepted while signed in; screens reload on a change.
class CertificateChanged extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final certificateChangedProvider = NotifierProvider<CertificateChanged, int>(
  CertificateChanged.new,
);
