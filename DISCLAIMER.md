# AI-generated code disclaimer

**This project is experimental, AI-assisted software. Use it at your own risk.**

This repository was created largely by an AI coding agent under human
direction. It has **not** been independently audited, reviewed, or certified by
a human. The protocol notes were derived from live probing of one retail
mouse, public reverse-engineering projects, and experimentation. They may be
wrong, incomplete, or specific to one firmware revision.

AI-generated code can make confident-looking mistakes. In this project those
mistakes can have real consequences:

- profile edits are written to the mouse’s **persistent onboard flash**;
- a bad write can corrupt button mappings, lighting settings, DPI stages, or
  the profile directory;
- host-mode remapping changes button ownership and can leave buttons muted;
- a hard kill or power loss during a profile restore can leave the mouse in a
  temporarily broken state;
- the RGB and macro paths involve undocumented or partially documented HID++
  behaviour;
- receiver and wired paths have different device indices and may behave
  differently across firmware versions.

## Before you run anything

1. Read the code and the protocol notes.
2. Back up the onboard profiles:
   ```sh
   ./scripts/pro2ctl stop
   python3 tools/pro2_profile.py backup my-backup
   ```
3. Keep a recovery path available, such as a Windows machine with Logitech
   G HUB or Onboard Memory Manager.
4. Test one change at a time. Do not run profile restores unattended.
5. Do not use this on a mouse you cannot afford to power-cycle or recover.

## No warranty

This software is provided “as is”, without warranty of any kind, express or
implied, including but not limited to the warranties of merchantability,
fitness for a particular purpose, and non-infringement. The authors and
contributors are not liable for damage to hardware, lost settings, lost data,
or any other damages arising from use of this software. See `LICENSE`.

## Not affiliated with Logitech

This is an independent community project. “Logitech”, “G PRO”, “LIGHTSPEED”,
and related names are trademarks of Logitech. This project is not endorsed by
or affiliated with Logitech.

## Contributions are welcome

Human review, hardware testing, bug reports, and safer implementations are
exactly what this project needs. If you find an AI-generated mistake, please
open an issue or submit a fix. See `CONTRIBUTING.md`.
