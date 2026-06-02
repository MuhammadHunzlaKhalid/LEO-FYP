"""
LEO — Caregiver Dashboard
==========================
Web dashboard to view patient data and videos stored in MongoDB.

Run:
    pip install flask pymongo
    python dashboard.py

Then open:  http://localhost:5000

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

import os
import json
from datetime   import datetime
from pathlib    import Path
from flask      import Flask, render_template_string, jsonify, send_file, abort, request
from pymongo    import MongoClient, DESCENDING
from bson       import ObjectId

# ─────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────
MONGO_URI  = "mongodb://localhost:27017"
DB_NAME    = "leo_fyp"
DATA_ROOT  = Path(__file__).parent / "data" / "patients"

app    = Flask(__name__)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db     = client[DB_NAME]


# ═══════════════════════════════════════════════════════════
#  HTML TEMPLATE
# ═══════════════════════════════════════════════════════════
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LEO — Caregiver Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', sans-serif;
    background: #0d0f1a;
    color: #c8cde8;
    min-height: 100vh;
  }

  /* ── TOP BAR ── */
  .topbar {
    background: #131625;
    border-bottom: 1px solid #2a2d45;
    padding: 14px 28px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: sticky; top: 0; z-index: 100;
  }
  .topbar h1 { font-size: 1.3rem; color: #00d4ff; letter-spacing: 2px; }
  .topbar span { color: #5a5f80; font-size: 0.8rem; }
  .db-status {
    margin-left: auto;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .db-ok   { background: #0a2e1a; color: #00e676; border: 1px solid #00e676; }
  .db-fail { background: #2e0a0a; color: #ff5252; border: 1px solid #ff5252; }

  /* ── LAYOUT ── */
  .layout { display: flex; height: calc(100vh - 57px); }

  /* ── SIDEBAR ── */
  .sidebar {
    width: 220px;
    background: #101220;
    border-right: 1px solid #1e2138;
    overflow-y: auto;
    flex-shrink: 0;
    padding: 12px 0;
  }
  .sidebar-title {
    padding: 6px 16px 10px;
    font-size: 0.68rem;
    letter-spacing: 2px;
    color: #3a3f60;
    text-transform: uppercase;
  }
  .patient-btn {
    width: 100%;
    text-align: left;
    padding: 10px 16px;
    background: none;
    border: none;
    color: #8890b8;
    cursor: pointer;
    font-size: 0.88rem;
    border-left: 3px solid transparent;
    transition: all 0.15s;
  }
  .patient-btn:hover   { background: #181b30; color: #c8cde8; }
  .patient-btn.active  {
    background: #181b30;
    color: #00d4ff;
    border-left-color: #00d4ff;
  }
  .patient-btn .age { float: right; color: #3a3f60; font-size: 0.75rem; }

  /* ── MAIN AREA ── */
  .main { flex: 1; overflow-y: auto; padding: 24px; }

  /* ── CARDS ── */
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }
  .card {
    background: #131625;
    border: 1px solid #1e2138;
    border-radius: 10px;
    padding: 16px;
  }
  .card .label { font-size: 0.7rem; color: #3a3f60; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #00d4ff; }
  .card .value.red   { color: #ff5252; }
  .card .value.green { color: #00e676; }
  .card .value.amber { color: #ffab40; }
  .card .sub   { font-size: 0.72rem; color: #5a5f80; margin-top: 4px; }

  /* ── SECTION ── */
  .section { margin-bottom: 28px; }
  .section h2 {
    font-size: 0.75rem;
    letter-spacing: 2px;
    color: #3a3f60;
    text-transform: uppercase;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2138;
  }

  /* ── TABLE ── */
  table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
  th {
    text-align: left;
    padding: 8px 12px;
    background: #0e1020;
    color: #3a3f60;
    font-size: 0.68rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    border-bottom: 1px solid #1e2138;
  }
  td {
    padding: 9px 12px;
    border-bottom: 1px solid #181b30;
    color: #9098c0;
    vertical-align: middle;
  }
  tr:hover td { background: #131830; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 600;
  }
  .badge-red    { background: #2e0a0a; color: #ff5252; }
  .badge-green  { background: #0a2e1a; color: #00e676; }
  .badge-amber  { background: #2e1a0a; color: #ffab40; }
  .badge-blue   { background: #0a1a2e; color: #40c4ff; }
  .badge-purple { background: #1a0a2e; color: #ce93d8; }

  .play-btn {
    background: #001a2e;
    border: 1px solid #0d47a1;
    color: #40c4ff;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.75rem;
    text-decoration: none;
  }
  .play-btn:hover { background: #0d47a1; color: #fff; }

  /* ── VIDEO MODAL ── */
  .modal-overlay {
    display: none;
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.85);
    z-index: 999;
    align-items: center;
    justify-content: center;
  }
  .modal-overlay.open { display: flex; }
  .modal {
    background: #131625;
    border: 1px solid #2a2d45;
    border-radius: 12px;
    padding: 20px;
    max-width: 760px;
    width: 95%;
  }
  .modal h3 { color: #00d4ff; margin-bottom: 12px; font-size: 0.9rem; }
  .modal video { width: 100%; border-radius: 8px; background: #000; }
  .modal-close {
    float: right;
    background: none;
    border: none;
    color: #5a5f80;
    font-size: 1.4rem;
    cursor: pointer;
    line-height: 1;
  }
  .modal-close:hover { color: #ff5252; }
  .modal-info { margin-top: 10px; font-size: 0.78rem; color: #5a5f80; }

  /* ── PROFILE GRID ── */
  .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .profile-item { background: #0e1020; border-radius: 8px; padding: 12px 16px; }
  .profile-item .key   { font-size: 0.68rem; color: #3a3f60; letter-spacing: 1px; text-transform: uppercase; }
  .profile-item .val   { font-size: 0.9rem; color: #c8cde8; margin-top: 4px; }

  .empty { color: #3a3f60; font-size: 0.82rem; padding: 16px; text-align: center; }

  /* ── TABS ── */
  .tabs { display: flex; gap: 4px; margin-bottom: 16px; }
  .tab-btn {
    padding: 7px 16px;
    background: none;
    border: 1px solid #1e2138;
    border-radius: 6px;
    color: #5a5f80;
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.15s;
  }
  .tab-btn.active { background: #1a2050; border-color: #00d4ff; color: #00d4ff; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  .welcome {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 60vh; color: #2a2d45; text-align: center;
  }
  .welcome h2 { font-size: 2rem; margin-bottom: 8px; }
  .welcome p  { font-size: 0.9rem; }

  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: #0d0f1a; }
  ::-webkit-scrollbar-thumb { background: #2a2d45; border-radius: 4px; }
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <h1>LEO</h1>
  <span>AI Home Assistant — Caregiver Dashboard</span>
  <div class="db-status {{ 'db-ok' if db_ok else 'db-fail' }}">
    {{ '● MongoDB Connected' if db_ok else '✕ MongoDB Offline' }}
  </div>
</div>

<div class="layout">

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-title">Patients</div>
    {% for p in patients %}
    <button class="patient-btn" onclick="loadPatient('{{ p.username }}')">
      {{ p.name }}
      <span class="age">{{ p.age }}y</span>
    </button>
    {% else %}
    <div class="empty">No patients yet</div>
    {% endfor %}
  </div>

  <!-- MAIN -->
  <div class="main" id="main">
    <div class="welcome">
      <h2>Select a Patient</h2>
      <p>Choose a patient from the sidebar to view their data and videos.</p>
    </div>
  </div>

</div>

<!-- VIDEO MODAL -->
<div class="modal-overlay" id="videoModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">×</button>
    <h3 id="videoTitle">Video</h3>
    <video id="videoPlayer" controls autoplay></video>
    <div class="modal-info" id="videoInfo"></div>
  </div>
</div>

<script>
let currentPatient = null;

function loadPatient(username) {
  currentPatient = username;
  document.querySelectorAll('.patient-btn').forEach(b => b.classList.remove('active'));
  event.target.closest('.patient-btn').classList.add('active');

  fetch('/api/patient/' + username)
    .then(r => r.json())
    .then(data => renderPatient(data));
}

function renderPatient(d) {
  const main = document.getElementById('main');

  // Summary cards
  const fallColor = d.summary.falls_today > 0 ? 'red' : 'green';
  const cards = `
    <div class="cards">
      <div class="card">
        <div class="label">Falls Today</div>
        <div class="value ${fallColor}">${d.summary.falls_today}</div>
        <div class="sub">Total: ${d.summary.total_falls}</div>
      </div>
      <div class="card">
        <div class="label">Sessions</div>
        <div class="value">${d.summary.total_sessions}</div>
        <div class="sub">monitoring runs</div>
      </div>
      <div class="card">
        <div class="label">Last Activity</div>
        <div class="value amber" style="font-size:1.1rem">${d.summary.last_activity || '—'}</div>
        <div class="sub">today</div>
      </div>
      <div class="card">
        <div class="label">Last Fall</div>
        <div class="value red" style="font-size:0.95rem">${d.summary.last_fall || 'None'}</div>
      </div>
    </div>`;

  // Tabs
  const tabs = `
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab(this,'tab-falls')">Falls & Videos</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-logs')">Activity Logs</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-sessions')">Sessions</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-profile')">Profile</button>
      <button class="tab-btn" onclick="switchTab(this,'tab-meds')">Medications</button>
    </div>`;

  // Falls table
  const fallRows = d.falls.map(f => `
    <tr>
      <td>${f.date} ${f.time}</td>
      <td><span class="badge badge-red">FALL</span></td>
      <td>${f.score}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${f.reason}">${f.reason}</td>
      <td>${f.posture}</td>
      <td>${f.clip_path
        ? `<a class="play-btn" href="#" onclick="playVideo('${f.clip_path}','Fall — ${f.date} ${f.time}','${f.reason}');return false;">▶ Play Clip</a>`
        : '<span style="color:#3a3f60">No clip</span>'}</td>
    </tr>`).join('') || `<tr><td colspan="6" class="empty">No falls recorded</td></tr>`;

  const fallsTab = `
    <div class="section">
      <h2>Fall Events</h2>
      <table>
        <thead><tr><th>Time</th><th>Event</th><th>Score</th><th>Reason</th><th>Posture</th><th>Video</th></tr></thead>
        <tbody>${fallRows}</tbody>
      </table>
    </div>`;

  // Recordings table
  const recRows = d.recordings.map(r => `
    <tr>
      <td>${r.date}</td>
      <td>${r.filename}</td>
      <td>${r.type === 'fall' ? '<span class="badge badge-red">Fall Clip</span>' : '<span class="badge badge-blue">Recording</span>'}</td>
      <td><a class="play-btn" href="#" onclick="playVideo('${r.path}','${r.filename}','${r.date}');return false;">▶ Play</a></td>
    </tr>`).join('') || `<tr><td colspan="4" class="empty">No videos saved</td></tr>`;

  const recsSection = `
    <div class="section">
      <h2>All Saved Videos</h2>
      <table>
        <thead><tr><th>Date</th><th>File</th><th>Type</th><th>Play</th></tr></thead>
        <tbody>${recRows}</tbody>
      </table>
    </div>`;

  // Logs table
  const catColor = {chat:'blue', fall:'red', medication:'green', emotion:'amber', emergency:'red', inactivity:'purple'};
  const logRows = d.logs.map(l => {
    const c = catColor[l.category] || 'blue';
    return `<tr>
      <td>${l.date} ${l.time}</td>
      <td><span class="badge badge-${c}">${l.category}</span></td>
      <td>${l.content}</td>
      <td><span class="badge badge-${l.severity==='critical'?'red':l.severity==='warning'?'amber':'blue'}">${l.severity}</span></td>
    </tr>`;
  }).join('') || `<tr><td colspan="4" class="empty">No logs yet</td></tr>`;

  const logsTab = `
    <div class="section">
      <h2>Activity Log</h2>
      <table>
        <thead><tr><th>Time</th><th>Category</th><th>Content</th><th>Severity</th></tr></thead>
        <tbody>${logRows}</tbody>
      </table>
    </div>`;

  // Sessions table
  const sessRows = d.sessions.map(s => `
    <tr>
      <td>${s.start_time}</td>
      <td>${s.end_time || '<span style="color:#00e676">Active</span>'}</td>
      <td>${s.fall_count}</td>
      <td><span class="badge badge-${s.status==='active'?'green':'blue'}">${s.status}</span></td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${s.recording_path||''}">${s.recording_path ? s.recording_path.split(/[\\/]/).pop() : '—'}</td>
    </tr>`).join('') || `<tr><td colspan="5" class="empty">No sessions yet</td></tr>`;

  const sessTab = `
    <div class="section">
      <h2>Monitoring Sessions</h2>
      <table>
        <thead><tr><th>Start</th><th>End</th><th>Falls</th><th>Status</th><th>Recording</th></tr></thead>
        <tbody>${sessRows}</tbody>
      </table>
    </div>`;

  // Profile
  const p = d.profile || {};
  const personal = p.personal || {};
  const routine  = p.routine  || {};
  const prfItems = [
    ['Name',       personal.name  || '—'],
    ['Age',        personal.age   || '—'],
    ['Wake Up',    routine.wake_up || '—'],
    ['Sleep',      routine.sleep   || '—'],
    ['Active Zones', (p.active_zones||[]).join(', ') || '—'],
  ];
  const profileTab = `
    <div class="section">
      <h2>Personal Info</h2>
      <div class="profile-grid">
        ${prfItems.map(([k,v])=>`<div class="profile-item"><div class="key">${k}</div><div class="val">${v}</div></div>`).join('')}
      </div>
    </div>
    <div class="section">
      <h2>Emergency Contacts</h2>
      <table>
        <thead><tr><th>Name</th><th>Relation</th><th>Phone</th></tr></thead>
        <tbody>
          ${(p.emergency_contacts||[]).map(c=>`<tr><td>${c.name}</td><td>${c.relation}</td><td>${c.phone}</td></tr>`).join('')
            || `<tr><td colspan="3" class="empty">None saved</td></tr>`}
        </tbody>
      </table>
    </div>`;

  // Medications
  const medRows = (d.profile?.medications || []).map(m => `
    <tr>
      <td>${m.medicine}</td>
      <td>${m.purpose || '—'}</td>
      <td>${m.dose || '—'}</td>
      <td>${m.time}</td>
      <td>${m.before_after_food || '—'}</td>
      <td>${m.quantity_left ?? '—'}</td>
      <td>${m.doctor || '—'}</td>
    </tr>`).join('') || `<tr><td colspan="7" class="empty">No medications saved</td></tr>`;

  const medsTab = `
    <div class="section">
      <h2>Medication Schedule</h2>
      <table>
        <thead><tr><th>Medicine</th><th>Purpose</th><th>Dose</th><th>Time</th><th>Food</th><th>Remaining</th><th>Doctor</th></tr></thead>
        <tbody>${medRows}</tbody>
      </table>
    </div>`;

  main.innerHTML = `
    <h2 style="color:#c8cde8;margin-bottom:20px;font-size:1.2rem">
      ${d.name} <span style="color:#3a3f60;font-size:0.8rem;margin-left:8px">Patient Overview</span>
    </h2>
    ${cards}
    ${tabs}
    <div id="tab-falls"    class="tab-panel active">${fallsTab}${recsSection}</div>
    <div id="tab-logs"     class="tab-panel">${logsTab}</div>
    <div id="tab-sessions" class="tab-panel">${sessTab}</div>
    <div id="tab-profile"  class="tab-panel">${profileTab}</div>
    <div id="tab-meds"     class="tab-panel">${medsTab}</div>
  `;
}

function switchTab(btn, tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

function playVideo(path, title, info) {
  document.getElementById('videoTitle').textContent = title;
  document.getElementById('videoInfo').textContent  = info;
  document.getElementById('videoPlayer').src = '/video?path=' + encodeURIComponent(path);
  document.getElementById('videoModal').classList.add('open');
}

function closeModal() {
  document.getElementById('videoModal').classList.remove('open');
  document.getElementById('videoPlayer').pause();
  document.getElementById('videoPlayer').src = '';
}

document.getElementById('videoModal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _str_id(doc: dict) -> dict:
    """Convert ObjectId to string for JSON serialisation."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

