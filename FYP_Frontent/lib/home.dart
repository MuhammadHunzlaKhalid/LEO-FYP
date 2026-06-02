import 'dart:async';
import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';
import 'leo_fab.dart';

class HomeSecurityPage extends StatefulWidget {
  const HomeSecurityPage({super.key});
  @override
  State<HomeSecurityPage> createState() => _HomeSecurityPageState();
}

class _HomeSecurityPageState extends State<HomeSecurityPage>
    with TickerProviderStateMixin {

  // ── Live vision state ─────────────────────────────────────
  bool   _fallDetected   = false;
  String _visionState    = 'UNKNOWN';
  String _posture        = '—';
  String _lastUpdated    = '—';
  bool   _brainOnline    = false; // true if monitoring brain is running
  bool   _statusLoading  = true;

  // ── MongoDB summary ───────────────────────────────────────
  int    _fallsToday     = 0;
  int    _totalFalls     = 0;
  int    _totalSessions  = 0;
  String _lastActivity   = '—';

  // ── Recent videos ─────────────────────────────────────────
  List<Map<String, dynamic>> _recentVideos = [];
  bool _videosLoading = true;

  // ── Patient profile ───────────────────────────────────────
  String _patientName    = '';
  String _condition      = '';

  int _selectedIndex = 0;
  late AnimationController _pulseCtrl;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(vsync: this,
        duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 6), (_) => _refresh());
  }

  @override
  void dispose() { _pulseCtrl.dispose(); _timer?.cancel(); super.dispose(); }

  Future<void> _refresh() async {
    final results = await Future.wait([
      ApiService.getVisionStatus(),
      ApiService.getSummary(Session.username),
      ApiService.getVideos(Session.username),
      ApiService.getProfile(Session.username),
    ]);

    if (!mounted) return;
    final vision   = results[0] as Map<String, dynamic>?;
    final summary  = results[1] as Map<String, dynamic>?;
    final videos   = results[2] as List<Map<String, dynamic>>;
    final profile  = results[3] as Map<String, dynamic>?;

    setState(() {
      _statusLoading = false;
      _videosLoading = false;

      // Vision
      if (vision != null) {
        _fallDetected  = vision['fall_detected'] == true;
        _visionState   = vision['state'] as String? ?? 'UNKNOWN';
        _posture       = vision['posture'] as String? ?? '—';
        final ts       = vision['timestamp'] as String?;
        _lastUpdated   = _ago(ts);
        // If updated within last 30 seconds → brain is online
        _brainOnline   = ts != null && _secondsAgo(ts) < 30;
      }

      // Summary
      if (summary != null) {
        _fallsToday   = (summary['falls_today']    as num?)?.toInt() ?? 0;
        _totalFalls   = (summary['total_falls']    as num?)?.toInt() ?? 0;
        _totalSessions= (summary['total_sessions'] as num?)?.toInt() ?? 0;
        final la = summary['last_activity'] as String?;
        _lastActivity = la != null && la.length > 15
            ? la.substring(11, 16) : la ?? '—';
      }

      // Videos (most recent 3)
      _recentVideos = videos.take(3).toList();

      // Profile
      if (profile != null) {
        final p = profile['personal'] as Map<String, dynamic>? ?? {};
        _patientName = p['name'] as String? ?? Session.displayName;
        _condition   = p['condition'] as String? ?? '';
      }
    });
  }

  int _secondsAgo(String iso) {
    try {
      return DateTime.now().difference(DateTime.parse(iso)).inSeconds;
    } catch (_) { return 9999; }
  }

  String _ago(String? iso) {
    if (iso == null) return '—';
    try {
      final d = DateTime.now().difference(DateTime.parse(iso));
      if (d.inSeconds < 60)  return '${d.inSeconds}s ago';
      if (d.inMinutes < 60)  return '${d.inMinutes}m ago';
      return '${d.inHours}h ago';
    } catch (_) { return iso; }
  }

  void _onNav(int i) {
    setState(() => _selectedIndex = i);
    if (i == 1) Navigator.pushNamed(context, 'alerts');
    if (i == 2) { Session.clear(); Navigator.pushReplacementNamed(context, 'login'); }
    if (i == 3) Navigator.pushNamed(context, 'contact');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: const LeoFab(),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [Color(0xFFE2C7E9), Color(0xFF783E9E), Color(0xFF110031)],
          ),
        ),
        child: SafeArea(child: RefreshIndicator(
          onRefresh: _refresh,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              // ── Top bar ──────────────────────────────────
              _topBar(),
              const SizedBox(height: 12),

              // ── Monitoring brain status ───────────────────
              _brainStatusBar(),
              const SizedBox(height: 12),

              // ── Live fall status banner ───────────────────
              _statusBanner(),
              const SizedBox(height: 14),

              // ── 4 stats cards ─────────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(children: [
                  _statCard('Falls\nToday', '$_fallsToday',
                      _fallsToday > 0 ? Colors.red : Colors.green),
                  const SizedBox(width: 8),
                  _statCard('Total\nFalls', '$_totalFalls', Colors.orange),
                  const SizedBox(width: 8),
                  _statCard('Sessions', '$_totalSessions', Colors.blue),
                  const SizedBox(width: 8),
                  _statCard('Last\nActive', _lastActivity, Colors.purple),
                ]),
              ),
              const SizedBox(height: 18),

              // ── Patient Information button ────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    onPressed: () => Navigator.pushNamed(context, 'info'),
                    child: Row(mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                      const Icon(Icons.person, size: 18),
                      const SizedBox(width: 8),
                      Text('Patient Information'
                          '${_patientName.isNotEmpty ? " — $_patientName" : ""}',
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                    ]),
                  ),
                ),
              ),
              const SizedBox(height: 14),

              // ── Quick action cards ────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(children: [
                  Expanded(child: GestureDetector(
                    onTap: () => Navigator.pushNamed(context, 'detection'),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _brainOnline
                            ? Colors.blue.shade900 : Colors.white,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Column(children: [
                        Icon(Icons.monitor_heart,
                            color: _brainOnline ? Colors.white : Colors.black),
                        const SizedBox(height: 8),
                        Text('Live Detection',
                            style: TextStyle(
                                color: _brainOnline
                                    ? Colors.white : Colors.black,
                                fontWeight: FontWeight.w600,
                                fontSize: 13)),
                        const SizedBox(height: 4),
                        Text(_brainOnline ? '● Active' : '○ Offline',
                            style: TextStyle(
                                color: _brainOnline
                                    ? Colors.greenAccent : Colors.grey,
                                fontSize: 11)),
                      ]),
                    ),
                  )),
                  const SizedBox(width: 14),
                  Expanded(child: GestureDetector(
                    onTap: () => Navigator.pushNamed(context, 'alerts'),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: const [BoxShadow(
                            color: Colors.black26, blurRadius: 6,
                            offset: Offset(0, 3))],
                      ),
                      child: Column(children: [
                        Badge(
                          label: Text('$_fallsToday',
                              style: const TextStyle(fontSize: 10)),
                          isLabelVisible: _fallsToday > 0,
                          child: const Icon(Icons.analytics,
                              color: Colors.black),
                        ),
                        const SizedBox(height: 8),
                        const Text('Alerts & Reports',
                            style: TextStyle(fontWeight: FontWeight.w600,
                                fontSize: 13)),
                        const SizedBox(height: 4),
                        Text('$_fallsToday alert${_fallsToday == 1 ? "" : "s"} today',
                            style: TextStyle(
                                color: _fallsToday > 0
                                    ? Colors.red : Colors.grey,
                                fontSize: 11)),
                      ]),
                    ),
                  )),
                ]),
              ),
              const SizedBox(height: 20),

              // ── Saved Videos section ──────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(children: [
                  const Text('Saved Videos',
                      style: TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 16)),
                  const Spacer(),
                  GestureDetector(
                    onTap: () => Navigator.pushNamed(context, 'videos'),
                    child: const Text('See All →',
                        style: TextStyle(
                            color: Colors.purpleAccent, fontSize: 13)),
                  ),
                ]),
              ),
              const SizedBox(height: 10),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: _videosSection(),
              ),

              // ── Start monitoring hint ─────────────────────
              if (!_brainOnline) ...[
                const SizedBox(height: 14),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.orange.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color: Colors.orange.withOpacity(0.4)),
                    ),
                    child: Row(children: const [
                      Icon(Icons.play_circle_outline,
                          color: Colors.orange, size: 20),
                      SizedBox(width: 10),
                      Expanded(child: Text(
                        'To start monitoring, run:\n'
                        'python final_monitering_brain.py',
                        style: TextStyle(
                            color: Colors.orange, fontSize: 12),
                      )),
                    ]),
                  ),
                ),
              ],

              const SizedBox(height: 80),
            ]),
          ),
        )),
      ),
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _selectedIndex,
        onTap: _onNav,
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined),
              activeIcon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(
              icon: Icon(Icons.notifications_active_outlined),
              label: 'Alerts'),
          BottomNavigationBarItem(
              icon: Icon(Icons.logout), label: 'Logout'),
          BottomNavigationBarItem(
              icon: Icon(Icons.contact_phone_outlined),
              activeIcon: Icon(Icons.contact_phone), label: 'Contact'),
        ],
      ),
    );
  }

  // ── Top bar ───────────────────────────────────────────────
  Widget _topBar() => Padding(
    padding: const EdgeInsets.fromLTRB(8, 10, 16, 0),
    child: Row(children: [
      IconButton(
        icon: const Icon(Icons.arrow_back, color: Colors.white),
        onPressed: () {
          Session.clear();
          Navigator.pushReplacementNamed(context, 'login');
        }),
      const Spacer(),
      Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Text('Hi, ${_patientName.isNotEmpty ? _patientName : Session.displayName}',
            style: const TextStyle(color: Colors.white,
                fontWeight: FontWeight.bold, fontSize: 14)),
        const Text('LEO is watching',
            style: TextStyle(color: Colors.white60, fontSize: 11)),
      ]),
      const SizedBox(width: 10),
      const CircleAvatar(radius: 18,
          backgroundColor: Color(0xff4c505b),
          child: Icon(Icons.person, color: Colors.white, size: 18)),
    ]),
  );

  // ── Monitoring brain status bar ───────────────────────────
  Widget _brainStatusBar() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: _brainOnline
            ? Colors.green.withOpacity(0.15)
            : Colors.orange.withOpacity(0.15),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _brainOnline
            ? Colors.green.withOpacity(0.4)
            : Colors.orange.withOpacity(0.4)),
      ),
      child: Row(children: [
        AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) => Container(
            width: 8, height: 8,
            decoration: BoxDecoration(
              color: _brainOnline
                  ? Colors.green.withOpacity(0.5 + _pulseCtrl.value * 0.5)
                  : Colors.orange,
              shape: BoxShape.circle,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(child: Text(
          _brainOnline
              ? 'Monitoring Brain Online  ·  Camera Active  ·  $_lastUpdated'
              : 'Monitoring Brain Offline  ·  Run: python final_monitering_brain.py',
          style: TextStyle(
              color: _brainOnline ? Colors.greenAccent : Colors.orange,
              fontSize: 11, fontWeight: FontWeight.w600),
        )),
        Icon(Icons.circle,
            color: _brainOnline ? Colors.green : Colors.orange,
            size: 8),
      ]),
    ),
  );

  // ── Fall status banner ────────────────────────────────────
  Widget _statusBanner() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16),
    child: GestureDetector(
      onTap: () => Navigator.pushNamed(context, 'detection'),
      child: AnimatedBuilder(
        animation: _pulseCtrl,
        builder: (_, child) => Transform.scale(
          scale: _fallDetected ? 1.0 + _pulseCtrl.value * 0.015 : 1.0,
          child: child,
        ),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _statusLoading
                ? Colors.grey.shade700
                : _fallDetected
                    ? Colors.red.shade700
                    : const Color(0xFF1B5E20),
            borderRadius: BorderRadius.circular(12),
            boxShadow: [BoxShadow(
              color: (_fallDetected ? Colors.red : Colors.green)
                  .withOpacity(0.35),
              blurRadius: 14,
            )],
          ),
          child: _statusLoading
              ? const Center(child: SizedBox(
                  width: 20, height: 20,
                  child: CircularProgressIndicator(
                      color: Colors.white, strokeWidth: 2)))
              : Row(children: [
                  Icon(
                    _fallDetected
                        ? Icons.warning_amber_rounded
                        : Icons.check_circle,
                    color: Colors.white, size: 22),
                  const SizedBox(width: 10),
                  Expanded(child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(
                      _fallDetected ? 'EMERGENCY DETECTED'
                          : 'ALL CLEAR — $_visionState',
                      style: const TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 15)),
                    Text(
                      _fallDetected
                          ? 'IMMEDIATE ATTENTION REQUIRED'
                          : 'Posture: $_posture  ·  $_lastUpdated',
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 11)),
                  ])),
                  const Icon(Icons.chevron_right,
                      color: Colors.white54, size: 20),
                ]),
        ),
      ),
    ),
  );

  // ── Videos section ────────────────────────────────────────
  Widget _videosSection() {
    if (_videosLoading) {
      return Container(
        height: 80,
        decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.08),
            borderRadius: BorderRadius.circular(12)),
        child: const Center(child: CircularProgressIndicator(
            color: Colors.white54, strokeWidth: 2)),
      );
    }

    if (_recentVideos.isEmpty) {
      return GestureDetector(
        onTap: () => Navigator.pushNamed(context, 'videos'),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.08),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white12),
          ),
          child: Column(children: [
            const Icon(Icons.video_library_outlined,
                color: Colors.white38, size: 32),
            const SizedBox(height: 8),
            const Text('No recordings yet',
                style: TextStyle(color: Colors.white54, fontSize: 13)),
            const SizedBox(height: 4),
            Text(
              _brainOnline
                  ? 'Brain is online — videos appear after falls are recorded'
                  : 'Start python final_monitering_brain.py to record',
              style: const TextStyle(color: Colors.white38, fontSize: 10),
              textAlign: TextAlign.center,
            ),
          ]),
        ),
      );
    }

    return Row(children: _recentVideos.asMap().entries.map((e) {
      final v      = e.value;
      final isFall = v['type'] == 'fall';
      final date   = v['date'] as String? ?? '';
      final name   = v['filename'] as String? ?? '';

      return Expanded(child: Padding(
        padding: EdgeInsets.only(left: e.key == 0 ? 0 : 8),
        child: GestureDetector(
          onTap: () => Navigator.pushNamed(context, 'videos'),
          child: Container(
            height: 90,
            decoration: BoxDecoration(
              color: isFall
                  ? Colors.red.withOpacity(0.2)
                  : Colors.blue.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: isFall
                  ? Colors.red.withOpacity(0.5)
                  : Colors.blue.withOpacity(0.3)),
            ),
            child: Column(
                mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(isFall ? Icons.warning : Icons.play_circle,
                  color: isFall ? Colors.red : Colors.blue, size: 26),
              const SizedBox(height: 4),
              Text(date, style: const TextStyle(
                  color: Colors.white70, fontSize: 9),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 2),
              Text(isFall ? 'Fall Clip' : 'Recording',
                  style: TextStyle(
                      color: isFall ? Colors.red : Colors.blue,
                      fontSize: 9, fontWeight: FontWeight.bold)),
            ]),
          ),
        ),
      ));
    }).toList());
  }

  // ── Stat card ─────────────────────────────────────────────
  Widget _statCard(String label, String value, Color color) =>
      Expanded(child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.12),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.4)),
        ),
        child: Column(children: [
          Text(value, style: TextStyle(color: color,
              fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 3),
          Text(label, style: const TextStyle(
              color: Colors.white60, fontSize: 9),
              textAlign: TextAlign.center),
        ]),
      ));
}
