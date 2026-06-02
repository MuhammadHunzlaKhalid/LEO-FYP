# import subprocess, sys, time, os, webbrowser, socket
# from pathlib import Path

# # ── CONFIGURE ─────────────────────────────────────────────────
# BACKEND_DIR  = Path(r"D:\Python\FYP\FYP_Connected\FYP_Backend")
# FRONTEND_DIR = Path(r"D:\Python\FYP\FYP_Connected\FYP_Frontent")
# PYTHON       = sys.executable
# MONGOD       = r"C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
# MONGO_DBPATH = r"C:\data\db"
# BACKEND_PORT   = 8000
# DASHBOARD_PORT = 5000

# C="\033[96m";G="\033[92m";Y="\033[93m";R="\033[91m";W="\033[97m";D="\033[2m";X="\033[0m"
# def p(m,c=""): print(f"{c}{m}{X}",flush=True)
# def ok(m):     p(f"  [OK]  {m}",G)
# def wait(m):   p(f"  ...   {m}",D)
# def bad(m):    p(f"  [!!]  {m}",R)
# def go(m):     p(f"  -->   {m}",C)

# NW = subprocess.CREATE_NO_WINDOW  # hides terminal window

# def bg(args, cwd):
#     """Run silently — no window at all."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         stdout=subprocess.DEVNULL,
#         stderr=subprocess.DEVNULL,
#         creationflags=NW,
#     )

# def gui(args, cwd):
#     """Launch a GUI app — no terminal, but its own window opens."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
#     )

# def alive(port):
#     try:
#         socket.create_connection(("localhost", port), 1).close()
#         return True
#     except: return False

# def wait_for(port, name, timeout=40):
#     wait(f"Waiting for {name}...")
#     for i in range(timeout):
#         if alive(port): return True
#         time.sleep(1)
#     return False

# def main():
#     os.system("cls")
#     p("╔════════════════════════════════════════╗",C)
#     p("║  LEO  —  FYP 2024-25  System Launcher ║",C)
#     p("╚════════════════════════════════════════╝\n",C)

#     # 1. MongoDB
#     p("[1/5]  MongoDB",C)
#     if alive(27017): ok("Already running")
#     else:
#         go("Starting MongoDB (background)")
#         Path(MONGO_DBPATH).mkdir(parents=True, exist_ok=True)
#         bg([MONGOD, "--dbpath", MONGO_DBPATH, "--quiet"], BACKEND_DIR)
#         if wait_for(27017, "MongoDB", 15): ok("MongoDB started")
#         else: bad("MongoDB slow — continuing")

#     # 2. FastAPI Backend — starts AFTER everything else, runs IN this terminal
#     _backend_ready = alive(BACKEND_PORT)

#     # 3. Flask Dashboard
#     p("\n[3/5]  Dashboard",C)
#     if alive(DASHBOARD_PORT): ok("Already running")
#     else:
#         go("Starting dashboard (background, no window)")
#         bg([PYTHON, "dashboard.py"], BACKEND_DIR)
#         if wait_for(DASHBOARD_PORT, "Dashboard", 12):
#             ok(f"Dashboard ready  →  localhost:{DASHBOARD_PORT}")
#         else: bad("Dashboard slow")

#     # 4. LEO Desktop App  (GUI only — no terminal window)
#     p("\n[4/5]  LEO Desktop App",C)
#     leo = BACKEND_DIR / "leo_app.py"
#     if not leo.exists():
#         bad(f"leo_app.py not found in {BACKEND_DIR}")
#     else:
#         go("Opening LEO Desktop App (no terminal)")
#         gui([PYTHON, "leo_app.py"], BACKEND_DIR)
#         ok("LEO Desktop App opened")
#     time.sleep(2)

#     # 5. Flutter
#     p("\n[5/5]  Flutter Web App",C)
#     if not FRONTEND_DIR.exists():
#         bad(f"Flutter folder not found: {FRONTEND_DIR}")
#     else:
#         go("Starting Flutter — Chrome opens automatically (~30s)")
#         gui(["flutter", "run", "-d", "chrome", "--no-color"],
#             FRONTEND_DIR)
#         ok("Flutter started")

