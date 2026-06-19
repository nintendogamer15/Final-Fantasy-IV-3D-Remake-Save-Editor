# FFIV 3D Remake Save Editor

## Human written foreword

This tool is pretty much all AI generated, besides what was taken from the repo of the old save editor by KingCyrus20 which is listed below.
I'm not a programmer, and the code is probably a giant mess, but it works. KingCyrus20's editor stopped working because an update to the game in 2020 changed how saves work. There are now (I think) multiple checksums that need to be validated. By bouncing some saves around several AI agents and doing some trial and error testing, they seem to have cracked it. I left their explanation for how all that works in the file titled FFIV_3D_CHECKSUM_ISSUE_EXPLAINED.
Anyway, I'll let Jippity take it from here.


`ffiv3d_save_tool.py` is a standalone Python 3 command-line utility for the PC/GOG/Steam **Final Fantasy IV 3D Remake** `SAVE.BIN` format.

It was built for the post-2020 save format where older save editors can still modify values, but edited saves fail validation unless the newer checksum behavior is repaired.

## Features


<img width="1382" height="825" alt="image" src="https://github.com/user-attachments/assets/ed38a0ce-29a9-4f4d-8bc5-38cfb2060302" />



- Inspect visible save slots and the redundant/shadow copy.
- Recalculate post-2020 checksums.
- Edit slot 1, slot 2, slot 3, all occupied slots, or only the redundant copy.
- Automatically update the redundant copy at `0xB940` when editing a visible slot.
- Max current-party HP, MP, level, EXP, Strength, Stamina, Speed, Intellect, and Spirit.
- Max all non-empty character rows.
- Add individual items or gear by name or hex ID.
- Add every known non-equipment inventory item.
- Add every known equipment/gear item.
- Equip a tested late-game high-stat loadout.
- Write to a new output file or edit in place with a `.bak` backup.

## Requirements

- Python 3.10 or newer recommended.
- No third-party Python packages for the CLI tool itself.
- The optional TUI (below) needs the third-party `textual` package.

Check Python:

```bash
python3 --version
```

## TUI (interactive terminal UI)

`ffiv3d_save_tui.py` is an optional, more visual front-end for the same editing
logic in `ffiv3d_save_tool.py` (it imports from that file directly, so the two
never drift apart). It shows checksum status, party stats, and inventory for
visible slots 1/2/3 in tabs, with buttons for every action the CLI supports,
instead of needing to remember flag combinations.

The redundant/shadow copy at `0xB940` is intentionally not shown anywhere in
the TUI. It isn't a separate thing to manage: every slot-targeting action
already updates it automatically behind the scenes whenever it's occupied,
exactly like the CLI's default `--slot` behavior described above.

Install the one extra dependency it needs:

```bash
pip install textual
# or: pip install -e ".[tui]"
```

Run it:

```bash
python3 ffiv3d_save_tui.py SAVE.BIN
```

or launch it first and type/browse to a path inside the app:

```bash
python3 ffiv3d_save_tui.py
```

In the TUI:

- Pick a target slot (`1`/`2`/`3`/`all`) in the sidebar, same meaning as `--slot`. Switching the slot tab on the right and switching the radio button in the sidebar stay in sync with each other — changing one updates the other.
- Click an action button (Max Party, Give Everything, Equip Best, etc.) to apply it to the selected slot; checksums are recalculated automatically after every edit, same as the CLI.
- "Add Item" can be filled in two ways: pick a name from the dropdown list, or type a name/hex ID directly into the text field, same matching rules as `--add-item`.
- "Write New File" writes to the path in the output box (or an auto-generated `*.edited.BIN` name) without touching your input file.
- "Write In-Place" asks for confirmation, then backs up the original to `.bak` before overwriting it, same as `--in-place`.
- The log panel at the bottom shows the result of every action, and the tabs refresh immediately so you can see the effect.

## Quick start

Inspect the file first:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --inspect-all
```

Create an edited copy of slot 1:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --max-party --give-everything --equip-best --out SAVE_EDITED.BIN
```

Create an edited copy of slot 2:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --give-everything --out SAVE_SLOT2_EDITED.BIN
```

Create an edited copy of slot 3:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 3 --max-party --give-everything --out SAVE_SLOT3_EDITED.BIN
```

Then inspect the output:

