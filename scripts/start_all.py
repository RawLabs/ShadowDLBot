#!/usr/bin/env python3
"""Simple supervisor that launches every Telegram bot in this workspace."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_env_values(path: Path) -> Dict[str, str]:
    """Parse .env if it exists, otherwise fall back to already-exported env vars."""

    env: Dict[str, str] = dict(os.environ)
    if not path.exists():
        print(f"[i] {path} not found; relying on existing environment variables.")
        return env

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"' ")
        env[key] = value
    return env


@dataclass(slots=True)
class BotConfig:
    name: str
    command: List[str]
    cwd: Path
    env_map: Dict[str, str] = field(default_factory=dict)
    extra_env: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BotRunner:
    config: BotConfig
    log_path: Path
    process: Optional[subprocess.Popen] = None
    log_handle: Optional[object] = None

    def start(self, env_values: Dict[str, str]) -> None:
        missing = [
            source
            for source in self.config.env_map.values()
            if source not in env_values
        ]
        if missing:
            raise RuntimeError(
                f"Missing environment values for {self.config.name}: {', '.join(missing)}"
            )

        env = os.environ.copy()
        env.update(self.config.extra_env)
        for target, source in self.config.env_map.items():
            env[target] = env_values[source]

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("ab", buffering=0)
        self.log_handle.write(
            f"\n\n==== Starting {self.config.name} ====\n".encode("utf-8")
        )

        self.process = subprocess.Popen(
            self.config.command,
            cwd=self.config.cwd,
            env=env,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
        )
        print(f"[+] {self.config.name} (pid {self.process.pid})")

    def stop(self, timeout: float = 10.0) -> None:
        if not self.process or self.process.poll() is not None:
            self._close_log()
            return
        print(f"[-] Stopping {self.config.name}…")
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"[!] {self.config.name} did not exit; killing.")
            self.process.kill()
        finally:
            self._close_log()

    def check_alive(self) -> Optional[int]:
        if not self.process:
            return None
        return self.process.poll()

    def _close_log(self) -> None:
        if self.log_handle:
            try:
                self.log_handle.flush()
            except Exception:
                pass
            try:
                self.log_handle.close()
            except Exception:
                pass
            self.log_handle = None


def build_bot_configs() -> list[BotRunner]:
    bots: list[BotConfig] = [
        BotConfig(
            name="shadowDLBot",
            command=["python", "main.py"],
            cwd=ROOT / "bots" / "shadowDLBot",
            env_map={"TELEGRAM_BOT_TOKEN": "SHADOWDL_TELEGRAM_BOT_TOKEN"},
        ),
        BotConfig(
            name="ShadowPI",
            command=["python", "-m", "shadowpi.bot"],
            cwd=ROOT / "bots",
            env_map={"SHADOWPI_BOT_TOKEN": "SHADOWPI_BOT_TOKEN"},
            extra_env={
                "SHADOWPI_DATA_DIR": str((ROOT / "bots" / "shadowpi_data").resolve()),
            },
        ),
        BotConfig(
            name="Transkrypt",
            command=["python", "bot.py"],
            cwd=ROOT / "bots" / "transkrypt",
            env_map={"TELEGRAM_BOT_TOKEN": "TRANSKRYPT_TELEGRAM_BOT_TOKEN"},
        ),
        BotConfig(
            name="ShadowSafe",
            command=["python", "-m", "ShadowSafe.bot.main"],
            cwd=ROOT / "bots" / "shadowsafe",
            env_map={"SHADOWSAFE_BOT_TOKEN": "SHADOWSAFE_BOT_TOKEN"},
            extra_env={
                "SHADOWSAFE_LOG_DIR": str((ROOT / "bots" / "shadowsafe" / "ShadowSafe" / "logs").resolve()),
            },
        ),
        BotConfig(
            name="TicTocDoc",
            command=["python", "bot_main.py"],
            cwd=ROOT / "bots" / "tictocdoc",
            env_map={"TICTOCDOC_BOT_TOKEN": "TICTOCDOC_BOT_TOKEN"},
            extra_env={
                "TICTOCDOC_TEMP_DIR": str((ROOT / "bots" / "tictocdoc" / "tmp").resolve()),
            },
        ),
        BotConfig(
            name="SudoLink",
            command=["./start_all"],
            cwd=ROOT / "bots" / "sudolink",
            env_map={
                "SUDOLINK_TELEGRAM_BOT_TOKEN": "SUDOLINK_TELEGRAM_BOT_TOKEN",
                "SUDOLINK_OPENAI_API_KEY": "SUDOLINK_OPENAI_API_KEY",
            },
        ),
    ]
    return [
        BotRunner(config=bot, log_path=LOG_DIR / f"{bot.name}.log")
        for bot in bots
    ]


def main() -> None:
    env_values = load_env_values(ENV_FILE)
    runners = build_bot_configs()

    for runner in runners:
        try:
            runner.start(env_values)
        except Exception as exc:
            print(f"[!] Failed to start {runner.config.name}: {exc}", file=sys.stderr)
            for started in runners:
                if started is runner:
                    break
                started.stop()
            sys.exit(1)

    print("All bots launched. Logs are written to ./logs/<bot>.log. Press Ctrl+C to stop everything.")

    try:
        while True:
            for runner in runners:
                code = runner.check_alive()
                if code is not None:
                    print(
                        f"[!] {runner.config.name} exited with status {code}. "
                        f"Check {runner.log_path} for details."
                    )
                    for other in runners:
                        if other is runner:
                            continue
                        other.stop()
                    sys.exit(code if code else 0)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping all bots…")
        for runner in runners:
            runner.stop()
        print("Goodbye!")


if __name__ == "__main__":
    main()
