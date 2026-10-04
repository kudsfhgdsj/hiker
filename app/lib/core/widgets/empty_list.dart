import 'package:flutter/material.dart';

/// The text of a list without entries. It can still be pulled down to ask the
/// server again, like the list itself.
class EmptyList extends StatelessWidget {
  const EmptyList({super.key, required this.text, required this.onRefresh});

  final String text;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: onRefresh,
    child: LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: SizedBox(
          height: constraints.maxHeight,
          child: Center(child: Text(text)),
        ),
      ),
    ),
  );
}
