// ignore_for_file: avoid_web_libraries_in_flutter
import 'dart:html' as html;
import 'dart:ui_web' as ui_web;
import 'package:flutter/widgets.dart';

/// Open URL in a new browser tab (web only)
void openInBrowser(String url) {
  html.window.open(url, '_blank');
}

/// Register + return an embedded HTML <video> player widget
Widget buildVideoPlayer(String streamUrl, String viewType) {
  try {
    ui_web.platformViewRegistry.registerViewFactory(viewType, (int id) {
      return html.VideoElement()
        ..src             = streamUrl
        ..controls        = true
        ..autoplay        = true
        ..style.width     = '100%'
        ..style.height    = '100%'
        ..style.objectFit = 'contain'
        ..style.background = 'black';
    });
    return HtmlElementView(viewType: viewType);
  } catch (_) {
    return _fallback();
  }
}

Widget _fallback() => const Center(
  child: Text('Tap "Open in Browser Tab" to play',
      style: TextStyle(color: Color(0xFFFFFFFF), fontSize: 13)),
);
