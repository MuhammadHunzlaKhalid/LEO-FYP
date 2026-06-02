import 'package:flutter/material.dart';

/// Drop this widget into any Scaffold's floatingActionButton
/// or use LeoFab.wrap() to add it as an overlay.
class LeoFab extends StatelessWidget {
  const LeoFab({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton.extended(
      backgroundColor: Colors.transparent,
      elevation: 0,
      onPressed: () => Navigator.pushNamed(context, 'leo_chat'),
      label: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
              colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
          borderRadius: BorderRadius.circular(30),
          boxShadow: [BoxShadow(
              color: Colors.purple.withOpacity(0.5), blurRadius: 12)],
        ),
        child: const Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.smart_toy, color: Colors.white, size: 18),
          SizedBox(width: 6),
          Text('Ask LEO', style: TextStyle(
              color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
        ]),
      ),
    );
  }
}
