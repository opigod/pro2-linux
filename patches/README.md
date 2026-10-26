# Patches

`0001-libratbag-pro2-profile-rgb.patch` applies to libratbag PR #1896
(`1fec67f684d410590ffbcf7ba4b8ab4c644701a3`).

It contains:

1. profile format `0x07` writes preserve unmodelled bytes (alternate/G-Shift
   buttons, extra LEDs, reserved fields);
2. live `0x8071` static RGB application instead of only writing profile bytes;
3. re-select the active onboard profile after commit so button maps reload;
4. make the SWIG `ratbag-command` development target optional when `swig` is
   absent.

The patch is applied by `scripts/build-libratbag.sh`. Rebuild and regenerate it
as described in `CONTRIBUTING.md`.

The patch is a derivative of libratbag and follows its MIT license.
