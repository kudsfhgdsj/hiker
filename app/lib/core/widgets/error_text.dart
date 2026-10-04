import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    'mfa_required' => l10n.errorMfaRequired,
    'mfa_token_invalid' => l10n.errorMfaTokenInvalid,
    'invalid_mfa_code' => l10n.errorInvalidMfaCode,
    'wrong_password' => l10n.errorWrongPassword,
    'weak_password' => switch (error.body?['reason']) {
      'contains_personal_data' => l10n.errorPasswordPersonal,
      'too_common' => l10n.errorPasswordCommon,
      'too_short' => l10n.passwordTooShort,
      _ => l10n.passwordTooSimple,
    },
    'email_taken' => l10n.errorEmailTaken,
    'registration_closed' => l10n.errorRegistrationClosed,
    'rate_limited' => l10n.errorRateLimited,
    'invalid_token' || 'unauthorized' => l10n.errorSessionExpired,
    'invalid_image' => l10n.errorInvalidImage,
    'already_in_catalog' => l10n.gearAlreadyInCatalog,
    'barcode_in_catalog' => l10n.errorBarcodeInCatalog,
    'invalid_gpx' => l10n.errorInvalidGpx,
    'owner_only_field' || 'insufficient_permission' => l10n.errorOwnerOnly,
    'points_from_track' => l10n.errorPointsFromTrack,
    'no_sample_points' => l10n.errorNoSamplePoints,
    'no_profile' => l10n.tourNoEstimateProfile,
    'no_track' => l10n.tourNoEstimateTrack,
    'no_duration' => l10n.tourNoEstimateDuration,
    'source_unavailable' => l10n.foodSourceUnavailable,
    'no_route' => l10n.errorNoRoute,
    'routing_unavailable' => l10n.errorRoutingUnavailable,
    'version_conflict' => l10n.errorVersionConflict,
    _ => switch (error.statusCode) {
      403 => l10n.errorForbidden,
      404 => l10n.errorNotFound,
      409 => l10n.errorConflict,
      413 => l10n.errorTooLarge,
      422 => l10n.errorValidation,
      _ => l10n.errorUnknown,
    },
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

/// Shows the German text of an error at the bottom of the screen.
void showError(BuildContext context, Object error) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(describeError(AppLocalizations.of(context), error))),
  );
}

/// Loading, error with retry, or the content: the three states of a request.
class AsyncBody<T> extends StatelessWidget {
  const AsyncBody({
    super.key,
    required this.value,
    required this.onRetry,
    required this.builder,
  });

  final AsyncValue<T> value;
  final VoidCallback onRetry;
  final Widget Function(T data) builder;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return value.when(
      skipLoadingOnRefresh: true,
      skipLoadingOnReload: true,
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => CenteredForm(
        children: [
          ErrorText(error),
          const SizedBox(height: AppSpacing.m),
          OutlinedButton(onPressed: onRetry, child: Text(l10n.retry)),
        ],
      ),
      data: builder,
    );
  }
}

/// Hint that the data on screen comes from the device, not from the server.
class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: scheme.secondaryContainer,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.m,
        vertical: AppSpacing.s,
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_off, size: 18, color: scheme.onSecondaryContainer),
          const SizedBox(width: AppSpacing.s),
          Expanded(
            child: Text(
              AppLocalizations.of(context).offlineData,
              style: TextStyle(color: scheme.onSecondaryContainer),
            ),
          ),
        ],
      ),
    );
  }
}

/// Asks before something is deleted; true if the user confirmed.
Future<bool> confirmDelete(BuildContext context, String what) async {
  final l10n = AppLocalizations.of(context);
  final result = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(l10n.confirmDeleteTitle),
      content: Text(what),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(l10n.delete),
        ),
      ],
    ),
  );
  return result ?? false;
}
