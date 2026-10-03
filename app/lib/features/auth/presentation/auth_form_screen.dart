import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_config.dart';
import '../../../core/router/app_router.dart';
import '../../../core/session/session.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/auth_repository.dart';

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
  bool _busy = false;
  Object? _error;

  String _initialServer() {
    final stored = ref.read(sessionProvider).baseUrl;
    if (stored.isNotEmpty) return stored;
    // In the browser the app is normally served by the server it talks to.
    return kIsWeb ? Uri.base.origin : '';
  }

  @override
  void dispose() {
    _server.dispose();
    _email.dispose();
    _name.dispose();
    _password.dispose();
    super.dispose();
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
      final result = widget.register
          ? await repository.register(
              email: _email.text.trim(),
              displayName: _name.text.trim(),
              password: _password.text,
            )
          : await repository.login(
              email: _email.text.trim(),
              password: _password.text,
            );
      await session.signIn(result.tokens, result.user);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
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
                decoration: InputDecoration(labelText: l10n.password),
                obscureText: true,
                autofillHints: [
                  widget.register
                      ? AutofillHints.newPassword
                      : AutofillHints.password,
                ],
                onFieldSubmitted: (_) => _submit(),
                validator: (value) {
                  if ((value ?? '').isEmpty) return l10n.requiredField;
                  if (widget.register && value!.length < 10) {
                    return l10n.passwordTooShort;
                  }
                  return null;
                },
              ),
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
            ],
          ),
        ),
      ),
    );
  }
}
