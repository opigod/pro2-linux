#!/usr/bin/env python3
"""
Host-mode button remapper for the Logitech PRO 2 LIGHTSPEED.

The Pro 2's onboard profile format 0x07 does not expose a usable macro or
double-click encoding through libratbag. This daemon takes the other route:
it puts the mouse into HID++ host mode, mutes only the buttons listed in the
config via 0x8110, reads button-spy masks, and injects keys / clicks through
Linux uinput. All other buttons stay native.

Usage:
    ./pro2ctl stop
    ./pro2_remap.py [config.json]

The default config is ./pro2-remap.json. Press Ctrl+C to restore the mouse.

Config:
    {
      "buttons": {
        "7": {"type": "double_click"},
        "8": {"type": "macro",
              "steps": ["+KEY_LEFTCTRL", "+KEY_C", "t50", "-KEY_C", "-KEY_LEFTCTRL"]},
        "6": {"type": "key", "key": "KEY_F13"}
      }
    }

Button numbers are the 0x8110 slots 1..8. Actions:
    key          tap one key on press
    hold         hold key while the button is held
    double_click two left clicks on press
    macro        run the steps on press (+KEY hold, -KEY release, KEY tap, tMS wait)
    disabled     mute without injecting anything
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from evdev import UInput, ecodes as e

SECTOR_SIZE = 255


def find_device() -> tuple[str, int]:
    candidates: list[tuple[int, str, int]] = []
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        try:
            text = (entry / "device" / "uevent").read_text()
            descriptor = (entry / "device" / "report_descriptor").read_bytes()
        except OSError:
            continue
        fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        parts = fields.get("HID_ID", "").split(":")
        if len(parts) != 3 or int(parts[1], 16) != 0x046D:
            continue
        if b"\x85\x11" not in descriptor:
            continue
        product = int(parts[2], 16)
        if product == 0xC09A:
            candidates.append((0, f"/dev/{entry.name}", 0xFF))
        elif product == 0xC543:
            candidates.append((1, f"/dev/{entry.name}", 1))
    if not candidates:
        raise SystemExit("PRO 2 LIGHTSPEED not found")
    candidates.sort(key=lambda item: item[0])
    _, path, index = candidates[0]
    return path, index


class Hidpp:
    def __init__(self, path: str, index: int) -> None:
        self.path = path
        self.index = index
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def close(self) -> None:
        os.close(self.fd)

    def request(self, feature: int, function: int, params: bytes = b"", *, long: bool = False, timeout: float = 1.0):
        frame = bytes([0x11 if long else 0x10, self.index, feature, function]) + params
        frame += b"\x00" * ((20 if long else 7) - len(frame))
        os.write(self.fd, frame)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            reply = os.read(self.fd, 64)
            if len(reply) >= 7 and reply[1] == self.index and reply[2] == feature and (reply[3] & 0xF0) == (function & 0xF0):
                return reply
        return None

    def feature_index(self, feature: int) -> int:
        reply = self.request(0x00, 0x00, bytes([feature >> 8, feature & 0xFF]))
        if reply is None or reply[4] == 0:
            raise SystemExit(f"feature 0x{feature:04x} not found")
        return reply[4]


def keycode(name: str) -> int:
    value = getattr(e, name, None)
    if not isinstance(value, int):
        raise SystemExit(f"unknown key name: {name}")
    return value


class Injector:
    def __init__(self, config: dict) -> None:
        used: set[int] = set()
        for action in config.values():
            kind = action.get("type")
            if kind in ("key", "hold"):
                used.add(keycode(action["key"]))
            elif kind == "macro":
                for step in action.get("steps", []):
                    if step.startswith(("+", "-")):
                        used.add(keycode(step[1:]))
                    elif step.startswith("t") and step[1:].isdigit():
                        continue
                    else:
                        used.add(keycode(step))
        self.lock = threading.Lock()
        self.keyboard = UInput({e.EV_KEY: sorted(used) or [e.KEY_F13]}, name="pro2-remap-keyboard")
        self.mouse = UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]}, name="pro2-remap-mouse")
        self.held: dict[int, int] = {}

    def close(self) -> None:
        with self.lock:
            for code in self.held.values():
                self.keyboard.write(e.EV_KEY, code, 0)
            self.keyboard.syn()
            self.held.clear()
            self.keyboard.close()
            self.mouse.close()

    def tap(self, name: str) -> None:
        code = keycode(name)
        with self.lock:
            self.keyboard.write(e.EV_KEY, code, 1)
            self.keyboard.syn()
            time.sleep(0.02)
            self.keyboard.write(e.EV_KEY, code, 0)
            self.keyboard.syn()

    def hold(self, button: int, name: str) -> None:
        code = keycode(name)
        with self.lock:
            self.keyboard.write(e.EV_KEY, code, 1)
            self.keyboard.syn()
            self.held[button] = code

    def release(self, button: int) -> None:
        with self.lock:
            code = self.held.pop(button, None)
            if code is not None:
                self.keyboard.write(e.EV_KEY, code, 0)
                self.keyboard.syn()

    def double_click(self) -> None:
        def run() -> None:
            with self.lock:
                for _ in range(2):
                    self.mouse.write(e.EV_KEY, e.BTN_LEFT, 1)
                    self.mouse.syn()
                    time.sleep(0.04)
                    self.mouse.write(e.EV_KEY, e.BTN_LEFT, 0)
                    self.mouse.syn()
                    time.sleep(0.04)
        threading.Thread(target=run, daemon=True).start()

    def macro(self, steps: list[str]) -> None:
        def run() -> None:
            with self.lock:
                for step in steps:
                    if step.startswith("t") and step[1:].isdigit():
                        time.sleep(int(step[1:]) / 1000)
                    elif step.startswith("+"):
                        self.keyboard.write(e.EV_KEY, keycode(step[1:]), 1)
                        self.keyboard.syn()
                    elif step.startswith("-"):
                        self.keyboard.write(e.EV_KEY, keycode(step[1:]), 0)
                        self.keyboard.syn()
                    else:
                        code = keycode(step)
                        self.keyboard.write(e.EV_KEY, code, 1)
                        self.keyboard.syn()
                        time.sleep(0.02)
                        self.keyboard.write(e.EV_KEY, code, 0)
                        self.keyboard.syn()
                    time.sleep(0.01)
        threading.Thread(target=run, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser()
    default_config = Path(__file__).resolve().parent.parent / "config" / "pro2-remap.json"
    parser.add_argument("config", nargs="?", default=str(default_config))
    args = parser.parse_args()

    if subprocess.run(["pgrep", "-x", "ratbagd"], stdout=subprocess.DEVNULL).returncode == 0:
        raise SystemExit("ratbagd is running. Run './pro2ctl stop' first.")

    config_path = Path(args.config)
    if not config_path.exists():
        config_path.write_text(
            json.dumps(
                {
                    "buttons": {
                        "7": {"type": "double_click"},
                        "8": {
                            "type": "macro",
                            "steps": ["+KEY_LEFTCTRL", "+KEY_C", "t50", "-KEY_C", "-KEY_LEFTCTRL"],
                        },
                    }
                },
                indent=2,
            )
            + "\n"
        )
        print(f"wrote default config to {config_path}")
    buttons = json.loads(config_path.read_text()).get("buttons", {})
    if not buttons:
        raise SystemExit("config has no buttons")

    path, index = find_device()
    device = Hidpp(path, index)
    onboard = device.feature_index(0x8100)
    spy = device.feature_index(0x8110)
    injector = Injector({int(k): v for k, v in buttons.items()})
    original_mapping: list[int] | None = None
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        count_reply = device.request(spy, 0x00)
        if count_reply is None:
            raise SystemExit("0x8110 button count failed")
        count = count_reply[4]
        mapping_reply = device.request(spy, 0x30, b"", long=True)
        if mapping_reply is None:
            raise SystemExit("0x8110 mapping read failed")
        original_mapping = list(mapping_reply[4 : 4 + count])
        mapping = original_mapping[:]
        for number in buttons:
            slot = int(number) - 1
            if not 0 <= slot < count:
                raise SystemExit(f"button {number} outside 1..{count}")
            mapping[slot] = 0
        if device.request(spy, 0x40, bytes(mapping) + bytes(16 - len(mapping)), long=True) is None:
            raise SystemExit("0x8110 mapping write failed")
        if device.request(onboard, 0x10, bytes([2, 0, 0])) is None:
            raise SystemExit("failed to enter host mode")
        if device.request(spy, 0x10, bytes([0, 0, 0])) is None:
            raise SystemExit("failed to start button spy")
        print(f"remapping {len(buttons)} button(s) on {path}; Ctrl+C to stop", flush=True)
        last_mask = 0
        while running:
            ready, _, _ = select.select([device.fd], [], [], 0.5)
            if not ready:
                continue
            try:
                report = os.read(device.fd, 64)
            except BlockingIOError:
                continue
            if len(report) < 6 or report[2] != spy or report[3] != 0x00:
                continue
            mask = int.from_bytes(report[4:6], "big")
            changed = mask ^ last_mask
            for slot in range(count):
                bit = 1 << slot
                if not changed & bit:
                    continue
                number = slot + 1
                action = buttons.get(str(number))
                if action is None:
                    continue
                kind = action.get("type")
                print(f"button {number} {'down' if mask & bit else 'up'} -> {kind}", flush=True)
                if mask & bit:
                    if kind == "key":
                        injector.tap(action["key"])
                    elif kind == "hold":
                        injector.hold(number, action["key"])
                    elif kind == "double_click":
                        injector.double_click()
                    elif kind == "macro":
                        injector.macro(action.get("steps", []))
                elif kind == "hold":
                    injector.release(number)
            last_mask = mask
    finally:
        try:
            device.request(spy, 0x20, bytes([0, 0, 0]))
            if original_mapping is not None:
                device.request(spy, 0x40, bytes(original_mapping) + bytes(16 - len(original_mapping)), long=True)
            device.request(onboard, 0x10, bytes([1, 0, 0]))
        finally:
            injector.close()
            device.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
