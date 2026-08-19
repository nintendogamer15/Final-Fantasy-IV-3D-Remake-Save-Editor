// SPDX-License-Identifier: LGPL-3.0-or-later
using System.Buffers.Binary;

namespace FFIV3D.SaveEditor.Core;

public sealed class FfivSaveDocument
{
    private readonly byte[] _data;

    private FfivSaveDocument(byte[] data) => _data = data;

    public static FfivSaveDocument Load(string path) => Parse(File.ReadAllBytes(path));

    public static FfivSaveDocument Parse(ReadOnlySpan<byte> source)
    {
        Validate(source);
        return new FfivSaveDocument(source.ToArray());
    }

    public static void Validate(ReadOnlySpan<byte> source)
    {
        if (source.Length != SaveLayout.SaveSize)
            throw new SaveFormatException(
                $"Unexpected file size {source.Length} bytes; expected {SaveLayout.SaveSize} / 0x{SaveLayout.SaveSize:X}.");

        var foundHeader = false;
        foreach (var copyBase in SaveLayout.VisibleSlotBases.Values.Append(SaveLayout.RedundantCopyBase))
            if (source.Slice(copyBase, SaveLayout.CopyMagic.Length).SequenceEqual(SaveLayout.CopyMagic))
            {
                foundHeader = true;
                break;
            }
        if (!foundHeader)
            throw new SaveFormatException(
                "No FFIV 3D save-copy header was found at any known slot offset; refusing to edit this file.");
    }

    public byte[] ToArray() => (byte[])_data.Clone();

    public IReadOnlyList<SaveCopyInfo> ReadVisibleCopies() =>
        SaveLayout.VisibleSlotBases.Values.Select(ReadCopy).ToArray();

    public SaveCopyInfo ReadRedundantCopy() => ReadCopy(SaveLayout.RedundantCopyBase);

    public SaveCopyInfo ReadCopy(int copyBase)
    {
        EnsureKnownBase(copyBase);
        var checksum = GetChecksumInfo(_data, copyBase);
        var party = DetectedPartySlots(_data, copyBase)
            .Select(pair => ReadPartyMember(_data, copyBase, pair.PartySlot, pair.RosterIndex))
            .ToArray();
        return new SaveCopyInfo(
            copyBase,
            SaveLayout.LabelForBase(copyBase),
            LooksOccupied(_data, copyBase),
            checksum,
            party,
            ReadInventory(_data, copyBase));
    }

    public IReadOnlyList<int> SelectCopyBases(SlotTarget target) => SelectCopyBases(_data, target);

    public IReadOnlyDictionary<int, IReadOnlyList<int>> MaxParty(SlotTarget target)
    {
        Dictionary<int, IReadOnlyList<int>>? result = null;
        TransactionalEdit(target, (candidate, bases) =>
        {
            result = [];
            foreach (var copyBase in bases)
            {
                var pairs = DetectedPartySlots(candidate, copyBase);
                var rosterIndices = pairs.Select(x => x.RosterIndex).ToArray();
                result[copyBase] = rosterIndices;
                foreach (var pair in pairs)
                    MaxQuickPartyBlock(candidate, copyBase, pair.PartySlot);
                foreach (var rosterIndex in rosterIndices.Distinct())
                    MaxCharacter(candidate, copyBase, rosterIndex);
            }
        });
        return result!;
    }

    public IReadOnlyDictionary<int, IReadOnlyList<int>> MaxAllCharacters(SlotTarget target)
    {
        Dictionary<int, IReadOnlyList<int>>? result = null;
        TransactionalEdit(target, (candidate, bases) =>
        {
            result = [];
            foreach (var copyBase in bases)
            {
                var used = Enumerable.Range(0, SaveLayout.CharacterCount)
                    .Where(index => LooksLikeUsedCharacter(candidate, copyBase, index)).ToArray();
                result[copyBase] = used;
                foreach (var rosterIndex in used)
                    MaxCharacter(candidate, copyBase, rosterIndex);
            }
        });
        return result!;
    }

