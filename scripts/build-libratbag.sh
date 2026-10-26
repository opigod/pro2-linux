#!/usr/bin/env bash
#
# Build patched libratbag from PR #1896 plus the Pro 2 fixes in patches/.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/.build"
SRC="$BUILD/libratbag"
PATCH="$ROOT/patches/0001-libratbag-pro2-profile-rgb.patch"

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "missing required command: $1" >&2
        exit 1
    }
}
need git
need meson
need ninja
need cc

mkdir -p "$BUILD"

if [ ! -d "$SRC/.git" ]; then
    echo "==> cloning libratbag"
    git clone https://github.com/libratbag/libratbag.git "$SRC"
fi

cd "$SRC"
echo "==> fetching PR #1896"
if ! git fetch --depth 1 origin pull/1896/head; then
    echo "==> PR ref unavailable, using the pinned fork commit"
    git remote add fork https://github.com/buntatoes/libratbag.git 2>/dev/null || true
    git fetch --depth 1 fork 1fec67f684d410590ffbcf7ba4b8ab4c644701a3
fi
git checkout --force FETCH_HEAD
git clean -fdx

echo "==> applying PRO 2 patch"
git apply --check "$PATCH"
git apply "$PATCH"

echo "==> building libratbag"
if [ -d build ]; then
    meson setup build -Dtests=false -Ddocumentation=false --wipe
else
    meson setup build -Dtests=false -Ddocumentation=false
fi
ninja -C build

echo
echo "built: $SRC/build/ratbagd"
echo "       $SRC/build/ratbagctl"
