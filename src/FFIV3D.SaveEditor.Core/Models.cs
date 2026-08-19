// SPDX-License-Identifier: LGPL-3.0-or-later
namespace FFIV3D.SaveEditor.Core;

public enum SlotTarget
{
    Active,
    Slot1,
    Slot2,
    Slot3,
    AllOccupied,
    RedundantOnly,
}

public sealed record ChecksumInfo(int CopyBase, uint Stored, uint Calculated)
{
    public bool IsValid => Stored == Calculated;
}

public sealed record PartyMemberInfo(
    int PartySlot,
    int RosterIndex,
    byte Level,
    uint Experience,
    uint CurrentHp,
    uint MaximumHp,
    uint CurrentMp,
    uint MaximumMp,
    byte Strength,
    byte Stamina,
    byte Speed,
    byte Intellect,
    byte Spirit);

public sealed record InventoryEntry(ushort ItemId, ushort Quantity)
{
    public string Name => ItemCatalog.TryGetName(ItemId, out var name) ? name : $"0x{ItemId:X4}";
}

public sealed record SaveCopyInfo(
    int CopyBase,
    string Label,
    bool IsOccupied,
    ChecksumInfo Checksum,
    IReadOnlyList<PartyMemberInfo> Party,
    IReadOnlyList<InventoryEntry> Inventory);

public sealed record RedundantPartnerInfo(int? VisibleSlot, int? DifferingBodyBytes);

public sealed class SaveFormatException : Exception
{
    public SaveFormatException(string message) : base(message) { }
    public SaveFormatException(string message, Exception innerException) : base(message, innerException) { }
}
