# PRO 2 LIGHTSPEED protocol notes

Everything below was read from a real **G PRO 2 LIGHTSPEED** (`MR0110`) on
Linux, wired as `046d:c09a`. The Lightspeed receiver is `046d:c543`.

## Transport

The wired mouse exposes three HID interfaces:

| Interface | Usage | Reports | Purpose |
|---|---|---|---|
| 1.0 | mouse | 0x01, 0x03, 0x04 | normal mouse/keyboard |
| 1.1 | keyboard | 0x01, 0x03, 0x04 | keyboard/consumer reports |
| 1.2 | vendor `0xFF43/0x0301`, `0xFF43/0x0302` | 0x10, 0x11 | HID++ 2.0 |

HID++ frames:

```
short: 10 <device_idx> <feature_idx> <function> <3 bytes>
long:  11 <device_idx> <feature_idx> <function> <16 bytes>
```

- wired device index: `0xff`
- receiver slot: normally `1`
- responses use the same report ID; errors use report ID `0xff`

Feature discovery:

```
root 0x0000 fn 0x00 getFeature(feature_id)
FEATURE_SET 0x0001 fn 0x00 getCount
FEATURE_SET 0x0001 fn 0x10 getFeatureId(index)
```

## Feature table (wired unit, firmware 31.x)

35 entries including root. The important ones:

| Feature | ID | Version | Notes |
|---|---|---:|---|
| ROOT | `0x0000` | 2 | |
| FEATURE SET | `0x0001` | 2 | |
| DEVICE FW VERSION | `0x0003` | 7 | |
| DEVICE NAME | `0x0005` | 5 | |
| WIRELESS DEVICE STATUS | `0x1D4B` | 0 | |
| CONFIG CHANGE | `0x0020` | 0 | |
| UNIFIED BATTERY | `0x1004` | 5 | |
| XY STATS | `0x2250` | 1 | |
| WHEEL STATS | `0x2251` | 0 | |
| RGB EFFECTS | `0x8071` | 4 | live and stored RGB |
| EXTENDED ADJUSTABLE DPI | `0x2202` | 0 | 100–44,000 DPI, X/Y + LOD |
| MODE STATUS | `0x8090` | 3 | |
| unknown | `0x80E0` | 0 | |
| EXTENDED ADJUSTABLE REPORT RATE | `0x8061` | 0 | |
| ONBOARD PROFILES | `0x8100` | 0 | format `0x07`, 5 profiles |
| MOUSE BUTTON SPY | `0x8110` | 0 | 8 slots |
| FORCE PAIRING | `0x1500` | 0 | |
| DEVICE RESET | `0x1802` | 0 | |

**There is no `0x1B00`–`0x1B04` ReprogControls feature.** That is why generic
button-remapping code paths cannot configure this mouse.

Feature indices are dynamic; always resolve them through ROOT.

## DPI — `0x2202`

Functions:

| fn | Meaning |
|---|---|
| `0x00` | sensor count |
| `0x10` | sensor capabilities |
| `0x20` | DPI range list |
| `0x30` | per-profile DPI list |
| `0x40` | LOD list |
| `0x50` | current/default DPI + LOD |
| `0x60` | set DPI + LOD |

Observed sensor:

- 1 sensor, 5 DPI levels
- current/default 800/6400 (factory profile)
- range 100–44,000 DPI
- LOD 0/1/2 = low/medium/high; factory `2`

`0x60` is a long request:

```
sensor, dpi_x_be16, dpi_y_be16, lod
```

If the mouse is in onboard mode (`0x8100` mode 1), a DPI write can be refused
with `ERR_INVALID_ARGUMENT` / `LogitechInternal`. Switch to host mode first, or
write the onboard profile.

## Report rate — `0x8061`

| fn | Meaning |
|---|---|
| `0x00` | supported rates for a connection (`0` wired, `1` wireless) |
| `0x10` | rates for the current connection |
| `0x20` | read current rate |
| `0x30` | write current rate |

Rate encoding: `0=125`, `1=250`, `2=500`, `3=1000`, `4=2000`, `5=4000`,
`6=8000` Hz.

Wired supports 125–1000 Hz; wireless supports 125–8000 Hz.

