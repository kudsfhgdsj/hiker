import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../network/trusted_certificates.dart';
import '../theme/app_theme.dart';

/// The self-signed certificates the user trusts, with a way to take the trust
/// back. Not shown while there is none.
class TrustedCertificatesSection extends ConsumerWidget {
  const TrustedCertificatesSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final trusted = ref.watch(trustedCertificatesProvider);
    if (trusted.isEmpty) return const SizedBox.shrink();
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.m),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.certificatesTitle, style: theme.textTheme.titleMedium),
            const SizedBox(height: AppSpacing.xs),
            Text(l10n.certificatesIntro, style: theme.textTheme.bodySmall),
            for (final entry in trusted.entries)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(entry.key),
                subtitle: Text(
                  entry.value,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                ),
                trailing: IconButton(
                  tooltip: l10n.certificateRemove,
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => ref
                      .read(trustedCertificatesProvider.notifier)
                      .forget(entry.key),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
