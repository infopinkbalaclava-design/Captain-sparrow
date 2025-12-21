"""F12-toggle timing simulator (dry-run).

This script is intentionally *non-injective*: it does not press keys in any app/game.
It only prints what it would do, with human-like timing and rate limiting.

Windows note:
- Requires the `keyboard` package for global hotkeys.
- Global hotkeys may require running the terminal as Administrator.

Install:
  pip install keyboard

Run:
  python scripts\f12_wasd_timing_simulator.py

Controls:
- F12: toggle on/off
- Ctrl+C: exit
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from random import Random


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _fmt_ms(value_seconds: float) -> str:
    return f"{int(round(value_seconds * 1000))}ms"


@dataclass(frozen=True)
class TimingProfile:
    hold_min_s: float = 0.060
    hold_max_s: float = 0.180
    gap_min_s: float = 0.090
    gap_max_s: float = 0.330
    long_pause_every_min: int = 25
    long_pause_every_max: int = 45
    long_pause_min_s: float = 0.55
    long_pause_max_s: float = 1.35


class DryRunKeySimulator:
    def __init__(self, rng: Random, profile: TimingProfile) -> None:
        self._rng = rng
        self._profile = profile

        self._active = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._last_key: str | None = None
        self._repeat_count = 0
        self._action_counter = 0
        self._next_long_pause_at = self._rng.randint(
            self._profile.long_pause_every_min, self._profile.long_pause_every_max
        )

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="dry-run-sim", daemon=True)
        self._thread.start()

    def toggle(self) -> None:
        if self._active.is_set():
            self.deactivate()
        else:
            self.activate()

    def activate(self) -> None:
        self.start_background()
        self._active.set()
        print(f"[{_now()}] ACTIVE  (dry-run) — printing simulated WASD taps", flush=True)

    def deactivate(self) -> None:
        self._active.clear()
        print(f"[{_now()}] PAUSED  (dry-run)", flush=True)

    def stop(self) -> None:
        self._stop.set()
        self._active.set()  # unblock loop if waiting
        if self._thread:
            self._thread.join(timeout=2.0)

    def _choose_key(self) -> str:
        keys = ["W", "A", "S", "D"]
        candidate = self._rng.choice(keys)

        # Avoid long runs of the same key.
        if self._last_key is None:
            self._last_key = candidate
            self._repeat_count = 1
            return candidate

        if candidate == self._last_key:
            self._repeat_count += 1
            if self._repeat_count >= 3:
                # Force a different key.
                alt = [k for k in keys if k != self._last_key]
                candidate = self._rng.choice(alt)
                self._repeat_count = 1
        else:
            self._repeat_count = 1

        self._last_key = candidate
        return candidate

    def _rand_between(self, min_s: float, max_s: float) -> float:
        return min_s + (max_s - min_s) * self._rng.random()

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._active.is_set():
                time.sleep(0.05)
                continue

            key = self._choose_key()
            hold_s = self._rand_between(self._profile.hold_min_s, self._profile.hold_max_s)
            gap_s = self._rand_between(self._profile.gap_min_s, self._profile.gap_max_s)

            self._action_counter += 1
            print(
                f"[{_now()}] TAP {key}  hold={_fmt_ms(hold_s)}  gap={_fmt_ms(gap_s)}",
                flush=True,
            )

            # These sleeps represent how long a real key would be held and the
            # human-ish delay before the next action.
            time.sleep(hold_s)
            time.sleep(gap_s)

            if self._action_counter >= self._next_long_pause_at:
                pause_s = self._rand_between(
                    self._profile.long_pause_min_s, self._profile.long_pause_max_s
                )
                print(f"[{_now()}] micro-pause {pause_s:.2f}s", flush=True)
                time.sleep(pause_s)
                self._action_counter = 0
                self._next_long_pause_at = self._rng.randint(
                    self._profile.long_pause_every_min, self._profile.long_pause_every_max
                )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "F12-toggle dry-run simulator that prints human-like WASD tap timing. "
            "Does not inject keys into any application."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for repeatable timing.",
    )
    args = parser.parse_args(argv)

    try:
        import keyboard  # type: ignore
    except Exception as exc:  # pragma: no cover
        print("Missing dependency: keyboard", file=sys.stderr)
        print("Install with: pip install keyboard", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        return 2

    rng = Random(args.seed)
    sim = DryRunKeySimulator(rng=rng, profile=TimingProfile())

    print("Dry-run simulator ready.")
    print("- Press F12 to toggle on/off")
    print("- Press Ctrl+C to exit")

    keyboard.add_hotkey("F12", sim.toggle)

    try:
        # Block forever; keyboard hooks run in background.
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] exiting...", flush=True)
        sim.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