    public void GiveItems(SlotTarget target, IEnumerable<ushort> itemIds, int quantity = 99)
    {
        var validatedQuantity = ValidateQuantity(quantity);
        var additions = itemIds.Select(x => ItemCatalog.ValidateId(x)).Distinct().ToArray();
        TransactionalEdit(target, (candidate, bases) =>
        {
            foreach (var copyBase in bases)
                UpsertInventory(candidate, copyBase, additions, validatedQuantity);
        });
    }

    public void GiveAllItems(SlotTarget target, int quantity = 99) => GiveItems(target, ItemCatalog.Items.Keys, quantity);

    public void GiveAllGear(SlotTarget target, int quantity = 99) => GiveItems(target, ItemCatalog.AllGear.Keys, quantity);

    public void GiveEverything(SlotTarget target, int quantity = 99) => GiveItems(target, ItemCatalog.All.Keys, quantity);

    public IReadOnlyList<string> EquipBestFinalParty(SlotTarget target)
    {
        List<string>? changed = null;
        TransactionalEdit(target, (candidate, bases) =>
        {
            changed = [];
            foreach (var copyBase in bases)
            {
                var party = DetectedPartySlots(candidate, copyBase).Select(x => x.RosterIndex).ToHashSet();
                foreach (var (rosterIndex, loadout) in FinalPartyLoadouts)
                {
                    if (!party.Contains(rosterIndex))
                        continue;
                    var itemIds = loadout.Equipment.Values.Where(x => x is not null).Select(x => ItemCatalog.Resolve(x!)).ToArray();
                    UpsertInventory(candidate, copyBase, itemIds, 1);
                    WriteEquipment(candidate, copyBase, rosterIndex, loadout.Equipment);
                    changed.Add($"{loadout.Name}@{SaveLayout.LabelForBase(copyBase)}");
                }
            }
        });
        return changed!;
    }

    public void RepairChecksums(SlotTarget target) => TransactionalEdit(target, (_, _) => { });

    public RedundantPartnerInfo GetRedundantPartner()
    {
        if (!LooksOccupied(_data, SaveLayout.RedundantCopyBase))
            return new(null, null);
        var scores = SaveLayout.VisibleSlotBases
            .Where(x => LooksOccupied(_data, x.Value))
            .Select(x => (Slot: x.Key, Difference: CountBodyDifferences(_data, x.Value, SaveLayout.RedundantCopyBase,
                SaveLayout.RedundantPairDifferenceThreshold + 1)))
            .OrderBy(x => x.Difference)
            .ToArray();
        if (scores.Length == 0)
            return new(null, null);
        return scores[0].Difference <= SaveLayout.RedundantPairDifferenceThreshold
            ? new(scores[0].Slot, scores[0].Difference)
            : new(null, scores[0].Difference);
    }

    public static uint CalculateChecksum(ReadOnlySpan<byte> data, int copyBase)
    {
        if (copyBase < 0 || copyBase + SaveLayout.BodyEndRelative > data.Length)
            throw new ArgumentOutOfRangeException(nameof(copyBase));
        uint total = 0;
        for (var offset = copyBase + SaveLayout.BodyStartRelative;
             offset < copyBase + SaveLayout.BodyEndRelative;
             offset += sizeof(uint))
            total = unchecked(total + BinaryPrimitives.ReadUInt32LittleEndian(data[offset..]));
        return unchecked(total + SaveLayout.ChecksumConstant);
    }

    public static ChecksumInfo GetChecksumInfo(ReadOnlySpan<byte> data, int copyBase) =>
        new(copyBase, ReadUInt32(data, copyBase + SaveLayout.ChecksumRelative), CalculateChecksum(data, copyBase));

    public static bool LooksOccupied(ReadOnlySpan<byte> data, int copyBase)
    {
        if (!data.Slice(copyBase, SaveLayout.CopyMagic.Length).SequenceEqual(SaveLayout.CopyMagic))
            return false;
        var checksum = GetChecksumInfo(data, copyBase);
        if (checksum.Stored != SaveLayout.InactiveChecksumSentinel && checksum.IsValid)
            return true;
        return DetectedPartySlots(data, copyBase).Count != 0 || ReadUInt32(data, copyBase + SaveLayout.ItemCountRelative) > 0;
    }

