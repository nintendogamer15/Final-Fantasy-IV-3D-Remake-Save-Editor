# FFIV 3D Remake Save Editor

## Human written foreword

This tool is pretty much all AI generated, besides what was taken from the repo of the old save editor by KingCyrus20 which is listed below.
I'm not a programmer, and the code is probably a giant mess, but it works. KingCyrus20's editor stopped working because an update to the game in 2020 changed how saves work. There are now (I think) multiple checksums that need to be validated. By bouncing some saves around several AI agents and doing some trial and error testing, they seem to have cracked it. I left their explanation for how all that works in the file titled FFIV_3D_CHECKSUM_ISSUE_EXPLAINED.
Anyway, I'll let Jippity take it from here.

This is a desktop, command-line, and interactive terminal editor for the PC/GOG/Steam Final Fantasy IV 3D Remake `SAVE.BIN` format. Version 0.6.1 is implemented in C# on .NET 10, with an Avalonia desktop interface for Windows and Linux.

## Features

- Validates the exact 65,536-byte save format and `cd1000` header.
- Inspects all three visible slots, checksum state, party statistics, inventory, and the redundant save copy.
- Repairs the post-2020 checksums and updates an occupied redundant copy along with the selected visible slot.
- Maxes the current party or every occupied roster row.
- Adds individual items/gear or the complete known catalog, with quantity control.
- Applies the established late-game equipment preset.
- Preserves bytes outside the edited fields.
- Writes a new file by default; explicit in-place writes first create `.bak`, `.bak.1`, and later numbered backups.

## Download and use

Tagged releases provide:

- `FFIV3DSaveEditor-vX.Y.Z-windows-x64.exe`
- `FFIV3DSaveEditor-vX.Y.Z-linux-x64`

The builds are self-contained; no separate .NET installation is needed. Windows builds are unsigned, so Windows may display a SmartScreen warning.

On Windows, run the `.exe`. On Linux:

```bash
chmod +x FFIV3DSaveEditor-vX.Y.Z-linux-x64
./FFIV3DSaveEditor-vX.Y.Z-linux-x64
```

Choose the original `SAVE.BIN`, make edits in memory, and use **Write New File**. Keep a clean copy of the original save until the edited save has loaded successfully in-game.

## Command line

The source tree also contains `FFIV3DSaveEditor.Cli`:

```bash
dotnet run --project src/FFIV3D.SaveEditor.Cli -- SAVE.BIN --inspect-all
dotnet run --project src/FFIV3D.SaveEditor.Cli -- SAVE.BIN --slot 1 --max-party --give-everything --out SAVE_EDITED.BIN
dotnet run --project src/FFIV3D.SaveEditor.Cli -- SAVE.BIN --interactive
```

Run with `--help` for slot targeting, checksum-only repair, item lookup, equipment, output, and in-place options.

## Build from source

Install the .NET 10 SDK, then run:

```bash
dotnet restore FFIV3D.SaveEditor.slnx
dotnet build FFIV3D.SaveEditor.slnx --configuration Release
dotnet test FFIV3D.SaveEditor.slnx --configuration Release
./scripts/build-release.sh v0.6.1
```

The release script runs on Linux and publishes both `win-x64` and `linux-x64` self-contained single-file applications. Output goes to `artifacts/` unless another directory is supplied.

## Notes and limitations

- This editor supports the PC 3D Remake `SAVE.BIN`; it does not support unrelated FFIV releases or console save containers.
- The redundant copy is handled automatically for normal visible-slot edits. The CLI also provides an advanced redundant-only target.
- Detailed checksum research remains in [`FFIV_3D_CHECKSUM_ISSUE_EXPLAINED.txt`](FFIV_3D_CHECKSUM_ISSUE_EXPLAINED.txt).

## License and credits

The project is LGPL-3.0-or-later. Save-layout and item/equipment data adapted from KingCyrus20's FFIV Save Editor remain credited in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). See `LICENSE`, `COPYING`, `COPYING.LESSER`, and `ADDITIONAL_PERMISSIONS.md`.
