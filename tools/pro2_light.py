#!/usr/bin/env python3
"""
Static RGB control for the Logitech PRO 2 LIGHTSPEED via HID++ 0x8071
(rgbEffects), plus optional persistence into onboard profile 1.

Piper/libratbag's current format-0x07 path writes the onboard profile LED
bytes but never calls 0x8071, so the colour does not change until a profile
reload. This tool writes the profile bytes *and* applies the live 0x8071
static effect.

Usage:
    ./pro2_light.py set RRGGBB [--persist]
    ./pro2_light.py release
    ./pro2_light.py status
"""

from __future__ import annotations

import argparse
import os
import select
import sys
import time
from pathlib import Path

SECTOR_SIZE = 255
PROFILE_LED_OFFSET = 208


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
        raise SystemExit("PRO 2 LIGHTSPEED not found (wired 046d:c09a or receiver 046d:c543)")
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
        try:
            os.write(self.fd, frame)
        except OSError as error:
            raise SystemExit(f"write to {self.path} failed: {error}") from error
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            reply = os.read(self.fd, 64)
            if (
                len(reply) >= 7
                and reply[1] == self.index
                and reply[2] == feature
                and (reply[3] & 0xF0) == (function & 0xF0)
            ):
                return reply
        return None

    def feature_index(self, feature: int) -> int:
        reply = self.request(0x00, 0x00, bytes([feature >> 8, feature & 0xFF]))
        if reply is None or reply[4] == 0:
            raise SystemExit(f"device does not expose HID++ feature 0x{feature:04x}")
        return reply[4]

    def read_sector(self, sector: int) -> bytes:
        data = b""
        offset = 0
        while offset < SECTOR_SIZE - 15:
            reply = self.request(0x0F, 0x50, bytes([sector >> 8, sector & 0xFF, offset >> 8, offset & 0xFF]), long=True)
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
        return data[:SECTOR_SIZE]

    def write_sector(self, sector: int, data: bytes) -> None:
        if crc_ccitt(data[:-2]) != int.from_bytes(data[-2:], "big"):
            raise SystemExit("refusing to write a profile with a bad CRC")
        prepare = bytes([sector >> 8, sector & 0xFF, 0, 0, 0, SECTOR_SIZE])
        if self.request(0x0F, 0x60, prepare, long=True) is None:
            raise SystemExit("profile prepare failed")
        for offset in range(0, SECTOR_SIZE, 16):
            if self.request(0x0F, 0x70, data[offset : offset + 16], long=True) is None:
                raise SystemExit(f"profile chunk at {offset} failed")
        if self.request(0x0F, 0x80, b"", long=True) is None:
            raise SystemExit("profile commit failed")
        if self.read_sector(sector) != data:
            raise SystemExit("profile readback mismatch")


def set_profile_color(device: Hidpp, rgb: bytes) -> None:
    data = bytearray(device.read_sector(1))
    data[PROFILE_LED_OFFSET] = 1  # LED mode: static/on
    data[PROFILE_LED_OFFSET + 1 : PROFILE_LED_OFFSET + 4] = rgb
    data[PROFILE_LED_OFFSET + 4] = 0  # effect
    data[-2:] = crc_ccitt(bytes(data[:-2])).to_bytes(2, "big")
    device.write_sector(1, bytes(data))


def set_live_color(device: Hidpp, rgb: bytes, feature: int) -> None:
    # Claim software control of all clusters: [write, control=ALL_CLUSTERS, events]
    if device.request(feature, 0x50, bytes([1, 1, 0])) is None:
        raise SystemExit("0x8071 setSwControl failed")
    # cluster 0, effect ordinal 1 (Static), 10 effect params, flags=VOLATILE
    params = bytes([0, 1]) + rgb + bytes(7) + bytes([1, 0, 0, 0])
    if device.request(feature, 0x10, params, long=True) is None:
        raise SystemExit("0x8071 setRGBClusterEffect failed")


def release(device: Hidpp, feature: int) -> None:
    if device.request(feature, 0x50, bytes([1, 0, 0])) is None:
        raise SystemExit("0x8071 release failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_set = sub.add_parser("set")
    p_set.add_argument("color", help="RRGGBB, e.g. 00aaff")
    p_set.add_argument("--persist", action="store_true", help="also store the colour in onboard profile 1")
    sub.add_parser("release")
    sub.add_parser("status")

    args = parser.parse_args()
    path, index = find_device()
    device = Hidpp(path, index)
    try:
        feature = device.feature_index(0x8071)
        if args.command == "status":
            reply = device.request(feature, 0x50, bytes([0, 0, 0]))
            print(reply.hex(" ") if reply else "no reply")
        elif args.command == "release":
            release(device, feature)
            print("released")
        else:
            value = args.color.strip().lstrip("#")
            if len(value) != 6:
                raise SystemExit("colour must be RRGGBB")
            rgb = bytes.fromhex(value)
            if args.persist:
                set_profile_color(device, rgb)
            set_live_color(device, rgb, feature)
            print(f"set {value.upper()}" + (" (persisted to profile 1)" if args.persist else " (volatile)"))
    finally:
        device.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
