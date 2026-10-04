import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/session/session.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/auth_repository.dart';

/// The rules of the server, checked before sending: at least 8 characters
/// with three kinds of characters, or at least 20 with two.
String? passwordProblem(AppLocalizations l10n, String password) {
  if (password.length < 8) return l10n.passwordTooShort;
  final kinds = [
    RegExp('[a-zäöüß]'),
    RegExp('[A-ZÄÖÜ]'),
    RegExp('[0-9]'),
    RegExp(r'[^A-Za-z0-9äöüßÄÖÜ]'),
  ].where((kind) => kind.hasMatch(password)).length;
  final ok = kinds >= 3 || (password.length >= 20 && kinds >= 2);
  return ok ? null : l10n.passwordTooSimple;
}

Future<void> _signOut(WidgetRef ref) async {
  final refresh = ref.read(sessionProvider).tokens?.refresh;
  if (refresh != null) await ref.read(authRepositoryProvider).logout(refresh);
  await ref.read(sessionProvider.notifier).signOut();
}

/// Leaves a screen that completes the sign-in: back if it was opened from the
/// profile, otherwise the router moves on by itself.
void _leave(BuildContext context) {
  if (context.canPop()) context.pop();
}

/// Sets up the second factor: the secret for the authenticator app, the first
/// code, and then the recovery codes, which are shown exactly once.
class MfaSetupScreen extends ConsumerStatefulWidget {
  const MfaSetupScreen({super.key});

  @override
  ConsumerState<MfaSetupScreen> createState() => _MfaSetupScreenState();
}

class _MfaSetupScreenState extends ConsumerState<MfaSetupScreen> {
  final _code = TextEditingController();
  MfaSetup? _setup;
  ({AuthResult auth, List<String> recoveryCodes})? _done;
  bool _busy = false;
  Object? _error;

  String get _access => ref.read(sessionProvider).tokens?.access ?? '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _load() => _run(() async {
    final setup = await ref.read(authRepositoryProvider).mfaSetup(_access);
    if (mounted) setState(() => _setup = setup);
  });

  Future<void> _enable() => _run(() async {
    final done = await ref
        .read(authRepositoryProvider)
        .mfaEnable(_access, _code.text.trim());
    if (mounted) setState(() => _done = done);
  });

  Future<void> _finish() async {
    final auth = _done!.auth;
    await ref
        .read(sessionProvider.notifier)
        .signIn(auth.tokens, auth.user, pending: auth.pending);
    if (mounted) _leave(context);
  }

  Future<void> _copy(String text, String message) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final forced =
        ref.watch(sessionProvider).pending == SessionPending.mfaSetup;
    const gap = SizedBox(height: AppSpacing.m);
    final done = _done;
    final setup = _setup;

    return Scaffold(
      appBar: AppBar(
        title: Text(done == null ? l10n.mfaTitle : l10n.mfaRecoveryTitle),
        actions: [
          if (forced && done == null)
            TextButton(
              onPressed: () => _signOut(ref),
              child: Text(l10n.logout),
            ),
        ],
      ),
      body: CenteredForm(
        children: done != null
            ? [
                Text(l10n.mfaRecoveryIntro),
                gap,
                for (final code in done.recoveryCodes)
                  SelectableText(
                    code,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 18,
                    ),
                  ),
                gap,
                OutlinedButton.icon(
                  onPressed: () =>
                      _copy(done.recoveryCodes.join('\n'), l10n.copied),
                  icon: const Icon(Icons.copy),
                  label: Text(l10n.mfaRecoveryCopy),
                ),
                gap,
                Text(
                  l10n.mfaRecoveryOnce,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
                const SizedBox(height: AppSpacing.l),
                FilledButton(
                  onPressed: _finish,
                  child: Text(l10n.mfaRecoveryDone),
                ),
              ]
            : [
                if (forced) ...[Text(l10n.mfaForced), gap],
                Text(l10n.mfaStepApp),
                gap,
                if (setup == null && _error == null)
                  const Center(child: CircularProgressIndicator()),
                if (setup != null) ...[
                  Text(l10n.mfaStepSecret),
                  const SizedBox(height: AppSpacing.s),
                  SelectableText(
                    setup.secret,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 18,
                    ),
                  ),
                  Wrap(
                    spacing: AppSpacing.s,
                    children: [
                      OutlinedButton.icon(
                        onPressed: () => _copy(setup.secret, l10n.copied),
                        icon: const Icon(Icons.copy),
                        label: Text(l10n.mfaCopySecret),
                      ),
                      OutlinedButton.icon(
                        onPressed: () => _copy(setup.otpauthUri, l10n.copied),
                        icon: const Icon(Icons.link),
                        label: Text(l10n.mfaCopyLink),
                      ),
                    ],
                  ),
                  gap,
                  Text(l10n.mfaStepCode),
                  gap,
                  TextField(
                    controller: _code,
                    decoration: InputDecoration(labelText: l10n.mfaCode),
                    keyboardType: TextInputType.number,
                    autofillHints: const [AutofillHints.oneTimeCode],
                    maxLength: 6,
                    onSubmitted: (_) => _enable(),
                  ),
                ],
                if (_error != null) ...[gap, ErrorText(_error!)],
                const SizedBox(height: AppSpacing.l),
                if (setup != null)
                  FilledButton(
                    onPressed: _busy ? null : _enable,
                    child: Text(l10n.mfaEnable),
                  )
                else if (_error != null)
                  OutlinedButton(
                    onPressed: _busy ? null : _load,
                    child: Text(l10n.retry),
                  ),
              ],
      ),
    );
  }
}

