from __future__ import annotations

import ffiv3d_save_tool as tool


def make_save() -> bytearray:
    """Create a minimal occupied slot 1 plus its redundant copy."""
    save = bytearray(tool.SAVE_SIZE)
    for base in (tool.VISIBLE_SLOT_BASES[1], tool.REDUNDANT_COPY_BASE):
        save[base:base + 7] = b"cd1000\x00"

        party_entry = base + tool.PARTY_ENTRY_REL
        save[party_entry + tool.PARTY_INDEX_REL] = 1
        quick = party_entry + tool.PARTY_HPMP_REL
        for offset, value in ((0, 320), (2, 400), (4, 48), (6, 60)):
            tool.w16(save, quick + offset, value)

        char = tool.char_base(base, 1)
        save[char + tool.LEVEL_REL] = 20
        tool.w32(save, char + tool.EXP_REL, 123_456)
        tool.w16(save, char + tool.HP_CAP_SOURCE_REL, 400)
        tool.w32(save, char + tool.CUR_HP_REL, 320)
        tool.w32(save, char + tool.MAX_HP_REL, 400)
        tool.w32(save, char + tool.CUR_MP_REL, 48)
        tool.w32(save, char + tool.MAX_MP_REL, 60)
        save[char + tool.STR_REL] = 30
        save[char + tool.STA_REL] = 28
        save[char + tool.SPD_REL] = 25
        save[char + tool.INT_REL] = 18
        save[char + tool.SPI_REL] = 22
        tool.w16(save, char + tool.MP_CAP_SOURCE_REL, 60)

        tool.write_inventory_entries(save, base, [(5001, 5)])
        tool.fix_checksums(save, [base])
    return save
