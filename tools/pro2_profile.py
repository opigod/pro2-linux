#!/usr/bin/env python3
"""
Inspector, backup/restore and raw profile editor for the Logitech PRO 2
LIGHTSPEED (G PRO 2 LIGHTSPEED).

It speaks HID++ 2.0 directly over /dev/hidraw, using feature 0x8100
(Onboard Profiles) to read or write the 255-byte profile sectors.  It does
not need libratbag, ratbagd, Solaar or G HUB.

Usage:
    ./pro2_profile.py show
    ./pro2_profile.py backup DIR
    ./pro2_profile.py restore DIR
    ./pro2_profile.py set-stage N DPI [--lod 0|1|2]
    ./pro2_profile.py set-default N
    ./pro2_profile.py set-button N mouse|key|special|disabled VALUE

Restore writes the sectors in DIR back to the mouse.  Use it only with a
backup made from the same mouse.  A profile write is persistent; keep the
mouse powered while restoring.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import select
import sys
import time
from pathlib import Path

SECTOR_SIZE = 255
PROFILE_COUNT = 5


def crc_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        temp = ((crc >> 8) ^ byte) & 0xFFFF
        crc = (crc << 8) & 0xFFFF
        quick = (temp ^ (temp >> 4)) & 0xFFFF
        crc ^= quick
        quick = (quick << 5) & 0xFFFF
        crc ^= quick
        quick = (quick << 7) & 0xFFFF
        crc ^= quick
    return crc & 0xFFFF


def find_device() -> tuple[str, int]:
    """Return (hidraw_path, HID++ device index) for the PRO 2 or its receiver."""
    candidates: list[tuple[int, str, int]] = []
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = entry / "device" / "uevent"
        try:
            text = uevent.read_text()
        except OSError:
            continue
        fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        hid_id = fields.get("HID_ID", "")
        name = fields.get("HID_NAME", "")
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        vendor, product = int(parts[1], 16), int(parts[2], 16)
        if vendor != 0x046D:
            continue
        try:
            descriptor = (entry / "device" / "report_descriptor").read_bytes()
        except OSError:
            continue
        # HID++ long-report interface. The plain mouse/keyboard interfaces on
        # the same USB device do not carry report ID 0x11.
        if b"\x85\x11" not in descriptor:
            continue
        if product == 0xC09A:
            candidates.append((0, f"/dev/{entry.name}", 0xFF))
        elif product == 0xC543:
            candidates.append((1, f"/dev/{entry.name}", 1))
        elif "PRO 2" in name.upper():
            candidates.append((2, f"/dev/{entry.name}", 0xFF))
    if not candidates:
        raise SystemExit(
            "PRO 2 LIGHTSPEED not found. Connect it by USB (046d:c09a) "
            "or its receiver (046d:c543)."
        )
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

    def request(
        self,
        feature: int,
        function: int,
        params: bytes = b"",
        *,
        long: bool = False,
        timeout: float = 1.0,
    ) -> bytes | None:
        report_id = 0x11 if long else 0x10
        size = 20 if long else 7
        frame = bytes([report_id, self.index, feature, function]) + params
        frame = frame + b"\x00" * (size - len(frame))
        try:
            os.write(self.fd, frame)
        except OSError as error:
            raise SystemExit(
                f"write to {self.path} failed: {error}. "
                "Is another program (ratbagd, Solaar, OpenLogi) holding the device?"
            ) from error
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            reply = os.read(self.fd, 64)
            if (
                len(reply) >= 7
                and reply[0] in (0x10, 0x11)
                and reply[1] == self.index
                and reply[2] == feature
                and (reply[3] & 0xF0) == (function & 0xF0)
            ):
                return reply
        return None

    def read_sector(self, sector: int) -> bytes:
        data = b""
        offset = 0
        while offset < SECTOR_SIZE - 15:
            reply = self.request(
                0x0F, 0x50, bytes([sector >> 8, sector & 0xFF, offset >> 8, offset & 0xFF]), long=True
            )
            if reply is None:
                raise SystemExit(f"no reply reading sector {sector} offset {offset}")
            data += reply[4:20]
            offset += 16
        reply = self.request(
            0x0F, 0x50, bytes([sector >> 8, sector & 0xFF, (SECTOR_SIZE - 16) >> 8, (SECTOR_SIZE - 16) & 0xFF]), long=True
        )
        if reply is None:
            raise SystemExit(f"no reply reading sector {sector} tail")
        data += reply[4:20][1:]
        data = data[:SECTOR_SIZE]
        stored = int.from_bytes(data[-2:], "big")
        if crc_ccitt(data[:-2]) != stored:
            raise SystemExit(f"sector {sector}: bad CRC in read data")
        return data

    def write_sector(self, sector: int, data: bytes) -> None:
        if len(data) != SECTOR_SIZE:
            raise SystemExit(f"sector {sector}: expected {SECTOR_SIZE} bytes")
        if crc_ccitt(data[:-2]) != int.from_bytes(data[-2:], "big"):
            raise SystemExit(f"sector {sector}: refusing to write a bad CRC")
        prepare = bytes([sector >> 8, sector & 0xFF, 0, 0, 0, SECTOR_SIZE])
        if self.request(0x0F, 0x60, prepare, long=True) is None:
            raise SystemExit(f"sector {sector}: prepare write failed")
        for offset in range(0, SECTOR_SIZE, 16):
            if self.request(0x0F, 0x70, data[offset : offset + 16], long=True) is None:
                raise SystemExit(f"sector {sector}: chunk at {offset} failed")
        if self.request(0x0F, 0x80, b"", long=True) is None:
            raise SystemExit(f"sector {sector}: commit failed")


def decode_buttons(data: bytes) -> list[str]:
    out = []
    for i in range(8):
        offset = 48 + 4 * i
        kind, subtype = data[offset], data[offset + 1]
        value = int.from_bytes(data[offset + 2 : offset + 4], "big")
        if kind == 0x80 and subtype == 0x01:
            bits = [n + 1 for n in range(16) if value & (1 << n)]
            out.append(f"button {'/'.join(map(str, bits))}" if bits else "none")
        elif kind == 0x80 and subtype == 0x02:
            out.append(f"keyboard key 0x{value:02x}")
        elif kind == 0x90:
            out.append(f"special 0x{subtype:02x}")
        else:
            out.append(f"type 0x{kind:02x}/0x{subtype:02x} value 0x{value:04x}")
    return out


def show(device: Hidpp) -> None:
    directory = device.read_sector(0)
    entries = []
    for offset in range(0, 20, 4):
        sector = int.from_bytes(directory[offset : offset + 2], "big")
        if sector == 0xFFFF:
            break
        entries.append((sector, directory[offset + 2] != 0))
    print(f"device: {device.path} (HID++ index {device.index})")
    for number, (sector, enabled) in enumerate(entries, 1):
        if not enabled:
            print(f"profile {number}: sector {sector}, disabled")
            continue
        data = device.read_sector(sector)
        print(f"profile {number}: sector {sector}, enabled")
        stages = []
        for i in range(5):
            offset = 4 + 5 * i
            x = int.from_bytes(data[offset : offset + 2], "little")
            y = int.from_bytes(data[offset + 2 : offset + 4], "little")
            stages.append(f"{x}x{y}@LOD{data[offset + 4]}")
        print(f"  DPI stages: {', '.join(stages)}")
        print(f"  default stage: {data[2] + 1}, switched stage: {data[3] + 1}")
        dpi = device.request(0x0B, 0x50, b"\x00", long=False)
        if dpi is not None and len(dpi) >= 9:
            print(f"  current DPI: {int.from_bytes(dpi[5:7], 'big')}x{int.from_bytes(dpi[9:11], 'big') if len(dpi) >= 11 else int.from_bytes(dpi[5:7], 'big')}")
        print(f"  report rate: wired={data[1]}, wireless={data[0]} (0=125Hz..6=8kHz)")
        for i, label in enumerate(decode_buttons(data), 1):
            print(f"  button {i}: {label}")


def backup(device: Hidpp, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for sector in range(PROFILE_COUNT + 1):
        data = device.read_sector(sector)
        (directory / f"profile_sector_{sector}.bin").write_bytes(data)
        (directory / f"profile_sector_{sector}.hex").write_text(data.hex(" ") + "\n")
        print(f"sector {sector}: {hashlib.sha256(data).hexdigest()[:16]}  {len(data)} bytes")
    print(f"backup written to {directory}")


def restore(device: Hidpp, directory: Path) -> None:
    # Profiles first, directory last: if the write is interrupted, the old
    # directory still points at the old profiles rather than at half-written
    # ones.
    order = list(range(1, PROFILE_COUNT + 1)) + [0]
    for sector in order:
        path = directory / f"profile_sector_{sector}.bin"
        if not path.exists():
            raise SystemExit(f"missing {path}")
        data = path.read_bytes()
        device.write_sector(sector, data)
        print(f"sector {sector}: written")
    for sector in order:
        expected = (directory / f"profile_sector_{sector}.bin").read_bytes()
        actual = device.read_sector(sector)
        if actual != expected:
            raise SystemExit(f"sector {sector}: readback mismatch")
        print(f"sector {sector}: verified")


def update_profile(device: Hidpp, mutate) -> bytes:
    data = bytearray(device.read_sector(1))
    mutate(data)
    data[-2:] = crc_ccitt(bytes(data[:-2])).to_bytes(2, "big")
    device.write_sector(1, bytes(data))
    check = device.read_sector(1)
    if check != bytes(data):
        raise SystemExit("profile readback mismatch")
    return bytes(data)


def set_stage(device: Hidpp, stage: int, dpi: int, lod: int | None) -> None:
    if not 1 <= stage <= 5:
        raise SystemExit("stage must be 1..5")
    if not 100 <= dpi <= 44000:
        raise SystemExit("dpi must be 100..44000")
    def mutate(data: bytearray) -> None:
        offset = 4 + 5 * (stage - 1)
        data[offset : offset + 2] = dpi.to_bytes(2, "little")
        data[offset + 2 : offset + 4] = dpi.to_bytes(2, "little")
        if lod is not None:
            data[offset + 4] = lod
    update_profile(device, mutate)
    print(f"stage {stage}: {dpi}x{dpi}" + (f", LOD {lod}" if lod is not None else ""))


def set_default_stage(device: Hidpp, stage: int) -> None:
    if not 1 <= stage <= 5:
        raise SystemExit("stage must be 1..5")
    def mutate(data: bytearray) -> None:
        data[2] = stage - 1
    update_profile(device, mutate)
    print(f"default stage: {stage}")


def set_button(device: Hidpp, number: int, action: str, value: str) -> None:
    if not 1 <= number <= 8:
        raise SystemExit("button must be 1..8")
    offset = 48 + 4 * (number - 1)

    def mutate(data: bytearray) -> None:
        if action == "mouse":
            button = int(value, 0)
            if not 1 <= button <= 16:
                raise SystemExit("mouse button must be 1..16")
            data[offset : offset + 4] = bytes([0x80, 0x01]) + (1 << (button - 1)).to_bytes(2, "big")
        elif action == "key":
            key = int(value, 0)
            if not 0 <= key <= 0xFF:
                raise SystemExit("key code must be 0..255")
            data[offset : offset + 4] = bytes([0x80, 0x02, 0x00, key])
        elif action == "special":
            code = int(value, 0)
            if not 0 <= code <= 0xFF:
                raise SystemExit("special code must be 0..255")
            data[offset : offset + 4] = bytes([0x90, code, 0x00, 0x00])
        elif action == "disabled":
            data[offset : offset + 4] = bytes([0xFF, 0x00, 0x00, 0x00])
        else:
            raise SystemExit("action must be mouse, key, special or disabled")

    update_profile(device, mutate)
    print(f"button {number}: {action} {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show")
    p_backup = sub.add_parser("backup")
    p_backup.add_argument("directory", type=Path)
    p_restore = sub.add_parser("restore")
    p_restore.add_argument("directory", type=Path)
    p_stage = sub.add_parser("set-stage", help="change one DPI stage in the enabled profile")
    p_stage.add_argument("stage", type=int, choices=range(1, 6))
    p_stage.add_argument("dpi", type=int)
    p_stage.add_argument("--lod", type=int, choices=range(0, 3))
    p_default = sub.add_parser("set-default", help="choose the DPI stage used after power-on")
    p_default.add_argument("stage", type=int, choices=range(1, 6))
    p_button = sub.add_parser("set-button", help="change a button binding in the enabled profile")
    p_button.add_argument("number", type=int, choices=range(1, 9))
    p_button.add_argument("action", choices=["mouse", "key", "special", "disabled"])
    p_button.add_argument("value", nargs="?", default="0", help="button number, key code, or special code")
    args = parser.parse_args()

    path, index = find_device()
    device = Hidpp(path, index)
    try:
        if args.command == "show":
            show(device)
        elif args.command == "backup":
            backup(device, args.directory)
        elif args.command == "restore":
            restore(device, args.directory)
        elif args.command == "set-stage":
            set_stage(device, args.stage, args.dpi, args.lod)
        elif args.command == "set-default":
            set_default_stage(device, args.stage)
        elif args.command == "set-button":
            set_button(device, args.number, args.action, args.value)
    finally:
        device.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