```bash
python3 ffiv3d_save_tool.py SAVE_EDITED.BIN --inspect-all
```

## Safety workflow

Always keep a clean backup:

```bash
cp SAVE.BIN SAVE.BIN.clean-backup
```

Prefer `--out` while testing:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --give-everything --out SAVE_TEST.BIN
```

This reads `SAVE.BIN` and writes `SAVE_TEST.BIN`. The original input is not modified.

Use `--in-place` only when you are comfortable overwriting the input file:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --give-everything --in-place
```

The script creates a backup first:

```text
SAVE.BIN.bak
```

## Slot targeting

The file is always `SAVE.BIN`. The visible save slots are regions inside that file.

Known region bases:

```text
visible slot 1:       0x0000
visible slot 2:       0x3DC0
visible slot 3:       0x7B80
redundant/shadow:     0xB940
```

The old public editor documented a visible-slot spacing of `0x3DC0`. Current testing shows the post-2020 game also keeps a redundant active copy at `0xB940`.

When editing a visible slot, the script now edits the visible slot **and** the redundant copy at `0xB940` if that redundant copy is occupied. This is the default behavior because the game may load or validate against the redundant copy. Editing only the visible slot can appear to do nothing in-game.

Slot selector values:

```text
--slot active   default; visible slot 1 plus redundant copy if occupied
--slot 1        visible slot 1 plus redundant copy if occupied
--slot 2        visible slot 2 plus redundant copy if occupied
--slot 3        visible slot 3 plus redundant copy if occupied
--slot all      all occupied visible slots plus redundant copy if occupied
--slot backup   only the redundant copy at 0xB940
```

Examples:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --inspect
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --inspect
python3 ffiv3d_save_tool.py SAVE.BIN --slot 3 --inspect
python3 ffiv3d_save_tool.py SAVE.BIN --inspect-all
```

## Checksums

The tool automatically recalculates checksums after edits. You do not need to run a separate checksum fixer.

Checksum-only command:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --fix-checksum --out SAVE_FIXED.BIN
```

Inspect checksum status:

```bash
python3 ffiv3d_save_tool.py SAVE_FIXED.BIN --inspect-all
```

The current checksum formula for a save-copy base `B` is:

```text
checksum offset = B + 0x1C
body start      = B + 0x20
body end        = B + 0x3DC0, end-exclusive
constant        = 0x010FC266
checksum        = (sum_u32_le(data[B+0x20 : B+0x3DC0]) + 0x010FC266) & 0xFFFFFFFF
```

The checksum value is stored as a little-endian `u32` at `B + 0x1C`.

See `FFIV_3D_CHECKSUM_ISSUE_EXPLAINED.txt` for the technical write-up.

## Common commands

Max current party stats for slot 1:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --max-party --out SAVE_MAXED_SLOT1.BIN
```

Max current party stats for slot 2:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --out SAVE_MAXED_SLOT2.BIN
```

Max all non-empty roster rows:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --max-all-chars --out SAVE_ALL_CHARS_MAXED.BIN
```

Give every known item and gear:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --give-everything --out SAVE_ITEMS.BIN
```

Add a specific item or gear:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --add-item "Ragnarok" --add-item "Crystal Ring" --out SAVE_GEAR.BIN
```

Set quantity for added inventory entries:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --give-everything --quantity 99 --out SAVE_ITEMS_99.BIN
```

