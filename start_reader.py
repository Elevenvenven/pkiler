#!/usr/bin/env python3
"""
pkiler - Quick Start Script
Run this to start the reader application
"""
import os, sys, subprocess, time, webbrowser

PORT = 8899
DESKTOP = os.path.expanduser("~/Desktop")

print("=" * 50)
print("pkiler PDF Reader")
print("=" * 50)
print()
print("Starting backend server...")

# Kill any existing server
subprocess.run(["lsof", "-ti:8899"], capture_output=True)
try:
    pids = subprocess.run(["lsof", "-ti:8899"], capture_output=True, text=True).stdout.strip()
    if pids:
        for pid in pids.split('\n'):
            subprocess.run(["kill", pid], capture_output=True)
        print("Killed existing server")
except:
    pass

time.sleep(1)

# Start server
print(f"Starting server on http://127.0.0.1:{PORT}")
print("Press Ctrl+C to stop")
print()

# Import and run the app
sys.path.insert(0, DESKTOP)
from reader_server import app

# Open browser after a delay
def open_browser():
    time.sleep(2)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

import threading
threading.Thread(target=open_browser, daemon=True).start()

app.run(host="127.0.0.1", port=PORT, debug=False)