#     p(f"\n{'═'*42}",D)
#     p("  ALL SERVICES RUNNING  🚀",G)
#     p(f"{'═'*42}",D)
#     p(f"\n  Dashboard →  http://localhost:{DASHBOARD_PORT}",W)
#     p(f"  Flutter   →  Opens in Chrome automatically",W)
#     p(f"  LEO App   →  Opened in its own window",W)
#     p(f"  Backend   →  Starting now (logs below)\n",W)
#     p("  Ctrl+C to stop backend",Y)

#     time.sleep(1)
#     try: webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
#     except: pass

#     if _backend_ready:
#         ok("Backend already running")
#         input("\n  Press Enter to close this window...\n")
#     else:
#         p("\n  ── Backend logs ──────────────────────────",D)
#         # Run backend IN this terminal (blocking — shows all logs)
#         subprocess.run(
#             [PYTHON, "-m", "uvicorn", "main:app",
#              "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
#             cwd=str(BACKEND_DIR)
#         )

# if __name__ == "__main__":
#     main()








# import subprocess, sys, time, os, webbrowser, socket
# from pathlib import Path

# # ── CONFIGURE ─────────────────────────────────────────────────
# BACKEND_DIR  = Path(r"D:\Python\FYP\FYP_Connected\FYP_Backend")
# FRONTEND_DIR = Path(r"D:\Python\FYP\FYP_Connected\FYP_Frontent")
# PYTHON       = sys.executable
# MONGOD       = r"C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
# MONGO_DBPATH = r"C:\data\db"
# BACKEND_PORT   = 8000
# DASHBOARD_PORT = 5000

# C="\033[96m";G="\033[92m";Y="\033[93m";R="\033[91m";W="\033[97m";D="\033[2m";X="\033[0m"
# def p(m,c=""): print(f"{c}{m}{X}",flush=True)
# def ok(m):     p(f"  [OK]  {m}",G)
# def wait(m):   p(f"  ...   {m}",D)
# def bad(m):    p(f"  [!!]  {m}",R)
# def go(m):     p(f"  -->   {m}",C)

# NW = subprocess.CREATE_NO_WINDOW  # hides terminal window

# def bg(args, cwd):
#     """Run silently — no window at all."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         stdout=subprocess.DEVNULL,
#         stderr=subprocess.DEVNULL,
#         creationflags=NW,
#     )

# def gui(args, cwd):
#     """Launch a GUI app — no terminal, but its own window opens."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
#     )

# def alive(port):
#     try:
#         socket.create_connection(("localhost", port), 1).close()
#         return True
#     except: return False

# def wait_for(port, name, timeout=40):
#     wait(f"Waiting for {name}...")
#     for i in range(timeout):
#         if alive(port): return True
#         time.sleep(1)
#     return False

# def main():
#     os.system("cls")
#     p("╔════════════════════════════════════════╗",C)
#     p("║  LEO  —  FYP 2024-25  System Launcher ║",C)
#     p("╚════════════════════════════════════════╝\n",C)

#     # 1. MongoDB
#     p("[1/5]  MongoDB",C)
#     if alive(27017): ok("Already running")
#     else:
#         go("Starting MongoDB (background)")
#         Path(MONGO_DBPATH).mkdir(parents=True, exist_ok=True)
#         bg([MONGOD, "--dbpath", MONGO_DBPATH, "--quiet"], BACKEND_DIR)
#         if wait_for(27017, "MongoDB", 15): ok("MongoDB started")
#         else: bad("MongoDB slow — continuing")

#     # 2. FastAPI Backend — starts AFTER everything else, runs IN this terminal
#     _backend_ready = alive(BACKEND_PORT)

#     # 3. Flask Dashboard
#     p("\n[3/5]  Dashboard",C)
#     if alive(DASHBOARD_PORT): ok("Already running")
#     else:
#         go("Starting dashboard (background, no window)")
#         bg([PYTHON, "dashboard.py"], BACKEND_DIR)
#         if wait_for(DASHBOARD_PORT, "Dashboard", 12):
#             ok(f"Dashboard ready  →  localhost:{DASHBOARD_PORT}")
#         else: bad("Dashboard slow")

