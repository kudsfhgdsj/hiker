import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/error_text.dart';
import '../../../l10n/app_localizations.dart';
import '../../gear/data/gear_models.dart';
import '../../gear/data/gear_repository.dart';
import '../../nutrition/data/food_models.dart';
import '../../nutrition/data/food_repository.dart';
import '../data/tour_models.dart';
import '../data/tour_repository.dart';
import 'tour_labels.dart';

/// Creates a tour or edits the document of an existing one.
class TourEditScreen extends ConsumerWidget {
  const TourEditScreen({super.key, this.tourId});

  final String? tourId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final id = tourId;
    return Scaffold(
      appBar: AppBar(title: Text(id == null ? l10n.tourNew : l10n.tourEdit)),
      body: id == null
          ? const _TourForm()
          : AsyncBody(
              value: ref.watch(tourProvider(id)),
              onRetry: () => ref.invalidate(tourProvider(id)),
              builder: (loaded) => _TourForm(tour: loaded.value),
            ),
    );
  }
}

class _TourForm extends ConsumerStatefulWidget {
  const _TourForm({this.tour});

  final Tour? tour;

  @override
  ConsumerState<_TourForm> createState() => _TourFormState();
}

class _TourFormState extends ConsumerState<_TourForm> {
  final _formKey = GlobalKey<FormState>();

  /// The state the edit started from, for merging after a conflict.
  late Json _base = widget.tour == null
      ? _empty()
      : documentOf(widget.tour!.json);
  late int? _version = widget.tour?.version;
  late final Json _doc = documentOf(_base);
  late final _title = TextEditingController(text: _doc['title'] as String?);
  late final _summary = TextEditingController(text: _doc['summary'] as String?);
  late final _tags = TextEditingController(
    text: ((_doc['tags'] as List<dynamic>?) ?? const []).join(', '),
  );
  late final _duration = TextEditingController(
    text: Format.input(_doc['duration_minutes'] as num?),
  );
  late final _packWeight = TextEditingController(
    text: Format.input(_doc['pack_weight_start_g'] as num?),
  );
  late final _calories = TextEditingController(
    text: Format.input(_doc['calories_burned'] as num?),
  );
  bool _busy = false;
  Object? _error;

  bool get _isOwner => widget.tour?.isOwner ?? true;

  static Json _empty() => {
    for (final field in documentFields)
      field: const {'gear', 'food', 'peaks', 'partners'}.contains(field)
          ? <Json>[]
          : (field == 'tags' ? <String>[] : null),
  };

  List<Json> _entries(String field) =>
      (_doc[field] as List<dynamic>).cast<Json>();

