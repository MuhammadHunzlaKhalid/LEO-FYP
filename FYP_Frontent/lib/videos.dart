import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';
import 'leo_fab.dart';

// ── Conditional import: web → dart:html, mobile → stub ───────
import 'video_platform_stub.dart'
    // ignore: uri_does_not_exist
    if (dart.library.html) 'video_platform_web.dart' as vp;

class VideosPage extends StatefulWidget {
  const VideosPage({Key? key}) : super(key: key);
  @override
  State<VideosPage> createState() => _VideosPageState();
}

class _VideosPageState extends State<VideosPage>
    with SingleTickerProviderStateMixin {
  late TabController _tab;
  List<Map<String, dynamic>> _all   = [];
  List<Map<String, dynamic>> _falls = [];
  List<Map<String, dynamic>> _recs  = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 3, vsync: this);
    _load();
  }

  @override
  void dispose() { _tab.dispose(); super.dispose(); }

  Future<void> _load() async {
    setState(() => _loading = true);
    final videos = await ApiService.getVideos(Session.username);
    if (!mounted) return;
    setState(() {
      _loading = false;
      _all   = videos;
      _falls = videos.where((v) => v['type'] == 'fall').toList();
      _recs  = videos.where((v) => v['type'] != 'fall').toList();
    });
  }

  void _showPlayer(Map<String, dynamic> v) {
    final path      = v['path'] as String? ?? '';
    if (path.isEmpty) return;
    final streamUrl = ApiService.videoStreamUrl(path);
    final name      = v['filename'] as String? ?? 'Video';
    final isFall    = v['type'] == 'fall';
    final date      = v['date']     as String? ?? '';
    final sizeMb    = v['size_mb'];
    final viewType  = 'leo-video-${streamUrl.hashCode}';

    showDialog(
      context: context,
      barrierColor: Colors.black87,
      builder: (_) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(12),
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF110031),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            // Title bar
            Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
              decoration: BoxDecoration(
                color: isFall ? Colors.red.shade900 : const Color(0xFF1a0040),
                borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16)),
              ),
              child: Row(children: [
                Icon(isFall ? Icons.warning_amber_rounded : Icons.videocam,
                    color: Colors.white, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text(name,
                    style: const TextStyle(color: Colors.white,
                        fontWeight: FontWeight.bold),
                    maxLines: 1, overflow: TextOverflow.ellipsis)),
                IconButton(
                    icon: const Icon(Icons.close, color: Colors.white),
                    onPressed: () => Navigator.pop(context)),
              ]),
            ),

            // Video player (web: real video, mobile: placeholder)
            SizedBox(
              height: 240,
              child: vp.buildVideoPlayer(streamUrl, viewType),
            ),

            // URL — always selectable so user can copy/open
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(8)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  const Text('Stream URL (tap & copy):',
                      style: TextStyle(color: Colors.white54, fontSize: 10)),
                  const SizedBox(height: 4),
                  SelectableText(streamUrl,
                      style: const TextStyle(
                          color: Colors.lightBlueAccent, fontSize: 11)),
                ]),
              ),
            ),

            // Open in browser button
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
              child: SizedBox(width: double.infinity,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white30),
                      padding: const EdgeInsets.symmetric(vertical: 10)),
                  icon: const Icon(Icons.open_in_browser, size: 16),
                  label: const Text('Open in Browser Tab'),
                  onPressed: () {
                    Navigator.pop(context);
                    vp.openInBrowser(streamUrl);
                  },
                )),
            ),

            // Meta chips
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(children: [
                _chip(Icons.calendar_today, date),
                const SizedBox(width: 6),
                _chip(Icons.storage, '$sizeMb MB'),
                const SizedBox(width: 6),
                _chip(isFall ? Icons.warning : Icons.videocam,
                    isFall ? 'Fall Clip' : 'Recording'),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _chip(IconData icon, String label) => Expanded(
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(20)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, color: Colors.white54, size: 11),
        const SizedBox(width: 4),
        Flexible(child: Text(label, style: const TextStyle(
            color: Colors.white60, fontSize: 10),
            maxLines: 1, overflow: TextOverflow.ellipsis)),
      ]),
    ),
  );

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
        child: SafeArea(child: Column(children: [
          // Red AppBar
          Container(
            color: const Color(0xFFB71C1C),
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 8, 16, 0),
                child: Row(children: [
                  IconButton(
                      icon: const Icon(Icons.arrow_back_ios_new,
                          color: Colors.white),
                      onPressed: () => Navigator.pop(context)),
                  Expanded(child: Text('Saved Videos (${_all.length})',
                      style: const TextStyle(color: Colors.white,
                          fontSize: 18, fontWeight: FontWeight.w600))),
                  IconButton(
                      icon: const Icon(Icons.refresh, color: Colors.white),
                      onPressed: _load),
                ]),
              ),
              TabBar(
                controller: _tab,
                indicatorColor: Colors.white,
                labelColor: Colors.white,
                unselectedLabelColor: Colors.white60,
                tabs: [
                  Tab(text: 'All (${_all.length})'),
                  Tab(text: '🚨 Falls (${_falls.length})'),
                  Tab(text: '📹 Clips (${_recs.length})'),
                ],
              ),
            ]),
          ),

          // Info bar
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            color: Colors.black.withOpacity(0.25),
            child: Row(children: const [
              Icon(Icons.info_outline, color: Colors.white54, size: 14),
              SizedBox(width: 8),
              Expanded(child: Text(
                  'Videos saved by monitoring brain · Tap to play',
                  style: TextStyle(color: Colors.white60, fontSize: 11))),
            ]),
          ),

          Expanded(child: _loading
              ? const Center(child: CircularProgressIndicator(
                  color: Colors.white))
              : TabBarView(controller: _tab, children: [
                  _buildList(_all),
                  _buildList(_falls),
                  _buildList(_recs),
                ])),
        ])),
      ),
    );
  }

  Widget _buildList(List<Map<String, dynamic>> vids) {
    if (vids.isEmpty) {
      return Center(child: Column(
          mainAxisAlignment: MainAxisAlignment.center, children: [
        const Icon(Icons.video_library_outlined,
            color: Colors.white38, size: 64),
        const SizedBox(height: 16),
        const Text('No recordings yet',
            style: TextStyle(color: Colors.white60, fontSize: 16)),
        const SizedBox(height: 8),
        const Text(
            'Start the monitoring brain to begin recording.\n'
            'Run:  python final_monitering_brain.py',
            style: TextStyle(color: Colors.white38, fontSize: 12),
            textAlign: TextAlign.center),
        const SizedBox(height: 20),
        ElevatedButton.icon(
          onPressed: _load,
          icon: const Icon(Icons.refresh),
          label: const Text('Refresh'),
          style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white24,
              foregroundColor: Colors.white),
        ),
      ]));
    }

    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final v in vids) {
      grouped.putIfAbsent(v['date'] as String? ?? 'Unknown', () => []).add(v);
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: grouped.length,
        itemBuilder: (_, i) {
          final date    = grouped.keys.elementAt(i);
          final dayVids = grouped[date]!;
          return Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
            Padding(
              padding: EdgeInsets.only(bottom: 8, top: i == 0 ? 0 : 16),
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(20)),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.calendar_today,
                      color: Colors.white70, size: 12),
                  const SizedBox(width: 6),
                  Text(date, style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold,
                      fontSize: 13)),
                  const SizedBox(width: 8),
                  Text('${dayVids.length} clip${dayVids.length == 1 ? "" : "s"}',
                      style: const TextStyle(
                          color: Colors.white60, fontSize: 11)),
                ]),
              ),
            ),
            ...dayVids.map(_videoCard),
          ]);
        },
      ),
    );
  }

  Widget _videoCard(Map<String, dynamic> v) {
    final isFall  = v['type'] == 'fall';
    final name    = v['filename'] as String? ?? 'video.avi';
    final sizeMb  = v['size_mb'] as num?;
    final path    = v['path'] as String? ?? '';
    final thumbUrl = path.isNotEmpty
        ? ApiService.videoThumbnailUrl(path) : null;

    return GestureDetector(
      onTap: () => _showPlayer(v),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.1),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isFall
              ? Colors.red.withOpacity(0.5)
              : Colors.white.withOpacity(0.1)),
        ),
        child: Row(children: [
          // Thumbnail
          ClipRRect(
            borderRadius: const BorderRadius.horizontal(
                left: Radius.circular(14)),
            child: Stack(children: [
              thumbUrl != null
                  ? Image.network(thumbUrl,
                      width: 100, height: 72, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _placeholder(isFall))
                  : _placeholder(isFall),
              Positioned.fill(child: Center(child: Container(
                  width: 30, height: 30,
                  decoration: const BoxDecoration(
                      color: Colors.black54, shape: BoxShape.circle),
                  child: const Icon(Icons.play_arrow,
                      color: Colors.white, size: 18)))),
            ]),
          ),

          // Info
          Expanded(child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                      color: isFall ? Colors.red : Colors.blue,
                      borderRadius: BorderRadius.circular(8)),
                  child: Text(isFall ? 'FALL' : 'REC',
                      style: const TextStyle(color: Colors.white,
                          fontSize: 9, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 6),
                if (sizeMb != null)
                  Text('${sizeMb} MB', style: const TextStyle(
                      color: Colors.white54, fontSize: 10)),
              ]),
              const SizedBox(height: 4),
              Text(name, style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w600,
                  fontSize: 12),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              const Text('Tap to play', style: TextStyle(
                  color: Colors.white38, fontSize: 10)),
            ]),
          )),

          const Padding(
            padding: EdgeInsets.only(right: 12),
            child: Icon(Icons.play_circle_filled,
                color: Colors.white54, size: 28)),
        ]),
      ),
    );
  }

  Widget _placeholder(bool isFall) => Container(
    width: 100, height: 72,
    color: isFall
        ? Colors.red.withOpacity(0.2) : Colors.blue.withOpacity(0.2),
    child: Icon(isFall ? Icons.warning : Icons.videocam,
        color: isFall ? Colors.red : Colors.blue, size: 32),
  );
}
