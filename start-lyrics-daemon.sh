#!/bin/bash
# Start the lyrics daemon
# This script starts the universal lyrics daemon in the background

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="/tmp/lyrics-daemon.pid"

# Kill any existing daemon instance
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[Lyrics Daemon] Stopping existing daemon (PID: $PID)..."
        kill "$PID"
        # Wait for process to exit
        for i in {1..10}; do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 0.1
        done
    fi
    # Ensure PID file is removed if it still exists (stale)
    rm -f "$PID_FILE"
else
    # Fallback to pkill if PID file is missing
    pkill -f "universal_lyrics.py --daemon" 2>/dev/null || true
fi

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