/// A new password; mandatory after an administrator reset it.
class PasswordChangeScreen extends ConsumerStatefulWidget {
  const PasswordChangeScreen({super.key});

  @override
  ConsumerState<PasswordChangeScreen> createState() =>
      _PasswordChangeScreenState();
}

class _PasswordChangeScreenState extends ConsumerState<PasswordChangeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _repeat = TextEditingController();
  bool _busy = false;
  Object? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _repeat.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final session = ref.read(sessionProvider);
      final result = await ref
          .read(authRepositoryProvider)
          .changePassword(
            session.tokens?.access ?? '',
            current: _current.text,
            next: _next.text,
          );
      await ref
          .read(sessionProvider.notifier)
          .signIn(result.tokens, result.user, pending: result.pending);
      if (mounted) {
        final l10n = AppLocalizations.of(context);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(l10n.passwordChanged)));
        _leave(context);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final forced =
        ref.watch(sessionProvider).pending == SessionPending.passwordChange;
    const gap = SizedBox(height: AppSpacing.m);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.passwordChange),
        actions: [
          if (forced)
            TextButton(
              onPressed: () => _signOut(ref),
              child: Text(l10n.logout),
            ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: CenteredForm(
          children: [
            if (forced) ...[Text(l10n.passwordForced), gap],
            TextFormField(
              controller: _current,
              decoration: InputDecoration(labelText: l10n.passwordCurrent),
              obscureText: true,
              autofillHints: const [AutofillHints.password],
              validator: (value) =>
                  (value ?? '').isEmpty ? l10n.requiredField : null,
            ),
            gap,
            TextFormField(
              controller: _next,
              decoration: InputDecoration(
                labelText: l10n.passwordNew,
                helperText: l10n.passwordRules,
                helperMaxLines: 4,
              ),
              obscureText: true,
              autofillHints: const [AutofillHints.newPassword],
              validator: (value) => passwordProblem(l10n, value ?? ''),
            ),
            gap,
            TextFormField(
              controller: _repeat,
              decoration: InputDecoration(labelText: l10n.passwordRepeat),
              obscureText: true,
              autofillHints: const [AutofillHints.newPassword],
              validator: (value) =>
                  value == _next.text ? null : l10n.passwordsDiffer,
              onFieldSubmitted: (_) => _submit(),
            ),
            if (_error != null) ...[gap, ErrorText(_error!)],
            const SizedBox(height: AppSpacing.l),
            FilledButton(
              onPressed: _busy ? null : _submit,
              child: Text(l10n.save),
            ),
            const SizedBox(height: AppSpacing.s),
            Text(
              l10n.passwordSessions,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
