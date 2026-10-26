# Contributing

Thanks for helping make the PRO 2 LIGHTSPEED usable on Linux.

## Good first contributions

- Test on a receiver, different firmware, or different distribution/kernel.
- Add the OpenLogi detection fixes (`0xFF43/0x0302`, receiver `0xC543`).
- Add `C543` to Solaar’s receiver table.
- Improve the host-mode remapper: `dpi_cycle`, profile switching, per-app
  profiles, tray UI, systemd user service.
- Add format-`0x07` macro page support if you can capture G HUB traffic.
- Build a standalone GUI on top of the Python tools.

## Reporting a hardware issue

Include:

- exact model, colour, wired or receiver;
- `lsusb -d 046d:`;
- distribution and kernel;
- `./scripts/pro2ctl list`;
- `python3 tools/pro2_profile.py show`;
- relevant `dmesg`/daemon logs.

Use the bug report template.

## Development

```sh
make setup
make check
```

The patches in `patches/` are applied on top of libratbag PR #1896. If you
change the daemon:

1. edit `.build/libratbag`;
2. rebuild with `ninja -C .build/libratbag/build`;
3. regenerate the patch:
   ```sh
   cd .build/libratbag
   git diff > ../../patches/0001-libratbag-pro2-profile-rgb.patch
   ```
4. test a clean rebuild with `./scripts/build-libratbag.sh`.

## Safety

- Back up profiles before writing:
  ```sh
  python3 tools/pro2_profile.py backup my-backup
  ```
- Do not cut power during a restore.
- Prefer volatile host-mode experiments over repeated profile writes.
- Keep a Windows/G HUB recovery option if you experiment with profile format
  `0x07` macro pages.

## Style

- Python: standard library where possible, `python3 -m py_compile` clean.
- Shell: `bash -n` clean, `set -euo pipefail`.
- C patch: follow libratbag style, no unrelated reformatting.

## Pull requests

Describe the hardware, the exact commands run, and the before/after HID++
reads. Screenshots are useful for GUI work. If a change touches profile
writes, include a backup/restore transcript.
