#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 FFIV 3D Save Tool contributors
#
# This tool uses/adapts save-layout offsets and item/equipment ID tables
# from KingCyrus20/FFIV-Save-Editor, licensed under GNU LGPL v3.0.
# See THIRD_PARTY_NOTICES.md and licenses/FFIV-Save-Editor-LGPL-3.0.txt.
"""
FFIV 3D Remake post-2020 SAVE.BIN utility.

Features:
  * verify/fix the active primary + backup checksums
  * max current-party or all-roster HP/MP, level, EXP, and base stats
  * give all consumable/key inventory items
  * give all known equipment/gear
  * equip the tested endgame gear loadout for the late-game party
  * target an individual visible save slot with --slot

This is intentionally conservative:
  * By default it edits visible slot 1 and the redundant/shadow copy at 0xB940 when present.
  * With --slot, it can target visible slot 1, 2, 3, all occupied visible slots, or only the redundant copy.
  * The 0xB940 copy is not a fixed slot-1 backup. It is a redundant/shadow copy the game may prefer when loading. For reliability, visible-slot edits always update 0xB940 too when it is occupied.
  * It does NOT recalculate inactive/empty visible-slot regions unless you explicitly target all occupied slots.
  * It preserves the header/counter fields.

Typical usage:
  python ffiv3d_save_tool.py SAVE.BIN --inspect
  python ffiv3d_save_tool.py SAVE.BIN --fix-checksum --in-place
  python ffiv3d_save_tool.py SAVE.BIN --max-party --give-everything --equip-best --out SAVE_EDITED.BIN
  python ffiv3d_save_tool.py SAVE.BIN --inspect-all
  python ffiv3d_save_tool.py SAVE.BIN --slot 2 --max-party --out SAVE_SLOT2_EDITED.BIN
  python ffiv3d_save_tool.py SAVE.BIN --max-all-chars --give-all-items --quantity 99 --out SAVE_ITEMS.BIN
"""
from __future__ import annotations

import argparse
import shutil
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

SAVE_SIZE = 0x10000
EMPTY_ID = 0xFF9D
CHECKSUM_CONST = 0x010FC266
VISIBLE_SLOT_BASES = {1: 0x0000, 2: 0x3DC0, 3: 0x7B80}
REDUNDANT_COPY_BASE = 0xB940
ACTIVE_COPY_BASES = (0x0000, REDUNDANT_COPY_BASE)  # default: active slot-1 primary + redundant copy
COPY_BASES = ACTIVE_COPY_BASES  # compatibility alias used by older helper code
INACTIVE_CHECKSUM_SENTINEL = 0x01100002
REDUNDANT_PAIR_DIFF_THRESHOLD = 512  # body-byte diff threshold for auto-pairing 0xB940 with a visible slot
CHECKSUM_REL = 0x1C
BODY_START_REL = 0x20
BODY_END_REL = 0x3DC0  # exclusive

# Offsets copied from the old public FFIV-Save-Editor, plus the newly-found HP/MP cap/source fields.
GIL_REL = 0x88
FIRST_CHAR_REL = 0x9C
CHAR_SEP = 0x1D4
CHAR_COUNT = 14

LEVEL_REL = 0x00
EXP_REL = 0x04
HP_CAP_SOURCE_REL = 0x0A   # u16; required for 9999 HP to stick in-game
CUR_HP_REL = 0x0C          # u32
MAX_HP_REL = 0x10          # u32
CUR_MP_REL = 0x14          # u32
MAX_MP_REL = 0x18          # u32
STR_REL = 0x1CA            # u8
STA_REL = 0x1CB            # u8
SPD_REL = 0x1CC            # u8
INT_REL = 0x1CD            # u8
SPI_REL = 0x1CE            # u8
MP_CAP_SOURCE_REL = 0x1D0  # u16; required for max MP to stick in-game

RIGHT_HAND_REL = 0x26
LEFT_HAND_REL = 0x28
HEAD_REL = 0x2A
BODY_REL = 0x2C
ARMS_REL = 0x2E

ITEM_COUNT_REL = 0x20F4
FIRST_ITEM_REL = 0x1AF0
ITEM_SEP = 0x04
INVENTORY_CAPACITY = (ITEM_COUNT_REL - FIRST_ITEM_REL) // ITEM_SEP  # 385 entries in observed layout

# Party quick blocks. Each party member entry starts every 0x14 bytes from 0x20.
# The active roster index lives at quick_entry + 0x04.
# HP/MP block starts at quick_entry + 0x08: u16 curHP, maxHP, curMP, maxMP.
PARTY_ENTRY_REL = 0x20
PARTY_ENTRY_SEP = 0x14
PARTY_INDEX_REL = 0x04
PARTY_HPMP_REL = 0x08
PARTY_SIZE = 5

