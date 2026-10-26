# Support status

Tested on a real **G PRO 2 LIGHTSPEED** (`046d:c09a`, MR0110) on CachyOS,
kernel 7.3, wired USB. Receiver support uses the same device file
(`046d:c543`) but needs testing on more units.

## This project

| Area | Status | Notes |
|---|---|---|
| Detection, wired | ✅ | vendor collection `0xFF43/0x0302` |
| Detection, receiver | ✅ expected | receiver ID `046d:c543`; test reports welcome |
| DPI / LOD | ✅ | `0x2202`, 100–44,000 |
| Report rate | ✅ | `0x8061`, wired 1 kHz, wireless up to 8 kHz |
| Five onboard DPI stages | ✅ | profile format `0x07` |
| Basic button remap | ✅ | mouse/key/special, via onboard profile |
| RGB | ✅ | live `0x8071` + stored profile |
| Double-click | ✅ via host remapper | not representable in format `0x07` |
| Multi-step macros | ✅ via host remapper | onboard macro pages not implemented |
| Per-application profiles | ❌ | not in scope yet |
| Battery | ✅ | `0x1004` |

## Upstream

### libratbag

- PR **#1896** adds `0x2202`, `0x8061`, profile formats `0x06`/`0x07` and the
  Pro 2 device file. This repo builds that PR plus local fixes.
- Older PR **#1707** also targeted the Pro 2 and was hardware-tested, but is
  stale and conflicts with current master.
- Local fixes in `patches/`:
  - preserve unmodelled profile bytes (alternate/G-Shift buttons, extra LEDs);
  - apply live `0x8071` RGB;
  - re-select the active profile after commit.

### OpenLogi

Current OpenLogi does not detect the mouse:

- wired HID++ is on `0xFF43/0x0302`, which is not in
  `HIDPP_LONG_COLLECTIONS` (only `0xFF43/0x0202` and `0xFF43/0x0602`);
- the receiver registry lacks `0xC543`;
- buttons require the `0x8110`/`0x8100` host-mode work from PR #1729;
- DPI writes in onboard mode need the host-mode fallback from PR #1289.

The two detection fixes are small and should be contributed upstream.

### Solaar

- `0x2202` and `0x8061` settings exist.
- Receiver `0xC543` is missing from `base_usb.py`.
- Onboard-profile parser rejects format `0x07` (`profile > 0x05`), so no
  button editing.
- Good fallback for DPI/report rate only.

### logiops

Not suitable: its DPI path targets `0x2201`, and there are reports of DPI
writes having no effect on this generation.

## Test matrix wanted

Please report:

- wired and receiver;
- firmware versions;
- other colours/regions (same hardware expected);
- Windows dual-boot behaviour after using this tool;
- profile backup/restore;
- host-mode remapper with different desktop environments.

Use the bug report template and include `python3 tools/pro2_profile.py show`.