    public static IReadOnlyList<InventoryEntry> ReadInventory(ReadOnlySpan<byte> data, int copyBase)
    {
        var count = (int)Math.Min(ReadUInt32(data, copyBase + SaveLayout.ItemCountRelative), SaveLayout.InventoryCapacity);
        var entries = new List<InventoryEntry>(count);
        for (var index = 0; index < count; index++)
        {
            var offset = copyBase + SaveLayout.FirstItemRelative + index * SaveLayout.ItemStride;
            var itemId = ReadUInt16(data, offset);
            var quantity = ReadUInt16(data, offset + 2);
            if (itemId is not 0 && itemId != SaveLayout.EmptyItemId)
                entries.Add(new(itemId, quantity));
        }
        return entries;
    }

    private void TransactionalEdit(SlotTarget target, Action<byte[], IReadOnlyList<int>> operation)
    {
        var candidate = (byte[])_data.Clone();
        var bases = SelectCopyBases(candidate, target);
        operation(candidate, bases);
        foreach (var copyBase in bases)
            WriteUInt32(candidate, copyBase + SaveLayout.ChecksumRelative, CalculateChecksum(candidate, copyBase));

        Validate(candidate);
        foreach (var copyBase in bases)
            if (!GetChecksumInfo(candidate, copyBase).IsValid)
                throw new InvalidOperationException($"Checksum verification failed for {SaveLayout.LabelForBase(copyBase)}.");
        candidate.CopyTo(_data, 0);
    }

    private static IReadOnlyList<int> SelectCopyBases(ReadOnlySpan<byte> data, SlotTarget target)
    {
        var bases = target switch
        {
            SlotTarget.Active or SlotTarget.Slot1 => [SaveLayout.VisibleSlotBases[1]],
            SlotTarget.Slot2 => [SaveLayout.VisibleSlotBases[2]],
            SlotTarget.Slot3 => [SaveLayout.VisibleSlotBases[3]],
            SlotTarget.RedundantOnly => [SaveLayout.RedundantCopyBase],
            SlotTarget.AllOccupied => OccupiedVisibleBases(data),
            _ => throw new ArgumentOutOfRangeException(nameof(target)),
        };
        if (target != SlotTarget.RedundantOnly && LooksOccupied(data, SaveLayout.RedundantCopyBase))
            bases.Add(SaveLayout.RedundantCopyBase);
        if (bases.Count == 0)
            bases.Add(SaveLayout.VisibleSlotBases[1]);
        return bases;
    }

    private static PartyMemberInfo ReadPartyMember(ReadOnlySpan<byte> data, int copyBase, int partySlot, int rosterIndex)
    {
        var character = SaveLayout.CharacterBase(copyBase, rosterIndex);
        return new(
            partySlot,
            rosterIndex,
            data[character + SaveLayout.LevelRelative],
            ReadUInt32(data, character + SaveLayout.ExperienceRelative),
            ReadUInt32(data, character + SaveLayout.CurrentHpRelative),
            ReadUInt32(data, character + SaveLayout.MaximumHpRelative),
            ReadUInt32(data, character + SaveLayout.CurrentMpRelative),
            ReadUInt32(data, character + SaveLayout.MaximumMpRelative),
            data[character + SaveLayout.StrengthRelative],
            data[character + SaveLayout.StaminaRelative],
            data[character + SaveLayout.SpeedRelative],
            data[character + SaveLayout.IntellectRelative],
            data[character + SaveLayout.SpiritRelative]);
    }

    private static List<int> OccupiedVisibleBases(ReadOnlySpan<byte> data)
    {
        var result = new List<int>();
        foreach (var copyBase in SaveLayout.VisibleSlotBases.Values)
            if (LooksOccupied(data, copyBase))
                result.Add(copyBase);
        return result;
    }

    private static List<(int PartySlot, int RosterIndex)> DetectedPartySlots(ReadOnlySpan<byte> data, int copyBase)
    {
        var result = new List<(int, int)>();
        for (var partySlot = 0; partySlot < SaveLayout.PartySize; partySlot++)
        {
            var entry = copyBase + SaveLayout.PartyEntryRelative + partySlot * SaveLayout.PartyEntryStride;
            var rosterIndex = data[entry + SaveLayout.PartyIndexRelative];
            var hpMp = data.Slice(entry + SaveLayout.PartyHpMpRelative, 8);
            if (rosterIndex < SaveLayout.CharacterCount && hpMp.ContainsAnyExcept((byte)0))
                result.Add((partySlot, rosterIndex));
        }
        return result;
    }