ITEMS = {5001: 'Potion',
 5002: 'Hi-Potion',
 5003: 'X-Potion',
 5004: 'Ether',
 5005: 'Dry Ether',
 5006: 'Elixir',
 5007: 'Megalixir',
 5008: 'Phoenix Down',
 5009: 'Gold Needle',
 5010: "Maiden's Kiss",
 5011: 'Mallet',
 5012: 'Diet Ration',
 5013: 'Echo Herbs',
 5014: 'Eye Drops',
 5015: 'Antidote',
 5016: 'Cross',
 5017: 'Remedy',
 5018: 'Alarm Clock',
 5019: 'Unicorn Horn',
 5020: 'Tent',
 5021: 'Cottage',
 5022: 'Emergency Exit',
 5023: 'Gnomish Bread',
 5024: 'Gysahl Greens',
 5025: 'Gysahl Whistle',
 5026: 'Golden Apple',
 5027: 'Silver Apple',
 5028: 'Soma Drop',
 5029: 'Siren',
 5030: 'Lustful Lali-Ho',
 5031: 'Ninja Sutra',
 5035: 'Red Fang',
 5036: 'White Fang',
 5037: 'Blue Fang',
 5038: 'Bomb Fragment',
 5039: 'Bomb Crank',
 5040: 'Antarctic Wind',
 5041: 'Arctic Wind',
 5042: "Zeus' Wrath",
 5043: 'Heavenly Wrath',
 5044: 'Gaia Drum',
 5045: 'Bomb Core',
 5046: 'Stardust',
 5047: "Lilith's Kiss",
 5048: 'Vampire Fang',
 5049: 'Spider Silk',
 5050: 'Silent Bell',
 5051: 'Coeurl Whisker',
 5052: 'Bestiary',
 5053: 'Bronze Hourglass',
 5054: 'Silver Hourglass',
 5055: 'Gold Hourglass',
 5056: "Bacchus's Wine",
 5057: 'Hermes Sandals',
 5058: 'Decoy',
 5059: 'Light Curtain',
 5060: 'Lunar Curtain',
 5061: 'Crystal',
 5062: "Member's Writ",
 5191: 'Rainbow Pudding',
 7401: 'Shuriken',
 7402: 'Fuma Shuriken'}
HAND_GEAR = {6001: 'Dark Sword',
 6002: 'Shadowblade',
 6003: 'Deathbringer',
 6004: 'Mythgraven Sword',
 6005: 'Lustrous Sword',
 6006: 'Excalibur',
 6007: 'Ragnarok',
 6008: 'Ancient Sword',
 6009: 'Blood Sword',
 6010: 'Mythril Sword',
 6011: 'Sleep Blade',
 6012: 'Flame Sword',
 6013: 'Icebrand',
 6014: 'Stone Blade',
 6015: 'Avenger',
 6016: 'Defender',
 6017: 'Fireshard',
 6018: 'Frostshard',
 6019: 'Thundershard',
 6020: 'Onion Sword',
 6101: 'Spear',
 6102: 'Wind Spear',
 6103: 'Flame Lance',
 6104: 'Ice Lance',
 6105: 'Blood Lance',
 6106: 'Gungnir',
 6107: 'Wyvern Lance',
 6108: 'Holy Lance',
 6201: 'Mythril Knife',
 6202: 'Dancing Dagger',
 6203: 'Mage Masher',
 6204: 'Knife',
 6301: 'Dream Harp',
 6302: 'Lamia Harp',
 6401: 'Flame Claw',
 6402: 'Ice Claw',
 6403: 'Lightning Claw',
 6404: 'Faerie Claw',
 6405: 'Hell Claw',
 6406: 'Cat Claw',
 6501: 'Wooden Hammer',
 6502: 'Mythril Hammer',
 6503: 'Gaia Hammer',
 6601: 'Dwarven Axe',
 6602: 'Ogrekiller',
 6603: 'Poison Axe',
 6604: 'Rune Axe',
 6701: 'Kunai',
 6702: 'Ashura',
 6703: 'Kotetsu',
 6704: 'Kiku-ichimonji',
 6705: 'Murasame',
 6706: 'Masamune',
 6801: 'Rod',
 6802: 'Flame Rod',
 6803: 'Ice Rod',
 6804: 'Thunder Rod',
 6805: 'Lilith Rod',
 6806: 'Polymorph Rod',
 6807: 'Faerie Rod',
 6808: 'Stardust Rod',
 6901: 'Staff',
 6902: 'Healing Staff',
 6903: 'Mythril Staff',
 6904: 'Power Staff',
 6905: 'Aura Staff',
 6906: "Sage's Staff",
 6907: 'Rune Staff',
 7001: 'Bow',
 7002: 'Power Bow',
 7003: 'Great Bow',
 7004: 'Killer Bow',
 7005: 'Elven Bow',
 7006: 'Yoichi Bow',
 7007: 'Artemis Bow',
 7101: 'Medusa Arrows',
 7102: 'Iron Arrows',
 7103: 'Holy Arrows',
 7104: 'Fire Arrows',
 7105: 'Ice Arrows',
 7106: 'Lightning Arrows',
 7107: 'Blinding Arrows',
 7108: 'Poison Arrows',
 7109: 'Silencing Arrows',
 7110: 'Angel Arrows',
 7111: 'Yoichi Arrows',
 7112: 'Artemis Arrows',
 7201: 'Whip',
 7202: 'Chain Whip',
 7203: 'Blitz Whip',
 7204: 'Flame Whip',
 7205: 'Dragon Whisker',
 7301: 'Boomerang',
 7302: 'Moonring Blade',
 8001: 'Iron Shield',
 8002: 'Dark Shield',
 8003: 'Demon Shield',
 8004: 'Lustrous Shield',
 8005: 'Mythril Shield',
 8006: 'Flame Shield',
 8007: 'Ice Shield',
 8008: 'Diamond Shield',
 8009: 'Aegis Shield',
 8010: 'Genji Shield',
 8011: 'Dragon Shield',
 8012: 'Crystal Shield',
 8013: 'Onion Shield'}
