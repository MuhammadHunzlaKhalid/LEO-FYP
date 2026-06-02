import 'package:flutter/widgets.dart';

/// On mobile/desktop — can't open browser tab directly.
/// Just shows a message; user copies URL from the dialog.
void openInBrowser(String url) {
  // no-op on mobile — the dialog shows a selectable URL instead
}

/// On mobile there's no HtmlElementView — return a placeholder.
Widget buildVideoPlayer(String streamUrl, String viewType) {
  return Container(
    color: const Color(0xFF000000),
    child: const Center(
      child: Text(
        'Copy the URL below and open\nit in your phone browser to play.',
        textAlign: TextAlign.center,
        style: TextStyle(color: Color(0xFFFFFFFF70), fontSize: 13),
      ),
    ),
  );
}
