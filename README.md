# Logitech PRO 2 LIGHTSPEED on Linux

> [!CAUTION]
> **AI-GENERATED, EXPERIMENTAL CODE — USE AT YOUR OWN RISK.**
>
> This repository was written largely by an AI coding agent under human
> direction. It has **not** been independently audited by a human, and it may
> contain mistakes, unsafe assumptions, incomplete edge cases, protocol
> misunderstandings, or destructive bugs that a human reviewer would catch.
>
> It writes persistent data to the mouse’s onboard flash, switches HID++
> modes, and can leave buttons muted or profiles corrupted. Back up your
> profiles before testing. Do not use it unattended, in production, or on
> hardware you cannot recover. There is **no warranty** of any kind.
>
> Read the full [`DISCLAIMER.md`](DISCLAIMER.md) before running anything.

[![CI](https://github.com/opigod/pro2-linux/actions/workflows/ci.yml/badge.svg)](https://github.com/opigod/pro2-linux/actions/workflows/ci.yml)

Linux support for the **Logitech G PRO 2 LIGHTSPEED** (`G PRO 2 LIGHTSPEED`,
wired `046d:c09a`, Lightspeed receiver `046d:c543`) — not the Superlight 2.

The Pro 2 is an ambidextrous 8-button mouse with RGB, five onboard profiles and
HERO 2 sensor. It speaks HID++ 2.0 but is unusual in two ways:

- it has **no `0x1B04` ReprogControls** feature, so generic “reprogrammable
  keys” support cannot remap it;
- button actions live in `0x8100` onboard profiles using **profile format
  `0x07`**, with live button reports available through `0x8110`.

This repository packages the patches and tools needed to make it usable on
Linux, and documents the protocol so others can build a fuller GUI.

## What works

| Feature | Status |
|---|---|
| DPI, X/Y and lift-off distance | ✅ 100–44,000 DPI |
| Report rate | ✅ 125–1000 Hz wired, 125–8000 Hz wireless |
| Five DPI stages / profile presets | ✅ |
| Basic button remapping (mouse button, key, special action) | ✅ |
| RGB colour | ✅ live `0x8071` + persisted profile |
| Battery / device info | ✅ |
| Double-click and multi-step macros | ✅ via the host-mode remapper |
| Piper GUI | ✅ locally built patched libratbag |
| OpenLogi / Solaar | ⚠️ partial / not patched here |

The Pro 2’s onboard profile format does **not** expose a usable macro or
double-click encoding in libratbag. Those are handled by `pro2-special`, which
puts the mouse in host mode, captures the requested buttons through `0x8110`,
and injects keys/clicks with `/dev/uinput`.

## Requirements

Linux, Python 3.10+, Meson, Ninja, a C compiler, GTK 3 / PyGObject and the
libratbag build dependencies.

Arch:

```sh
sudo pacman -S --needed base-devel meson ninja pkgconf systemd-libs libevdev \
  json-glib glib2 python-gobject gtk3 gettext
```

Fedora:

```sh
sudo dnf install gcc meson ninja-build pkgconf systemd-devel libevdev-devel \
  json-glib-devel glib2-devel python3-gobject gtk3 gettext
```

Debian/Ubuntu:

```sh
sudo apt install build-essential meson ninja-build pkg-config libsystemd-dev \
  libevdev-dev libjson-glib-dev libglib2.0-dev python3-gi gir1.2-gtk-3.0 gettext
```

## Build and install

```sh
git clone https://github.com/opigod/pro2-linux.git
cd pro2-linux
make setup
sudo ./scripts/install-udev.sh
./scripts/pro2ctl list
```

`make setup` builds:

- **libratbag** from PR #1896 (`buntatoes/libratbag`, pinned commit) plus the
  patches in `patches/`;
- **Piper** from upstream, installed under `.build/piper-install`.

Nothing is installed system-wide except the udev rule. The local builds live
in `.build/` and are ignored by git.

## Use

Piper GUI:

```sh
./scripts/pro2-piper
```

CLI:

```sh
./scripts/pro2ctl list
./scripts/pro2ctl info
./scripts/pro2ctl dpi get
./scripts/pro2ctl dpi set 1600
./scripts/pro2ctl profile 0 button 7 action set key KEY_F13   # 0-based
./scripts/pro2ctl rate set 1000
./scripts/pro2ctl stop
```

Double-click, macros and held keys:

```sh
./scripts/pro2-special
```

Close Piper first. `pro2-special` stops `ratbagd`, enters host mode, mutes only
the buttons in `config/pro2-remap.json`, and restores everything on Ctrl+C.

## Raw profile tool

`pro2_profile.py` talks HID++ directly and preserves fields the GUI does not
model:

```sh
./scripts/pro2ctl stop
python3 tools/pro2_profile.py show
python3 tools/pro2_profile.py backup my-backup
python3 tools/pro2_profile.py restore my-backup
python3 tools/pro2_profile.py set-stage 3 1600
python3 tools/pro2_profile.py set-default 3
python3 tools/pro2_profile.py set-button 8 key 0x68   # 1-based
```

Always back up before writing profiles. A profile write is persistent; do not
cut power during a restore.

## RGB

Piper colour changes now apply a live `0x8071` static effect in addition to
writing the profile. A direct fallback is included:

```sh
python3 tools/pro2_light.py set 00aaff --persist
python3 tools/pro2_light.py release
```

## Status and upstream work

- libratbag PR #1896: profile formats `0x06`/`0x07`, `0x2202` DPI, `0x8061`
  report rate. This repository carries local fixes on top.
- OpenLogi issue #1615: receiver/wired detection. The exact missing pieces are
  documented in `docs/protocol.md`.
- Solaar: DPI/report-rate support exists; the receiver ID must be added, and
  its onboard-profile parser does not understand format `0x07`.

See [`docs/status.md`](docs/status.md) and
[`docs/protocol.md`](docs/protocol.md).

## Contributing

Issues and PRs are welcome. Hardware test reports are especially useful:
wired vs receiver, firmware version, distribution/kernel, and `pro2_profile.py
show` output. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

The long-term goal is a proper cross-desktop GUI/daemon; see
[`docs/gui-roadmap.md`](docs/gui-roadmap.md). The intended pieces are:

- native DPI/report-rate/profile editors;
- per-button host-mode remapping;
- macro and double-click support without onboard macro pages;
- per-application profiles;
- a clean upstream path into libratbag/Piper or a standalone app.

## Credits

- libratbag and PR #1896 by the libratbag contributors and `buntatoes`;
- Piper by the libratbag project;
- HID++ protocol research from Solaar, OpenLogi, libratbag, and testing on a
  real PRO 2 LIGHTSPEED.

## License

The original code in this repository is MIT. The libratbag patch is a
derivative of libratbag and follows libratbag’s MIT license. Piper is built
from upstream and is not vendored here.