HEAD_GEAR = {8101: 'Leather Cap',
 8102: 'Headband',
 8103: 'Feathered Cap',
 8104: 'Iron Helm',
 8105: "Wizard's Hat",
 8106: 'Green Beret',
 8107: 'Dark Helm',
 8108: 'Hades Helm',
 8109: "Sage's Miter",
 8110: 'Black Cowl',
 8111: 'Demon Helm',
 8112: 'Lustrous Helm',
 8113: 'Gold Hairpin',
 8114: 'Mythril Helm',
 8115: 'Diamond Helm',
 8116: 'Ribbon',
 8117: 'Genji Helm',
 8118: 'Dragon Helm',
 8119: 'Crystal Helm',
 8120: 'Glass Mask',
 8121: 'Onion Helm'}
BODY_GEAR = {8201: 'Clothing',
 8202: 'Prison Garb',
 8203: 'Leather Clothing',
 8204: "Bard's Tunic",
 8205: 'Gaia Gear',
 8206: 'Iron Armor',
 8207: 'Dark Armor',
 8208: "Sage's Surplice",
 8209: 'Kenpo Gi',
 8210: 'Hades Armor',
 8211: 'Black Robe',
 8212: 'Demon Armor',
 8213: 'Black Belt Gi',
 8214: "Knight's Armor",
 8215: 'Luminous Robe',
 8216: 'Mythril Armor',
 8217: 'Flame Mail',
 8218: 'Power Sash',
 8219: 'Ice Armor',
 8220: 'White Robe',
 8221: 'Diamond Armor',
 8222: 'Minerva Bustier',
 8223: 'Genji Armor',
 8224: 'Dragon Mail',
 8225: 'Black Garb',
 8226: 'Crystal Mail',
 8227: 'Adamant Armor',
 8228: 'Onion Armor'}
ARM_GEAR = {8301: 'Ruby Ring',
 8302: 'Cursed Ring',
 8303: 'Iron Gloves',
 8304: 'Dark Gloves',
 8305: 'Iron Armlet',
 8306: 'Power Armlet',
 8307: 'Hades Gloves',
 8308: 'Demon Gloves',
 8309: 'Silver Armlet',
 8310: 'Gauntlets',
 8311: 'Rune Armlet',
 8312: 'Mythril Gloves',
 8313: 'Diamond Armlet',
 8314: 'Diamond Gloves',
 8315: 'Genji Gloves',
 8316: 'Dragon Gloves',
 8317: "Giant's Gloves",
 8318: 'Crystal Gloves',
 8319: 'Protect Ring',
 8320: 'Crystal Ring',
 8321: 'Onion Gloves'}

ALL_GEAR = {**HAND_GEAR, **HEAD_GEAR, **BODY_GEAR, **ARM_GEAR}
ALL_KNOWN = {**ITEMS, **ALL_GEAR}
NAME_TO_ID = {name.lower(): item_id for item_id, name in ALL_KNOWN.items()}

