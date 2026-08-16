#!/usr/bin/env bash
# Build FFIV3DSaveEditor-x86_64.AppImage without requiring root access.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
HERE="$(pwd)"

PYTHON=python3
USING_BOOTSTRAPPED_PYTHON=false
if ! command -v python3 >/dev/null 2>&1 || ! python3 -m pip --version >/dev/null 2>&1; then
    echo "=== No usable system Python with pip; bootstrapping a local Python ==="
    if [ ! -x "$HERE/.buildenv/bin/python3" ]; then
        if [ ! -x "$HERE/micromamba" ]; then
            curl -Ls "https://micro.mamba.pm/api/micromamba/linux-64/latest" | tar -xj -C "$HERE" bin/micromamba
            mv "$HERE/bin/micromamba" "$HERE/micromamba"
            rmdir "$HERE/bin" 2>/dev/null || true
        fi
        MAMBA_ROOT_PREFIX="$HERE/.mamba_root" "$HERE/micromamba" create -y -p "$HERE/.buildenv" -c conda-forge python=3.11
    fi
    PYTHON="$HERE/.buildenv/bin/python3"
    USING_BOOTSTRAPPED_PYTHON=true
fi

echo "=== Using $("$PYTHON" --version) at $PYTHON ==="
if [ "$USING_BOOTSTRAPPED_PYTHON" = true ]; then
    # pip's PySide6 wheels intentionally rely on common Linux desktop
    # libraries. Minimal/container hosts may not have them, so install them
    # into the rootless build prefix and let PyInstaller bundle them.
    MAMBA_ROOT_PREFIX="$HERE/.mamba_root" "$HERE/micromamba" install -y \
        -p "$HERE/.buildenv" -c conda-forge \
        dbus libegl libgl libxkbcommon libxcb xorg-libx11 \
        xcb-util xcb-util-cursor xcb-util-image xcb-util-keysyms \
        xcb-util-renderutil xcb-util-wm
    export LD_LIBRARY_PATH="$HERE/.buildenv/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet pyinstaller pyside6-essentials

echo "=== Building standalone Qt binary ==="
"$PYTHON" -m PyInstaller --noconfirm --clean FFIV3DSaveEditor.spec

echo "=== Assembling AppDir ==="
rm -rf AppDir
mkdir -p AppDir/usr/bin
cp dist/FFIV3DSaveEditor AppDir/usr/bin/FFIV3DSaveEditor
cp "$ROOT/assets/icon.svg" AppDir/ffiv3dsaveeditor.svg

cat > AppDir/ffiv3dsaveeditor.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=FFIV 3D Save Editor
Comment=Save editor for Final Fantasy IV 3D Remake
Exec=FFIV3DSaveEditor %f
Icon=ffiv3dsaveeditor
Categories=Utility;
Terminal=false
EOF

cat > AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/FFIV3DSaveEditor" "$@"
EOF
chmod +x AppDir/AppRun

echo "=== Fetching appimagetool ==="
if [ ! -x "$HERE/appimagetool" ]; then
    curl -Ls -o "$HERE/appimagetool" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$HERE/appimagetool"
fi

echo "=== Packaging AppImage ==="
if ! "$HERE/appimagetool" --appimage-extract-and-run ./AppDir FFIV3DSaveEditor-x86_64.AppImage 2>appimagetool.err; then
    if grep -qi fuse appimagetool.err; then
        if [ ! -d "$HERE/.appimagetool-extracted" ]; then
            (cd "$HERE" && "$HERE/appimagetool" --appimage-extract >/dev/null && mv squashfs-root .appimagetool-extracted)
        fi
        "$HERE/.appimagetool-extracted/AppRun" ./AppDir FFIV3DSaveEditor-x86_64.AppImage
    else
        cat appimagetool.err >&2
        exit 1
    fi
fi
rm -f appimagetool.err

echo "=== Done: $HERE/FFIV3DSaveEditor-x86_64.AppImage ==="
