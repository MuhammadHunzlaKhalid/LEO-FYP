import 'dart:async';
import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';
import 'leo_fab.dart';

class AlertsPage extends StatefulWidget {
  const AlertsPage({super.key});
  @override
  State<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends State<AlertsPage>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnim;
  late Animation<Offset> _slideAnim;

  List<Map<String, dynamic>> _logs = [];
  List<Map<String, dynamic>> _falls = [];
  Map<String, dynamic>? _summary;
  bool _loading = true;

  // tab: 0=alerts, 1=falls, 2=summary
  int _tab = 0;

  double _scale = 1.0;
  void _onTapDown(_) => setState(() => _scale = 0.95);
  void _onTapUp(_) => setState(() => _scale = 1.0);

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900));
    _fadeAnim = CurvedAnimation(parent: _controller, curve: Curves.easeIn);
    _slideAnim = Tween<Offset>(begin: const Offset(0, 0.2), end: Offset.zero)
        .animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));
    _loadAll();
  }

  Future<void> _loadAll() async {
    setState(() => _loading = true);
    final results = await Future.wait([
      ApiService.getLogs(Session.username),
      ApiService.getFalls(Session.username),
      ApiService.getSummary(Session.username),
    ]);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _logs = results[0] as List<Map<String, dynamic>>;
      _falls = results[1] as List<Map<String, dynamic>>;
      _summary = results[2] as Map<String, dynamic>?;
    });
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: const LeoFab(),
      backgroundColor: Colors.transparent,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFE2C7E9), Color(0xFF783E9E), Color(0xFF110031)],
          ),
        ),
        child: SafeArea(
            child: Column(children: [
          // ── AppBar (original red style) ───────────────────
          Container(
            color: const Color(0xFFB71C1C),
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 6, 16, 0),
                child: Row(children: [
                  IconButton(
                      icon: const Icon(Icons.arrow_back_ios_new,
                          color: Colors.white),
                      onPressed: () => Navigator.pop(context)),
                  const Text('Alerts',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w600)),
                  const Spacer(),
                  IconButton(
                      icon: const Icon(Icons.refresh, color: Colors.white),
                      onPressed: _loadAll),
                ]),
              ),
              // Tab bar
              Row(children: [
                _tabBtn('Activity', 0),
                _tabBtn('Falls', 1),
                _tabBtn('Summary', 2),
              ]),
            ]),
          ),

          // ── Content ───────────────────────────────────────
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(color: Colors.white))
                : FadeTransition(
                    opacity: _fadeAnim,
                    child: SlideTransition(
                      position: _slideAnim,
                      child: Container(
                        margin: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(16),
                          child: _tab == 0
                              ? _activityTab()
                              : _tab == 1
                                  ? _fallsTab()
                                  : _summaryTab(),
                        ),
                      ),
                    ),
                  ),
          ),
        ])),
      ),
    );
  }

  Widget _tabBtn(String label, int index) => Expanded(
        child: GestureDetector(
          onTap: () {
            setState(() => _tab = index);
            _controller.forward(from: 0);
          },
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
                border: Border(
                    bottom: BorderSide(
                        color:
                            _tab == index ? Colors.white : Colors.transparent,
                        width: 2))),
            child: Text(label,
                textAlign: TextAlign.center,
                style: TextStyle(
                    color: _tab == index ? Colors.white : Colors.white60,
                    fontWeight:
                        _tab == index ? FontWeight.bold : FontWeight.normal)),
          ),
        ),
      );

  // ── ACTIVITY TAB ──────────────────────────────────────────
  Widget _activityTab() =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: const [
          Icon(Icons.local_fire_department, color: Colors.red),
          SizedBox(width: 8),
          Text('Activity Log',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 12),
        if (_logs.isEmpty)
          const Text('No activity logged yet.',
              style: TextStyle(color: Colors.grey))
        else
          ..._logs.take(15).toList().asMap().entries.map((e) {
            final delay = 0.1 * (e.key % 5);
            return _animatedAlert(delay, e.value);
          }),
        const SizedBox(height: 20),
        GestureDetector(
          onTapDown: _onTapDown,
          onTapUp: _onTapUp,
          onTapCancel: () => _onTapUp(null),
          child: AnimatedScale(
            scale: _scale,
            duration: const Duration(milliseconds: 150),
            child: SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _loadAll,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Refresh Alerts',
                    style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white)),
              ),
            ),
          ),
        ),
      ]);

  Widget _animatedAlert(double delay, Map<String, dynamic> log) {
    final anim = CurvedAnimation(
        parent: _controller,
        curve: Interval(delay, 1.0, curve: Curves.easeOut));
    final cat = log['category'] as String? ?? 'info';
    final msg = log['message'] as String? ?? log['content'] as String? ?? '';
    final ts = log['timestamp'] as String? ?? log['time'] as String? ?? '';
    final isCrit = log['severity'] == 'critical' || cat == 'fall';

    return FadeTransition(
      opacity: anim,
      child: SlideTransition(
        position: Tween<Offset>(begin: const Offset(0.3, 0), end: Offset.zero)
            .animate(anim),
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: Colors.white,
            border: Border.all(
                color: isCrit ? Colors.red.shade200 : Colors.grey.shade200),
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 8,
                  offset: const Offset(0, 4))
            ],
          ),
          child: Row(children: [
            _catIcon(cat),
            const SizedBox(width: 10),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(msg,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 4),
                  Text(_shortTime(ts),
                      style: const TextStyle(color: Colors.grey, fontSize: 12)),
                ])),
            Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                    color: isCrit ? Colors.red : Colors.green,
                    shape: BoxShape.circle)),
          ]),
        ),
      ),
    );
  }

  // ── FALLS TAB ────────────────────────────────────────────
  Widget _fallsTab() =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.red),
          const SizedBox(width: 8),
          Text('Fall Events (${_falls.length})',
              style:
                  const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 12),
        if (_falls.isEmpty)
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green.shade200)),
            child: const Row(children: [
              Icon(Icons.check_circle, color: Colors.green),
              SizedBox(width: 10),
              Text('No falls recorded — patient is safe!',
                  style: TextStyle(
                      color: Colors.green, fontWeight: FontWeight.w600)),
            ]),
          )
        else
          ..._falls.asMap().entries.map((e) {
            final f = e.value;
            final date = f['date'] as String? ?? '';
            final time = f['time'] as String? ?? '';
            final reason = f['reason'] as String? ?? '';
            final posture = f['posture'] as String? ?? '';
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.red.shade200),
              ),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      const Icon(Icons.warning_amber_rounded,
                          color: Colors.red, size: 18),
                      const SizedBox(width: 6),
                      Text('Fall #${e.key + 1} — $date $time',
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, color: Colors.red)),
                    ]),
                    if (reason.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(reason, style: const TextStyle(fontSize: 13)),
                    ],
                    if (posture.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Row(children: [
                        _badge(posture.toUpperCase(), Colors.orange),
                        const SizedBox(width: 6),
                        _badge('FALL', Colors.red),
                      ]),
                    ],
                  ]),
            );
          }),
      ]);

  // ── SUMMARY TAB ───────────────────────────────────────────
  Widget _summaryTab() =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FadeTransition(
          opacity: Tween<double>(begin: 0, end: 1).animate(CurvedAnimation(
              parent: _controller,
              curve: const Interval(0.3, 1.0, curve: Curves.easeIn))),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: const [
              Icon(Icons.directions_walk),
              SizedBox(width: 8),
              Text('Daily Summary',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 16),
            if (_summary != null) ...[
              _summaryRow(
                  'Falls today',
                  '${_summary!['falls_today'] ?? 0}',
                  (_summary!['falls_today'] ?? 0) > 0
                      ? Colors.red
                      : Colors.green),
              _summaryRow('Total falls ever',
                  '${_summary!['total_falls'] ?? 0}', Colors.orange),
              _summaryRow('Monitoring sessions',
                  '${_summary!['total_sessions'] ?? 0}', Colors.blue),
              if (_summary!['last_activity'] != null)
                _summaryRow('Last activity',
                    _summary!['last_activity'] as String, Colors.purple),
              if (_summary!['last_fall'] != null)
                _summaryRow(
                    'Last fall', _summary!['last_fall'] as String, Colors.red),
            ] else ...[
              _summaryRow(
                  'Activity logs today', '${_logs.length}', Colors.blue),
              _summaryRow('Fall alerts', '${_falls.length}', Colors.red),
            ],
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 12),
            const Text('Activity Breakdown',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 12),
            ..._categoryBreakdown(),
          ]),
        ),
      ]);

  List<Widget> _categoryBreakdown() {
    final counts = <String, int>{};
    for (final l in _logs) {
      final c = l['category'] as String? ?? 'other';
      counts[c] = (counts[c] ?? 0) + 1;
    }
    return counts.entries
        .map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                _catIcon(e.key),
                const SizedBox(width: 10),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(e.key.toUpperCase(),
                          style: const TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      LinearProgressIndicator(
                        value: _logs.isEmpty ? 0 : e.value / _logs.length,
                        backgroundColor: Colors.grey.shade200,
                        color: _catColor(e.key),
                      ),
                    ])),
                const SizedBox(width: 10),
                Text('${e.value}',
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 13)),
              ]),
            ))
        .toList();
  }

  // helpers
  Widget _summaryRow(String label, String value, Color color) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child:
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(label, style: const TextStyle(fontSize: 14)),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: color.withOpacity(0.3))),
            child: Text(value,
                style: TextStyle(color: color, fontWeight: FontWeight.bold)),
          ),
        ]),
      );

  Widget _badge(String t, Color c) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
            color: c.withOpacity(0.1),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: c.withOpacity(0.4))),
        child: Text(t,
            style:
                TextStyle(color: c, fontSize: 9, fontWeight: FontWeight.bold)),
      );

  Widget _catIcon(String cat) {
    final info = {
          'fall': [Icons.warning_amber_rounded, Colors.red],
          'emergency': [Icons.sos, Colors.red],
          'medication': [Icons.medication, Colors.green],
          'chat': [Icons.chat, Colors.blue],
          'inactivity': [Icons.timer_off, Colors.orange],
        }[cat] ??
        [Icons.info_outline, Colors.grey];
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
          color: (info[1] as Color).withOpacity(0.1), shape: BoxShape.circle),
      child: Icon(info[0] as IconData, color: info[1] as Color, size: 16),
    );
  }

  Color _catColor(String cat) =>
      {
        'fall': Colors.red,
        'emergency': Colors.red,
        'medication': Colors.green,
        'chat': Colors.blue,
        'inactivity': Colors.orange,
      }[cat] ??
      Colors.grey;

  String _shortTime(String? ts) {
    if (ts == null || ts.isEmpty) return '';
    try {
      final dt = DateTime.parse(ts).toLocal();
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return ts.length > 5 ? ts.substring(0, 5) : ts;
    }
  }
}
