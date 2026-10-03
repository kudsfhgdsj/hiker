import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/db/app_database.dart';
import '../../../core/session/session.dart';
import '../../../core/sync/sync_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../core/widgets/sync_section.dart';
import '../../../l10n/app_localizations.dart';
import '../data/auth_repository.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _logout(BuildContext context, WidgetRef ref) async {
    // Changes that were not sent yet would be lost: ask first.
    if (!ref.read(syncProvider).isClean) {
      final l10n = AppLocalizations.of(context);
      final proceed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          content: Text(l10n.syncLogoutWarning),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(l10n.cancel),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: Text(l10n.logout),
            ),
          ],
        ),
      );
      if (proceed != true) return;
    }
    final refresh = ref.read(sessionProvider).tokens?.refresh;
    if (refresh != null) await ref.read(authRepositoryProvider).logout(refresh);
    // Nothing of this user may stay on the device.
    await ref.read(appDatabaseProvider).clear();
    await ref.read(syncProvider.notifier).load();
    await ref.read(sessionProvider.notifier).signOut();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final user = ref.watch(sessionProvider.select((s) => s.user));
    final profile = ref.watch(profileProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.profileTitle),
        actions: [
          TextButton.icon(
            onPressed: () => _logout(context, ref),
            icon: const Icon(Icons.logout),
            label: Text(l10n.logout),
          ),
        ],
      ),
      body: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => CenteredForm(
          children: [
            ErrorText(error),
            const SizedBox(height: AppSpacing.m),
            OutlinedButton(
              onPressed: () => ref.invalidate(profileProvider),
              child: Text(l10n.retry),
            ),
          ],
        ),
        data: (data) => _ProfileForm(
          initial: data,
          header: user == null
              ? null
              : ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const CircleAvatar(child: Icon(Icons.person)),
                  title: Text(l10n.signedInAs(user.displayName)),
                  subtitle: Text(
                    user.isAdmin
                        ? '${user.email} · ${l10n.roleAdmin}'
                        : user.email,
                  ),
                ),
        ),
      ),
    );
  }
}

class _ProfileForm extends ConsumerStatefulWidget {
  const _ProfileForm({required this.initial, this.header});

  final Profile initial;
  final Widget? header;

  @override
  ConsumerState<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends ConsumerState<_ProfileForm> {
  final _formKey = GlobalKey<FormState>();
  late final _weight = TextEditingController(
    text: _text(widget.initial.weightKg),
  );
  late final _birthYear = TextEditingController(
    text: _text(widget.initial.birthYear),
  );
  late final _maxRate = TextEditingController(
    text: _text(widget.initial.maxHeartRate),
  );
  late final _restingRate = TextEditingController(
    text: _text(widget.initial.restingHeartRate),
  );
  late String? _sex = widget.initial.sex;
  bool _busy = false;
  Object? _error;

  static String _text(num? value) {
    if (value == null) return '';
    return value == value.roundToDouble()
        ? value.round().toString()
        : value.toString();
  }

  /// Accepts a comma as decimal separator, as it is typed in German.
  static double? _number(String text) =>
      double.tryParse(text.trim().replaceAll(',', '.'));

  @override
  void dispose() {
    _weight.dispose();
    _birthYear.dispose();
    _maxRate.dispose();
    _restingRate.dispose();
    super.dispose();
  }

  String? Function(String?) _range(AppLocalizations l10n, num min, num max) {
    return (value) {
      if ((value ?? '').trim().isEmpty) return null;
      final number = _number(value!);
      if (number == null || number < min || number > max) {
        return l10n.invalidNumber;
      }
      return null;
    };
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    try {
      await ref
          .read(authRepositoryProvider)
          .saveProfile(
            Profile(
              weightKg: _number(_weight.text),
              birthYear: _number(_birthYear.text)?.round(),
              sex: _sex,
              maxHeartRate: _number(_maxRate.text)?.round(),
              restingHeartRate: _number(_restingRate.text)?.round(),
            ),
          );
      messenger.showSnackBar(SnackBar(content: Text(l10n.saved)));
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
    final wholeNumber = [FilteringTextInputFormatter.digitsOnly];
    final sexLabels = {
      'female': l10n.sexFemale,
      'male': l10n.sexMale,
      'trans': l10n.sexTrans,
      'undisclosed': l10n.sexUndisclosed,
    };
    return Form(
      key: _formKey,
      child: CenteredForm(
        children: [
          if (widget.header != null) ...[widget.header!, gap],
          const SyncSection(),
          gap,
          Text(
            l10n.profileIntro,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: AppSpacing.l),
          TextFormField(
            controller: _weight,
            decoration: InputDecoration(labelText: l10n.weightKg),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            validator: _range(l10n, 20, 400),
          ),
          gap,
          TextFormField(
            controller: _birthYear,
            decoration: InputDecoration(labelText: l10n.birthYear),
            keyboardType: TextInputType.number,
            inputFormatters: wholeNumber,
            validator: _range(l10n, 1900, DateTime.now().year),
          ),
          gap,
          DropdownButtonFormField<String?>(
            initialValue: _sex,
            decoration: InputDecoration(labelText: l10n.sex),
            items: [
              DropdownMenuItem(child: Text(l10n.sexNotSet)),
              for (final value in Profile.sexValues)
                DropdownMenuItem(value: value, child: Text(sexLabels[value]!)),
            ],
            onChanged: (value) => setState(() => _sex = value),
          ),
          gap,
          TextFormField(
            controller: _maxRate,
            decoration: InputDecoration(labelText: l10n.maxHeartRate),
            keyboardType: TextInputType.number,
            inputFormatters: wholeNumber,
            validator: _range(l10n, 60, 250),
          ),
          gap,
          TextFormField(
            controller: _restingRate,
            decoration: InputDecoration(labelText: l10n.restingHeartRate),
            keyboardType: TextInputType.number,
            inputFormatters: wholeNumber,
            validator: _range(l10n, 20, 150),
          ),
          if (_error != null) ...[gap, ErrorText(_error!)],
          const SizedBox(height: AppSpacing.l),
          FilledButton(onPressed: _busy ? null : _save, child: Text(l10n.save)),
        ],
      ),
    );
  }
}
