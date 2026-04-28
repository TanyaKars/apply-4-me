#!/bin/bash
set -e

# Remove stale X lock from any previous container run
rm -f /tmp/.X99-lock

# Virtual display so Playwright can run headed inside Docker
Xvfb :99 -screen 0 1280x900x24 -ac &
sleep 2

# VNC server on the virtual display (no password, localhost only)
x11vnc -display :99 -nopw -listen localhost -forever -shared -quiet &

# noVNC: browser-based VNC client at http://localhost:6080/vnc.html
websockify --web /usr/share/novnc 6080 localhost:5900 &

# `python -m uvicorn` (unlike the console script) adds cwd to sys.path,
# so Python can resolve the app package from /app/api/app/
cd /app/api
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
