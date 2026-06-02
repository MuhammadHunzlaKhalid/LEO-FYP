import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';

class MyContactsPage extends StatefulWidget {
  const MyContactsPage({Key? key}) : super(key: key);
  @override
  State<MyContactsPage> createState() => _MyContactsPageState();
}

class _MyContactsPageState extends State<MyContactsPage> {
  List<Map<String, dynamic>> _contacts = [];
  bool _loading = true;
  bool _showChat = false;

  final _msgCtrl    = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<_Msg> _msgs = [
    _Msg('Hello! I am LEO. How can I help you today?', true),
  ];
  bool _chatLoading = false;
  bool _leoReady    = false;

  @override
  void initState() {
    super.initState();
    _load();
    ApiService.isLeoReady().then((v) {
      if (mounted) setState(() => _leoReady = v);
    });
  }

  // ── Load contacts from profile ────────────────────────────
  Future<void> _load() async {
    setState(() => _loading = true);
    final p = await ApiService.getProfile(Session.username);
    if (!mounted) return;
    setState(() {
      _loading = false;
      if (p != null) {
        final ec = p['emergency_contacts'];
        final c  = p['contacts'];
        _contacts = [
          if (ec is List) ...ec.cast<Map<String, dynamic>>(),
          if (c  is List) ...c.cast<Map<String, dynamic>>(),
        ];
      }
    });
  }

