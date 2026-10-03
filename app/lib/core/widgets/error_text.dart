import 'package:flutter/material.dart';

import '../../l10n/app_localizations.dart';
import '../network/api_exception.dart';
import '../theme/app_theme.dart';

/// German text for an error of the API; the server only sends codes.
String describeError(AppLocalizations l10n, Object error) {
  if (error is! ApiException) return l10n.errorUnknown;
  return switch (error.code) {
    ApiException.network => l10n.errorNetwork,
    ApiException.validation => l10n.errorValidation,
    'invalid_credentials' => l10n.errorInvalidCredentials,
    'email_taken' => l10n.errorEmailTaken,
    'registration_closed' => l10n.errorRegistrationClosed,
    'rate_limited' => l10n.errorRateLimited,
    'invalid_token' || 'unauthorized' => l10n.errorSessionExpired,
    _ => l10n.errorUnknown,
  };
}

/// Error message inside a form.
class ErrorText extends StatelessWidget {
  const ErrorText(this.error, {super.key});

  final Object error;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.m),
        decoration: BoxDecoration(
          color: scheme.errorContainer,
          borderRadius: BorderRadius.circular(AppSpacing.s),
        ),
        child: Text(
          describeError(AppLocalizations.of(context), error),
          style: TextStyle(color: scheme.onErrorContainer),
        ),
      ),
    );
  }
}

/// Centers a column of limited width, for forms on wide screens.
class CenteredForm extends StatelessWidget {
  const CenteredForm({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.l),
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.maxContentWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ),
    );
  }
}