#     # 4. LEO Desktop App  (GUI only — no terminal window)
#     p("\n[4/5]  LEO Desktop App",C)
#     leo = BACKEND_DIR / "leo_app.py"
#     if not leo.exists():
#         bad(f"leo_app.py not found in {BACKEND_DIR}")
#     else:
#         go("Opening LEO Desktop App (no terminal)")
#         gui([PYTHON, "leo_app.py"], BACKEND_DIR)
#         ok("LEO Desktop App opened")
#     time.sleep(2)

#     # 5. Flutter
#     p("\n[5/5]  Flutter Web App",C)
#     if not FRONTEND_DIR.exists():
#         bad(f"Flutter folder not found: {FRONTEND_DIR}")
#     else:
#         go("Starting Flutter — Chrome opens automatically (~30s)")
#         gui(["flutter", "run", "-d", "chrome", "--no-color"],
#             FRONTEND_DIR)
#         ok("Flutter started")

#     p(f"\n{'═'*42}",D)
#     p("  ALL SERVICES RUNNING  🚀",G)
#     p(f"{'═'*42}",D)
#     p(f"\n  Dashboard →  http://localhost:{DASHBOARD_PORT}",W)
#     p(f"  Flutter   →  Opens in Chrome automatically",W)
#     p(f"  LEO App   →  Opened in its own window",W)
#     p(f"  Backend   →  Starting now (logs below)\n",W)
#     p("  Ctrl+C to stop backend",Y)

#     time.sleep(1)
#     try: webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
#     except: pass

#     if _backend_ready:
#         ok("Backend already running")
#         input("\n  Press Enter to close this window...\n")
#     else:
#         p("\n  ── Backend logs ──────────────────────────",D)
#         # Run backend IN this terminal (blocking — shows all logs)
#         subprocess.run(
#             [PYTHON, "-m", "uvicorn", "main:app",
#              "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
#             cwd=str(BACKEND_DIR)
#         )

# if __name__ == "__main__":
#     main()










# import subprocess, sys, time, os, webbrowser, socket
# from pathlib import Path

# # ── CONFIGURE ─────────────────────────────────────────────────
# BACKEND_DIR  = Path(r"D:\Python\FYP\FYP_Connected\FYP_Backend")
# FRONTEND_DIR = Path(r"D:\Python\FYP\FYP_Connected\FYP_Frontent")
# PYTHON       = sys.executable
# MONGOD       = r"C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
# MONGO_DBPATH = r"C:\data\db"
# BACKEND_PORT   = 8000
# DASHBOARD_PORT = 5000

# C="\033[96m";G="\033[92m";Y="\033[93m";R="\033[91m";W="\033[97m";D="\033[2m";X="\033[0m"
# def p(m,c=""): print(f"{c}{m}{X}",flush=True)
# def ok(m):     p(f"  [OK]  {m}",G)
# def wait(m):   p(f"  ...   {m}",D)
# def bad(m):    p(f"  [!!]  {m}",R)
# def go(m):     p(f"  -->   {m}",C)

# NW = subprocess.CREATE_NO_WINDOW  # hides terminal window

# def bg(args, cwd):
#     """Run silently — no window at all."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         stdout=subprocess.DEVNULL,
#         stderr=subprocess.DEVNULL,
#         creationflags=NW,
#     )

# def gui(args, cwd):
#     """Launch a GUI app — no terminal, but its own window opens."""
#     return subprocess.Popen(
#         args, cwd=str(cwd),
#         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
#     )

# def alive(port):
#     try:
#         socket.create_connection(("localhost", port), 1).close()
#         return True
#     except: return False

# def wait_for(port, name, timeout=40):
#     wait(f"Waiting for {name}...")
#     for i in range(timeout):
#         if alive(port): return True
#         time.sleep(1)
#     return False

# def main():
#     os.system("cls")
#     p("╔════════════════════════════════════════╗",C)
#     p("║  LEO  —  FYP 2024-25  System Launcher ║",C)
#     p("╚════════════════════════════════════════╝\n",C)

#     # 1. MongoDB
#     p("[1/5]  MongoDB",C)
#     if alive(27017): ok("Already running")
#     else:
#         go("Starting MongoDB (background)")
#         Path(MONGO_DBPATH).mkdir(parents=True, exist_ok=True)
#         bg([MONGOD, "--dbpath", MONGO_DBPATH, "--quiet"], BACKEND_DIR)
#         if wait_for(27017, "MongoDB", 15): ok("MongoDB started")
#         else: bad("MongoDB slow — continuing")

