"""Safe injector utilities (opt-in).

This module provides a minimal, carefully-guarded API to *optionally* send
keyboard events for legitimate testing purposes **only**. Injection is
*disabled by default* and requires two independent confirmations:

1) The CLI flag `--enable-inject` (or programmatic flag) must be set.
2) The user must type the shown confirmation token into the console when
   requested.

Additional safeguards:
- It refuses to enable injection if processes with names commonly used by
  games (e.g., 'gta5', 'FiveM') are currently running.
- The module logs every action it performs and returns a clear error if
  injection cannot be performed.

Note: on Windows the `keyboard` package is used for sending keys. Running as
Administrator may be required for global injection.
"""
from __future__ import annotations

import os
import random
import string
import sys
import time
from typing import Iterable

try:
    import psutil
except Exception:  # pragma: no cover - optional
    psutil = None

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - optional
    keyboard = None


GAME_PROCESS_KEYWORDS = ["gta5", "gta_v", "gta", "fivem", "steam", "epicgames"]


def _check_game_processes() -> list[str]:
    if psutil is None:
        return []
    matches = []
    for p in psutil.process_iter(['name']):
        try:
            name = (p.info.get('name') or '').lower()
            for kw in GAME_PROCESS_KEYWORDS:
                if kw in name:
                    matches.append(name)
        except Exception:
            continue
    return matches


def request_consent() -> bool:
    """Ask the user to confirm injection intent by typing a random token.

    Returns True only if the user types the token exactly.
    """
    token = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    print("\n*** INJECTION CONSENT REQUIRED ***")
    print("You requested to enable keyboard injection. This is potentially dangerous")
    print("and should only be used for legitimate testing on non-game, authorized apps.")
    print(f"If you understand and want to proceed, type this token exactly: {token}")
    resp = input("token> ").strip()
    return resp == token


def enable_injection(allow_flag: bool) -> bool:
    """Attempt to enable injection if allowed by flag and environment.

    Returns True on success, False otherwise.
    """
    if not allow_flag:
        print("Injection not allowed: enable flag not set")
        return False

    matches = _check_game_processes()
    if matches:
        print("Refusing to enable injection because possibly offending processes are running:")
        for m in set(matches):
            print(" - ", m)
        return False

    if not request_consent():
        print("Consent check failed; injection disabled.")
        return False

    if keyboard is None:
        print("Injection requested but 'keyboard' package is not available; install it first: pip install keyboard")
        return False

    print("Injection enabled (use responsibly)")
    return True


def perform_action(action: str, dry_run: bool = True) -> bool:
    """Perform a simple action string such as 'press W' or 'type OK'

    This function supports a small grammar for safety: 'press <KEY>' or
    'type <TEXT>'. Returns True on success.
    """
    print(f"[injector] request: {action} (dry_run={dry_run})")
    parts = action.strip().split(maxsplit=1)
    if not parts:
        return False
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if dry_run:
        print(f"[injector] dry-run: would execute: {cmd} {arg}")
        return True

    if keyboard is None:
        print("[injector] keyboard package unavailable; cannot inject")
        return False

    if cmd == 'press' and arg:
        key = arg.strip()
        keyboard.press_and_release(key)
        print(f"[injector] pressed {key}")
        return True
    elif cmd == 'type' and arg:
        keyboard.write(arg)
        print(f"[injector] typed '{arg}'")
        return True
    else:
        print(f"[injector] unsupported action: {action}")
        return False