    private static void MaxCharacter(Span<byte> data, int copyBase, int rosterIndex)
    {
        var character = SaveLayout.CharacterBase(copyBase, rosterIndex);
        data[character + SaveLayout.LevelRelative] = 99;
        WriteUInt32(data, character + SaveLayout.ExperienceRelative, 9_999_999);
        WriteUInt16(data, character + SaveLayout.HpCapSourceRelative, 9_999);
        WriteUInt32(data, character + SaveLayout.CurrentHpRelative, 9_999);
        WriteUInt32(data, character + SaveLayout.MaximumHpRelative, 9_999);
        WriteUInt32(data, character + SaveLayout.CurrentMpRelative, 999);
        WriteUInt32(data, character + SaveLayout.MaximumMpRelative, 999);
        WriteUInt16(data, character + SaveLayout.MpCapSourceRelative, 999);
        foreach (var relative in new[] { SaveLayout.StrengthRelative, SaveLayout.StaminaRelative,
                     SaveLayout.SpeedRelative, SaveLayout.IntellectRelative, SaveLayout.SpiritRelative })
            data[character + relative] = 99;
    }

    private static void MaxQuickPartyBlock(Span<byte> data, int copyBase, int partySlot)
    {
        var block = copyBase + SaveLayout.PartyEntryRelative + partySlot * SaveLayout.PartyEntryStride + SaveLayout.PartyHpMpRelative;
        WriteUInt16(data, block, 9_999);
        WriteUInt16(data, block + 2, 9_999);
        WriteUInt16(data, block + 4, 999);
        WriteUInt16(data, block + 6, 999);
    }

    private static bool LooksLikeUsedCharacter(ReadOnlySpan<byte> data, int copyBase, int rosterIndex)
    {
        var character = SaveLayout.CharacterBase(copyBase, rosterIndex);
        if (ReadUInt32(data, character + SaveLayout.CurrentHpRelative) != 0
               || ReadUInt32(data, character + SaveLayout.MaximumHpRelative) != 0
               || ReadUInt32(data, character + SaveLayout.CurrentMpRelative) != 0
               || ReadUInt32(data, character + SaveLayout.MaximumMpRelative) != 0
               || data[character + SaveLayout.LevelRelative] != 0)
            return true;
        foreach (var relative in new[] { SaveLayout.StrengthRelative, SaveLayout.StaminaRelative,
                     SaveLayout.SpeedRelative, SaveLayout.IntellectRelative, SaveLayout.SpiritRelative })
            if (data[character + relative] != 0)
                return true;
        return false;
    }

    private static void UpsertInventory(Span<byte> data, int copyBase, IEnumerable<ushort> additions, ushort quantity)
    {
        var countOffset = copyBase + SaveLayout.ItemCountRelative;
        var count = (int)Math.Min(ReadUInt32(data, countOffset), SaveLayout.InventoryCapacity);
        foreach (var itemId in additions)
        {
            var foundOffset = -1;
            var availableOffset = -1;
            for (var index = 0; index < count; index++)
            {
                var offset = copyBase + SaveLayout.FirstItemRelative + index * SaveLayout.ItemStride;
                var existingId = ReadUInt16(data, offset);
                if (existingId == itemId)
                {
                    foundOffset = offset;
                    break;
                }
                if (availableOffset < 0 && (existingId is 0 || existingId == SaveLayout.EmptyItemId))
                    availableOffset = offset;
            }

            if (foundOffset >= 0)
            {
                WriteUInt16(data, foundOffset + 2, Math.Max(ReadUInt16(data, foundOffset + 2), quantity));
                continue;
            }

            if (availableOffset < 0)
            {
                if (count >= SaveLayout.InventoryCapacity)
                    throw new InvalidOperationException(
                        $"Inventory at {SaveLayout.LabelForBase(copyBase)} is full ({SaveLayout.InventoryCapacity} entries).");
                availableOffset = copyBase + SaveLayout.FirstItemRelative + count * SaveLayout.ItemStride;
                count++;
                WriteUInt32(data, countOffset, (uint)count);
            }
            WriteUInt16(data, availableOffset, itemId);
            WriteUInt16(data, availableOffset + 2, quantity);
        }
    }