  @override
  void dispose() {
    for (final c in [
      _title,
      _summary,
      _tags,
      _duration,
      _packWeight,
      _calories,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  /// The document as it is on screen right now.
  Json _collect() => {
    ..._doc,
    'title': _title.text.trim(),
    'summary': _summary.text.trim().isEmpty ? null : _summary.text.trim(),
    'tags': parseTags(_tags.text),
    if (_isOwner) ...{
      'duration_minutes': Format.parseNumber(_duration.text)?.round(),
      'pack_weight_start_g': Format.parseNumber(_packWeight.text)?.round(),
      'calories_burned': Format.parseNumber(_calories.text),
    },
  };

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final repository = ref.read(tourRepositoryProvider);
    final router = GoRouter.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final l10n = AppLocalizations.of(context);
    var document = _collect();
    try {
      final tour = widget.tour;
      if (tour == null) {
        final created = await repository.create(document);
        ref.invalidate(tourListProvider);
        router.pushReplacement('/protocols/tour/${created.id}');
        return;
      }
      // After a conflict the merge is repeated on the newer state, until it fits.
      for (var attempt = 0; attempt < 3; attempt++) {
        try {
          await repository.update(tour.id, document, _version!);
          ref.invalidate(tourListProvider);
          ref.invalidate(tourProvider(tour.id));
          router.pop();
          return;
        } on ApiException catch (error) {
          final current = error.body?['current'] as Json?;
          if (error.code != 'version_conflict' || current == null) rethrow;
          final merge = mergeDocuments(_base, document, documentOf(current));
          var merged = merge.merged;
          if (merge.conflicts.isNotEmpty) {
            if (!mounted) return;
            final mine = await _askConflicts(merge.conflicts);
            if (mine == null) return;
            merged = {
              ...merged,
              for (final field in mine) field: document[field],
            };
          } else {
            messenger.showSnackBar(
              SnackBar(content: Text(l10n.tourConflictMerged)),
            );
          }
          _base = documentOf(current);
          _version = current['version'] as int;
          document = merged;
        }
      }
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Asks which side wins for the fields both changed; null if cancelled.
  Future<Set<String>?> _askConflicts(List<String> fields) {
    final mine = <String>{...fields};
    return showDialog<Set<String>>(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        final l10n = AppLocalizations.of(context);
        return StatefulBuilder(
          builder: (context, setState) => AlertDialog(
            title: Text(l10n.tourConflictTitle),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.tourConflictBody),
                  for (final field in fields) ...[
                    const SizedBox(height: AppSpacing.m),
                    Text(
                      fieldLabel(l10n, field),
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    SegmentedButton<bool>(
                      segments: [
                        ButtonSegment(
                          value: true,
                          label: Text(l10n.tourConflictMine),
                        ),
                        ButtonSegment(
                          value: false,
                          label: Text(l10n.tourConflictTheirs),
                        ),
                      ],
                      selected: {mine.contains(field)},
                      onSelectionChanged: (value) => setState(
                        () =>
                            value.first ? mine.add(field) : mine.remove(field),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(l10n.cancel),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, mine),
                child: Text(l10n.save),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _pickTime(String field) async {
    final current =
        DateTime.tryParse(_doc[field] as String? ?? '')?.toLocal() ??
        DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: DateTime(1970),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(current),
    );
    if (time == null) return;
    final picked = DateTime(
      date.year,
      date.month,
      date.day,
      time.hour,
      time.minute,
    );
    setState(() => _doc[field] = picked.toUtc().toIso8601String());
  }

  Future<void> _addGear() async {
    final items =
        (await ref
                .read(gearRepositoryProvider)
                .listItems(const GearFilter(status: 'active')))
            .value;
    if (!mounted) return;
    final used = {for (final entry in _entries('gear')) entry['gear_item_id']};
    final chosen = await showDialog<List<GearItem>>(
      context: context,
      builder: (context) => _MultiPickDialog<GearItem>(
        title: AppLocalizations.of(context).tourAddGear,
        options: [
          for (final item in items)
            if (!used.contains(item.id)) item,
        ],
        label: (item) => item.name,
        detail: (item) => Format.weight(item.weightG),
      ),
    );
    if (chosen == null) return;
    setState(() {
      _entries('gear').addAll([
        for (final item in chosen)
          {
            'gear_item_id': item.id,
            'name': item.name,
            'weight_g': item.weightG,
            'quantity': 1,
            'carried': true,
          },
      ]);
    });
  }

  Future<void> _addFood() async {
    final entry = await showDialog<Json>(
      context: context,
      builder: (context) => const _FoodPickDialog(),
    );
    if (entry != null) setState(() => _entries('food').add(entry));
  }

  Future<void> _addPeak() async {
    final name = TextEditingController();
    final elevation = TextEditingController();
    final l10n = AppLocalizations.of(context);
    final peak = await showDialog<Json>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.tourAddPeak),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: name,
              autofocus: true,
              decoration: InputDecoration(labelText: l10n.tourPeakName),
            ),
            const SizedBox(height: AppSpacing.m),
            TextField(
              controller: elevation,
              decoration: InputDecoration(labelText: l10n.tourPeakElevation),
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () {
              if (name.text.trim().isEmpty) return;
              Navigator.pop(context, <String, dynamic>{
                'name': name.text.trim(),
                'elevation_m': int.tryParse(elevation.text),
              });
            },
            child: Text(l10n.add),
          ),
        ],
      ),
    );
    if (peak != null) setState(() => _entries('peaks').add(peak));
  }

  Future<void> _addPartner() async {
    final repository = ref.read(tourRepositoryProvider);
    final l10n = AppLocalizations.of(context);
    final contacts = await repository.contacts();
    if (!mounted) return;
    final used = {
      for (final partner in _entries('partners')) partner['contact_id'],
    };
    final name = TextEditingController();
    final chosen = await showDialog<Json>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.tourAddPartner),
        content: SizedBox(
          width: AppSpacing.maxContentWidth,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final contact in contacts)
                if (!used.contains(contact['id']))
                  ListTile(
                    title: Text(contact['display_name'] as String),
                    onTap: () => Navigator.pop(context, contact),
                  ),
              TextField(
                controller: name,
                decoration: InputDecoration(labelText: l10n.tourNewContact),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, <String, dynamic>{
              'new': name.text.trim(),
            }),
            child: Text(l10n.add),
          ),
        ],
      ),
    );
    if (chosen == null) return;
    try {
      var contact = chosen;
      if (chosen.containsKey('new')) {
        if ((chosen['new'] as String).isEmpty) return;
        contact = await repository.createContact(chosen['new'] as String);
        ref.invalidate(contactsProvider);
      }
      setState(
        () => _entries('partners').add({
          'contact_id': contact['id'],
          'display_name': contact['display_name'],
        }),
      );
    } catch (error) {
      if (mounted) showError(context, error);
    }
  }

  Widget _timeField(String label, String field) {
    final value = DateTime.tryParse(_doc[field] as String? ?? '');
    return InkWell(
      onTap: _isOwner ? () => _pickTime(field) : null,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          enabled: _isOwner,
          suffixIcon: value == null || !_isOwner
              ? const Icon(Icons.schedule)
              : IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () => setState(() => _doc[field] = null),
                ),
        ),
        child: Text(value == null ? '' : Format.dateTime(value)),
      ),
    );
  }

  Widget _numberField(
    TextEditingController controller,
    String label,
    String hint,
    num max,
  ) => TextFormField(
    controller: controller,
    enabled: _isOwner,
    decoration: InputDecoration(labelText: label, helperText: hint),
    keyboardType: TextInputType.number,
    validator: (value) {
      if ((value ?? '').trim().isEmpty) return null;
      final number = Format.parseNumber(value!);
      return number == null || number < 0 || number > max
          ? AppLocalizations.of(context).invalidNumber
          : null;
    },
  );

  Widget _listHeader(String title, String addLabel, VoidCallback onAdd) =>
      Padding(
        padding: const EdgeInsets.only(top: AppSpacing.l),
        child: Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            TextButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add),
              label: Text(addLabel),
            ),
          ],
        ),
      );

  Widget _removable(
    Json entry,
    String field,
    String title, {
    Widget? subtitle,
    Widget? leading,
  }) => ListTile(
    contentPadding: EdgeInsets.zero,
    leading: leading,
    title: Text(title),
    subtitle: subtitle,
    trailing: IconButton(
      tooltip: AppLocalizations.of(context).delete,
      icon: const Icon(Icons.close),
      onPressed: () => setState(() => _entries(field).remove(entry)),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    const gap = SizedBox(height: AppSpacing.m);
    return Form(
      key: _formKey,
      child: CenteredForm(
        children: [
          TextFormField(
            controller: _title,
            decoration: InputDecoration(labelText: l10n.tourTitleField),
            validator: (v) =>
                (v ?? '').trim().isEmpty ? l10n.requiredField : null,
          ),
          gap,
          TextFormField(
            controller: _summary,
            decoration: InputDecoration(labelText: l10n.tourSummary),
            maxLines: null,
            minLines: 3,
          ),
          gap,
          TextFormField(
            key: const ValueKey('tour-tags'),
            controller: _tags,
            decoration: InputDecoration(
              labelText: l10n.tourTags,
              helperText: l10n.tourTagsHint,
            ),
            textInputAction: TextInputAction.done,
          ),
          gap,
          if (!_isOwner) ...[
            Text(
              l10n.tourOwnerOnly,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            gap,
          ],
          _timeField(l10n.tourStart, 'start_time'),
          gap,
          _timeField(l10n.tourEnd, 'end_time'),
          gap,
          _numberField(
            _duration,
            l10n.tourDurationMinutes,
            l10n.tourDurationHint,
            100000,
          ),
          gap,
          _numberField(
            _packWeight,
            l10n.tourPackWeightField,
            l10n.tourPackWeightHint,
            200000,
          ),
          gap,
          _numberField(
            _calories,
            l10n.tourCaloriesBurnedField,
            l10n.tourCaloriesBurnedHint,
            50000,
          ),
          _listHeader(l10n.tourGear, l10n.tourAddGear, _addGear),
          for (final entry in _entries('gear'))
            _removable(
              entry,
              'gear',
              entry['name'] as String? ?? '',
              subtitle: Text(Format.weight(entry['weight_g'] as int?)),
              leading: _Stepper(
                value: entry['quantity'] as int? ?? 1,
                onChanged: (value) => setState(() => entry['quantity'] = value),
              ),
            ),
          _listHeader(l10n.tourFood, l10n.tourAddFood, _addFood),
          for (final entry in _entries('food'))
            _removable(
              entry,
              'food',
              '${entry['name']} · ${Format.number(entry['amount_g'] as num)} g',
              subtitle: Wrap(
                spacing: AppSpacing.s,
                children: [
                  FilterChip(
                    label: Text(l10n.tourCarried),
                    selected: entry['carried'] as bool? ?? true,
                    onSelected: (v) => setState(() => entry['carried'] = v),
                  ),
                  FilterChip(
                    label: Text(l10n.tourEaten),
                    selected: entry['eaten'] as bool? ?? false,
                    onSelected: (v) => setState(() => entry['eaten'] = v),
                  ),
                ],
              ),
            ),
          _listHeader(l10n.tourPeaks, l10n.tourAddPeak, _addPeak),
          for (final peak in _entries('peaks'))
            _removable(
              peak,
              'peaks',
              peak['name'] as String,
              subtitle: peak['elevation_m'] == null
                  ? null
                  : Text(Format.meters(peak['elevation_m'] as num)),
            ),
          _listHeader(l10n.tourPartners, l10n.tourAddPartner, _addPartner),
          for (final partner in _entries('partners'))
            _removable(partner, 'partners', partner['display_name'] as String),
          if (_error != null) ...[gap, ErrorText(_error!)],
          const SizedBox(height: AppSpacing.l),
          FilledButton(onPressed: _busy ? null : _save, child: Text(l10n.save)),
        ],
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({required this.value, required this.onChanged});

  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          tooltip: '${l10n.gearQuantity} −',
          icon: const Icon(Icons.remove_circle_outline),
          onPressed: value > 1 ? () => onChanged(value - 1) : null,
        ),
        Text('$value'),
        IconButton(
          tooltip: '${l10n.gearQuantity} +',
          icon: const Icon(Icons.add_circle_outline),
          onPressed: value < 999 ? () => onChanged(value + 1) : null,
        ),
      ],
    );
  }
}