# Tested late-game party loadout:
# quick party roster indices observed as [5, 1, 2, 3, 12] = Rydia, Cecil, Kain, Rosa, Edge.
# This is intentionally not Onion gear; it is the gear-probe loadout that changed lower stats.
FINAL_PARTY_LOADOUT_BY_ROSTER_INDEX = {
    5: {"name": "Rydia", "right": "Dragon Whisker", "left": None, "head": "Ribbon", "body": "Adamant Armor", "arms": "Crystal Ring"},
    1: {"name": "Cecil", "right": "Ragnarok", "left": "Crystal Shield", "head": "Crystal Helm", "body": "Adamant Armor", "arms": "Crystal Ring"},
    2: {"name": "Kain", "right": "Holy Lance", "left": "Dragon Shield", "head": "Dragon Helm", "body": "Adamant Armor", "arms": "Crystal Ring"},
    3: {"name": "Rosa", "right": "Artemis Bow", "left": "Artemis Arrows", "head": "Ribbon", "body": "Adamant Armor", "arms": "Crystal Ring"},
    12: {"name": "Edge", "right": "Masamune", "left": "Murasame", "head": "Ribbon", "body": "Adamant Armor", "arms": "Crystal Ring"},
}


def u16(data: bytearray | bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 2], "little")


