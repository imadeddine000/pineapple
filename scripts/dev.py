#!/usr/bin/env python3
"""
Development launcher — starts backend with auto-restart + frontend dev server.

Usage:
    python3 scripts/dev.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent

def start_backend():
    """Start the backend server, restart on file changes."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    
    # Track file modification times
    py_files = list((ROOT / "src" / "pineapple").rglob("*.py"))
    last_mtimes = {f: f.stat().st_mtime for f in py_files}
    
    proc = None
    while True:
        if proc is None or proc.poll() is not None:
            if proc is not None:
                print("  [backend] Restarting...")
                time.sleep(0.5)
            print("  [backend] Starting on port 8765...")
            proc = subprocess.Popen(
                [sys.executable, "-m", "pineapple", "dashboard"],
                cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        
        # Check for file changes
        changed = False
        for f in py_files:
            try:
                mtime = f.stat().st_mtime
                if mtime != last_mtimes.get(f, 0):
                    print(f"  [backend] Changed: {f.name}")
                    last_mtimes[f] = mtime
                    changed = True
            except FileNotFoundError:
                pass
        
        if changed:
            print("  [backend] File change detected, restarting...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            continue
        
        # Read output
        try:
            line = proc.stdout.readline()
            if line:
                print(f"  [backend] {line.rstrip()}")
        except:
            pass
        
        time.sleep(0.1)

def start_frontend():
    """Start the Vite dev server."""
    print("  [frontend] Starting Vite dev server...")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=ROOT / "frontend",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in iter(proc.stdout.readline, ""):
        print(f"  [frontend] {line.rstrip()}")
    proc.wait()

if __name__ == "__main__":
    import threading
    
    print("  Pineapple Development")
    print("  " + "=" * 40)
    print("  Backend:  http://localhost:8765")
    print("  Frontend: http://localhost:5173 (proxies /api to :8765)")
    print("  " + "=" * 40)
    print("")
    
    t = threading.Thread(target=start_frontend, daemon=True)
    t.start()
    time.sleep(2)
    
    try:
        start_backend()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        sys.exit(0)
