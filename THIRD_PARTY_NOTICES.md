# Third-party notices

## KingCyrus20/FFIV-Save-Editor

This project uses/adapts save-layout offsets and item/equipment ID tables from:

```text
Project: KingCyrus20/FFIV-Save-Editor
URL:     https://github.com/KingCyrus20/FFIV-Save-Editor
License: GNU Lesser General Public License v3.0
```

A copy of the upstream license text is included at:

```text
licenses/FFIV-Save-Editor-LGPL-3.0.txt
```

The upstream project is a Kotlin/TornadoFX save editor for the PC port of Final Fantasy IV 3D Remake. Its README notes that the original editor became non-functional for current saves due to checksum protection added after a November 2020 update.

This Python project reuses/adapts some non-checksum data from that editor, including save-layout offsets and item/equipment ID mappings. The current Python project adds post-2020 checksum repair, redundant-copy handling, multi-slot targeting, command-line editing, HP/MP source-field handling, and updated technical documentation.

## Licensing of this repository

This repository is distributed under the GNU Lesser General Public License v3.0 or later:

```text
SPDX-License-Identifier: LGPL-3.0-or-later
```

Included license files:

```text
LICENSE                         project license text, LGPL v3 or later
COPYING.LESSER                  GNU Lesser General Public License v3 text
COPYING                         GNU General Public License v3 text
licenses/FFIV-Save-Editor-LGPL-3.0.txt
licenses/MIT.txt                supplemental permissive grant for separable original portions
```

The LGPL-covered upstream-derived portions cannot be relicensed as purely permissive by this project. For maximum freedom where allowed, separable original project-specific contributions are additionally made available under MIT as described in `ADDITIONAL_PERMISSIONS.md`.
