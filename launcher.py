#!/usr/bin/env python3
# GIOAI Launcher — runs all platform bots as subprocesses
# One command to start everything

import subprocess
import sys
import os
import signal
import time
from dotenv import load_dotenv

load_dotenv()

BOTS = [
    {"name": "GIOAI Controller", "path": "GIOAI.py", "token_var": "DISCORD_TOKEN"},
    {"name": "Sparx Maths",      "path": "platforms/sparx/main.py", "token_var": "SPARX_TOKEN"},
    {"name": "Languagenut",      "path": "platforms/languagenut/main.py", "token_var": "LN_TOKEN"},
]

processes = []

def start_all():
    print("=" * 50)
    print("  GIOAI Multi-Bot Launcher")
    print("=" * 50)
    
    started = []
    for bot in BOTS:
        token = os.getenv(bot["token_var"])
        if not token:
            print(f"  ⚠️  {bot['name']} — no token ({bot['token_var']})")
            continue
        
        env = os.environ.copy()
        env["DISCORD_TOKEN"] = token
        proc = subprocess.Popen(
            [sys.executable, bot["path"]],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        processes.append(proc)
        print(f"  ✅ {bot['name']} (PID: {proc.pid})")
        started.append(bot["name"])
        time.sleep(1)  # stagger startup
    
    print(f"\n  Running: {', '.join(started)}")
    print("  Press Ctrl+C to stop all\n")
    
    # Stream output from all
    try:
        while processes:
            for proc in processes[:]:
                if proc.poll() is not None:
                    print(f"  ❌ {proc.pid} exited with code {proc.returncode}")
                    processes.remove(proc)
                else:
                    try:
                        line = proc.stdout.readline()
                        if line:
                            print(f"  [{proc.pid}] {line.rstrip()}")
                    except:
                        pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_all()

def stop_all():
    print("\n  Shutting down...")
    for proc in processes:
        proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
    print("  All bots stopped.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: stop_all())
    start_all()
