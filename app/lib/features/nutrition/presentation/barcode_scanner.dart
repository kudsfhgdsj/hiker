import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_zxing/flutter_zxing.dart';

import '../../../l10n/app_localizations.dart';
import '../data/food_models.dart';

/// Opens the camera scanner and returns the barcode, or null if the user left.
typedef ScanBarcode = Future<String?> Function(BuildContext context);

/// The scanner reads codes on the device with ZXing; no cloud service is involved.
/// There is no camera scanner in the browser.
final barcodeScannerProvider = Provider<ScanBarcode?>((ref) {
  if (kIsWeb) return null;
  return (context) => Navigator.of(context).push<String>(
    MaterialPageRoute(builder: (context) => const _ScannerScreen()),
  );
});

class _ScannerScreen extends StatefulWidget {
  const _ScannerScreen();

  @override
  State<_ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends State<_ScannerScreen> {
  bool _done = false;

  void _onScan(Code code) {
    final text = code.text?.trim() ?? '';
    if (_done || !code.isValid || !isValidBarcode(text)) return;
    _done = true;
    Navigator.of(context).pop(text);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.foodScan)),
      body: Stack(
        alignment: Alignment.bottomCenter,
        children: [
          ReaderWidget(
            onScan: _onScan,
            codeFormat: Format.ean13 | Format.ean8 | Format.upca | Format.upce,
            showGallery: false,
            showToggleCamera: false,
            tryHarder: true,
          ),
          Padding(
            padding: const EdgeInsets.all(24),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                child: Text(
                  l10n.foodScannerHint,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
