import 'dart:async';
import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';
import 'leo_fab.dart';

class DetectionPage extends StatefulWidget {
  const DetectionPage({Key? key}) : super(key: key);
  @override
  State<DetectionPage> createState() => _DetectionPageState();
}

class _DetectionPageState extends State<DetectionPage>
    with TickerProviderStateMixin {

  // ── Vision state ──────────────────────────────────────────
  bool   _fallDetected = false;
  String _state        = 'UNKNOWN';
  String _posture      = '—';
  double _confidence   = 0.0;
  String _timestamp    = '—';
  bool   _onSafeZone   = false;
  bool   _statusLoading = true;

  // ── Safe zones ────────────────────────────────────────────
  List<Map<String, dynamic>> _zones      = [];
  bool _zonesLoading = true;

  // ── Patient data ──────────────────────────────────────────
  Map<String, dynamic>? _profile;
  Map<String, dynamic>? _summary;

  // ── Recent falls & videos ─────────────────────────────────
  List<Map<String, dynamic>> _recentFalls  = [];
  List<Map<String, dynamic>> _recentVideos = [];

  // ── Live video frame counter ──────────────────────────────
  int  _frameCounter = 0;
  bool _liveActive   = false;   // true = monitoring brain is running
  Timer? _statusTimer;
  Timer? _frameTimer;

  // Pulse animation for FALL state
  late AnimationController _pulseCtrl;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(vsync: this,
        duration: const Duration(milliseconds: 700))
      ..repeat(reverse: true);
    _loadAll();
    _statusTimer = Timer.periodic(const Duration(seconds: 5), (_) => _fetchVision());
    _frameTimer  = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (mounted) setState(() => _frameCounter++);
    });
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _statusTimer?.cancel();
    _frameTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadAll() async {
    await Future.wait([
      _fetchVision(),
      _fetchProfile(),
      _fetchZones(),
      _fetchFalls(),
      _fetchVideos(),
    ]);
  }

  Future<void> _fetchVision() async {
    final v = await ApiService.getVisionStatus();
    if (!mounted) return;
    setState(() {
      _statusLoading = false;
      if (v != null) {
        _fallDetected = v['fall_detected'] == true;
        _state        = v['state']        as String? ?? 'UNKNOWN';
        _posture      = v['posture']      as String? ?? '—';
        _confidence   = (v['confidence']  as num?)?.toDouble() ?? 0.0;
        _timestamp    = v['timestamp']    as String? ?? '—';
        _onSafeZone   = v['on_safe_zone'] == true;
        // Consider brain online if updated within last 20 seconds
        _liveActive   = _secondsAgo(v['timestamp'] as String?) < 20;
      }
    });
  }

  Future<void> _fetchProfile() async {
    final p = await ApiService.getProfile(Session.username);
    final s = await ApiService.getSummary(Session.username);
    if (!mounted) return;
    setState(() { _profile = p; _summary = s; });
  }

  Future<void> _fetchZones() async {
    final z = await ApiService.getUserZones(Session.username);
    if (!mounted) return;
    setState(() { _zones = z; _zonesLoading = false; });
  }

  Future<void> _fetchFalls() async {
    final f = await ApiService.getFalls(Session.username);
    if (!mounted) return;
    setState(() => _recentFalls = f.take(5).toList());
  }

  Future<void> _fetchVideos() async {
    final v = await ApiService.getVideos(Session.username);
    if (!mounted) return;
    setState(() => _recentVideos = v.take(3).toList());
  }

  int _secondsAgo(String? iso) {
    if (iso == null) return 9999;
    try { return DateTime.now().difference(DateTime.parse(iso)).inSeconds; }
    catch (_) { return 9999; }
  }

  String _ago(String? iso) {
    final s = _secondsAgo(iso);
    if (s < 60)   return '${s}s ago';
    if (s < 3600) return '${s ~/ 60}m ago';
    return '${s ~/ 3600}h ago';
  }

  Future<void> _triggerEmergency() async {
    final ok = await ApiService.triggerEmergency(
        username: Session.username,
        reason: 'Fall detected — manual trigger from detection page');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '🚨 Emergency alert sent!' : '❌ Failed'),
        backgroundColor: ok ? Colors.green : Colors.red));
  }

  // ── COLORS matching leo_app.py ────────────────────────────
  static const Color _cBg      = Color(0xFF090b12);
  static const Color _cPanel   = Color(0xFF0f1120);
  static const Color _cCard    = Color(0xFF151827);
  static const Color _cAccent  = Color(0xFF00c8ff);
  static const Color _cGreen   = Color(0xFF00e676);
  static const Color _cRed     = Color(0xFFff3d3d);
  static const Color _cOrange  = Color(0xFFff9800);
  static const Color _cPurple  = Color(0xFF7c3aed);
  static const Color _cDim     = Color(0xFF566080);
  static const Color _cText    = Color(0xFFdde1f5);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _cBg,
      floatingActionButton: const LeoFab(),
      body: SafeArea(child: Column(children: [
        // ── Top bar ─────────────────────────────────────────
        _topBar(),
        Expanded(child: RefreshIndicator(
          onRefresh: _loadAll,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(children: [
              // ── Patient card ───────────────────────────────
              _patientCard(),

              // ── LIVE VIDEO FEED ────────────────────────────
              _liveVideoSection(),

              // ── Status card ────────────────────────────────
              _statusCard(),

              // ── Safe zones ─────────────────────────────────
              _safeZonesSection(),

              // ── Emergency buttons ──────────────────────────
              _emergencyButtons(),

              // ── Recent falls from MongoDB ──────────────────
              _recentFallsSection(),

              // ── Recent saved videos ────────────────────────
              _recentVideosSection(),

              const SizedBox(height: 80),
            ]),
          ),
        )),
      ])),
    );
  }

  // ── TOP BAR ───────────────────────────────────────────────
  Widget _topBar() => Container(
    color: _cPanel,
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
    child: Row(children: [
      IconButton(
          icon: const Icon(Icons.arrow_back, color: _cAccent),
          onPressed: () => Navigator.pop(context)),
      const Text('Live Detection',
          style: TextStyle(color: _cAccent, fontSize: 16,
              fontWeight: FontWeight.bold,
              fontFamily: 'monospace')),
      const Spacer(),
      // Brain status indicator
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
            color: _liveActive
                ? _cGreen.withOpacity(0.15) : _cOrange.withOpacity(0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
                color: _liveActive ? _cGreen : _cOrange, width: 1)),
        child: Row(children: [
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, __) => Container(width: 7, height: 7,
                decoration: BoxDecoration(
                    color: _liveActive
                        ? _cGreen.withOpacity(0.5 + _pulseCtrl.value * 0.5)
                        : _cOrange,
                    shape: BoxShape.circle)),
          ),
          const SizedBox(width: 5),
          Text(_liveActive ? 'LIVE' : 'OFFLINE',
              style: TextStyle(
                  color: _liveActive ? _cGreen : _cOrange,
                  fontSize: 10, fontWeight: FontWeight.bold,
                  fontFamily: 'monospace')),
        ]),
      ),
      const SizedBox(width: 8),
      IconButton(
          icon: const Icon(Icons.refresh, color: _cDim),
          onPressed: _loadAll),
    ]),
  );

  // ── PATIENT CARD ──────────────────────────────────────────
  Widget _patientCard() {
    final personal  = _profile?['personal'] as Map<String, dynamic>? ?? {};
    final name      = personal['name'] as String? ?? Session.displayName;
    final age       = personal['age']?.toString() ?? '—';
    final condition = personal['condition'] as String? ?? '';
    final initials  = name.split(' ').where((w) => w.isNotEmpty).take(2)
        .map((w) => w[0].toUpperCase()).join();

    final fallsToday  = _summary?['falls_today']    ?? 0;
    final totalFalls  = _summary?['total_falls']     ?? 0;
    final sessions    = _summary?['total_sessions']  ?? 0;

    return Container(
      margin: const EdgeInsets.all(10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: _cCard, borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cAccent.withOpacity(0.3))),
      child: Column(children: [
        Row(children: [
          // Avatar
          Container(width: 52, height: 52,
              decoration: BoxDecoration(
                  gradient: const LinearGradient(
                      colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
                  shape: BoxShape.circle),
              child: Center(child: Text(initials, style: const TextStyle(
                  color: Colors.white, fontSize: 20,
                  fontWeight: FontWeight.bold)))),
          const SizedBox(width: 12),
          Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name, style: const TextStyle(color: _cAccent,
                fontSize: 16, fontWeight: FontWeight.bold,
                fontFamily: 'monospace')),
            Text('Age: $age${condition.isNotEmpty ? "  •  $condition" : ""}',
                style: const TextStyle(color: _cDim, fontSize: 11,
                    fontFamily: 'monospace')),
          ])),
          // Active indicator
          Column(children: [
            Container(width: 10, height: 10,
                decoration: const BoxDecoration(
                    color: _cGreen, shape: BoxShape.circle)),
            const SizedBox(height: 3),
            const Text('Active', style: TextStyle(
                color: _cGreen, fontSize: 9, fontFamily: 'monospace')),
          ]),
        ]),
        const SizedBox(height: 12),
        // Stats row
        Row(children: [
          _statBox('FALLS TODAY', '$fallsToday',
              (fallsToday as int) > 0 ? _cRed : _cGreen),
          _vDivider(),
          _statBox('TOTAL FALLS', '$totalFalls', _cOrange),
          _vDivider(),
          _statBox('SESSIONS', '$sessions', _cAccent),
        ]),
      ]),
    );
  }

  Widget _statBox(String label, String value, Color color) => Expanded(
    child: Column(children: [
      Text(value, style: TextStyle(color: color,
          fontSize: 22, fontWeight: FontWeight.bold,
          fontFamily: 'monospace')),
      Text(label, style: const TextStyle(color: _cDim,
          fontSize: 9, fontFamily: 'monospace'),
          textAlign: TextAlign.center),
    ]),
  );

  Widget _vDivider() => Container(
      width: 1, height: 36, color: _cDim.withOpacity(0.3));

  // ── LIVE VIDEO SECTION ────────────────────────────────────
  Widget _liveVideoSection() => Container(
    margin: const EdgeInsets.symmetric(horizontal: 10),
    decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
            color: _fallDetected ? _cRed : _cAccent.withOpacity(0.4),
            width: _fallDetected ? 2 : 1)),
    child: Column(children: [
      // Title bar
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
            color: _cPanel,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12))),
        child: Row(children: [
          Icon(Icons.videocam,
              color: _liveActive ? _cGreen : _cDim, size: 16),
          const SizedBox(width: 6),
          Text(_liveActive ? 'LIVE MONITORING FEED' : 'MONITORING OFFLINE',
              style: TextStyle(
                  color: _liveActive ? _cGreen : _cDim,
                  fontSize: 11, fontWeight: FontWeight.bold,
                  fontFamily: 'monospace')),
          const Spacer(),
          if (_fallDetected)
            AnimatedBuilder(
              animation: _pulseCtrl,
              builder: (_, __) => Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                    color: _cRed.withOpacity(0.2 + _pulseCtrl.value * 0.3),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: _cRed)),
                child: const Text('🚨 FALL',
                    style: TextStyle(color: _cRed,
                        fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ),
        ]),
      ),

      // Video frame
      _liveActive
          ? Image.network(
              ApiService.liveFrameUrl(_frameCounter),
              width: double.infinity,
              height: 240,
              fit: BoxFit.cover,
              gaplessPlayback: true,
              errorBuilder: (_, __, ___) => _videoPlaceholder(),
            )
          : _videoPlaceholder(),

      // State overlay at bottom
      Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        color: Colors.black87,
        child: Row(children: [
          Container(width: 8, height: 8,
              decoration: BoxDecoration(
                  color: _fallDetected ? _cRed : _cGreen,
                  shape: BoxShape.circle)),
          const SizedBox(width: 8),
          Text(_state.toUpperCase(),
              style: TextStyle(
                  color: _fallDetected ? _cRed : _cGreen,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'monospace', fontSize: 12)),
          const Spacer(),
          Text('Posture: $_posture',
              style: const TextStyle(color: _cDim,
                  fontSize: 11, fontFamily: 'monospace')),
        ]),
      ),
    ]),
  );

  Widget _videoPlaceholder() => Container(
    height: 240, color: const Color(0xFF050508),
    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.videocam_off, color: _cDim, size: 48),
      const SizedBox(height: 12),
      Text(_liveActive ? 'Loading frame...' : 'Camera Offline',
          style: const TextStyle(color: _cDim,
              fontFamily: 'monospace', fontSize: 13)),
      const SizedBox(height: 6),
      if (!_liveActive)
        const Text('Run: python final_monitering_brain.py',
            style: TextStyle(color: Color(0xFF3a4060),
                fontFamily: 'monospace', fontSize: 10)),
    ]),
  );

  // ── STATUS CARD ───────────────────────────────────────────
  Widget _statusCard() => Container(
    margin: const EdgeInsets.fromLTRB(10, 10, 10, 0),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
        color: _cCard, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _cDim.withOpacity(0.3))),
    child: _statusLoading
        ? const Center(child: CircularProgressIndicator(
            color: _cAccent, strokeWidth: 2))
        : Column(children: [
            // Confidence bar
            Row(children: [
              const Text('CONFIDENCE', style: TextStyle(
                  color: _cDim, fontSize: 10, fontFamily: 'monospace')),
              const Spacer(),
              Text('${(_confidence * 100).toStringAsFixed(1)}%',
                  style: TextStyle(
                      color: _confidence > 0.6 ? _cRed : _cGreen,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace')),
            ]),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _confidence,
                backgroundColor: const Color(0xFF1e2340),
                valueColor: AlwaysStoppedAnimation(
                    _confidence > 0.6 ? _cRed : _cGreen),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 12),
            // Info chips
            Row(children: [
              _infoChip('Posture', _posture.toUpperCase()),
              const SizedBox(width: 8),
              _infoChip('Safe Zone', _onSafeZone ? 'YES ✓' : 'NO',
                  color: _onSafeZone ? _cGreen : _cDim),
              const SizedBox(width: 8),
              _infoChip('Updated', _ago(_timestamp)),
            ]),
          ]),
  );

  Widget _infoChip(String label, String value, {Color? color}) =>
      Expanded(child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
            color: const Color(0xFF1a1e30),
            borderRadius: BorderRadius.circular(8)),
        child: Column(children: [
          Text(label, style: const TextStyle(
              color: _cDim, fontSize: 9, fontFamily: 'monospace')),
          const SizedBox(height: 3),
          Text(value, style: TextStyle(
              color: color ?? _cText,
              fontWeight: FontWeight.bold,
              fontFamily: 'monospace', fontSize: 11),
              maxLines: 1, overflow: TextOverflow.ellipsis),
        ]),
      ));

  // ── SAFE ZONES SECTION ────────────────────────────────────
  Widget _safeZonesSection() => Container(
    margin: const EdgeInsets.fromLTRB(10, 10, 10, 0),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
        color: _cCard, borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _cAccent.withOpacity(0.2))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Icon(Icons.location_on, color: _cAccent, size: 16),
        const SizedBox(width: 6),
        const Text('SAFE ZONES', style: TextStyle(
            color: _cAccent, fontWeight: FontWeight.bold,
            fontFamily: 'monospace', fontSize: 12)),
        const Spacer(),
        Text('${_zones.length} configured',
            style: TextStyle(
                color: _zones.isNotEmpty ? _cGreen : _cOrange,
                fontSize: 10, fontFamily: 'monospace')),
      ]),
      const SizedBox(height: 10),

      if (_zonesLoading)
        const Center(child: SizedBox(width: 16, height: 16,
            child: CircularProgressIndicator(
                color: _cAccent, strokeWidth: 2)))
      else if (_zones.isEmpty)
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
              color: _cOrange.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _cOrange.withOpacity(0.3))),
          child: const Row(children: [
            Icon(Icons.warning_amber_outlined, color: _cOrange, size: 16),
            SizedBox(width: 8),
            Expanded(child: Text(
                'No safe zones defined. Falls anywhere will trigger alerts.\n'
                'Run monitoring brain to auto-configure zones.',
                style: TextStyle(color: _cOrange,
                    fontSize: 10, fontFamily: 'monospace'))),
          ]),
        )
      else
        ..._zones.map((z) {
          final type = (z['type'] as String? ?? '').toUpperCase();
          final box  = (z['box'] as List?)?.map((v) => v.toString()).join(', ') ?? '';
          final isActive = _onSafeZone;
          return Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.symmetric(
                horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
                color: type == 'BED'
                    ? const Color(0xFF00c8ff).withOpacity(0.08)
                    : const Color(0xFF008cff).withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                    color: type == 'BED'
                        ? _cAccent.withOpacity(0.4)
                        : const Color(0xFF008cff).withOpacity(0.4))),
            child: Row(children: [
              Icon(type == 'BED' ? Icons.hotel : Icons.weekend,
                  color: type == 'BED' ? _cAccent : const Color(0xFF008cff),
                  size: 18),
              const SizedBox(width: 10),
              Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(type, style: TextStyle(
                    color: type == 'BED' ? _cAccent : const Color(0xFF008cff),
                    fontWeight: FontWeight.bold,
                    fontFamily: 'monospace', fontSize: 12)),
                Text('[$box]', style: const TextStyle(
                    color: _cDim, fontSize: 9, fontFamily: 'monospace')),
              ])),
              if (isActive && _onSafeZone)
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                      color: _cGreen.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: _cGreen.withOpacity(0.4))),
                  child: const Text('PATIENT HERE',
                      style: TextStyle(color: _cGreen,
                          fontSize: 8, fontFamily: 'monospace')),
                ),
            ]),
          );
        }),
    ]),
  );

  // ── EMERGENCY BUTTONS ─────────────────────────────────────
  Widget _emergencyButtons() => Padding(
    padding: const EdgeInsets.fromLTRB(10, 10, 10, 0),
    child: Column(children: [
      if (_fallDetected) ...[
        SizedBox(width: double.infinity,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
                backgroundColor: _cRed, padding: const EdgeInsets.symmetric(
                    vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(30))),
            icon: const Icon(Icons.sos, color: Colors.white),
            label: const Text('FALL DETECTED — SEND EMERGENCY ALERT',
                style: TextStyle(color: Colors.white,
                    fontWeight: FontWeight.bold, fontFamily: 'monospace')),
            onPressed: _triggerEmergency,
          )),
        const SizedBox(height: 8),
      ],
      SizedBox(width: double.infinity,
          child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
            foregroundColor: _cText,
            side: BorderSide(color: _cDim.withOpacity(0.5)),
            padding: const EdgeInsets.symmetric(vertical: 12),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(25))),
        icon: const Icon(Icons.contact_phone, size: 16),
        label: const Text('Emergency Contact',
            style: TextStyle(fontFamily: 'monospace')),
        onPressed: () => Navigator.pushNamed(context, 'contact'),
      )),
    ]),
  );

  // ── RECENT FALLS FROM MONGODB ─────────────────────────────
  Widget _recentFallsSection() {
    if (_recentFalls.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 10, 10, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: _cCard, borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cRed.withOpacity(0.3))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.history, color: _cRed, size: 16),
          SizedBox(width: 6),
          Text('RECENT FALLS', style: TextStyle(
              color: _cRed, fontWeight: FontWeight.bold,
              fontFamily: 'monospace', fontSize: 12)),
        ]),
        const SizedBox(height: 10),
        ..._recentFalls.map((f) {
          final ts     = f['timestamp'] as String? ?? '';
          final reason = f['reason']    as String? ?? '';
          final posture= f['posture']   as String? ?? '';
          final score  = f['score'];
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              const Icon(Icons.warning_amber_rounded,
                  color: _cRed, size: 13),
              const SizedBox(width: 6),
              Expanded(child: Text(
                '${ts.length > 16 ? ts.substring(0, 16) : ts} — '
                '${reason.isNotEmpty ? reason : "Fall detected"}'
                '${posture.isNotEmpty ? " | $posture" : ""}'
                '${score != null ? " | score:$score" : ""}',
                style: const TextStyle(color: _cDim,
                    fontSize: 11, fontFamily: 'monospace'),
                maxLines: 2, overflow: TextOverflow.ellipsis,
              )),
            ]),
          );
        }),
      ]),
    );
  }

  // ── RECENT SAVED VIDEOS ───────────────────────────────────
  Widget _recentVideosSection() {
    if (_recentVideos.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 10, 10, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: _cCard, borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cPurple.withOpacity(0.3))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.video_library, color: _cPurple, size: 16),
          const SizedBox(width: 6),
          const Text('SAVED RECORDINGS', style: TextStyle(
              color: _cPurple, fontWeight: FontWeight.bold,
              fontFamily: 'monospace', fontSize: 12)),
          const Spacer(),
          GestureDetector(
            onTap: () => Navigator.pushNamed(context, 'videos'),
            child: const Text('See All →', style: TextStyle(
                color: _cAccent, fontSize: 11,
                fontFamily: 'monospace')),
          ),
        ]),
        const SizedBox(height: 10),
        Row(children: _recentVideos.asMap().entries.map((e) {
          final v = e.value;
          final isFall = v['type'] == 'fall';
          final date   = v['date'] as String? ?? '';
          final path   = v['path'] as String? ?? '';
          return Expanded(child: Padding(
            padding: EdgeInsets.only(left: e.key == 0 ? 0 : 8),
            child: GestureDetector(
              onTap: () => Navigator.pushNamed(context, 'videos'),
              child: Container(
                height: 80,
                decoration: BoxDecoration(
                    color: isFall
                        ? _cRed.withOpacity(0.1)
                        : _cAccent.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                        color: isFall
                            ? _cRed.withOpacity(0.4)
                            : _cAccent.withOpacity(0.2))),
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                  Icon(isFall ? Icons.warning : Icons.play_circle,
                      color: isFall ? _cRed : _cAccent, size: 24),
                  const SizedBox(height: 4),
                  Text(date, style: const TextStyle(
                      color: _cDim, fontSize: 8,
                      fontFamily: 'monospace'),
                      maxLines: 1, overflow: TextOverflow.ellipsis),
                  Text(isFall ? 'FALL' : 'REC',
                      style: TextStyle(
                          color: isFall ? _cRed : _cAccent,
                          fontSize: 9, fontWeight: FontWeight.bold,
                          fontFamily: 'monospace')),
                ]),
              ),
            ),
          ));
        }).toList()),
      ]),
    );
  }
}