class _MultiPickDialog<T> extends StatefulWidget {
  const _MultiPickDialog({
    required this.title,
    required this.options,
    required this.label,
    required this.detail,
  });

  final String title;
  final List<T> options;
  final String Function(T) label;
  final String Function(T) detail;

  @override
  State<_MultiPickDialog<T>> createState() => _MultiPickDialogState<T>();
}

class _MultiPickDialogState<T> extends State<_MultiPickDialog<T>> {
  final _chosen = <T>{};

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: AppSpacing.maxContentWidth,
        height: 400,
        child: widget.options.isEmpty
            ? Center(child: Text(l10n.tourNothing))
            : ListView(
                children: [
                  for (final option in widget.options)
                    CheckboxListTile(
                      value: _chosen.contains(option),
                      title: Text(widget.label(option)),
                      subtitle: Text(widget.detail(option)),
                      onChanged: (selected) => setState(
                        () => (selected ?? false)
                            ? _chosen.add(option)
                            : _chosen.remove(option),
                      ),
                    ),
                ],
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _chosen.toList()),
          child: Text(l10n.add),
        ),
      ],
    );
  }
}

/// Search a food (own or catalog) and enter the amount.
class _FoodPickDialog extends ConsumerStatefulWidget {
  const _FoodPickDialog();

