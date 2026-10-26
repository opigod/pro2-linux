# GUI / app roadmap

The repository deliberately ships small tools instead of a monolithic app. A
full GUI can be built on top without redoing the protocol work.

## Suggested architecture

```
┌─────────────────────────────┐
│ GUI (GTK4/libadwaita, Qt,   │
│ Tauri, Electron, …)         │
└──────────────┬──────────────┘
               │ D-Bus / local API
┌──────────────▼──────────────┐
│ pro2 daemon                 │
│  - inventory                │
│  - DPI / rate / profiles    │
│  - RGB                      │
│  - host-mode remapper       │
│  - per-app profiles         │
└──────────────┬──────────────┘
               │ HID++ over hidraw
┌──────────────▼──────────────┐
│ PRO 2 LIGHTSPEED            │
└─────────────────────────────┘
```

## Reuse options

1. **Fork OpenLogi** and add the two detection fixes plus the `0x8110`/`0x8100`
   host-mode work from PR #1729. This is the shortest route to a polished
   cross-platform GUI.
2. **Fork Piper/libratbag** and finish format-`0x07` support, including macro
   pages, if you can capture G HUB traffic.
3. **New GTK4 app** in Python or Rust using the HID++ layer documented in
   `docs/protocol.md`. The Python tools here are a working reference.
4. **Native** front end over a small Rust daemon. Suitable if
   you want a modern UI and per-app profiles.

## Features worth designing first

- device page with battery, firmware, connection, wired/wireless;
- DPI stages with per-stage X/Y/LOD and a “set as default” action;
- report-rate selector that knows wired vs wireless limits;
- five onboard profiles with enable/rename/switch;
- button map with physical mouse render and per-button action picker;
- host-mode “software layer” for macros, double-click, held keys, per-app
  profiles;
- RGB static colour and brightness;
- backup/restore of raw profile sectors;
- clear “onboard vs software” ownership indicator.

## Hard problems

- Format-`0x07` macro pages are not documented here. Capturing G HUB on
  Windows is the likely path.
- The DPI/profile buttons in host mode need explicit actions (for example
  `dpi_cycle`) because they no longer run their onboard special actions.
- Per-application profiles on Wayland need compositor-specific foreground
  window tracking (wlroots, GNOME extension, KWin script).
- The receiver and wired paths have different HID++ device indices.

## Contribution seams

- `tools/pro2_profile.py` — profile parser/editor and backups.
- `tools/pro2_light.py` — live RGB.
- `tools/pro2_remap.py` — host-mode capture/injection.
- `patches/` — libratbag fixes; keep this small and upstreamable.
- `docs/protocol.md` — protocol reference for any new implementation.
