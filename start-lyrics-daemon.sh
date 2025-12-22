#!/bin/bash
# Start the lyrics daemon
# This script starts the universal lyrics daemon in the background

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any existing daemon instance
pkill -f "universal_lyrics.py --daemon" 2>/dev/null || true

# Wait a moment for the process to fully terminate
sleep 0.5

# Start the daemon in background
echo "[Lyrics Daemon] Starting daemon..."
cd "$SCRIPT_DIR" && mise exec -- uv run python3 -u universal_lyrics.py --daemon > /tmp/lyrics-daemon.log 2>&1 &

DAEMON_PID=$!
echo "[Lyrics Daemon] Started with PID: $DAEMON_PID"

# Wait a moment to ensure daemon is running
sleep 1

# Check if daemon is still running
if kill -0 $DAEMON_PID 2>/dev/null; then
    echo "[Lyrics Daemon] Successfully started"
    exit 0
else
    echo "[Lyrics Daemon] Failed to start. Check /tmp/lyrics-daemon.log"
    exit 1
fi
