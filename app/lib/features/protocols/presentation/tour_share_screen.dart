import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../data/tour_repository.dart';

final _sharesProvider = FutureProvider.autoDispose.family<List<Json>, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).shares(id),
);

final _linksProvider = FutureProvider.autoDispose.family<List<Json>, String>(
  (ref, id) => ref.watch(tourRepositoryProvider).publicLinks(id),
);

/// Shares with other users and public links of a tour (owner only).
class TourShareScreen extends ConsumerStatefulWidget {
  const TourShareScreen({super.key, required this.tourId});

  final String tourId;

  @override
  ConsumerState<TourShareScreen> createState() => _TourShareScreenState();
}

class _TourShareScreenState extends ConsumerState<TourShareScreen> {
  final _email = TextEditingController();
  String _permission = 'read';
  String? _lookupError;

  String get _id => widget.tourId;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function(TourRepository r) action) async {
    try {
      await action(ref.read(tourRepositoryProvider));
      ref.invalidate(_sharesProvider(_id));
      ref.invalidate(_linksProvider(_id));
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Future<void> _share() async {
    final l10n = AppLocalizations.of(context);
    setState(() => _lookupError = null);
    await _run((r) async {
      final user = await r.lookupUser(_email.text.trim());
      if (user == null) {
        setState(() => _lookupError = l10n.shareUserNotFound);
        return;
      }
      await r.share(_id, user['id'] as String, _permission);
      _email.clear();
    });
  }

  Future<void> _newLink() async {
    final options = await showDialog<Json>(
      context: context,
      builder: (context) => const _LinkDialog(),
    );
    if (options != null) await _run((r) => r.createPublicLink(_id, options));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final permissions = [
      DropdownMenuItem(value: 'read', child: Text(l10n.shareRead)),
      DropdownMenuItem(value: 'edit', child: Text(l10n.shareEditPermission)),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(l10n.tourShare)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.m),
        children: [
          Text(l10n.shareWithUser, style: theme.textTheme.titleMedium),
          const SizedBox(height: AppSpacing.s),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: TextField(
                  controller: _email,
                  decoration: InputDecoration(
                    labelText: l10n.email,
                    hintText: l10n.shareEmailHint,
                    errorText: _lookupError,
                  ),
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                ),
              ),
              const SizedBox(width: AppSpacing.s),
              DropdownButton<String>(
                value: _permission,
                items: permissions,
                onChanged: (value) => setState(() => _permission = value!),
              ),
              IconButton.filled(
                tooltip: l10n.tourShare,
                icon: const Icon(Icons.person_add_alt),
                onPressed: _share,
              ),
            ],
          ),
          AsyncBody(
            value: ref.watch(_sharesProvider(_id)),
            onRetry: () => ref.invalidate(_sharesProvider(_id)),
            builder: (shares) => Column(
              children: [
                if (shares.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.m),
                    child: Text(l10n.shareNone),
                  ),
                for (final share in shares)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.person_outline),
                    title: Text(
                      (share['user'] as Json)['display_name'] as String? ?? '?',
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        DropdownButton<String>(
                          value: share['permission'] as String,
                          items: permissions,
                          onChanged: (value) => _run(
                            (r) => r.updateShare(
                              _id,
                              (share['user'] as Json)['id'] as String,
                              value!,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: l10n.delete,
                          icon: const Icon(Icons.close),
                          onPressed: () => _run(
                            (r) => r.removeShare(
                              _id,
                              (share['user'] as Json)['id'] as String,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const Divider(height: AppSpacing.xl),
          Row(
            children: [
              Expanded(
                child: Text(
                  l10n.sharePublicLinks,
                  style: theme.textTheme.titleMedium,
                ),
              ),
              TextButton.icon(
                onPressed: _newLink,
                icon: const Icon(Icons.add_link),
                label: Text(l10n.shareNewLink),
              ),
            ],
          ),
          Text(l10n.shareLinkHint, style: theme.textTheme.bodySmall),
          AsyncBody(
            value: ref.watch(_linksProvider(_id)),
            onRetry: () => ref.invalidate(_linksProvider(_id)),
            builder: (links) => Column(
              children: [
                if (links.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.m),
                    child: Text(l10n.shareNoLinks),
                  ),
                for (final link in links)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    enabled: link['active'] as bool,
                    leading: const Icon(Icons.link),
                    title: Text(
                      link['url'] as String,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      [
                        if (link['revoked_at'] != null)
                          l10n.shareLinkRevoked
                        else if (!(link['active'] as bool))
                          l10n.shareLinkExpired,
                        if (link['hide_exact_start'] == true)
                          l10n.shareLinkHideStart,
                        if (link['strip_photo_gps'] == true)
                          l10n.shareLinkStripGps,
                        if (link['show_health_data'] == true)
                          l10n.shareLinkHealth,
                      ].join(' · '),
                    ),
                    trailing: (link['active'] as bool)
                        ? Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                tooltip: l10n.shareLinkCopied,
                                icon: const Icon(Icons.copy),
                                onPressed: () async {
                                  final messenger = ScaffoldMessenger.of(
                                    context,
                                  );
                                  await Clipboard.setData(
                                    ClipboardData(text: link['url'] as String),
                                  );
                                  messenger.showSnackBar(
                                    SnackBar(
                                      content: Text(l10n.shareLinkCopied),
                                    ),
                                  );
                                },
                              ),
                              IconButton(
                                tooltip: l10n.shareLinkRevoke,
                                icon: const Icon(Icons.link_off),
                                onPressed: () => _run(
                                  (r) => r.revokePublicLink(
                                    _id,
                                    link['id'] as String,
                                  ),
                                ),
                              ),
                            ],
                          )
                        : null,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LinkDialog extends StatefulWidget {
  const _LinkDialog();

  @override
  State<_LinkDialog> createState() => _LinkDialogState();
}

class _LinkDialogState extends State<_LinkDialog> {
  bool _hideStart = false;
  bool _stripGps = false;
  bool _health = false;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(l10n.shareNewLink),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SwitchListTile(
            title: Text(l10n.shareLinkHideStart),
            value: _hideStart,
            onChanged: (v) => setState(() => _hideStart = v),
          ),
          SwitchListTile(
            title: Text(l10n.shareLinkStripGps),
            value: _stripGps,
            onChanged: (v) => setState(() => _stripGps = v),
          ),
          // Off by default: heart rate and calories burned are health data.
          SwitchListTile(
            title: Text(l10n.shareLinkHealth),
            value: _health,
            onChanged: (v) => setState(() => _health = v),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, <String, dynamic>{
            'hide_exact_start': _hideStart,
            'strip_photo_gps': _stripGps,
            'show_health_data': _health,
          }),
          child: Text(l10n.shareNewLink),
        ),
      ],
    );
  }
}