def _fmt_dt(dt) -> str:
    if dt is None: return None
    if isinstance(dt, datetime): return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

def _get_recordings(patient: str) -> list[dict]:
    """Scan local video folder and return all .avi files for this patient."""
    folder = DATA_ROOT / patient / "videos"
    if not folder.exists():
        return []
    result = []
    for date_dir in sorted(folder.iterdir(), reverse=True):
        if not date_dir.is_dir(): continue
        for vid in sorted(date_dir.glob("*.avi"), reverse=True):
            result.append({
                "date":     date_dir.name,
                "filename": vid.name,
                "path":     str(vid),
                "type":     "fall" if vid.name.startswith("fall_") else "recording",
            })
    return result


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    try:
        db_ok    = True
        raw_pts  = list(db.patients.find({}, {"username":1,"profile.personal":1}))
        patients = []
        for p in raw_pts:
            personal = p.get("profile", {}).get("personal", {})
            patients.append({
                "username": p["username"],
                "name":     personal.get("name", p["username"]),
                "age":      personal.get("age", "?"),
            })
        patients.sort(key=lambda x: x["name"])
    except Exception:
        db_ok    = False
        patients = []

    return render_template_string(HTML, patients=patients, db_ok=db_ok)


@app.route("/api/patient/<username>")
def api_patient(username):
    try:
        # Profile
        pdoc    = db.patients.find_one({"username": username})
        profile = pdoc["profile"] if pdoc else {}
        personal = profile.get("personal", {})

        # Summary
        today = datetime.now().strftime("%Y-%m-%d")
        summary = {
            "falls_today":    db.fall_events.count_documents({"patient": username, "date": today}),
            "total_falls":    db.fall_events.count_documents({"patient": username}),
            "total_sessions": db.sessions.count_documents({"patient": username}),
            "last_activity":  None,
            "last_fall":      None,
        }
        last_log  = db.activity_logs.find_one({"patient": username}, sort=[("timestamp", DESCENDING)])
        last_fall = db.fall_events.find_one({"patient": username},   sort=[("timestamp", DESCENDING)])
        if last_log:  summary["last_activity"] = _fmt_dt(last_log.get("timestamp"))
        if last_fall: summary["last_fall"]      = _fmt_dt(last_fall.get("timestamp"))

        # Falls
        falls = []
        for f in db.fall_events.find({"patient": username}).sort("timestamp", DESCENDING).limit(50):
            falls.append({
                "date":      f.get("date",""),
                "time":      f.get("time",""),
                "score":     f.get("score", 0),
                "reason":    f.get("reason",""),
                "posture":   f.get("posture",""),
                "state":     f.get("state",""),
                "clip_path": f.get("clip_path"),
            })

        # Logs
        logs = []
        for l in db.activity_logs.find({"patient": username}).sort("timestamp", DESCENDING).limit(100):
            logs.append({
                "date":     l.get("date",""),
                "time":     l.get("time",""),
                "category": l.get("category",""),
                "content":  l.get("content",""),
                "severity": l.get("severity","info"),
            })

        # Sessions
        sessions = []
        for s in db.sessions.find({"patient": username}).sort("start_time", DESCENDING).limit(20):
            sessions.append({
                "start_time":     _fmt_dt(s.get("start_time")),
                "end_time":       _fmt_dt(s.get("end_time")),
                "fall_count":     s.get("fall_count", 0),
                "status":         s.get("status",""),
                "recording_path": s.get("recording_path",""),
            })

        # Recordings from local disk
        recordings = _get_recordings(username)

        return jsonify({
            "username":    username,
            "name":        personal.get("name", username),
            "profile":     profile,
            "summary":     summary,
            "falls":       falls,
            "logs":        logs,
            "sessions":    sessions,
            "recordings":  recordings,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/video")
def serve_video():
    """Stream a local .avi file to the browser."""
    path = request.args.get("path", "")
    if not path:
        abort(400)
    p = Path(path)
    if not p.exists() or p.suffix.lower() not in (".avi", ".mp4", ".mkv"):
        abort(404)
    return send_file(str(p), mimetype="video/x-msvideo")


# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  LEO Caregiver Dashboard")
    print("  Open:  http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