#     # 2. FastAPI Backend — starts AFTER everything else, runs IN this terminal
#     _backend_ready = alive(BACKEND_PORT)

#     # 3. Flask Dashboard
#     p("\n[3/5]  Dashboard",C)
#     if alive(DASHBOARD_PORT): ok("Already running")
#     else:
#         go("Starting dashboard (background, no window)")
#         bg([PYTHON, "dashboard.py"], BACKEND_DIR)
#         if wait_for(DASHBOARD_PORT, "Dashboard", 12):
#             ok(f"Dashboard ready  →  localhost:{DASHBOARD_PORT}")
#         else: bad("Dashboard slow")

#     # 4. LEO Desktop App  (GUI only — no terminal window)
#     p("\n[4/5]  LEO Desktop App",C)
#     leo = BACKEND_DIR / "leo_app.py"
#     if not leo.exists():
#         bad(f"leo_app.py not found in {BACKEND_DIR}")
#     else:
#         go("Opening LEO Desktop App (no terminal)")
#         gui([PYTHON, "leo_app.py"], BACKEND_DIR)
#         ok("LEO Desktop App opened")
#     time.sleep(2)

#     # 5. Flutter
#     p("\n[5/5]  Flutter Web App",C)
#     if not FRONTEND_DIR.exists():
#         bad(f"Flutter folder not found: {FRONTEND_DIR}")
#     else:
#         go("Starting Flutter — Chrome opens automatically (~30s)")
#         gui(["flutter", "run", "-d", "chrome", "--no-color"],
#             FRONTEND_DIR)
#         ok("Flutter started")

#     p(f"\n{'═'*42}",D)
#     p("  ALL SERVICES RUNNING  🚀",G)
#     p(f"{'═'*42}",D)
#     p(f"\n  Dashboard →  http://localhost:{DASHBOARD_PORT}",W)
#     p(f"  Flutter   →  Opens in Chrome automatically",W)
#     p(f"  LEO App   →  Opened in its own window",W)
#     p(f"  Backend   →  Starting now (logs below)\n",W)
#     p("  Ctrl+C to stop backend",Y)

#     time.sleep(1)
#     try: webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
#     except: pass

#     if _backend_ready:
#         ok("Backend already running")
#         input("\n  Press Enter to close this window...\n")
#     else:
#         p("\n  ── Backend logs ──────────────────────────",D)
#         # Run backend IN this terminal (blocking — shows all logs)
#         subprocess.run(
#             [PYTHON, "-m", "uvicorn", "main:app",
#              "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
#             cwd=str(BACKEND_DIR)
#         )

# if __name__ == "__main__":
#     main()











import subprocess, sys, time, os, webbrowser, socket
from pathlib import Path

# ── CONFIGURE ─────────────────────────────────────────────────
BACKEND_DIR  = Path(r"D:\Python\FYP\FYP_Connected\FYP_Backend")
FRONTEND_DIR = Path(r"D:\Python\FYP\FYP_Connected\FYP_Frontent")
PYTHON       = sys.executable
MONGOD       = r"C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe"
MONGO_DBPATH = r"C:\data\db"
BACKEND_PORT   = 8000
DASHBOARD_PORT = 5000

C="\033[96m";G="\033[92m";Y="\033[93m";R="\033[91m";W="\033[97m";D="\033[2m";X="\033[0m"
def p(m,c=""): print(f"{c}{m}{X}",flush=True)
def ok(m):     p(f"  [OK]  {m}",G)
def wait(m):   p(f"  ...   {m}",D)
def bad(m):    p(f"  [!!]  {m}",R)
def go(m):     p(f"  -->   {m}",C)

NW = subprocess.CREATE_NO_WINDOW

def bg(args, cwd):
    """Run silently — no window at all."""
    return subprocess.Popen(
        args, cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=NW,
    )

