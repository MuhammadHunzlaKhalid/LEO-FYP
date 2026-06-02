import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

// ─────────────────────────────────────────────────────────────
//  AUTO-DETECT BACKEND URL
//  Web (Chrome/Edge)    → localhost:8000   (same PC as backend)
//  Android Emulator     → 10.0.2.2:8000   (emulator loopback)
//  Real Android device  → 192.168.18.88   (PC WiFi IP)
//  iOS Simulator        → localhost:8000
// ─────────────────────────────────────────────────────────────
String get _BASE {
  if (kIsWeb) {
    // Flutter Web running in browser on the same PC as the backend
    return 'http://localhost:8000';
  }

  // ── Native app (Android / iOS) ────────────────────────────
  // To run on Android EMULATOR:
  //   flutter run --dart-define=IS_EMULATOR=true
  // To run on REAL PHONE:
  //   flutter run                    (uses WiFi IP below)
  const bool isEmulator = bool.fromEnvironment(
    'IS_EMULATOR',
    defaultValue: false,
  );

  if (isEmulator) {
    // Android emulator maps 10.0.2.2 → host machine's localhost
    return 'http://10.0.2.2:8000';
  }

  // Real physical phone — must be on same WiFi as your PC
  // Your PC's WiFi IP (from ipconfig → IPv4): 192.168.18.88
  return 'http://192.168.18.88:8000';
}

class ApiService {
  /// Shows which URL is being used — useful for debugging
  static String get activeBaseUrl => _BASE;

  // ── Internal helpers ──────────────────────────────────────
  static Future<Map<String, dynamic>?> _get(String path) async {
    try {
      final r = await http
          .get(Uri.parse('$_BASE$path'))
          .timeout(const Duration(seconds: 8));
      if (r.statusCode == 200) return jsonDecode(r.body);
      return null;
    } catch (_) {
      return null;
    }
  }