def u32(data: bytearray | bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def w8(data: bytearray, off: int, value: int) -> None:
    data[off] = value & 0xFF


def w16(data: bytearray, off: int, value: int) -> None:
    data[off:off + 2] = (value & 0xFFFF).to_bytes(2, "little")


def w32(data: bytearray, off: int, value: int) -> None:
    data[off:off + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")


def validate_save_size(data: bytes | bytearray) -> None:
    if len(data) != SAVE_SIZE:
        raise ValueError(f"Unexpected file size {len(data)} bytes; expected {SAVE_SIZE} / 0x{SAVE_SIZE:X}")


def checksum_for_copy(data: bytes | bytearray, base: int) -> int:
    total = 0
    for off in range(base + BODY_START_REL, base + BODY_END_REL, 4):
        total = (total + u32(data, off)) & 0xFFFFFFFF
    return (total + CHECKSUM_CONST) & 0xFFFFFFFF


def checksum_status(data: bytes | bytearray, bases: Iterable[int] | None = None) -> list[tuple[int, int, int, bool]]:
    out = []
    for base in (list(bases) if bases is not None else list(VISIBLE_SLOT_BASES.values()) + [REDUNDANT_COPY_BASE]):
        stored = u32(data, base + CHECKSUM_REL)
        calc = checksum_for_copy(data, base)
        out.append((base, stored, calc, stored == calc))
    return out


def fix_checksums(data: bytearray, bases: Iterable[int] | None = None) -> None:
    for base in (list(bases) if bases is not None else ACTIVE_COPY_BASES):
        w32(data, base + CHECKSUM_REL, checksum_for_copy(data, base))


def detected_party_slots(data: bytes | bytearray, base: int = 0) -> list[tuple[int, int]]:
    """Return (party_slot_number, roster_index) for occupied quick-party entries."""
    out: list[tuple[int, int]] = []
    for party_slot in range(PARTY_SIZE):
        entry = base + PARTY_ENTRY_REL + party_slot * PARTY_ENTRY_SEP
        idx = data[entry + PARTY_INDEX_REL]
        block = entry + PARTY_HPMP_REL
        has_hpmp = any(data[block + j] for j in range(8))
        if 0 <= idx < CHAR_COUNT and has_hpmp:
            out.append((party_slot, idx))
    return out


def detected_party_indices(data: bytes | bytearray, base: int = 0) -> list[int]:
    return [idx for _, idx in detected_party_slots(data, base)]


def slot_label_for_base(base: int) -> str:
    if base == REDUNDANT_COPY_BASE:
        return "redundant"
    for slot, slot_base in VISIBLE_SLOT_BASES.items():
        if base == slot_base:
            return f"slot{slot}"
    return f"base_0x{base:X}"


def slot_looks_occupied(data: bytes | bytearray, base: int) -> bool:
    if data[base:base + 7] != b"cd1000\x00":
        return False
    stored = u32(data, base + CHECKSUM_REL)
    if stored != INACTIVE_CHECKSUM_SENTINEL and stored == checksum_for_copy(data, base):
        return True
    if detected_party_indices(data, base):
        return True
    if u32(data, base + ITEM_COUNT_REL) > 0:
        return True
    return False


def body_diff_count(data: bytes | bytearray, base_a: int, base_b: int, *, limit: int | None = None) -> int:
    """Count differing bytes between the checksummed bodies of two slot/copy regions."""
    a_start = base_a + BODY_START_REL
    b_start = base_b + BODY_START_REL
    length = BODY_END_REL - BODY_START_REL
    diffs = 0
    for i in range(length):
        if data[a_start + i] != data[b_start + i]:
            diffs += 1
            if limit is not None and diffs > limit:
                return diffs
    return diffs


def redundant_partner_slot(data: bytes | bytearray) -> tuple[int | None, int | None]:
    """Return (slot_number, diff_count) for the visible slot most likely paired with 0xB940.

    The post-2020 file still has three visible slot bodies at 0x0000, 0x3DC0,
    and 0x7B80, plus a redundant/shadow body at 0xB940. Older assumptions
    treated 0xB940 as always belonging to slot 1, but all-slot sample files show
    it can be a shadow of slot 2 or slot 3 instead. The paired visible slot is
    normally very close to 0xB940 by byte-diff, while unrelated occupied slots
    are much farther away.
    """
    if not slot_looks_occupied(data, REDUNDANT_COPY_BASE):
        return (None, None)
    scores: list[tuple[int, int]] = []
    for slot_num, base in VISIBLE_SLOT_BASES.items():
        if not slot_looks_occupied(data, base):
            continue
        diff = body_diff_count(data, base, REDUNDANT_COPY_BASE, limit=REDUNDANT_PAIR_DIFF_THRESHOLD + 1)
        scores.append((diff, slot_num))
    if not scores:
        return (None, None)
    scores.sort()
    best_diff, best_slot = scores[0]
    if best_diff <= REDUNDANT_PAIR_DIFF_THRESHOLD:
        return (best_slot, best_diff)
    return (None, best_diff)


def select_copy_bases(data: bytes | bytearray, slot_arg: str) -> list[int]:
    """Choose save-copy bases to edit.

    Important: for reliability, any visible-slot target also includes the
    redundant/shadow copy at 0xB940 when that copy looks occupied. The game can
    prefer/load from the redundant copy, so editing only the visible slot can
    appear to do nothing in-game.
    """
    slot_arg = str(slot_arg).lower()

    redundant_is_occupied = slot_looks_occupied(data, REDUNDANT_COPY_BASE)

    def with_redundant(bases: list[int]) -> list[int]:
        if redundant_is_occupied and REDUNDANT_COPY_BASE not in bases:
            bases.append(REDUNDANT_COPY_BASE)
        return bases

    if slot_arg in ("active", "default"):
        # Tested default: visible slot 1 plus the redundant/shadow copy.
        return with_redundant([VISIBLE_SLOT_BASES[1]])

    if slot_arg in ("backup", "redundant"):
        return [REDUNDANT_COPY_BASE]

    if slot_arg == "all":
        bases = [base for base in VISIBLE_SLOT_BASES.values() if slot_looks_occupied(data, base)]
        return with_redundant(bases) or with_redundant([VISIBLE_SLOT_BASES[1]])

    try:
        slot_num = int(slot_arg, 10)
    except ValueError:
        raise ValueError("--slot must be active, all, backup/redundant, or 1/2/3")
    if slot_num not in VISIBLE_SLOT_BASES:
        raise ValueError("--slot number must be 1, 2, or 3")

    return with_redundant([VISIBLE_SLOT_BASES[slot_num]])


def char_base(copy_base: int, roster_index: int) -> int:
    return copy_base + FIRST_CHAR_REL + roster_index * CHAR_SEP


def looks_like_used_character(data: bytes | bytearray, copy_base: int, roster_index: int) -> bool:
    c = char_base(copy_base, roster_index)
    if u32(data, c + CUR_HP_REL) or u32(data, c + MAX_HP_REL) or u32(data, c + CUR_MP_REL) or u32(data, c + MAX_MP_REL):
        return True
    if data[c + LEVEL_REL] != 0:
        return True
    if any(data[c + rel] for rel in (STR_REL, STA_REL, SPD_REL, INT_REL, SPI_REL)):
        return True
    return False


def max_character_record(data: bytearray, copy_base: int, roster_index: int, *, hp: int = 9999, mp: int = 999,
                         stat: int = 99, level: int = 99, exp: int = 9_999_999) -> None:
    c = char_base(copy_base, roster_index)

    w8(data, c + LEVEL_REL, level)
    w32(data, c + EXP_REL, exp)

    w32(data, c + CUR_HP_REL, hp)
    w32(data, c + MAX_HP_REL, hp)
    w32(data, c + CUR_MP_REL, mp)
    w32(data, c + MAX_MP_REL, mp)

    # Newly discovered source/cap fields needed for values to survive load.
    w16(data, c + HP_CAP_SOURCE_REL, hp)
    w16(data, c + MP_CAP_SOURCE_REL, mp)

    # Base stats shown on the Status page.
    for rel in (STR_REL, STA_REL, SPD_REL, INT_REL, SPI_REL):
        w8(data, c + rel, stat)


def max_party_quick_blocks(data: bytearray, copy_base: int, party_slots: Iterable[int] | None = None,
                           *, hp: int = 9999, mp: int = 999) -> None:
    # Only touch occupied quick-party entries. Early-game saves can have fewer than
    # five party members; maxing every quick block would accidentally convert empty
    # entries into duplicate roster index 0 entries.
    slots = list(party_slots) if party_slots is not None else list(range(PARTY_SIZE))
    for slot in slots:
        block = copy_base + PARTY_ENTRY_REL + slot * PARTY_ENTRY_SEP + PARTY_HPMP_REL
        w16(data, block + 0, hp)
        w16(data, block + 2, hp)
        w16(data, block + 4, mp)
        w16(data, block + 6, mp)


def max_party(data: bytearray, bases: Iterable[int]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for base in bases:
        party_pairs = detected_party_slots(data, base)
        indices = [idx for _, idx in party_pairs]
        result[base] = indices
        if not party_pairs:
            continue
        max_party_quick_blocks(data, base, [party_slot for party_slot, _ in party_pairs])
        for idx in sorted(set(indices)):
            max_character_record(data, base, idx)
    return result


def max_all_chars(data: bytearray, bases: Iterable[int]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for base in bases:
        used = [i for i in range(CHAR_COUNT) if looks_like_used_character(data, base, i)]
        result[base] = used
        for idx in used:
            max_character_record(data, base, idx)
    return result


def inventory_entries(data: bytes | bytearray, copy_base: int) -> list[tuple[int, int]]:
    count = u32(data, copy_base + ITEM_COUNT_REL)
    count = max(0, min(count, INVENTORY_CAPACITY))
    entries = []
    for i in range(count):
        off = copy_base + FIRST_ITEM_REL + i * ITEM_SEP
        item_id = u16(data, off)
        qty = u16(data, off + 2)
        if item_id != 0 and item_id != EMPTY_ID:
            entries.append((item_id, qty))
    return entries


def write_inventory_entries(data: bytearray, copy_base: int, entries: list[tuple[int, int]]) -> None:
    if len(entries) > INVENTORY_CAPACITY:
        raise ValueError(f"Inventory would have {len(entries)} entries; capacity appears to be {INVENTORY_CAPACITY}")
    w32(data, copy_base + ITEM_COUNT_REL, len(entries))
    start = copy_base + FIRST_ITEM_REL
    end = copy_base + ITEM_COUNT_REL
    data[start:end] = b"\x00" * (end - start)
    for i, (item_id, qty) in enumerate(entries):
        off = start + i * ITEM_SEP
        w16(data, off, item_id)
        w16(data, off + 2, qty)


def upsert_inventory(data: bytearray, additions: Iterable[int], *, quantity: int = 99, bases: Iterable[int] | None = None) -> None:
    additions = list(OrderedDict.fromkeys(additions))
    for base in (list(bases) if bases is not None else ACTIVE_COPY_BASES):
        ordered = OrderedDict()
        for item_id, qty in inventory_entries(data, base):
            ordered[item_id] = max(qty, 0)
        for item_id in additions:
            ordered[item_id] = max(ordered.get(item_id, 0), quantity)
        write_inventory_entries(data, base, list(ordered.items()))


def resolve_item_id(token: str) -> int:
    t = token.strip()
    if not t:
        raise ValueError("empty item token")
    try:
        return int(t, 0)
    except ValueError:
        pass
    key = t.lower()
    if key in NAME_TO_ID:
        return NAME_TO_ID[key]
    matches = [(item_id, name) for item_id, name in ALL_KNOWN.items() if key in name.lower()]
    if len(matches) == 1:
        return matches[0][0]
    if not matches:
        raise ValueError(f"Unknown item/gear name: {token!r}")
    preview = ", ".join(f"{name}=0x{item_id:04X}" for item_id, name in matches[:12])
    raise ValueError(f"Ambiguous item/gear name {token!r}. Matches: {preview}")


def write_equipment(data: bytearray, copy_base: int, roster_index: int, *, right=None, left=None, head=None, body=None, arms=None) -> None:
    c = char_base(copy_base, roster_index)
    if right is not None:
        w16(data, c + RIGHT_HAND_REL, resolve_item_id(right) if isinstance(right, str) else int(right))
    if left is not None:
        if left == "EMPTY":
            w16(data, c + LEFT_HAND_REL, EMPTY_ID)
        else:
            w16(data, c + LEFT_HAND_REL, resolve_item_id(left) if isinstance(left, str) else int(left))
    if head is not None:
        w16(data, c + HEAD_REL, resolve_item_id(head) if isinstance(head, str) else int(head))
    if body is not None:
        w16(data, c + BODY_REL, resolve_item_id(body) if isinstance(body, str) else int(body))
    if arms is not None:
        w16(data, c + ARMS_REL, resolve_item_id(arms) if isinstance(arms, str) else int(arms))


def equip_best_final_party(data: bytearray, bases: Iterable[int]) -> list[str]:
    changed = []
    gear_to_add = []
    for base in bases:
        party = set(detected_party_indices(data, base))
        for idx, loadout in FINAL_PARTY_LOADOUT_BY_ROSTER_INDEX.items():
            if idx not in party:
                continue
            for field in ("right", "left", "head", "body", "arms"):
                name = loadout.get(field)
                if name:
                    gear_to_add.append(resolve_item_id(name))
            write_equipment(data, base, idx,
                            right=loadout.get("right"),
                            left=(loadout.get("left") if loadout.get("left") is not None else None),
                            head=loadout.get("head"),
                            body=loadout.get("body"),
                            arms=loadout.get("arms"))
            label = f"{loadout['name']}@{slot_label_for_base(base)}"
            if label not in changed:
                changed.append(label)
    if gear_to_add:
        upsert_inventory(data, gear_to_add, quantity=1, bases=bases)
    return changed


def inspect(data: bytes | bytearray, bases: Iterable[int] | None = None) -> None:
    bases_list = list(bases) if bases is not None else list(VISIBLE_SLOT_BASES.values()) + [REDUNDANT_COPY_BASE]
    print(f"size: {len(data)} / 0x{len(data):X}")
    paired_slot, paired_diff = redundant_partner_slot(data)
    if paired_slot is not None:
        print(f"redundant 0xB940 appears paired with visible slot {paired_slot} by body diff ({paired_diff} differing bytes)")
    elif paired_diff is not None:
        print(f"redundant 0xB940 has no confident visible-slot pair; closest body diff was {paired_diff} bytes")
    for base, stored, calc, ok in checksum_status(data, bases_list):
        sentinel = " sentinel" if stored == INACTIVE_CHECKSUM_SENTINEL else ""
        occupied = "occupied" if slot_looks_occupied(data, base) else "empty/inactive"
        print(
            f"checksum {slot_label_for_base(base):9} base=0x{base:04X} "
            f"stored=0x{stored:08X} calc=0x{calc:08X} {'OK' if ok else 'BAD'}{sentinel} {occupied}"
        )
    for base in bases_list:
        party = detected_party_indices(data, base)
        inv_count = u32(data, base + ITEM_COUNT_REL)
        print(f"{slot_label_for_base(base):9} party roster indices: {party}  inventory count: {inv_count}")
        for idx in party:
            c = char_base(base, idx)
            print(
                f"  row {idx:2d}: level={data[c + LEVEL_REL]} "
                f"HP={u32(data, c + CUR_HP_REL)}/{u32(data, c + MAX_HP_REL)} cap={u16(data, c + HP_CAP_SOURCE_REL)} "
                f"MP={u32(data, c + CUR_MP_REL)}/{u32(data, c + MAX_MP_REL)} cap={u16(data, c + MP_CAP_SOURCE_REL)} "
                f"stats={data[c + STR_REL]},{data[c + SPD_REL]},{data[c + STA_REL]},{data[c + INT_REL]},{data[c + SPI_REL]}"
            )


def list_known_items(filter_text: str | None) -> None:
    filt = (filter_text or "").lower()
    for item_id, name in sorted(ALL_KNOWN.items()):
        if not filt or filt in name.lower() or filt in f"0x{item_id:04x}":
            print(f"0x{item_id:04X}  {name}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FFIV 3D Remake SAVE.BIN checksum/editor helper")
    p.add_argument("save", nargs="?", help="Path to SAVE.BIN")
    p.add_argument("--slot", default="active", metavar="active|1|2|3|all|backup",
                   help=("Target save slot/copy. Default: active, which edits visible slot 1 plus "
                         "the redundant/shadow copy at 0xB940 when present. Use 1, 2, or 3 for "
                         "a visible save slot; those targets also update 0xB940 when occupied. "
                         "Use all for occupied visible slots plus 0xB940, or backup/redundant for only 0xB940."))
    p.add_argument("--inspect", action="store_true", help="Print checksum, party, and inventory info for the selected slot/copy")
    p.add_argument("--inspect-all", action="store_true", help="Inspect all visible slots plus the redundant copy")
    p.add_argument("--fix-checksum", action="store_true", help="Recompute checksums for the selected slot/copy")
    p.add_argument("--max-party", action="store_true", help="Max HP/MP, level/EXP, and base stats for detected current party in the selected slot/copy")
    p.add_argument("--max-all-chars", action="store_true", help="Max HP/MP, level/EXP, and base stats for all non-empty roster rows in the selected slot/copy")
    p.add_argument("--give-all-items", action="store_true", help="Add all known non-equipment inventory items")
    p.add_argument("--give-all-gear", action="store_true", help="Add all known equipment/gear")
    p.add_argument("--give-everything", action="store_true", help="Shortcut for --give-all-items --give-all-gear")
    p.add_argument("--add-item", action="append", default=[], metavar="NAME_OR_0xID", help="Add one known item/gear by exact/partial name or hex ID. Repeatable")
    p.add_argument("--equip-best", action="store_true", help="Equip tested strong gear for late-game party rows Rydia/Cecil/Kain/Rosa/Edge if present")
    p.add_argument("--quantity", type=int, default=99, help="Quantity for added inventory items/gear, default 99")
    p.add_argument("--out", help="Write edited save to this path")
    p.add_argument("--in-place", action="store_true", help="Overwrite input save after creating a .bak backup")
    p.add_argument("--list-known", nargs="?", const="", metavar="FILTER", help="List known item/gear IDs, optionally filtered")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.list_known is not None:
        list_known_items(args.list_known)
        return 0

    if not args.save:
        print("error: SAVE.BIN path required unless using --list-known", file=sys.stderr)
        return 2

    path = Path(args.save)
    data = bytearray(path.read_bytes())
    validate_save_size(data)

    try:
        target_bases = select_copy_bases(data, args.slot)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    changed = False

    if args.inspect_all:
        inspect(data)
    elif args.inspect or not any((args.fix_checksum, args.max_party, args.max_all_chars, args.give_all_items,
                                  args.give_all_gear, args.give_everything, args.add_item, args.equip_best)):
        inspect(data, target_bases)

    if args.max_party:
        by_base = max_party(data, target_bases)
        summary = "; ".join(f"{slot_label_for_base(base)}={rows}" for base, rows in by_base.items())
        print(f"maxed current-party roster rows: {summary}")
        changed = True

    if args.max_all_chars:
        by_base = max_all_chars(data, target_bases)
        summary = "; ".join(f"{slot_label_for_base(base)}={rows}" for base, rows in by_base.items())
        print(f"maxed non-empty roster rows: {summary}")
        changed = True

    additions = []
    if args.give_all_items or args.give_everything:
        additions.extend(ITEMS.keys())
    if args.give_all_gear or args.give_everything:
        additions.extend(ALL_GEAR.keys())
    for token in args.add_item:
        additions.append(resolve_item_id(token))
    if additions:
        upsert_inventory(data, additions, quantity=args.quantity, bases=target_bases)
        print(f"added/updated {len(set(additions))} inventory entries to quantity >= {args.quantity} in {', '.join(slot_label_for_base(b) for b in target_bases)}")
        changed = True

    if args.equip_best:
        chars = equip_best_final_party(data, target_bases)
        print(f"equipped tested strong gear for: {', '.join(chars) if chars else 'no matching late-game party rows detected'}")
        changed = True

    if args.fix_checksum or changed:
        fix_checksums(data, target_bases)
        print(f"fixed checksums for: {', '.join(slot_label_for_base(b) for b in target_bases)}")
        changed = True

    if changed:
        if args.in_place and args.out:
            print("error: use either --in-place or --out, not both", file=sys.stderr)
            return 2
        if args.in_place:
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
            path.write_bytes(data)
            print(f"wrote in-place; backup: {backup}")
        else:
            out = Path(args.out) if args.out else path.with_name(path.stem + ".edited" + path.suffix)
            out.write_bytes(data)
            print(f"wrote: {out}")
            print("Copy/rename that file to SAVE.BIN when you are ready to test it.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
