import 'package:flutter/material.dart';
import 'login.dart';
import 'register.dart';
import 'home.dart';
import 'detection.dart';
import 'alerts.dart';
import 'contact.dart';
import 'info.dart';
import 'leo_chat.dart';
import 'videos.dart';

void main() {
  runApp(MaterialApp(
    debugShowCheckedModeBanner: false,
    initialRoute: 'login',
    routes: {
      'login': _w(MyLogin()),
      'register': _w(MyRegister()),
      'home': _w(HomeSecurityPage()),
      'detection': _w(DetectionPage()),
      'alerts': _w(AlertsPage()),
      'contact': _w(MyContactsPage()),
      'info': _w(PatientInformationPage()),
      'leo_chat': _w(LeoChatPage()),
      'videos': _w(VideosPage()),
    },
  ));
}

WidgetBuilder _w(Widget w) => (_) => w;
