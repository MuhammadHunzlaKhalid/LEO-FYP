import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';

class LeoChatPage extends StatefulWidget {
  const LeoChatPage({Key? key}) : super(key: key);
  @override
  State<LeoChatPage> createState() => _LeoChatPageState();
}

class _LeoChatPageState extends State<LeoChatPage> {
  final _msgCtrl    = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<_Msg>  _msgs = [
    _Msg('Hello Doctor! I am LEO, the AI assistant for this patient. '
        'You can ask me about fall history, medications, daily activity, '
        'or any patient concern.', isLeo: true),
  ];
  bool _chatLoading = false;
  bool _leoReady    = false;

  static const _suggestions = [
    'How many falls this week?',
    'What medications are due?',
    'Summarize today\'s activity',
    'Any inactivity alerts?',
    'What is the patient\'s condition?',
    'Is the patient eating on time?',
    'Show fall risk level',
    'What time did patient sleep?',
  ];

  @override
  void initState() {
    super.initState();
    ApiService.isLeoReady().then((v) {
      if (!mounted) return;
      setState(() { _leoReady = v; });
      if (!v) {
        setState(() => _msgs.add(_Msg(
          '⏳ My AI brain is still loading (may take 1–2 min after backend starts). '
          'Basic responses will work; full AI answers coming shortly.',
          isLeo: true)));
      }
    });
  }

  @override
  void dispose() { _msgCtrl.dispose(); _scrollCtrl.dispose(); super.dispose(); }

  Future<void> _send([String? sug]) async {
    final text = sug ?? _msgCtrl.text.trim();
    if (text.isEmpty) return;
    _msgCtrl.clear();
    setState(() { _msgs.add(_Msg(text, isLeo: false)); _chatLoading = true; });
    _scroll();
    final reply = await ApiService.chat(
        username: Session.username, message: text);
    if (!mounted) return;
    setState(() {
      _chatLoading = false;
      _msgs.add(_Msg(reply ?? '❌ LEO is not reachable. Check backend.', isLeo: true));
    });
    _scroll();
  }

  void _scroll() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (_scrollCtrl.hasClients) _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [Color(0xFFE2C7E9), Color(0xFF783E9E), Color(0xFF110031)],
          ),
        ),
        child: SafeArea(child: Column(children: [
          // ── Header ────────────────────────────────────────
          Container(
            padding: const EdgeInsets.fromLTRB(4, 8, 16, 12),
            decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.2)),
            child: Row(children: [
              IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => Navigator.pop(context)),
              // LEO avatar
              Container(width: 36, height: 36,
                  decoration: const BoxDecoration(
                      gradient: LinearGradient(
                          colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
                      shape: BoxShape.circle),
                  child: const Center(child: Text('L',
                      style: TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 18)))),
              const SizedBox(width: 10),
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('LEO AI Assistant',
                    style: TextStyle(color: Colors.white,
                        fontWeight: FontWeight.bold, fontSize: 16)),
                Row(children: [
                  Container(width: 7, height: 7,
                      decoration: BoxDecoration(
                          color: _leoReady ? Colors.greenAccent : Colors.orange,
                          shape: BoxShape.circle)),
                  const SizedBox(width: 4),
                  Text(_leoReady ? 'Online · Full AI' : 'Loading AI...',
                      style: const TextStyle(
                          color: Colors.white60, fontSize: 11)),
                ]),
              ]),
              const Spacer(),
              // Patient info chip
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20)),
                child: Text('Patient: ${Session.displayName}',
                    style: const TextStyle(color: Colors.white, fontSize: 11)),
              ),
            ]),
          ),

          // ── Suggestions strip ──────────────────────────────
          Container(
            height: 44,
            color: Colors.black.withOpacity(0.1),
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              itemCount: _suggestions.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, i) => GestureDetector(
                onTap: () => _send(_suggestions[i]),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.white24)),
                  child: Text(_suggestions[i],
                      style: const TextStyle(
                          color: Colors.white, fontSize: 11)),
                ),
              ),
            ),
          ),

          // ── Messages ───────────────────────────────────────
          Expanded(child: ListView.builder(
            controller: _scrollCtrl,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            itemCount: _msgs.length + (_chatLoading ? 1 : 0),
            itemBuilder: (_, i) {
              if (i == _msgs.length) return _typing();
              return _bubble(_msgs[i]);
            },
          )),

          // ── Input ──────────────────────────────────────────
          Container(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            color: Colors.black.withOpacity(0.2),
            child: Row(children: [
              Expanded(child: Container(
                decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.white24)),
                child: TextField(
                  controller: _msgCtrl,
                  style: const TextStyle(color: Colors.white),
                  maxLines: null,
                  decoration: const InputDecoration(
                    hintText: 'Ask LEO about your patient...',
                    hintStyle: TextStyle(color: Colors.white38),
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                  ),
                  onSubmitted: (_) => _send(),
                ),
              )),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: _chatLoading ? null : _send,
                child: Container(
                  width: 44, height: 44,
                  decoration: const BoxDecoration(
                      gradient: LinearGradient(
                          colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
                      shape: BoxShape.circle),
                  child: _chatLoading
                      ? const Padding(padding: EdgeInsets.all(12),
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2))
                      : const Icon(Icons.send, color: Colors.white, size: 20),
                ),
              ),
            ]),
          ),
        ])),
      ),
    );
  }

  Widget _bubble(_Msg m) => Padding(
    padding: EdgeInsets.only(
        left: m.isLeo ? 0 : 60, right: m.isLeo ? 60 : 0, bottom: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisAlignment:
          m.isLeo ? MainAxisAlignment.start : MainAxisAlignment.end,
      children: [
        if (m.isLeo) ...[
          Container(width: 28, height: 28,
              decoration: const BoxDecoration(
                  gradient: LinearGradient(
                      colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
                  shape: BoxShape.circle),
              child: const Center(child: Text('L',
                  style: TextStyle(color: Colors.white,
                      fontWeight: FontWeight.bold, fontSize: 12)))),
          const SizedBox(width: 8),
        ],
        Flexible(child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: m.isLeo
                ? Colors.white.withOpacity(0.15)
                : const Color(0xFF6A5AE0),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: Radius.circular(m.isLeo ? 4 : 16),
              bottomRight: Radius.circular(m.isLeo ? 16 : 4),
            ),
          ),
          child: Text(m.text,
              style: const TextStyle(color: Colors.white,
                  fontSize: 13, height: 1.4)),
        )),
        if (!m.isLeo) ...[
          const SizedBox(width: 8),
          const CircleAvatar(radius: 14,
              backgroundColor: Color(0xff4c505b),
              child: Icon(Icons.person, color: Colors.white, size: 14)),
        ],
      ],
    ),
  );

  Widget _typing() => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(children: [
      Container(width: 28, height: 28,
          decoration: const BoxDecoration(
              gradient: LinearGradient(
                  colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
              shape: BoxShape.circle),
          child: const Center(child: Text('L',
              style: TextStyle(color: Colors.white,
                  fontWeight: FontWeight.bold, fontSize: 12)))),
      const SizedBox(width: 8),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.15),
            borderRadius: BorderRadius.circular(16)),
        child: const Text('LEO is thinking...',
            style: TextStyle(color: Colors.white60, fontSize: 12)),
      ),
    ]),
  );
}

class _Msg {
  final String text; final bool isLeo;
  const _Msg(this.text, {required this.isLeo});
}