## Onboard profiles — `0x8100`

Info response (`fn 0x00`) from this unit:

```
memory_model=1, profile_format=0x07, macro_format=1,
profile_count=5, oob_count=1, button_count=8,
sector_count=16, sector_size=255
```

Directory is sector `0`, entries are 4 bytes `(sector_be16, enabled, pad)`,
terminated by sector `0xffff`. Factory state had only profile 1 enabled.

Modes (`fn 0x10` / `0x20`):

- `1` = onboard (profile owns DPI, rate, buttons, LEDs)
- `2` = host (host can write DPI/rate; `0x8110` owns buttons)

Profile sector layout for format `0x07` (255 bytes):

| Offset | Field |
|---:|---|
| 0 | wireless report rate |
| 1 | wired report rate |
| 2 | default DPI stage (0-based) |
| 3 | switched DPI stage (0-based) |
| 4–28 | 5 × `{x_le16, y_le16, lod}` |
| 29–36 | reserved |
| 37 | BHOP timeout |
| 38–43 | reserved |
| 44–45 | powersave timeout |
| 46–47 | poweroff timeout |
| 48–111 | 16 button bindings × 4 bytes |
| 112–159 | 12 alternate/G-Shift bindings × 4 bytes |
| 160–207 | UTF-16LE profile name |
| 208–229 | 2 × LED, 11 bytes each |
| 230–251 | 2 × alternate LED, 11 bytes each |
| 252 | reserved |
| 253–254 | CRC-16/CCITT over bytes 0–252, big-endian |

Button binding encoding:

```
80 01 <be16 bitmask>       mouse button (1 << (button-1))
80 02 <modifier> <key>     keyboard key
80 03 <be16 usage>         consumer control
90 <special> 00 00         Logitech special (05 = cycle DPI, etc.)
00 <page> 00 <offset>      macro reference
ff 00 00 00                disabled
```

Only special codes `0x01`–`0x0b` are mapped by libratbag. Double-click is not a
profile special code. Format `0x07` macro pages are not implemented; writing a
macro as a single key is wrong. Use host-mode remapping for macros/double-click.

LED entry (11 bytes): `mode, r, g, b, effect, padding...`. Mode `1` = on.
Writing these bytes only is not enough for an immediate change; also apply the
live `0x8071` effect.

## Button spy — `0x8110`

| fn | Meaning |
|---|---|
| `0x00` | button count (8) |
| `0x10` | start spy |
| `0x20` | stop spy |
| `0x30` | get mapping (8 HID button codes) |
| `0x40` | set mapping (long, 16 bytes) |

Mapping value `0` mutes that slot in host mode; values `1..8` send the
corresponding HID mouse button. Unsolicited reports use sub-ID `0` and a
big-endian 16-bit mask at payload bytes 0–1.

Host-mode remapping:

1. set `0x8100` mode 2;
2. mute only the chosen slots through `0x8110` fn `0x40`;
3. start spy;
4. inject actions with `/dev/uinput`;
5. stop spy, restore mapping, set mode 1.

A hard kill can leave muted buttons until the mouse is power-cycled.

## RGB — `0x8071`

`get_info` (`fn 0x00`, `[0xff,0xff,0x00]`) reports one cluster. Cluster 0 has
two effects; effect ordinal 1 is static.

`set_sw_control` (`fn 0x50`):

```
[0x01, control, events]   control bit 0 = ALL_CLUSTERS
```

`set_rgb_cluster_effect` (`fn 0x10`, long):

```
cluster, effect_ordinal, params[10], flags, 0,0,0
```

For static colour, `params = [r,g,b,0,0,0,0,0,0,0]`, effect ordinal `1`,
flags `0x01` = volatile. `0x02` in flags means non-volatile.

Apply colour live, then release with `[0x01,0,0]`. The profile LED bytes are
the persistent fallback.

## Useful diagnostics

```sh
./scripts/pro2ctl list
python3 tools/pro2_profile.py show
python3 tools/pro2_light.py status
sudo hid-recorder /dev/hidrawN
sudo usbmon / Wireshark
```

This document is intentionally implementation-oriented. Pull requests with
more firmware variants, captured macro pages, or cleaner protocol abstractions
are welcome.
