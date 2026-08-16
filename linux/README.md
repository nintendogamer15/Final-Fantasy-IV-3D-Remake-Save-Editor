# Linux portable build

Run:

```bash
./build.sh
```

The script uses the system Python when it has `pip`; otherwise it bootstraps a
local Python without `sudo`. It builds the Qt GUI with PyInstaller and packages:

```text
linux/FFIV3DSaveEditor-x86_64.AppImage
```

Run it with:

```bash
chmod +x FFIV3DSaveEditor-x86_64.AppImage
./FFIV3DSaveEditor-x86_64.AppImage
```

On systems without FUSE, AppImages can also be launched with
`--appimage-extract-and-run`.