  // ── Add contact dialog ────────────────────────────────────
  void _showAddContactDialog() {
    final nameCtrl     = TextEditingController();
    final phoneCtrl    = TextEditingController();
    final relationCtrl = TextEditingController();
    bool saving = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDlg) => AlertDialog(
          title: const Row(children: [
            Icon(Icons.person_add, color: Color(0xFF6A5AE0)),
            SizedBox(width: 8),
            Text('Add Emergency Contact'),
          ]),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Full Name *',
                prefixIcon: Icon(Icons.person),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: phoneCtrl,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Phone Number *',
                prefixIcon: Icon(Icons.phone),
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: relationCtrl,
              decoration: const InputDecoration(
                labelText: 'Relation (e.g. Son, Daughter, Doctor)',
                prefixIcon: Icon(Icons.people),
                border: OutlineInputBorder(),
              ),
            ),
          ]),
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6A5AE0)),
              onPressed: saving ? null : () async {
                final name  = nameCtrl.text.trim();
                final phone = phoneCtrl.text.trim();
                if (name.isEmpty || phone.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Name and phone are required')));
                  return;
                }
                setDlg(() => saving = true);

                // Build updated contacts list
                final newContact = {
                  'name':     name,
                  'phone':    phone,
                  'relation': relationCtrl.text.trim(),
                };
                final updatedContacts = [
                  ..._contacts.where((c) => c['_isEmergency'] != false),
                  newContact,
                ];

                // Save to backend → MongoDB
                final ok = await _saveContacts(updatedContacts);
                if (!mounted) return;
                Navigator.pop(ctx);

                if (ok) {
                  ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content: Text('✅ Contact saved to database!'),
                          backgroundColor: Colors.green));
                  await _load(); // Reload from DB
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content: Text('❌ Failed to save. Is the backend running?'),
                          backgroundColor: Colors.red));
                }
              },
              child: saving
                  ? const SizedBox(width: 16, height: 16,
                      child: CircularProgressIndicator(
                          color: Colors.white, strokeWidth: 2))
                  : const Text('Save',
                      style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<bool> _saveContacts(List<Map<String, dynamic>> contacts) async {
    try {
      // Use PUT /user/{username}/profile to update emergency_contacts
      final uri = Uri.parse(
          '${ApiService.activeBaseUrl}/user/${Session.username}/profile');
      final import_http = await _httpPut(uri, {
        'emergency_contacts': contacts,
      });
      return import_http;
    } catch (e) {
      return false;
    }
  }

  Future<bool> _httpPut(Uri uri, Map<String, dynamic> body) async {
    try {
      // Re-use ApiService's register method pattern via update
      // We call the backend PUT endpoint directly
      final r = await ApiService.updateProfileContacts(
          Session.username, body);
      return r;
    } catch (_) { return false; }
  }

  // ── Delete contact ────────────────────────────────────────
  void _deleteContact(int index) async {
    final updated = List<Map<String, dynamic>>.from(_contacts)
      ..removeAt(index);
    final ok = await ApiService.updateProfileContacts(
        Session.username, {'emergency_contacts': updated});
    if (!mounted) return;
    if (ok) {
      await _load();
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Contact removed'),
              backgroundColor: Colors.orange));
    }
  }

  // ── SOS ──────────────────────────────────────────────────
  Future<void> _triggerSOS() async {
    final ok = await ApiService.triggerEmergency(
        username: Session.username,
        reason: 'SOS triggered from Contacts page');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '🚨 Emergency alert sent!' : '❌ Failed'),
        backgroundColor: ok ? Colors.green : Colors.red));
  }

  // ── Chat ─────────────────────────────────────────────────
  Future<void> _send([String? sug]) async {
    final text = sug ?? _msgCtrl.text.trim();
    if (text.isEmpty) return;
    _msgCtrl.clear();
    setState(() { _msgs.add(_Msg(text, false)); _chatLoading = true; });
    _scrollDown();
    final reply = await ApiService.chat(
        username: Session.username, message: text);
    if (!mounted) return;
    setState(() {
      _chatLoading = false;
      _msgs.add(_Msg(reply ?? '❌ LEO not reachable.', true));
    });
    _scrollDown();
  }

  void _scrollDown() => WidgetsBinding.instance.addPostFrameCallback((_) {
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
    }
  });

  @override
  void dispose() { _msgCtrl.dispose(); _scrollCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(children: [
        // Gradient background
        Container(decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFE2C7E9), Color(0xFF783E9E), Color(0xFF110031)],
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
          ),
        )),

        Column(children: [
          const SizedBox(height: 50),
          // Back + LEO status
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [
              IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.white),
                onPressed: () => Navigator.pop(context)),
              const Spacer(),
              Row(children: [
                Container(width: 8, height: 8,
                    decoration: BoxDecoration(
                        color: _leoReady ? Colors.green : Colors.orange,
                        shape: BoxShape.circle)),
                const SizedBox(width: 4),
                Text(_leoReady ? 'LEO Ready' : 'LEO Loading',
                    style: const TextStyle(color: Colors.white70,
                        fontSize: 11)),
              ]),
            ]),
          ),

          const Text('MY CONTACTS', style: TextStyle(
              color: Colors.white, fontSize: 26,
              fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),

          // SOS Button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                minimumSize: const Size(double.infinity, 56),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(30)),
              ),
              onPressed: _triggerSOS,
              child: const Text('🚨 AI HELP / EMERGENCY',
                  style: TextStyle(color: Colors.white, fontSize: 16,
                      fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(height: 16),

          // White content sheet
          Expanded(child: Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(30)),
            ),
            child: _showChat ? _chatView() : _contactsView(),
          )),
        ]),

        // ASK LEO / CONTACTS toggle button
        Positioned(
          bottom: 80, right: 20,
          child: GestureDetector(
            onTap: () => setState(() => _showChat = !_showChat),
            child: Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                    colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
                borderRadius: BorderRadius.circular(30),
                boxShadow: [BoxShadow(
                    color: Colors.black.withOpacity(0.3), blurRadius: 8)],
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(_showChat ? Icons.contacts : Icons.smart_toy,
                    color: Colors.white),
                const SizedBox(width: 6),
                Text(_showChat ? 'CONTACTS' : 'ASK LEO',
                    style: const TextStyle(color: Colors.white,
                        fontWeight: FontWeight.bold)),
              ]),
            ),
          ),
        ),
      ]),

      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: const Color(0xFFE2C7E9),
        currentIndex: 1,
        selectedItemColor: Colors.black,
        unselectedItemColor: Colors.black54,
        onTap: (i) {
          if (i == 0) Navigator.pushNamed(context, 'home');
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.contacts), label: 'Contacts'),
        ],
      ),
    );
  }

  // ── CONTACTS VIEW ─────────────────────────────────────────
  Widget _contactsView() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      // Header row with Add button
      Row(children: [
        const Text('Emergency Contacts',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const Spacer(),
        ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF6A5AE0),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20)),
          ),
          icon: const Icon(Icons.add, color: Colors.white, size: 16),
          label: const Text('Add', style: TextStyle(
              color: Colors.white, fontSize: 12)),
          onPressed: _showAddContactDialog,
        ),
      ]),
      const SizedBox(height: 12),

      // Favorites (first 2)
      if (_contacts.length >= 2) ...[
        Row(children: [
          Expanded(child: _favCard(_contacts[0], 0)),
          const SizedBox(width: 10),
          Expanded(child: _favCard(_contacts[1], 1)),
        ]),
        const SizedBox(height: 20),
      ] else if (_contacts.length == 1) ...[
        Row(children: [
          Expanded(child: _favCard(_contacts[0], 0)),
          const Expanded(child: SizedBox()),
        ]),
        const SizedBox(height: 20),
      ],

      const Text('All Contacts', style: TextStyle(
          fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 10),

      // Contact list
      Expanded(child: _contacts.isEmpty
          ? Center(child: Column(
              mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.contacts_outlined,
                color: Colors.grey, size: 56),
            const SizedBox(height: 12),
            const Text('No contacts saved yet',
                style: TextStyle(color: Colors.grey, fontSize: 15)),
            const SizedBox(height: 8),
            const Text(
                'Tap "+ Add" above to add emergency contacts.\n'
                'They will be saved to the database.',
                style: TextStyle(color: Colors.grey, fontSize: 12),
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6A5AE0)),
              icon: const Icon(Icons.person_add, color: Colors.white),
              label: const Text('Add Emergency Contact',
                  style: TextStyle(color: Colors.white)),
              onPressed: _showAddContactDialog,
            ),
          ]))
          : ListView.builder(
              itemCount: _contacts.length,
              itemBuilder: (_, i) {
                final c    = _contacts[i];
                final name = c['name'] as String? ?? 'Unknown';
                final ph   = c['phone'] as String? ?? '';
                final rel  = c['relation'] as String? ?? '';
                return Dismissible(
                  key: Key('$name$ph'),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 16),
                    color: Colors.red,
                    child: const Icon(Icons.delete, color: Colors.white),
                  ),
                  onDismissed: (_) => _deleteContact(i),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: const Color(0xFF6A5AE0),
                      child: Text(name[0].toUpperCase(),
                          style: const TextStyle(color: Colors.white,
                              fontWeight: FontWeight.bold)),
                    ),
                    title: Text(name,
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text('$rel${rel.isNotEmpty ? " · " : ""}$ph'),
                    trailing: const Icon(Icons.phone, color: Colors.green),
                  ),
                );
              })),
    ]);
  }

  Widget _favCard(Map<String, dynamic> c, int index) {
    final name = c['name'] as String? ?? 'Unknown';
    final rel  = c['relation'] as String? ?? '';
    final ph   = c['phone'] as String? ?? '';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(20)),
      child: Column(children: [
        CircleAvatar(
          radius: 28,
          backgroundColor: const Color(0xFF6A5AE0),
          child: Text(name[0].toUpperCase(),
              style: const TextStyle(color: Colors.white,
                  fontSize: 20, fontWeight: FontWeight.bold)),
        ),
        const SizedBox(height: 8),
        Text(name, style: const TextStyle(
            fontWeight: FontWeight.bold, fontSize: 13)),
        if (rel.isNotEmpty)
          Text(rel, style: const TextStyle(
              fontSize: 11, color: Colors.grey)),
        Text(ph, style: const TextStyle(
            fontSize: 10, color: Colors.grey)),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: const [
          _ActionIcon(icon: Icons.call, label: 'Call'),
          _ActionIcon(icon: Icons.message, label: 'Msg'),
        ]),
      ]),
    );
  }

  // ── LEO CHAT VIEW ─────────────────────────────────────────
  Widget _chatView() => Column(children: [
    Row(children: [
      Container(width: 32, height: 32,
          decoration: const BoxDecoration(
              gradient: LinearGradient(
                  colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
              shape: BoxShape.circle),
          child: const Center(child: Text('L',
              style: TextStyle(color: Colors.white,
                  fontWeight: FontWeight.bold)))),
      const SizedBox(width: 8),
      const Text('LEO AI Assistant',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
      const Spacer(),
      Container(width: 8, height: 8,
          decoration: BoxDecoration(
              color: _leoReady ? Colors.green : Colors.orange,
              shape: BoxShape.circle)),
      const SizedBox(width: 4),
      Text(_leoReady ? 'Ready' : 'Loading...',
          style: TextStyle(
              color: _leoReady ? Colors.green : Colors.orange,
              fontSize: 11)),
    ]),
    const Divider(height: 16),

    // Quick suggestions
    SizedBox(height: 36,
        child: ListView(scrollDirection: Axis.horizontal,
            children: ['Check meds', 'Patient status', 'Any falls?',
                        'Daily summary', 'Emergency help']
                .map((s) => GestureDetector(
                  onTap: () => _send(s),
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                        color: const Color(0xFF6A5AE0).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                            color: const Color(0xFF6A5AE0).withOpacity(0.3))),
                    child: Text(s, style: const TextStyle(
                        fontSize: 12, color: Color(0xFF6A5AE0))),
                  ),
                )).toList())),
    const SizedBox(height: 8),

    // Messages
    Expanded(child: ListView.builder(
      controller: _scrollCtrl,
      itemCount: _msgs.length + (_chatLoading ? 1 : 0),
      itemBuilder: (_, i) {
        if (i == _msgs.length) return _typing();
        return _bubble(_msgs[i]);
      },
    )),

    const Divider(height: 8),
    Row(children: [
      Expanded(child: TextField(
        controller: _msgCtrl,
        decoration: InputDecoration(
          hintText: 'Ask LEO anything...',
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(20),
              borderSide: BorderSide.none),
          filled: true, fillColor: Colors.grey.shade100,
          contentPadding: const EdgeInsets.symmetric(
              horizontal: 16, vertical: 10),
        ),
        onSubmitted: (_) => _send(),
      )),
      const SizedBox(width: 8),
      GestureDetector(
        onTap: _chatLoading ? null : _send,
        child: Container(
          width: 42, height: 42,
          decoration: const BoxDecoration(
              gradient: LinearGradient(
                  colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
              shape: BoxShape.circle),
          child: _chatLoading
              ? const Padding(padding: EdgeInsets.all(10),
                  child: CircularProgressIndicator(
                      color: Colors.white, strokeWidth: 2))
              : const Icon(Icons.send, color: Colors.white, size: 18),
        ),
      ),
    ]),
  ]);

  Widget _bubble(_Msg m) => Align(
    alignment: m.isLeo ? Alignment.centerLeft : Alignment.centerRight,
    child: Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.7),
      decoration: BoxDecoration(
        color: m.isLeo ? Colors.grey.shade100
            : const Color(0xFF6A5AE0).withOpacity(0.9),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(16),
          topRight: const Radius.circular(16),
          bottomLeft: Radius.circular(m.isLeo ? 4 : 16),
          bottomRight: Radius.circular(m.isLeo ? 16 : 4),
        ),
      ),
      child: Text(m.text, style: TextStyle(
          color: m.isLeo ? Colors.black87 : Colors.white, fontSize: 13)),
    ),
  );

  Widget _typing() => Align(
    alignment: Alignment.centerLeft,
    child: Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(16)),
      child: const Text('LEO is thinking...',
          style: TextStyle(color: Colors.grey, fontSize: 12)),
    ),
  );
}

class _Msg { final String text; final bool isLeo;
  const _Msg(this.text, this.isLeo); }

class _ActionIcon extends StatelessWidget {
  final IconData icon; final String label;
  const _ActionIcon({required this.icon, required this.label});
  @override
  Widget build(BuildContext context) => Column(children: [
    CircleAvatar(radius: 18, child: Icon(icon, size: 18)),
    const SizedBox(height: 4),
    Text(label, style: const TextStyle(fontSize: 10)),
  ]);
}