Equip the tested high-stat gear loadout:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 1 --give-everything --equip-best --out SAVE_BEST_GEAR.BIN
```

List known item and gear IDs:

```bash
python3 ffiv3d_save_tool.py --list-known
python3 ffiv3d_save_tool.py --list-known "Adamant"
python3 ffiv3d_save_tool.py --list-known "Ragnarok"
```

## What `--max-party` edits

For each detected current-party character, the tool edits the detailed character table and quick-party HP/MP blocks.

Main character-table fields:

```text
relative +0x00: level, u8
relative +0x04: EXP, u32 little-endian
relative +0x0A: HP cap/source, u16 little-endian
relative +0x0C: current HP, u32 little-endian
relative +0x10: max HP, u32 little-endian
relative +0x14: current MP, u32 little-endian
relative +0x18: max MP, u32 little-endian
relative +0x1CA: Strength, u8
relative +0x1CB: Stamina, u8
relative +0x1CC: Speed, u8
relative +0x1CD: Intellect, u8
relative +0x1CE: Spirit, u8
relative +0x1D0: MP cap/source, u16 little-endian
```

The `+0x0A` and `+0x1D0` fields are important. In testing, changing only the documented HP/MP fields could load but still display old HP/MP values in-game. Setting those source/cap fields is what made max HP/MP stick.

Target values:

```text
HP:         9999 / 9999
MP:         999 / 999
Level:      99
EXP:        9999999
Base stats: 99
```

## What `--give-everything` edits

`--give-everything` is a shortcut:

```text
--give-all-items --give-all-gear
```

Inventory entries are four-byte records:

```text
u16 item_id
u16 quantity
```

The observed inventory table begins at relative `0x1AF0`. The item-count field is at relative `0x20F4`.

The script merges new entries into the existing inventory where possible. If an item already exists, it raises quantity up to the requested quantity. If it does not exist, it appends a new inventory record until capacity is reached.

## Gear editing notes

`--equip-best` was verified as a practical high-stat loadout for a late-game party layout. It is not a perfect universal equipment optimizer.

Current limitations:

- Story-state equipment restrictions still matter.
- Dark Knight Cecil and Paladin Cecil do not have the same gear rules.
- Early-game slots may contain party combinations that the tested loadout was not designed for.
- Equipment-derived lower stats such as Attack, Accuracy, Defense, Evasion, Magic Defense, and Magic Evasion are primarily affected by gear rather than the base-stat bytes alone.

If `--equip-best` gives odd results in an early/midgame slot, use `--give-everything` and equip manually in-game.

## Troubleshooting

### The game does not show Load

Most likely causes:

- The edited file was not copied back to the exact save path the game uses.
- Cloud sync restored the previous file.
- The checksum was not recalculated on the copy the game is actually reading.
- The save contains impossible values or invalid equipment for the story state.

Run:

```bash
python3 ffiv3d_save_tool.py SAVE_EDITED.BIN --inspect-all
```

Both edited copies should report checksum OK.

### Slot 2 or slot 3 looks unchanged

Make sure the command targeted the correct visible slot:

```bash
python3 ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --give-everything --out SAVE_SLOT2_EDITED.BIN
python3 ffiv3d_save_tool.py SAVE_SLOT2_EDITED.BIN --slot 2 --inspect
```

The current script also edits the redundant copy at `0xB940` by default when it is occupied. Older versions had a separate redundant-copy forcing flag; that flag has been removed because updating the redundant copy is the practical default.

### HP changed but MP did not

Use the current version of the script. Older experiments did not update the MP source/cap field at character-relative `+0x1D0`.

### Base stats changed but lower battle stats did not

That is expected. Strength/Stamina/Speed/Intellect/Spirit are not the same as displayed battle stats such as Attack, Accuracy, Defense, and Magic Defense. Testing showed the lower battle stats move when equipment changes, so use `--give-everything`, `--equip-best`, or equip manually in-game.

## Project license

This project is distributed as free and open-source software under:

```text
GNU Lesser General Public License v3.0 or later
SPDX-License-Identifier: LGPL-3.0-or-later
```

Relevant files:

```text
LICENSE                 project license notice
COPYING.LESSER          GNU Lesser General Public License v3 text
COPYING                 GNU General Public License v3 text, incorporated by LGPL v3
THIRD_PARTY_NOTICES.md  upstream attribution and license notes
licenses/               verbatim third-party and supplemental license texts
```

The tool uses/adapts save-layout offsets and item/equipment ID tables from `KingCyrus20/FFIV-Save-Editor`, which is licensed under GNU LGPL v3.0.

To the extent allowed by the upstream LGPL material, original project-specific contributions are also intended to be as permissive as possible. See `ADDITIONAL_PERMISSIONS.md`.

## Third-party attribution

This project uses/adapts data from:

```text
KingCyrus20/FFIV-Save-Editor
https://github.com/KingCyrus20/FFIV-Save-Editor
License: GNU Lesser General Public License v3.0
```

The old editor provided useful save-layout constants, item/equipment IDs, and baseline model structure. This tool adds post-2020 checksum repair, redundant-copy handling, multi-slot targeting, command-line editing, HP/MP source-field fixes, and updated documentation.
