# Troubleshooting

## `No devices available` / “Cannot connect to ratbagd”

The hidraw node is usually `root:root` after re-enumeration. Install the udev
rule once:

```sh
sudo ./scripts/install-udev.sh
```

Then unplug/replug the mouse or receiver. Verify:

```sh
getfacl -p /dev/hidraw*
```

You want `user:<you>:rw-` on the HID++ node.

## `Profile layout not supported: 0x07`

You are running stock libratbag, not this repository’s build. Run:

```sh
make setup
./scripts/pro2ctl list
```

Do not use the packaged Piper/libratbag for this mouse if they are older than
the format-`0x07` support.

## Colour changes do not appear

Use the patched build (`make setup`). If it still fails, test the live path:

```sh
./scripts/pro2ctl stop
python3 tools/pro2_light.py set 00ff00 --persist
```

If that works but Piper does not, report the libratbag build/commit.

## Button remap applies but does nothing

1. Power-cycle the mouse once. Some firmware keeps its old button map in RAM.
2. Verify the binding bytes:
   ```sh
   ./scripts/pro2ctl stop
   python3 tools/pro2_profile.py show
   ```
3. Try the safe raw path:
   ```sh
   python3 tools/pro2_profile.py set-button 7 key 0x68
   ```
4. If onboard remaps still do nothing, use the host-mode remapper:
   ```sh
   ./scripts/pro2-special
   ```

## Macro or double-click error

Expected: profile format `0x07` does not model macro pages, and double-click
has no profile special code. Do not use Piper’s macro editor. Use
`pro2-special` instead.

## Buttons stopped working after killing the remapper

A hard kill can leave muted buttons in host mode. Power-cycle the mouse. This
restores onboard mode and the original mapping.

## Receiver not detected

- Confirm `lsusb` shows `046d:c543`.
- Install the udev rule and replug.
- Stop Solaar/OpenLogi/Piper; only one process can own the receiver.
- Report `sudo ./scripts/pro2ctl list` with `--verbose` daemon logs.

## Restore a backup

```sh
./scripts/pro2ctl stop
python3 tools/pro2_profile.py restore my-backup
```

The restore writes profiles first and the directory last, so an interrupted
restore does not point at half-written data.

## Start over

```sh
rm -rf .build
make setup
```

Profiles live on the mouse, not in the repository.
