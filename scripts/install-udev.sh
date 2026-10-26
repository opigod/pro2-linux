#!/usr/bin/env bash
#
# Install the hidraw uaccess rule for the PRO 2 LIGHTSPEED.
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install -m 0644 "$ROOT/udev/70-logitech-pro2.rules" /etc/udev/rules.d/70-logitech-pro2.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw --action=add
echo "installed /etc/udev/rules.d/70-logitech-pro2.rules"
echo "unplug/replug the mouse or receiver if it is still not visible"
