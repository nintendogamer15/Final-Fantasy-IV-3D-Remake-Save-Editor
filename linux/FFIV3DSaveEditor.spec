# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Linux binary placed inside the AppImage.
import os
import glob
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))


def required_library(name):
    """Locate desktop libraries PyInstaller otherwise classifies as system libs."""
    patterns = [
        os.path.join(sys.prefix, "lib", name),
        os.path.join("/lib", "*", name),
        os.path.join("/usr/lib", "*", name),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return (matches[0], ".")
    raise RuntimeError(f"Required portable-GUI library not found: {name}")


PORTABLE_GL_LIBS = [
    required_library(name)
    for name in ("libGL.so.1", "libEGL.so.1", "libGLX.so.0", "libGLdispatch.so.0")
]

a = Analysis(
    [os.path.join(ROOT, "ffiv3d_save_gui.py")],
    pathex=[ROOT],
    binaries=PORTABLE_GL_LIBS,
    datas=[(os.path.join(ROOT, "assets", "icon.svg"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FFIV3DSaveEditor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
