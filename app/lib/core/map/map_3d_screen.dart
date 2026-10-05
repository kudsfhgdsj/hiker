import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../l10n/app_localizations.dart';

/// Builds the view that shows the 3D page; tests replace it, because a
/// WebView needs the platform.
final map3dViewBuilderProvider = Provider<Widget Function(Uri page)>(
  (ref) =>
      (page) => _Map3DWebView(page: page),
);

/// The map in 3D, to look at: the terrain is lifted by the elevation data.
///
/// The map library of the app cannot do that yet, so this screen shows the
/// library of the web frontend in a WebView. Page, style, tiles and elevation
/// all come from the map server inside the app (see TileProxy, `/3d/`).
class Map3DScreen extends ConsumerWidget {
  const Map3DScreen({super.key, required this.page});

  /// Address of the page on the app's own map server.
  final Uri page;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(l10n.map3dTitle)),
      body: Column(
        children: [
          Expanded(child: ref.watch(map3dViewBuilderProvider)(page)),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              l10n.map3dHint,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }
}

class _Map3DWebView extends StatefulWidget {
  const _Map3DWebView({required this.page});

  final Uri page;

  @override
  State<_Map3DWebView> createState() => _Map3DWebViewState();
}

class _Map3DWebViewState extends State<_Map3DWebView> {
  late final WebViewController _controller = WebViewController()
    ..setJavaScriptMode(JavaScriptMode.unrestricted)
    ..setBackgroundColor(const Color(0xFFE4E9E6))
    ..setNavigationDelegate(
      NavigationDelegate(
        // Only the app's own pages: links of the map (attribution) stay shut.
        onNavigationRequest: (request) =>
            Uri.tryParse(request.url)?.host == widget.page.host
            ? NavigationDecision.navigate
            : NavigationDecision.prevent,
      ),
    )
    ..loadRequest(widget.page);

  @override
  Widget build(BuildContext context) => WebViewWidget(controller: _controller);
}
