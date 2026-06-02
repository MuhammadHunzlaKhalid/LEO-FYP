import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';
import 'leo_fab.dart';

class PatientInformationPage extends StatefulWidget {
  const PatientInformationPage({Key? key}) : super(key: key);
  @override
  State<PatientInformationPage> createState() => _PatientInformationPageState();
}

class _PatientInformationPageState extends State<PatientInformationPage>
    with SingleTickerProviderStateMixin {
  late TabController _tab;
  Map<String, dynamic>? _profile;
  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _zones = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 4, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final results = await Future.wait([
      ApiService.getProfile(Session.username),
      ApiService.getSummary(Session.username),
      ApiService.getZones(),
    ]);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _profile = results[0] as Map<String, dynamic>?;
      _summary = results[1] as Map<String, dynamic>?;
      _zones = results[2] as List<Map<String, dynamic>>;
      if (_profile == null) {
        _error = 'Could not load profile for "${Session.username}".\n'
            'Check backend is running and patient is registered.';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: const LeoFab(),
      body: Container(
        width: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFE2C7E9), Color(0xFF783E9E), Color(0xFF110031)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
            child: Column(children: [
          Container(
            decoration: BoxDecoration(color: Colors.black.withOpacity(0.2)),
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 8, 16, 0),
                child: Row(children: [
                  IconButton(
                      icon: const Icon(Icons.arrow_back, color: Colors.white),
                      onPressed: () => Navigator.pop(context)),
                  const Text('All about Patient',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold)),
                  const Spacer(),
                  IconButton(
                      icon: const Icon(Icons.refresh, color: Colors.white),
                      onPressed: _load),
                ]),
              ),
              TabBar(
                controller: _tab,
                indicatorColor: Colors.purpleAccent,
                labelColor: Colors.white,
                unselectedLabelColor: Colors.white54,
                isScrollable: true,
                tabs: const [
                  Tab(text: 'Profile'),
                  Tab(text: 'Medications'),
                  Tab(text: 'Contacts'),
                  Tab(text: 'Safe Zones'),
                ],
              ),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(color: Colors.white))
                : _error != null
                    ? _errorView()
                    : TabBarView(controller: _tab, children: [
                        _profileTab(),
                        _medsTab(),
                        _contactsTab(),
                        _zonesTab(),
                      ]),
          ),
        ])),
      ),
    );
  }

  // ── PROFILE TAB ────────────────────────────────────────────
  Widget _profileTab() {
    final personal = _profile!['personal'] as Map<String, dynamic>? ?? {};
    final routine = _profile!['routine'] as Map<String, dynamic>? ?? {};
    final name = personal['name'] as String? ?? '—';
    final age = personal['age']?.toString() ?? '—';
    final gender = personal['gender'] as String? ?? '—';
    final condition = personal['condition'] as String? ?? '—';
    final phone = personal['phone'] as String? ?? '—';
    final initials = name
        .split(' ')
        .where((w) => w.isNotEmpty)
        .take(2)
        .map((w) => w[0].toUpperCase())
        .join();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              gradient: const LinearGradient(
                  colors: [Color(0xFF6A5AE0), Color(0xFF8E2DE2)]),
              borderRadius: BorderRadius.circular(16)),
          child: Row(children: [
            CircleAvatar(
              radius: 36,
              backgroundColor: Colors.white24,
              child: Text(initials,
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 26,
                      fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 16),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(name,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('Patient · ${Session.username}',
                      style:
                          const TextStyle(color: Colors.white70, fontSize: 12)),
                ])),
          ]),
        ),
        const SizedBox(height: 16),
        if (_summary != null) ...[
          Row(children: [
            _miniStat(
                'Falls Today',
                '${_summary!['falls_today'] ?? 0}',
                (_summary!['falls_today'] ?? 0) > 0
                    ? Colors.red
                    : Colors.green),
            const SizedBox(width: 8),
            _miniStat('Total Falls', '${_summary!['total_falls'] ?? 0}',
                Colors.orange),
            const SizedBox(width: 8),
            _miniStat(
                'Sessions', '${_summary!['total_sessions'] ?? 0}', Colors.blue),
          ]),
          const SizedBox(height: 16),
        ],
        _infoCard('Personal Info', Icons.person, [
          _row('Name', name),
          _row('Age', age),
          _row('Gender', gender),
          _row('Condition', condition),
          _row('Phone', phone),
        ]),
        const SizedBox(height: 12),
        _infoCard('Daily Routine', Icons.schedule, [
          _row('Wake up', routine['wake'] ?? routine['wake_up'] ?? '07:00'),
          _row('Sleep', routine['sleep'] ?? '22:00'),
        ]),
        const SizedBox(height: 80),
      ]),
    );
  }

  // ── ADD MEDICATION DIALOG ──────────────────────────────────
  void _showAddMedDialog() {
    final nameCtrl = TextEditingController();
    final doseCtrl = TextEditingController();
    final timeCtrl = TextEditingController(text: '08:00');
    final docCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) {
        bool saving = false;
        return StatefulBuilder(
          builder: (ctx, setDlg) => AlertDialog(
            title: const Row(children: [
              Icon(Icons.medication, color: Color(0xFF6A5AE0)),
              SizedBox(width: 8),
              Text('Add Medication'),
            ]),
            content: SingleChildScrollView(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(
                        labelText: 'Medicine Name *',
                        prefixIcon: Icon(Icons.medication_liquid),
                        border: OutlineInputBorder())),
                const SizedBox(height: 10),
                TextField(
                    controller: doseCtrl,
                    decoration: const InputDecoration(
                        labelText: 'Dose (e.g. 1 tablet)',
                        prefixIcon: Icon(Icons.scale),
                        border: OutlineInputBorder())),
                const SizedBox(height: 10),
                TextField(
                    controller: timeCtrl,
                    decoration: const InputDecoration(
                        labelText: 'Time HH:MM',
                        prefixIcon: Icon(Icons.access_time),
                        border: OutlineInputBorder())),
                const SizedBox(height: 10),
                TextField(
                    controller: docCtrl,
                    decoration: const InputDecoration(
                        labelText: 'Doctor (optional)',
                        prefixIcon: Icon(Icons.medical_services),
                        border: OutlineInputBorder())),
              ]),
            ),
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(ctx),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF6A5AE0)),
                onPressed: saving
                    ? null
                    : () async {
                        if (nameCtrl.text.trim().isEmpty) return;
                        setDlg(() => saving = true);
                        final existing = (_profile!['medications'] as List?)
                                ?.cast<Map<String, dynamic>>() ??
                            [];
                        final updated = [
                          ...existing,
                          {
                            'medicine': nameCtrl.text.trim(),
                            'dose': doseCtrl.text.trim(),
                            'time': timeCtrl.text.trim(),
                            'doctor': docCtrl.text.trim(),
                            'before_after_food': 'after',
                            'quantity_left': 30,
                          }
                        ];
                        final ok = await ApiService.updateProfileContacts(
                            Session.username, {'medications': updated});
                        if (!mounted) return;
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                            content: Text(ok
                                ? '✅ Medication saved!'
                                : '❌ Failed to save'),
                            backgroundColor: ok ? Colors.green : Colors.red));
                        if (ok) _load();
                      },
                child: saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                            color: Colors.white, strokeWidth: 2))
                    : const Text('Save', style: TextStyle(color: Colors.white)),
              ),
            ],
          ),
        );
      },
    );
  }

  // ── MEDICATIONS TAB ────────────────────────────────────────
  Widget _medsTab() {
    final meds =
        (_profile!['medications'] as List?)?.cast<Map<String, dynamic>>() ?? [];

    if (meds.isEmpty) {
      return Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.medication_outlined,
              color: Colors.white38, size: 56),
          const SizedBox(height: 16),
          const Text('No medications on record',
              style: TextStyle(color: Colors.white60, fontSize: 15)),
          const SizedBox(height: 8),
          const Text('Tap below to add medications.',
              style: TextStyle(color: Colors.white38, fontSize: 12)),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6A5AE0)),
            icon: const Icon(Icons.add, color: Colors.white),
            label: const Text('Add Medication',
                style: TextStyle(color: Colors.white)),
            onPressed: _showAddMedDialog,
          ),
        ]),
      );
    }

    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        child: SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6A5AE0),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12))),
            icon: const Icon(Icons.add, color: Colors.white),
            label: const Text('Add Medication',
                style: TextStyle(color: Colors.white)),
            onPressed: _showAddMedDialog,
          ),
        ),
      ),
      Expanded(
        child: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: meds.length,
          itemBuilder: (_, i) {
            final m = meds[i];
            final name =
                m['medicine'] as String? ?? m['name'] as String? ?? '—';
            final dose = m['dose'] as String? ?? m['dosage'] as String? ?? '—';
            final time = m['time'] as String? ?? '—';
            final purpose = m['purpose'] as String? ?? '';
            final qty = m['quantity_left'];
            final doctor = m['doctor'] as String? ?? '';
            final low = qty != null && (int.tryParse(qty.toString()) ?? 99) < 5;

            return Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.08),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                    color: low
                        ? Colors.red.withOpacity(0.4)
                        : Colors.white.withOpacity(0.1)),
              ),
              child: Row(children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                      color: Colors.green.withOpacity(0.15),
                      shape: BoxShape.circle),
                  child: const Icon(Icons.medication,
                      color: Colors.green, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Row(children: [
                        Text(name,
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 14)),
                        if (dose != '—') ...[
                          const SizedBox(width: 6),
                          Text('($dose)',
                              style: const TextStyle(
                                  color: Colors.white60, fontSize: 12)),
                        ],
                        if (low) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                                color: Colors.red.shade900,
                                borderRadius: BorderRadius.circular(8)),
                            child: const Text('LOW STOCK',
                                style: TextStyle(
                                    color: Colors.red,
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold)),
                          ),
                        ],
                      ]),
                      if (purpose.isNotEmpty) ...[
                        const SizedBox(height: 3),
                        Text(purpose,
                            style: const TextStyle(
                                color: Colors.white54, fontSize: 11)),
                      ],
                      const SizedBox(height: 6),
                      Wrap(spacing: 12, children: [
                        _inlineInfo(Icons.access_time, time),
                        if (qty != null)
                          _inlineInfo(Icons.inventory_2_outlined, 'Qty: $qty'),
                        if (doctor.isNotEmpty)
                          _inlineInfo(Icons.medical_services, doctor),
                      ]),
                    ])),
              ]),
            );
          },
        ),
      ),
    ]);
  }

  // ── CONTACTS TAB ───────────────────────────────────────────
  Widget _contactsTab() {
    final ec = (_profile!['emergency_contacts'] as List?)
            ?.cast<Map<String, dynamic>>() ??
        [];
    final c =
        (_profile!['contacts'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final all = [
      ...ec.map((x) => {...x, '_isEmergency': true}),
      ...c.map((x) => {...x, '_isEmergency': false}),
    ];

    if (all.isEmpty) {
      return _emptyState(Icons.contacts_outlined, 'No contacts saved',
          'Add emergency contacts via the Contacts page.');
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: all.length,
      itemBuilder: (_, i) {
        final c = all[i];
        final name = c['name'] as String? ?? 'Unknown';
        final phone = c['phone'] as String? ?? '—';
        final rel = c['relation'] as String? ?? '';
        final isEmerg = c['_isEmergency'] == true;
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
                color: isEmerg
                    ? Colors.red.withOpacity(0.4)
                    : Colors.white.withOpacity(0.1)),
          ),
          child: Row(children: [
            CircleAvatar(
              backgroundColor:
                  isEmerg ? Colors.red.shade900 : Colors.purple.shade700,
              child: Text(name[0].toUpperCase(),
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 12),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Row(children: [
                    Text(name,
                        style: const TextStyle(
                            color: Colors.white, fontWeight: FontWeight.bold)),
                    if (isEmerg) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                            color: Colors.red.shade900,
                            borderRadius: BorderRadius.circular(8)),
                        child: const Text('EMERGENCY',
                            style: TextStyle(
                                color: Colors.red,
                                fontSize: 9,
                                fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ]),
                  if (rel.isNotEmpty)
                    Text(rel,
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 12)),
                  Text(phone,
                      style:
                          const TextStyle(color: Colors.white60, fontSize: 12)),
                ])),
            const Icon(Icons.call, color: Colors.green, size: 20),
          ]),
        );
      },
    );
  }

  // ── SAFE ZONES TAB ─────────────────────────────────────────
  Widget _zonesTab() {
    final activeZones = (_profile!['active_zones'] as List?)
            ?.map((z) => z.toString())
            .toList() ??
        [];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionHeader('Camera Safe Zones', Icons.videocam,
            'Areas where falls are NOT alerted (bed/sofa)'),
        const SizedBox(height: 10),
        if (_zones.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.orange.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.orange.withOpacity(0.3)),
            ),
            child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Icon(Icons.warning_amber_outlined,
                        color: Colors.orange, size: 18),
                    SizedBox(width: 8),
                    Text('No safe zones defined',
                        style: TextStyle(
                            color: Colors.orange, fontWeight: FontWeight.bold)),
                  ]),
                  SizedBox(height: 8),
                  Text(
                    'Safe zones define where the patient sleeps (bed/sofa).\n'
                    'Falls inside these zones are suppressed.\n\n'
                    'They are set automatically when the monitoring brain runs,\n'
                    'or draw them manually via the desktop app.',
                    style: TextStyle(color: Colors.white60, fontSize: 12),
                  ),
                ]),
          )
        else
          ..._zones.map((z) {
            final type = z['type'] as String? ?? '—';
            final box = z['box'] as List? ?? [];
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green.withOpacity(0.3)),
              ),
              child: Row(children: [
                const Icon(Icons.check_circle, color: Colors.green, size: 20),
                const SizedBox(width: 12),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(type.toUpperCase(),
                          style: const TextStyle(
                              color: Colors.green,
                              fontWeight: FontWeight.bold)),
                      Text('Coordinates: $box',
                          style: const TextStyle(
                              color: Colors.white54, fontSize: 11)),
                    ])),
              ]),
            );
          }),
        const SizedBox(height: 24),
        _sectionHeader('Active Monitoring Rooms', Icons.home,
            'Rooms where movement is tracked'),
        const SizedBox(height: 10),
        activeZones.isEmpty
            ? const Text('No monitoring zones defined.',
                style: TextStyle(color: Colors.white54, fontSize: 13))
            : Wrap(
                spacing: 8,
                runSpacing: 8,
                children: activeZones
                    .map((z) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 8),
                          decoration: BoxDecoration(
                            color: Colors.purple.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                                color: Colors.purple.withOpacity(0.4)),
                          ),
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            const Icon(Icons.room,
                                color: Colors.purple, size: 14),
                            const SizedBox(width: 6),
                            Text(z,
                                style: const TextStyle(
                                    color: Colors.white70, fontSize: 13)),
                          ]),
                        ))
                    .toList(),
              ),
        const SizedBox(height: 80),
      ]),
    );
  }

  // ── HELPERS ────────────────────────────────────────────────
  Widget _errorView() => Center(
          child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.cloud_off, color: Colors.white38, size: 60),
          const SizedBox(height: 16),
          Text(_error!,
              style: const TextStyle(color: Colors.white60, fontSize: 14),
              textAlign: TextAlign.center),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
            style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6A5AE0)),
          ),
        ]),
      ));

  Widget _infoCard(String title, IconData icon, List<Widget> rows) => Card(
        color: Colors.white.withOpacity(0.1),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Icon(icon, color: Colors.purpleAccent, size: 18),
              const SizedBox(width: 8),
              Text(title,
                  style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 15)),
            ]),
            const SizedBox(height: 12),
            ...rows,
          ]),
        ),
      );

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(children: [
          SizedBox(
              width: 100,
              child: Text(label,
                  style: const TextStyle(color: Colors.white54, fontSize: 13))),
          Expanded(
              child: Text(value,
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.w500))),
        ]),
      );

  Widget _miniStat(String label, String value, Color color) => Expanded(
          child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(children: [
          Text(value,
              style: TextStyle(
                  color: color, fontSize: 20, fontWeight: FontWeight.bold)),
          Text(label,
              style: const TextStyle(color: Colors.white60, fontSize: 10),
              textAlign: TextAlign.center),
        ]),
      ));

  Widget _inlineInfo(IconData icon, String label) =>
      Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, color: Colors.white54, size: 12),
        const SizedBox(width: 3),
        Text(label,
            style: const TextStyle(color: Colors.white54, fontSize: 11)),
      ]);

  Widget _sectionHeader(String title, IconData icon, String sub) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: Colors.white70, size: 18),
          const SizedBox(width: 8),
          Text(title,
              style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 15)),
        ]),
        const SizedBox(height: 3),
        Text(sub, style: const TextStyle(color: Colors.white54, fontSize: 11)),
      ]);

  Widget _emptyState(IconData icon, String title, String sub) => Center(
          child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Icon(icon, color: Colors.white38, size: 56),
          const SizedBox(height: 16),
          Text(title,
              style: const TextStyle(color: Colors.white60, fontSize: 15),
              textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Text(sub,
              style: const TextStyle(color: Colors.white38, fontSize: 12),
              textAlign: TextAlign.center),
        ]),
      ));
}
