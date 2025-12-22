#!/usr/bin/env python3
"""
Universal Lyrics Fetcher (Python version)
Fetches and displays synchronized lyrics for currently playing media using syncedlyrics.
"""

import argparse
import hashlib
import html
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import syncedlyrics

try:
    import pympris

    HAS_PYMPRIS = True
except ImportError:
    HAS_PYMPRIS = False

CACHE_DIR = Path("/tmp/lyrics_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DAEMON_OUTPUT_FILE = Path("/tmp/lyrics-daemon.json")
DAEMON_PID_FILE = Path("/tmp/lyrics-daemon.pid")

PLAYER_ORDER = ["brave", "spotify"]

# Artist name mappings for search queries
# Maps full artist names to preferred search names
ARTIST_SEARCH_MAPPINGS = {
    "ずっと真夜中でいいのに。 ZUTOMAYO": "ずっと真夜中でいいのに。",
    # Add more artist mappings here as needed
    # "Full Artist Name": "Preferred Search Name",
}


def run_playerctl(player: str, *args) -> Optional[str]:
    """Run playerctl command and return output."""
    try:
        result = subprocess.run(
            ["playerctl", "-p", player, *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def detect_player(player_name: str) -> bool:
    """Check if player is playing or paused."""
    status = run_playerctl(player_name, "status")
    return status in ("Playing", "Paused")


def find_active_player(
    target_player: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Find active player and return (player_name, status)."""
    try:
        all_players = (
            subprocess.run(
                ["playerctl", "-l"], capture_output=True, text=True, check=True
            )
            .stdout.strip()
            .split("\n")
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, "Stopped"

    if target_player:
        # Search for specific player
        for p in all_players:
            if target_player.lower() in p.lower():
                if detect_player(p):
                    status = run_playerctl(p, "status") or "Stopped"
                    return p, status
        return None, "Stopped"

    # Auto-detect using priority order
    for priority_player in PLAYER_ORDER:
        for p in all_players:
            if priority_player.lower() in p.lower():
                if detect_player(p):
                    status = run_playerctl(p, "status") or "Stopped"
                    return p, status

    return None, "Stopped"


def clean_title(title: str, artist: str, player: str) -> tuple[str, str]:
    """
    Clean and extract title and artist from media title.
    Returns (title, artist).
    """
    extracted_artist = ""
    original_title = title  # Keep original for comparison

    # Special handling for specific artists
    # For ZUTOMAYO, extract content from 『』 and preserve inner brackets like 「」
    # Also remove half-width parentheses () from the extracted title
    if "ずっと真夜中でいいのに。 ZUTOMAYO" in artist:
        if "『" in title and "』" in title:
            match = re.search(r"『([^』]+)』", title)
            if match:
                extracted_title = match.group(1)
                # Remove half-width parentheses and their contents
                extracted_title = re.sub(r"\(.*?\)", "", extracted_title).strip()
                return extracted_title, extracted_artist

    # For Spotify, only remove feat./ft. from title
    if "spotify" in player.lower():
        # Remove feat./ft./featuring patterns (括弧内外両方)
        title = re.sub(
            r"[\(\[\【].*?(feat\.|ft\.|featuring).*?[\)\]\】]",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"(feat\.|ft\.|featuring).*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip()
        return title, extracted_artist

    # Normalize various dashes/hyphens to standard hyphen-minus
    title = re.sub(r"[–—−－]", "-", title)

    # Extract from "Title / Artist" format (YouTube)
    if " / " in title:
        title = title.split(" / ")[0]

    # Extract from 『』 brackets (Japanese format - high priority)
    if "『" in title and "』" in title:
        match = re.search(r"^[^『]*『([^』]+)』.*", title)
        if match:
            title = match.group(1)

    # Truncate at " - " (often separates Artist or extra info)
    if " - " in title:
        title = title.split(" - ")[0]

    # Remove all types of brackets and their contents ((), [], 【】)
    # These often contain translations, sub-titles, or metadata like [MV]
    title = re.sub(r"[\(\[\【].*?[\)\]\】]", "", title)

    # Replace separator characters with space
    title = re.sub(r"[\|/]", " ", title)

    # Remove feat./ft./featuring outside of brackets
    title = re.sub(r"(feat\.|ft\.|featuring).*", "", title, flags=re.IGNORECASE)

    # Remove special quotes
    title = re.sub(r"[『』「」]", "", title)

    # Normalize consecutive spaces to single space
    title = re.sub(r"\s+", " ", title).strip()

    return title, extracted_artist


def get_lyrics(artist: str, title: str, cache_key: str) -> tuple[str, str]:
    """Fetch lyrics using syncedlyrics and cache the result.
    Returns (lyrics_content, cache_key_used)."""
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = CACHE_DIR / f"{cache_key}.lrc"
    metadata_file = CACHE_DIR / f"{cache_key}.meta"

    # Check if cache exists and metadata matches
    if cache_file.exists():
        lyrics_content = cache_file.read_text()

        # Verify metadata if it exists
        if metadata_file.exists():
            try:
                cached_meta = json.loads(metadata_file.read_text())
                # Metadata includes title and artist for verification
                if (
                    cached_meta.get("title") == title
                    and cached_meta.get("artist") == artist
                ):
                    return lyrics_content, cache_key
                else:
                    # Metadata mismatch - delete stale cache
                    cache_file.unlink()
                    metadata_file.unlink()
            except (json.JSONDecodeError, KeyError):
                # Corrupted metadata - delete cache
                cache_file.unlink()
                if metadata_file.exists():
                    metadata_file.unlink()
        else:
            # Old cache without metadata - trust it for now
            return lyrics_content, cache_key

    # Search for lyrics
    # Check if artist has a specific mapping
    if artist and artist in ARTIST_SEARCH_MAPPINGS:
        # Use mapped artist name directly without further processing
        search_artist = ARTIST_SEARCH_MAPPINGS[artist]
        search_query = f"{title} {search_artist}".strip()
    else:
        # Clean up artist name: remove emojis and full-width alphanumerics
        clean_artist = artist
        if artist:
            # Remove emojis (U+1F000-U+1FFFF range and other common emoji ranges)
            # Remove full-width alphanumerics (U+FF00-U+FFEF)
            cleaned_chars = []
            for char in artist:
                code_point = ord(char)
                # Skip emojis and full-width alphanumerics
                if (0x1F000 <= code_point <= 0x1FFFF or  # Emojis and symbols
                    0xFF00 <= code_point <= 0xFFEF):      # Full-width forms
                    continue
                cleaned_chars.append(char)
            clean_artist = ''.join(cleaned_chars).strip()

        # Use artist name in search if it's reasonably short
        if clean_artist and len(clean_artist) < 30:
            search_query = f"{title} {clean_artist}".strip()
        else:
            # Very long artist name or no artist - search by title only
            search_query = title

    # Log search query (only in daemon mode to avoid log spam)
    if sys.argv and '--daemon' in sys.argv:
        print(f"[Lyrics Search] Query: '{search_query}' (Title: '{title}', Artist: '{artist}')", flush=True)

    # Use reliable providers only (exclude Megalobiz which often fails)
    lrc_content = syncedlyrics.search(
        search_query, providers=["Lrclib", "Musixmatch", "NetEase", "Genius"]
    )

    if lrc_content:
        cache_file.write_text(lrc_content)
        # Save metadata for verification
        metadata = {"title": title, "artist": artist, "cache_key": cache_key}
        metadata_file.write_text(json.dumps(metadata, ensure_ascii=False))
        return lrc_content, cache_key

    # Create empty cache file if not found
    cache_file.touch()
    metadata = {"title": title, "artist": artist, "cache_key": cache_key}
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False))
    return "", cache_key


def parse_timestamp(timestamp: str) -> float:
    """Parse LRC timestamp [mm:ss.xx] to seconds."""
    timestamp = timestamp.strip("[]")
    parts = timestamp.split(":")
    minutes = float(parts[0])
    seconds = float(parts[1])
    return minutes * 60 + seconds


def is_synced_lyrics(lyrics: str) -> bool:
    """Check if lyrics contain timestamps."""
    return bool(re.search(r"^\[\d+:\d+", lyrics, re.MULTILINE))


def find_current_line(lyrics_lines: list[str], position: float) -> int:
    """Find the current lyric line index based on playback position."""
    current_idx = -1

    for i, line in enumerate(lyrics_lines):
        match = re.match(r"^\[(\d+:\d+\.\d+)\]", line)
        if not match:
            continue

        line_time = parse_timestamp(match.group(0))

        # Get next line time
        next_time = 99999
        if i + 1 < len(lyrics_lines):
            next_match = re.match(r"^\[(\d+:\d+\.\d+)\]", lyrics_lines[i + 1])
            if next_match:
                next_time = parse_timestamp(next_match.group(0))

        # Check if position is in this line's time range
        if line_time <= position < next_time:
            current_idx = i
            break

    return current_idx


def strip_timestamp(line: str) -> str:
    """Remove timestamp from lyric line."""
    return re.sub(r"^\[[^\]]*\]\s*", "", line)


def output_json(lyrics_lines: list[str], position: float, is_synced: bool) -> str:
    """Generate JSON output for Eww."""
    if not lyrics_lines:
        return json.dumps({"status": "no_lyrics", "lines": []})

    if is_synced:
        current_idx = find_current_line(lyrics_lines, position)
        if current_idx < 0:
            current_idx = 0

        start = max(0, current_idx - 3)
        end = min(len(lyrics_lines), current_idx + 4)

        lines = []
        for i in range(start, end):
            text = strip_timestamp(lyrics_lines[i])
            if text:
                lines.append({"text": text, "current": i == current_idx})

        return json.dumps({"status": "ok", "lines": lines}, ensure_ascii=False)
    else:
        # Non-synced lyrics
        lines = [{"text": line, "current": False} for line in lyrics_lines[:10] if line]
        return json.dumps({"status": "ok", "lines": lines}, ensure_ascii=False)


def output_waybar(lyrics_lines: list[str], position: float, is_synced: bool) -> str:
    """Generate JSON output for Waybar."""
    if not lyrics_lines:
        return json.dumps({"text": "", "class": "hidden", "tooltip": "No lyrics found"})

    tooltip_lines = []
    current_lyric = ""

    if is_synced:
        current_idx = find_current_line(lyrics_lines, position)

        if current_idx >= 0:
            start = max(0, current_idx - 2)
            end = min(len(lyrics_lines), current_idx + 3)

            for i in range(start, end):
                lyric_text = strip_timestamp(lyrics_lines[i])

                # Handle empty lines
                if not lyric_text or lyric_text.isspace():
                    if i == current_idx:
                        lyric_text = "♪"
                    else:
                        continue

                if i == current_idx:
                    tooltip_lines.append(f"▶ {lyric_text}")
                    current_lyric = lyric_text
                else:
                    tooltip_lines.append(f"  {lyric_text}")
    else:
        # Non-synced lyrics
        tooltip_lines = lyrics_lines[:20]
        if len(lyrics_lines) > 20:
            tooltip_lines.append("... (以下省略)")

    tooltip = "\n".join(tooltip_lines) if tooltip_lines else "♪"
    display_text = f"󰎆 {current_lyric}" if current_lyric else "󰎆"

    return json.dumps(
        {
            "text": html.escape(display_text),
            "class": "visible",
            "tooltip": html.escape(tooltip),
        },
        ensure_ascii=False,
    )


def output_text(
    lyrics_lines: list[str],
    position: float,
    is_synced: bool,
    title: str,
    artist: str,
    player: str,
) -> str:
    """Generate text output for CLI."""
    output = [f"Now Playing: {title} - {artist} ({player})", "-" * 40]

    if is_synced:
        current_idx = find_current_line(lyrics_lines, position)

        for i, line in enumerate(lyrics_lines):
            text = strip_timestamp(line)
            if i == current_idx:
                output.append(f"--> {text}")
            else:
                output.append(f"    {text}")
    else:
        output.extend(lyrics_lines)

    return "\n".join(output)


# ============================================================================
# Daemon Components
# ============================================================================


@dataclass
class PositionSnapshot:
    """Captures a point-in-time position state."""

    position: float  # seconds
    timestamp: float  # time.time()
    rate: float  # playback rate
    status: str  # Playing/Paused/Stopped


class PositionInterpolator:
    """
    Interpolates playback position between MPRIS syncs.
    Provides smooth updates while only querying MPRIS every 5 seconds.
    """

    SYNC_INTERVAL = 5.0  # seconds between MPRIS syncs

    def __init__(self):
        self.last_snapshot: Optional[PositionSnapshot] = None
        self.last_sync_time: float = 0.0
        self.needs_sync = True

    def update_from_mpris(self, state: dict) -> None:
        """Update interpolator with fresh MPRIS data."""
        self.last_snapshot = PositionSnapshot(
            position=state["position"],
            timestamp=time.time(),
            rate=state["rate"],
            status=state["status"],
        )
        self.last_sync_time = time.time()
        self.needs_sync = False

    def should_sync(self) -> bool:
        """Check if it's time to sync with MPRIS."""
        if self.needs_sync:
            return True
        if self.last_snapshot is None:
            return True
        elapsed = time.time() - self.last_sync_time
        return elapsed >= self.SYNC_INTERVAL

    def get_interpolated_position(self) -> float:
        """Calculate current position using interpolation."""
        if self.last_snapshot is None:
            return 0.0

        # If paused or stopped, position doesn't change
        if self.last_snapshot.status != "Playing":
            return self.last_snapshot.position

        # Calculate elapsed time since snapshot
        elapsed = time.time() - self.last_snapshot.timestamp

        # Interpolate: position = last_position + (elapsed * rate)
        interpolated = self.last_snapshot.position + (elapsed * self.last_snapshot.rate)

        return max(0.0, interpolated)

    def handle_seek(self, new_position: float) -> None:
        """Handle user seeking - force resync."""
        if self.last_snapshot:
            self.last_snapshot = PositionSnapshot(
                position=new_position,
                timestamp=time.time(),
                rate=self.last_snapshot.rate,
                status=self.last_snapshot.status,
            )
        self.needs_sync = True


class TrackStateManager:
    """Handles track changes and lyrics caching."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.current_trackid: Optional[str] = None
        self.current_title: Optional[str] = None
        self.current_artist: Optional[str] = None
        self.lyrics_content: str = ""
        self.lyrics_lines: list[str] = []
        self.is_synced: bool = False

    def check_track_change(self, state: dict) -> bool:
        """
        Check if track has changed.
        Returns True if track changed and lyrics need refetching.
        """
        trackid = state["trackid"]
        title = state["title"]
        artist = state["artist"]

        # Primary detection: trackid changed
        if trackid and trackid != self.current_trackid:
            return True

        # Backup: title/artist changed (for players without trackid)
        if title != self.current_title or artist != self.current_artist:
            return True

        return False

    def update_track(self, state: dict, player_name: str) -> None:
        """Update to new track and fetch lyrics."""
        self.current_trackid = state["trackid"]
        self.current_title = state["title"]
        self.current_artist = state["artist"]

        # Clean title
        cleaned_title, extracted_artist = clean_title(state["title"], state["artist"], player_name)

        title = cleaned_title
        artist = extracted_artist or state["artist"]

        # Generate cache key using artist and title (unified with non-daemon mode)
        cache_key = hashlib.md5(f"{artist}{title}".encode()).hexdigest()

        # Fetch lyrics (uses cache if available)
        self.lyrics_content, _ = get_lyrics(artist, title, cache_key)

        # Parse lyrics
        if self.lyrics_content:
            self.lyrics_lines = self.lyrics_content.strip().split("\n")
            self.is_synced = is_synced_lyrics(self.lyrics_content)
        else:
            self.lyrics_lines = []
            self.is_synced = False


class MPRISPlayerMonitor:
    """Manages MPRIS connections and player lifecycle."""

    def __init__(self, player_order: list[str]):
        self.player_order = player_order
        self.current_player: Optional[object] = None
        self.current_player_name: Optional[str] = None

    def find_active_player(self) -> Optional[object]:
        """Find active player based on priority order."""
        if not HAS_PYMPRIS:
            return None

        # Get all available players
        try:
            available = list(pympris.available_players())
            print(f"[DEBUG] Available players: {available}", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] Failed to get available players: {e}", file=sys.stderr)
            return None

        # Search in priority order using partial matching
        for priority_name in self.player_order:
            print(f"[DEBUG] Searching for priority: {priority_name}", file=sys.stderr)
            for player_addr in available:
                try:
                    mp = pympris.MediaPlayer(player_addr)
                    # Get player identity
                    identity = mp.root.Identity
                    print(
                        f"[DEBUG]   Checking player: {player_addr} (Identity: {identity})",
                        file=sys.stderr,
                    )

                    # Match against identity, not bus name
                    if priority_name.lower() in identity.lower():
                        status = mp.player.PlaybackStatus
                        print(
                            f"[DEBUG]   Match found! Status: {status}", file=sys.stderr
                        )
                        if status in ("Playing", "Paused"):
                            self.current_player = mp
                            self.current_player_name = player_addr
                            print(
                                f"[DEBUG]   Selected player: {identity} ({player_addr})",
                                file=sys.stderr,
                            )
                            return mp
                except Exception as e:
                    print(
                        f"[DEBUG]   Exception with {player_addr}: {e}", file=sys.stderr
                    )
                    continue

        print(f"[DEBUG] No matching player found", file=sys.stderr)
        return None

    def reconnect_if_needed(self) -> bool:
        """Check if current player is still valid, reconnect if not."""
        if self.current_player:
            try:
                # Test connection with a simple property access
                _ = self.current_player.player.PlaybackStatus
                return True
            except Exception:
                self.current_player = None

        # Try to reconnect
        result = self.find_active_player()
        return result is not None


class LyricsDaemon:
    """Main daemon orchestrator - outputs lyrics JSON every 50ms."""

    UPDATE_INTERVAL = 0.05  # 50ms = 20Hz
    PRIORITY_CHECK_INTERVAL = 5.0  # 5秒ごとに優先順位チェック

    def __init__(self):
        self.running = True
        self.monitor = MPRISPlayerMonitor(["brave", "spotify"])
        self.interpolator = PositionInterpolator()
        self.track_manager = TrackStateManager(CACHE_DIR)
        self.last_priority_check = 0.0
        self.last_status = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.running = False

    def run(self) -> None:
        """Main daemon loop."""
        if not HAS_PYMPRIS:
            print(
                "Error: pympris not installed. Install with: uv add pympris",
                file=sys.stderr,
            )
            print(json.dumps({"status": "error", "lines": []}))
            sys.exit(1)

        # Write PID file
        try:
            DAEMON_PID_FILE.write_text(str(os.getpid()))
        except Exception as e:
            print(f"[ERROR] Failed to write PID file: {e}", file=sys.stderr)
            # Proceed even if PID file write fails, but log it.

        # Daemon startup notification
        print(
            f"[INFO] Lyrics daemon started. Output file: {DAEMON_OUTPUT_FILE}",
            file=sys.stderr,
        )
        sys.stderr.flush()

        try:
            while self.running:
                loop_start = time.time()

                try:
                    self._process_iteration()
                except Exception as e:
                    # Log error but keep running
                    import traceback

                    print(f"[ERROR] {e}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

                # Sleep to maintain 20Hz update rate
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.UPDATE_INTERVAL - elapsed)
                time.sleep(sleep_time)
        finally:
            # Clean up PID file on exit
            if DAEMON_PID_FILE.exists():
                try:
                    DAEMON_PID_FILE.unlink()
                except Exception:
                    pass
            print("[INFO] Lyrics daemon stopped.", file=sys.stderr)

    def _process_iteration(self) -> None:
        """Process one iteration of the daemon loop."""
        # 定期的に優先順位の高いプレイヤーをチェック
        current_time = time.time()
        if current_time - self.last_priority_check >= self.PRIORITY_CHECK_INTERVAL:
            self._check_priority()
            self.last_priority_check = current_time

        # Check player connection
        if not self.monitor.current_player:
            # Attempt to find a player
            if not self.monitor.find_active_player():
                # No player found
                self._write_json_file({"status": "stopped", "lines": []})
                return

        mp = self.monitor.current_player

        # Check if player is still alive
        if not self.monitor.reconnect_if_needed():
            self._write_json_file({"status": "stopped", "lines": []})
            return

        # Sync with MPRIS if needed (every 5s or on first run)
        if self.interpolator.should_sync():
            state = self._get_current_state(mp)
            if state is None:
                # Player died
                self.monitor.current_player = None
                return

            # Check for track changes
            if self.track_manager.check_track_change(state):
                # New track - fetch lyrics
                player_name = self.monitor.current_player_name or "unknown"
                self.track_manager.update_track(state, player_name)

            # Update interpolator
            self.interpolator.update_from_mpris(state)

            # Log status change
            if state["status"] != self.last_status:
                print(f"[INFO] Player status changed: {self.last_status} -> {state['status']} (Player: {self.monitor.current_player_name})", file=sys.stderr)
                self.last_status = state["status"]

        # Get interpolated position
        position = self.interpolator.get_interpolated_position()

        # Generate output
        output = self._generate_output(position)
        self._write_json_file(output)

    def _get_current_state(self, mp: object) -> Optional[dict]:
        """Extract current playback state from MPRIS player."""
        try:
            status = mp.player.PlaybackStatus
            position_us = mp.player.Position  # microseconds
            position = position_us / 1_000_000.0  # convert to seconds
            metadata = mp.player.Metadata
            rate = mp.player.Rate

            # Handle xesam:artist which can be a list
            artist = metadata.get("xesam:artist", "")
            if isinstance(artist, list):
                artist = ", ".join(artist) if artist else ""

            return {
                "status": status,
                "position": position,
                "rate": rate,
                "trackid": metadata.get("mpris:trackid", ""),
                "title": metadata.get("xesam:title", ""),
                "artist": artist,
                "length_us": metadata.get("mpris:length", 0),
            }
        except Exception:
            return None

    def _generate_output(self, position: float) -> dict:
        """Generate JSON output for current position."""
        if not self.track_manager.lyrics_lines:
            return {"status": "no_lyrics", "lines": []}

        # Reuse existing output logic
        json_str = output_json(
            self.track_manager.lyrics_lines, position, self.track_manager.is_synced
        )
        return json.loads(json_str)

    @staticmethod
    def _output_json_line(data: dict) -> None:
        """Output JSON to stdout for non-daemon mode or to file for daemon mode."""
        json_str = json.dumps(data, ensure_ascii=False)
        print(json_str, flush=True)  # flush=True is CRITICAL

    def _check_priority(self) -> None:
        """Check if a higher priority player is available."""
        if not self.monitor.current_player:
            return

        # 現在のプレイヤーのIdentityを取得
        try:
            current_identity = self.monitor.current_player.root.Identity
        except Exception:
            self.monitor.current_player = None
            return

        # 現在のプレイヤーの優先順位を取得
        current_priority = None
        for i, priority_name in enumerate(self.monitor.player_order):
            if priority_name.lower() in current_identity.lower():
                current_priority = i
                break

        if current_priority is None:
            # 現在のプレイヤーが優先リストにない → 再検索
            self.monitor.current_player = None
            return

        # 利用可能なプレイヤーをすべて取得
        try:
            available = list(pympris.available_players())
        except Exception:
            return

        # より優先順位の高いプレイヤーが再生中かチェック
        for i in range(current_priority):
            priority_name = self.monitor.player_order[i]

            # 利用可能なプレイヤーの中から部分一致で検索
            for player_addr in available:
                try:
                    mp = pympris.MediaPlayer(player_addr)
                    identity = mp.root.Identity
                    # Match against identity, not bus name
                    if priority_name.lower() in identity.lower():
                        status = mp.player.PlaybackStatus
                        if status in ("Playing", "Paused"):
                            # より優先順位の高いプレイヤーが見つかった
                            print(
                                f"[INFO] Found higher priority player! Switching to {identity} ({player_addr})",
                                file=sys.stderr,
                            )
                            self.monitor.current_player = mp
                            self.monitor.current_player_name = player_addr
                            # トラック状態をリセットして歌詞を再取得させる
                            self.track_manager.current_trackid = None
                            return
                except Exception:
                    continue

    @staticmethod
    def _write_json_file(data: dict) -> None:
        """Write JSON to daemon output file (atomic write)."""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            # Atomic write: write to temp file first, then rename
            temp_file = DAEMON_OUTPUT_FILE.with_suffix(".tmp")
            temp_file.write_text(json_str)
            temp_file.replace(DAEMON_OUTPUT_FILE)
        except Exception as e:
            print(f"[ERROR] Failed to write daemon output file: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Universal Lyrics Fetcher")
    parser.add_argument("--target", help="Target player name")
    parser.add_argument(
        "--format",
        choices=["json", "waybar", "text", "raw"],
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon with 20Hz updates",
    )
    args = parser.parse_args()

    # Daemon mode
    if args.daemon:
        daemon = LyricsDaemon()
        daemon.run()
        return

    # Find active player
    player, status = find_active_player(args.target)

    if not player or status not in ("Playing", "Paused"):
        if args.format == "json":
            print(json.dumps({"status": "stopped", "lines": []}))
        elif args.format == "waybar":
            print(
                json.dumps(
                    {"text": "", "class": "hidden", "tooltip": "No active player"}
                )
            )
        else:
            print("No active player found.")
        sys.exit(0)

    # Get metadata
    artist = run_playerctl(player, "metadata", "xesam:artist") or ""
    title = run_playerctl(player, "metadata", "xesam:title") or ""
    trackid = run_playerctl(player, "metadata", "mpris:trackid") or ""
    position_str = run_playerctl(player, "position") or "0"
    position = float(position_str)

    # Clean title (for all players including Spotify)
    cleaned_title, extracted_artist = clean_title(title, artist, player)
    title = cleaned_title
    if extracted_artist:
        artist = extracted_artist

    if not title:
        if args.format == "json":
            print(json.dumps({"status": "no_info", "lines": []}))
        elif args.format == "waybar":
            print(
                json.dumps({"text": "", "class": "hidden", "tooltip": "No track info"})
            )
        else:
            print("No track info available.")
        sys.exit(0)

    # Generate cache key using artist and title for consistency
    cache_key = hashlib.md5(f"{artist}{title}".encode()).hexdigest()

    # Get lyrics with metadata verification
    lyrics_content, verified_cache_key = get_lyrics(artist, title, cache_key)

    if not lyrics_content:
        if args.format == "json":
            print(json.dumps({"status": "no_lyrics", "lines": []}))
        elif args.format == "waybar":
            print(
                json.dumps(
                    {"text": "", "class": "hidden", "tooltip": "No lyrics found"}
                )
            )
        else:
            print(f"Lyrics not found for: {artist} - {title}")
        sys.exit(0)

    # Output raw LRC if requested
    if args.format == "raw":
        print(lyrics_content)
        sys.exit(0)

    # Parse lyrics
    lyrics_lines = lyrics_content.strip().split("\n")
    is_synced = is_synced_lyrics(lyrics_content)

    # Generate output based on format
    if args.format == "json":
        print(output_json(lyrics_lines, position, is_synced))
    elif args.format == "waybar":
        print(output_waybar(lyrics_lines, position, is_synced))
    elif args.format == "text":
        print(output_text(lyrics_lines, position, is_synced, title, artist, player))


if __name__ == "__main__":
    main()
