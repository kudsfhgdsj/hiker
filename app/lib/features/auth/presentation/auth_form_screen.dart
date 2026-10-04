import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_config.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/router/app_router.dart';
import '../../../core/session/session.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/certificate_dialog.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/auth_repository.dart';
import 'account_security_screens.dart';

/// Login and registration share one form; registration adds the display name.
class AuthFormScreen extends ConsumerStatefulWidget {
  const AuthFormScreen({super.key, required this.register});

  final bool register;

  @override
  ConsumerState<AuthFormScreen> createState() => _AuthFormScreenState();
}

class _AuthFormScreenState extends ConsumerState<AuthFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final _server = TextEditingController(text: _initialServer());
  final _email = TextEditingController();
  final _name = TextEditingController();
  final _password = TextEditingController();
  final _repeat = TextEditingController();
  final _code = TextEditingController();

  /// Set after the password was right for an account with a second factor:
  /// the screen then asks for the code only. It stands for the first step.
  String? _mfaToken;
  bool _busy = false;
  Object? _error;

  String _initialServer() => ref.read(sessionProvider).baseUrl;

  @override
  void dispose() {
    _server.dispose();
    _email.dispose();
    _name.dispose();
    _password.dispose();
    _repeat.dispose();
    _code.dispose();
    super.dispose();
  }

  /// The connection failed: if the reason is a certificate the system does
  /// not know (self-signed), show its fingerprint and let the user decide.
  Future<bool> _offerToTrustCertificate(Object error) async {
    if (error is! ApiException || error.code != ApiException.network) {
      return false;
    }
    final server = Uri.tryParse(normalizeBaseUrl(_server.text) ?? '');
    if (server == null || !mounted) return false;
    return offerToTrustCertificate(context, ref, server);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final session = ref.read(sessionProvider.notifier);
    try {
      await session.setBaseUrl(normalizeBaseUrl(_server.text)!);
      final repository = ref.read(authRepositoryProvider);
      final mfaToken = _mfaToken;
      final result = mfaToken != null
          ? await repository.loginSecondStep(
              mfaToken: mfaToken,
              code: _code.text.trim(),
            )
          : widget.register
          ? await repository.register(
              email: _email.text.trim(),
              displayName: _name.text.trim(),
              password: _password.text,
            )
          : await repository.login(
              email: _email.text.trim(),
              password: _password.text,
            );
      await session.signIn(result.tokens, result.user, pending: result.pending);
    } catch (error) {
      if (await _offerToTrustCertificate(error)) return _submit();
      if (mounted) {
        setState(() {
          final body = error is ApiException ? error.body : null;
          final token = body == null ? null : body['mfa_token'];
          if (error is ApiException &&
              error.code == 'mfa_required' &&
              token is String) {
            // The password was right: go on to the second step.
            _mfaToken = token;
            _code.clear();
            _error = null;
            return;
          }
          _error = error;
          // The first step is too long ago: start again.
          if (error is ApiException && error.code == 'mfa_token_invalid') {
            _mfaToken = null;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Second step of the sign-in: nothing but the code.
  Widget _codeStep(AppLocalizations l10n) {
    const gap = SizedBox(height: AppSpacing.m);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.mfaStepTitle)),
      body: Form(
        key: _formKey,
        child: CenteredForm(
          children: [
            Text(l10n.mfaStepIntro),
            gap,
            TextFormField(
              controller: _code,
              decoration: InputDecoration(
                labelText: l10n.mfaCode,
                helperText: l10n.mfaCodeHint,
                helperMaxLines: 2,
              ),
              keyboardType: TextInputType.visiblePassword,
              autofillHints: const [AutofillHints.oneTimeCode],
              autofocus: true,
              onFieldSubmitted: (_) => _submit(),
              validator: (value) =>
                  (value ?? '').trim().isEmpty ? l10n.requiredField : null,
            ),
            if (_error != null) ...[gap, ErrorText(_error!)],
            const SizedBox(height: AppSpacing.l),
            FilledButton(
              onPressed: _busy ? null : _submit,
              child: Text(l10n.loginAction),
            ),
            const SizedBox(height: AppSpacing.s),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _mfaToken = null;
                      _error = null;
                    }),
              child: Text(l10n.mfaStepBack),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    if (_mfaToken != null) return _codeStep(l10n);
    const gap = SizedBox(height: AppSpacing.m);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.register ? l10n.registerTitle : l10n.loginTitle),
      ),
      body: Form(
        key: _formKey,
        child: AutofillGroup(
          child: CenteredForm(
            children: [
              TextFormField(
                controller: _server,
                decoration: InputDecoration(
                  labelText: l10n.serverUrl,
                  hintText: l10n.serverUrlHint,
                ),
                keyboardType: TextInputType.url,
                autocorrect: false,
                textInputAction: TextInputAction.next,
                validator: (value) => normalizeBaseUrl(value ?? '') == null
                    ? l10n.serverUrlInvalid
                    : null,
              ),
              gap,
              TextFormField(
                controller: _email,
                decoration: InputDecoration(labelText: l10n.email),
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                autocorrect: false,
                textInputAction: TextInputAction.next,
                validator: (value) =>
                    RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                        .hasMatch((value ?? '').trim())
                    ? null
                    : l10n.emailInvalid,
              ),
              if (widget.register) ...[
                gap,
                TextFormField(
                  controller: _name,
                  decoration: InputDecoration(labelText: l10n.displayName),
                  autofillHints: const [AutofillHints.name],
                  textInputAction: TextInputAction.next,
                  validator: (value) =>
                      (value ?? '').trim().isEmpty ? l10n.requiredField : null,
                ),
              ],
              gap,
              TextFormField(
                controller: _password,
                decoration: InputDecoration(
                  labelText: l10n.password,
                  helperText: widget.register ? l10n.passwordRules : null,
                  helperMaxLines: 4,
                ),
                obscureText: true,
                autofillHints: [
                  widget.register
                      ? AutofillHints.newPassword
                      : AutofillHints.password,
                ],
                textInputAction: widget.register
                    ? TextInputAction.next
                    : TextInputAction.done,
                onFieldSubmitted: widget.register ? null : (_) => _submit(),
                validator: (value) {
                  if ((value ?? '').isEmpty) return l10n.requiredField;
                  return widget.register ? passwordProblem(l10n, value!) : null;
                },
              ),
              if (widget.register) ...[
                gap,
                TextFormField(
                  controller: _repeat,
                  decoration: InputDecoration(labelText: l10n.passwordRepeat),
                  obscureText: true,
                  autofillHints: const [AutofillHints.newPassword],
                  onFieldSubmitted: (_) => _submit(),
                  validator: (value) =>
                      value == _password.text ? null : l10n.passwordsDiffer,
                ),
              ],
              if (_error != null) ...[gap, ErrorText(_error!)],
              const SizedBox(height: AppSpacing.l),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        widget.register
                            ? l10n.registerAction
                            : l10n.loginAction,
                      ),
              ),
              const SizedBox(height: AppSpacing.s),
              TextButton(
                onPressed: _busy
                    ? null
                    : () => context.go(
                        widget.register ? AppRoutes.login : AppRoutes.register,
                      ),
                child: Text(
                  widget.register ? l10n.goToLogin : l10n.goToRegister,
                ),
              ),
              // The map needs no account.
              if (!widget.register)
                TextButton.icon(
                  icon: const Icon(Icons.map_outlined),
                  label: Text(l10n.mapOpenWithoutLogin),
                  onPressed: _busy ? null : () => context.go(AppRoutes.openMap),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
