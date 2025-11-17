#!/usr/bin/env python3
"""Stream all bot logs with filtered noise and colored severity hints."""

from __future__ import annotations

import argparse
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

IGNORED_PATTERNS = [
    re.compile(r"httpx: HTTP Request", re.IGNORECASE),
    re.compile(r"Application started", re.IGNORECASE),
    re.compile(r"Scheduler started", re.IGNORECASE),
]

RESET = "\033[0m"
LEVEL_COLORS = {
    "CRITICAL": "\033[35m",
    "ERROR": "\033[31m",
    "TRACEBACK": "\033[35m",
    "WARNING": "\033[33m",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Follow all bot logs at once.")
    parser.add_argument(
        "--show-http",
        action="store_true",
        help="Show httpx polling entries (hidden by default).",
    )
    parser.add_argument(
        "--dir",
        default=str(LOG_DIR),
        help="Log directory to watch (default: %(default)s).",
    )
    return parser.parse_args()


class TailThread(threading.Thread):
    """Thread that tails a single file and pushes lines into a queue."""

    def __init__(self, path: Path, sink: queue.Queue[tuple[str, str]]):
        super().__init__(daemon=True)
        self.path = path
        self.sink = sink

    def run(self) -> None:
        while True:
            try:
                self._follow()
            except FileNotFoundError:
                time.sleep(1.0)
            except Exception as exc:  # pragma: no cover - defensive
                self.sink.put((self.path.name, f"[tail error] {exc}"))
                time.sleep(1.0)

    def _follow(self) -> None:
        with self.path.open("r") as handle:
            handle.seek(0, os.SEEK_END)
            inode = os.fstat(handle.fileno()).st_ino
            while True:
                line = handle.readline()
                if line:
                    self.sink.put((self.path.name, line.rstrip("\n")))
                    continue
                if not self.path.exists():
                    time.sleep(0.5)
                    return
                stat = self.path.stat()
                if stat.st_ino != inode or stat.st_size < handle.tell():
                    return
                time.sleep(0.3)


def should_skip(line: str, show_http: bool) -> bool:
    if show_http:
        return False
    return any(pattern.search(line) for pattern in IGNORED_PATTERNS)


def colorize(line: str) -> str:
    upper = line.upper()
    for key, color in LEVEL_COLORS.items():
        if key in upper:
            return f"{color}{line}{RESET}"
    return line


def watch(directory: Path, show_http: bool) -> None:
    sink: queue.Queue[tuple[str, str]] = queue.Queue()
    log_paths = sorted(directory.glob("*.log"))
    if not log_paths:
        print(f"No log files found in {directory}. Start the bots first.")
        return

    for path in log_paths:
        print(f"[watching] {path}")
        TailThread(path, sink).start()

    while True:
        try:
            name, line = sink.get(timeout=0.5)
        except queue.Empty:
            continue
        if should_skip(line, show_http):
            continue
        timestamp = time.strftime("%H:%M:%S")
        print(f"{timestamp} [{name}] {colorize(line)}")


def main() -> None:
    args = parse_args()
    directory = Path(args.dir).resolve()
    if not directory.exists():
        print(f"Log directory {directory} does not exist.", file=sys.stderr)
        sys.exit(1)
    watch(directory, show_http=args.show_http)


if __name__ == "__main__":
    main()