  @override
  ConsumerState<_FoodPickDialog> createState() => _FoodPickDialogState();
}

class _FoodPickDialogState extends ConsumerState<_FoodPickDialog> {
  String _query = '';
  Food? _food;
  final _amount = TextEditingController();

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final food = _food;
    final amount = Format.parseNumber(_amount.text);
    final kcal = food == null || amount == null ? null : food.kcalFor(amount);
    return AlertDialog(
      title: Text(l10n.tourAddFood),
      content: SizedBox(
        width: AppSpacing.maxContentWidth,
        height: 400,
        child: food == null
            ? Column(
                children: [
                  TextField(
                    autofocus: true,
                    decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.search),
                      hintText: l10n.foodSearchHint,
                    ),
                    onSubmitted: (text) => setState(() => _query = text.trim()),
                  ),
                  Expanded(
                    child: AsyncBody(
                      value: ref.watch(foodSearchProvider(_query)),
                      onRetry: () => ref.invalidate(foodSearchProvider(_query)),
                      builder: (loaded) => ListView(
                        children: [
                          for (final option in loaded.value)
                            ListTile(
                              title: Text(option.name),
                              subtitle: option.brand == null
                                  ? null
                                  : Text(option.brand!),
                              trailing: option.kcalPer100g == null
                                  ? null
                                  : Text(
                                      l10n.foodKcalValue(
                                        Format.number(option.kcalPer100g!),
                                      ),
                                    ),
                              onTap: () => setState(() {
                                _food = option;
                                _amount.text = Format.input(
                                  option.servingSizeG,
                                );
                              }),
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    food.name,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.m),
                  TextField(
                    controller: _amount,
                    autofocus: true,
                    decoration: InputDecoration(labelText: l10n.tourAmountG),
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: AppSpacing.m),
                  if (kcal != null)
                    Text(l10n.tourKcal(Format.number(kcal.round()))),
                ],
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(l10n.cancel),
        ),
        if (food != null)
          FilledButton(
            onPressed: amount == null || amount <= 0
                ? null
                : () => Navigator.pop(context, <String, dynamic>{
                    'food_item_id': food.id,
                    'name': food.name,
                    'amount_g': amount,
                    'kcal': kcal,
                    'carried': true,
                    'eaten': false,
                  }),
            child: Text(l10n.add),
          ),
      ],
    );
  }
}
