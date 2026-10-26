#!/usr/bin/env bash
#
# Build upstream Piper and install it into .build/piper-install.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/.build"
SRC="$BUILD/piper"
PREFIX="$BUILD/piper-install"

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "missing required command: $1" >&2
        exit 1
    }
}
need git
need meson
need ninja

mkdir -p "$BUILD"

if [ ! -d "$SRC/.git" ]; then
    echo "==> cloning Piper"
    git clone --depth 1 https://github.com/libratbag/piper.git "$SRC"
fi

cd "$SRC"
if [ -d build ]; then
    meson setup build --prefix="$PREFIX" --wipe
else
    meson setup build --prefix="$PREFIX"
fi
ninja -C build
meson install -C build

echo
echo "installed: $PREFIX/bin/piper"