def terminal(args, cwd, title="LEO Backend"):
    """
    Open in a GUARANTEED new PERMANENT visible terminal window.
    Uses Windows built-in 'start' command via shell=True.
    Terminal will NOT close or hide — stays open forever (or until user closes it).
    """
    inner = subprocess.list2cmdline([str(a) for a in args])
    # start "Title" cmd /k <command> & pause
    # /k = keep window open after command
    # & pause = add pause so user MUST press a key to close it
    cmd = f'start "{title}" cmd /k "{inner} & pause"'
    subprocess.Popen(cmd, cwd=str(cwd), shell=True)

def gui(args, cwd):
    """Launch a GUI app — no terminal, but its own window opens."""
    return subprocess.Popen(
        args, cwd=str(cwd),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )

def alive(port):
    try:
        socket.create_connection(("localhost", port), 1).close()
        return True
    except: return False

def wait_for(port, name, timeout=40):
    wait(f"Waiting for {name}...")
    for i in range(timeout):
        if alive(port): return True
        time.sleep(1)
    return False

def main():
    os.system("cls")
    p("╔════════════════════════════════════════╗",C)
    p("║  LEO  —  FYP 2024-25  System Launcher ║",C)
    p("╚════════════════════════════════════════╝\n",C)

    # 1. MongoDB — background (hidden)
    p("[1/5]  MongoDB",C)
    if alive(27017): ok("Already running")
    else:
        go("Starting MongoDB (background)")
        Path(MONGO_DBPATH).mkdir(parents=True, exist_ok=True)
        bg([MONGOD, "--dbpath", MONGO_DBPATH, "--quiet"], BACKEND_DIR)
        if wait_for(27017, "MongoDB", 15): ok("MongoDB started")
        else: bad("MongoDB slow — continuing")

    # 2. FastAPI Backend — VISIBLE new terminal window
    p("\n[2/5]  FastAPI Backend",C)
    if alive(BACKEND_PORT): ok("Already running")
    else:
        go("Opening Backend in NEW terminal window...")
        terminal(
            [PYTHON, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--reload"],
            BACKEND_DIR,
            title="LEO  FastAPI Backend  :8000"
        )
        if wait_for(BACKEND_PORT, "Backend", 35):
            ok(f"Backend ready  →  localhost:{BACKEND_PORT}")
        else: bad("Backend failed — check the terminal window for errors")

    # 3. Flask Dashboard — background (hidden)
    p("\n[3/5]  Dashboard",C)
    if alive(DASHBOARD_PORT): ok("Already running")
    else:
        go("Starting dashboard (background, no window)")
        bg([PYTHON, "dashboard.py"], BACKEND_DIR)
        if wait_for(DASHBOARD_PORT, "Dashboard", 12):
            ok(f"Dashboard ready  →  localhost:{DASHBOARD_PORT}")
        else: bad("Dashboard slow")

    # 4. LEO Desktop App — GUI only, no terminal
    p("\n[4/5]  LEO Desktop App",C)
    leo = BACKEND_DIR / "leo_app.py"
    if not leo.exists():
        bad(f"leo_app.py not found in {BACKEND_DIR}")
    else:
        go("Opening LEO Desktop App (no terminal)")
        gui([PYTHON, "leo_app.py"], BACKEND_DIR)
        ok("LEO Desktop App opened")
    time.sleep(2)

    # 5. Flutter — GUI only
    p("\n[5/5]  Flutter Web App",C)
    if not FRONTEND_DIR.exists():
        bad(f"Flutter folder not found: {FRONTEND_DIR}")
    else:
        go("Starting Flutter — Chrome opens automatically (~30s)")
        gui(["flutter", "run", "-d", "chrome", "--no-color"], FRONTEND_DIR)
        ok("Flutter started")

    p(f"\n{'═'*42}",D)
    p("  ALL SERVICES RUNNING  🚀",G)
    p(f"{'═'*42}",D)
    p(f"\n  Backend   →  http://localhost:{BACKEND_PORT}  [own terminal]",W)
    p(f"  Dashboard →  http://localhost:{DASHBOARD_PORT}",W)
    p(f"  Flutter   →  Opens in Chrome automatically",W)
    p(f"  LEO App   →  Opened in its own window\n",W)
    p("  To STOP: double-click stop_leo.bat",Y)

    time.sleep(2)
    try: webbrowser.open(f"http://localhost:{DASHBOARD_PORT}")
    except: pass

    input("\n  Press Enter to close this launcher window...\n")

if __name__ == "__main__":
    main()