    private static void WriteEquipment(Span<byte> data, int copyBase, int rosterIndex,
        IReadOnlyDictionary<string, string?> equipment)
    {
        var character = SaveLayout.CharacterBase(copyBase, rosterIndex);
        foreach (var (slot, itemName) in equipment)
        {
            if (itemName is null)
                continue;
            var relative = slot switch
            {
                "right" => SaveLayout.RightHandRelative,
                "left" => SaveLayout.LeftHandRelative,
                "head" => SaveLayout.HeadRelative,
                "body" => SaveLayout.BodyRelative,
                "arms" => SaveLayout.ArmsRelative,
                _ => throw new InvalidOperationException($"Unknown equipment slot {slot}.")
            };
            WriteUInt16(data, character + relative, ItemCatalog.Resolve(itemName));
        }
    }

    private static int CountBodyDifferences(ReadOnlySpan<byte> data, int firstBase, int secondBase, int limit)
    {
        var differences = 0;
        for (var relative = SaveLayout.BodyStartRelative; relative < SaveLayout.BodyEndRelative; relative++)
            if (data[firstBase + relative] != data[secondBase + relative] && ++differences > limit)
                break;
        return differences;
    }

    private static ushort ValidateQuantity(int quantity)
    {
        if (quantity is < 1 or > 99)
            throw new ArgumentOutOfRangeException(nameof(quantity), "Quantity must be from 1 through 99.");
        return (ushort)quantity;
    }

    private static void EnsureKnownBase(int copyBase)
    {
        if (copyBase != SaveLayout.RedundantCopyBase && !SaveLayout.VisibleSlotBases.Values.Any(x => x == copyBase))
            throw new ArgumentOutOfRangeException(nameof(copyBase));
    }

    internal static ushort ReadUInt16(ReadOnlySpan<byte> data, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(data[offset..]);
    internal static uint ReadUInt32(ReadOnlySpan<byte> data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data[offset..]);
    internal static void WriteUInt16(Span<byte> data, int offset, int value) => BinaryPrimitives.WriteUInt16LittleEndian(data[offset..], (ushort)value);
    internal static void WriteUInt32(Span<byte> data, int offset, uint value) => BinaryPrimitives.WriteUInt32LittleEndian(data[offset..], value);

    private sealed record PartyLoadout(string Name, IReadOnlyDictionary<string, string?> Equipment);

    private static IReadOnlyDictionary<int, PartyLoadout> FinalPartyLoadouts { get; } =
        new Dictionary<int, PartyLoadout>
        {
            [5] = new("Rydia", new Dictionary<string, string?> { ["right"] = "Dragon Whisker", ["left"] = null,
                ["head"] = "Ribbon", ["body"] = "Adamant Armor", ["arms"] = "Crystal Ring" }),
            [1] = new("Cecil", new Dictionary<string, string?> { ["right"] = "Ragnarok", ["left"] = "Crystal Shield",
                ["head"] = "Crystal Helm", ["body"] = "Adamant Armor", ["arms"] = "Crystal Ring" }),
            [2] = new("Kain", new Dictionary<string, string?> { ["right"] = "Holy Lance", ["left"] = "Dragon Shield",
                ["head"] = "Dragon Helm", ["body"] = "Adamant Armor", ["arms"] = "Crystal Ring" }),
            [3] = new("Rosa", new Dictionary<string, string?> { ["right"] = "Artemis Bow", ["left"] = "Artemis Arrows",
                ["head"] = "Ribbon", ["body"] = "Adamant Armor", ["arms"] = "Crystal Ring" }),
            [12] = new("Edge", new Dictionary<string, string?> { ["right"] = "Masamune", ["left"] = "Murasame",
                ["head"] = "Ribbon", ["body"] = "Adamant Armor", ["arms"] = "Crystal Ring" }),
        };
}