  static Future<Map<String, dynamic>?> _post(
    String path,
    Map body, {
    int timeoutSec = 30,
  }) async {
    try {
      final r = await http
          .post(
            Uri.parse('$_BASE$path'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(Duration(seconds: timeoutSec));

      if (r.statusCode >= 200 && r.statusCode < 300) {
        return jsonDecode(r.body);
      }
      try {
        final err = jsonDecode(r.body);
        return {
          'reply': err['detail'] ?? 'Server error ${r.statusCode}',
          'error': true,
        };
      } catch (_) {
        return {'reply': 'Server error ${r.statusCode}', 'error': true};
      }
    } on Exception catch (e) {
      return {
        'reply': 'Cannot reach server: ${e.toString().split(':').first}',
        'error': true,
      };
    }
  }

  static Future<Map<String, dynamic>?> _put(String path, Map body) async {
    try {
      final r = await http
          .put(
            Uri.parse('$_BASE$path'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 8));
      if (r.statusCode == 200) return jsonDecode(r.body);
      return null;
    } catch (_) {
      return null;
    }
  }

  // ── Health ────────────────────────────────────────────────
  static Future<Map<String, dynamic>?> getHealth() => _get('/health');

  static Future<bool> isLeoReady() async {
    final h = await getHealth();
    return h?['leo_ready'] == true;
  }

  // ── Patients list ─────────────────────────────────────────
  static Future<List<Map<String, dynamic>>> getPatients() async {
    final r = await _get('/patients');
    final list = r?['patients'];
    return list is List ? list.cast<Map<String, dynamic>>() : [];
  }

  // ── Auth ──────────────────────────────────────────────────
  static Future<Map<String, dynamic>?> login(String username) =>
      _get('/user/${username.toLowerCase().trim()}/profile');

  static Future<bool> register({
    required String username,
    required String name,
    required String phone,
  }) async {
    final r = await _put('/user/${username.toLowerCase().trim()}/profile', {
      'personal': {'name': name, 'phone': phone},
      'emergency_contacts': [],
      'contacts': [],
      'medications': [],
      'routine': {'wake': '07:00', 'sleep': '22:00'},
      'active_zones': ['Living Room', 'Bedroom', 'Kitchen'],
    });
    return r != null;
  }

  // ── Profile & Summary ─────────────────────────────────────
  static Future<Map<String, dynamic>?> getProfile(String u) async {
    final r = await _get('/user/${u.toLowerCase()}/profile');
    return r?['profile'] as Map<String, dynamic>?;
  }

  static Future<Map<String, dynamic>?> getSummary(String u) =>
      _get('/user/${u.toLowerCase()}/summary');

  // ── Logs, Falls, Sessions ─────────────────────────────────
  static Future<List<Map<String, dynamic>>> getLogs(String u) async {
    final r = await _get('/user/${u.toLowerCase()}/logs?limit=100');
    final list = r?['logs'];
    return list is List ? list.cast() : [];
  }

  static Future<List<Map<String, dynamic>>> getFalls(String u) async {
    final r = await _get('/user/${u.toLowerCase()}/falls?limit=30');
    final list = r?['falls'];
    return list is List ? list.cast() : [];
  }

  static Future<List<Map<String, dynamic>>> getSessions(String u) async {
    final r = await _get('/user/${u.toLowerCase()}/sessions?limit=10');
    final list = r?['sessions'];
    return list is List ? list.cast() : [];
  }

  // ── Video URLs ────────────────────────────────────────────
  static String videoStreamUrl(String path) =>
      '$_BASE/video/stream?path=${Uri.encodeComponent(path)}';

  static String videoThumbnailUrl(String path) =>
      '$_BASE/video/thumbnail?path=${Uri.encodeComponent(path)}';

  static Future<List<Map<String, dynamic>>> getVideos(String u) async {
    final r = await _get('/user/${u.toLowerCase()}/videos');
    final list = r?['videos'];
    return list is List ? list.cast() : [];
  }

  // ── Live video URLs ──────────────────────────────────────────
  /// MJPEG stream URL — open in browser or HTML <img> tag
  static String get liveStreamUrl => '$_BASE/video/live-stream';

  /// Single JPEG frame URL — poll every ~150ms for Flutter image widget
  static String liveFrameUrl(int t) => '$_BASE/video/live-frame?t=$t';

  // ── Vision ────────────────────────────────────────────────
  static Future<Map<String, dynamic>?> getVisionStatus() =>
      _get('/vision/status');

  /// Get safe zones for specific patient (patient-specific file first)
  static Future<List<Map<String, dynamic>>> getUserZones(
      String username) async {
    final r = await _get('/user/${username.toLowerCase()}/zones');
    final list = r?['zones'];
    return list is List ? list.cast<Map<String, dynamic>>() : [];
  }

  /// Get global safe zones
  static Future<List<Map<String, dynamic>>> getZones() async {
    final r = await _get('/vision/zones');
    final list = r?['zones'];
    return list is List ? list.cast<Map<String, dynamic>>() : [];
  }

  // ── Emergency ─────────────────────────────────────────────
  static Future<bool> triggerEmergency({
    required String username,
    required String reason,
  }) async {
    final r = await _post('/emergency/alert', {
      'username': username,
      'reason': reason,
      'level': 'fall',
    });
    return r != null;
  }

  // ── Chat with LEO (60s timeout — brain may take time) ─────
  static Future<String?> chat({
    required String username,
    required String message,
  }) async {
    final r = await _post(
      '/chat',
      {'username': username, 'message': message},
      timeoutSec: 60,
    );
    return r?['reply'] as String?;
  }

  // ── Update profile fields (contacts, medications etc.) ────
  static Future<bool> updateProfileContacts(
      String username, Map<String, dynamic> patch) async {
    final r = await _put('/user/${username.toLowerCase()}/profile', patch);
    return r != null;
  }
}
