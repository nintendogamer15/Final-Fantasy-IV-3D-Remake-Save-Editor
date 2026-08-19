using FFIV3D.SaveEditor.Core;

namespace FFIV3D.SaveEditor.Tests;

public sealed class SaveDocumentTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" \t ")]
    public void LoadRejectsMissingFileSelection(string? path)
    {
        var exception = Assert.Throws<SaveFormatException>(() => FfivSaveDocument.Load(path));
        Assert.Equal("No save file was selected.", exception.Message);
    }

    [Fact]
    public void SyntheticSaveHasValidChecksums()
    {
        var document = FfivSaveDocument.Parse(TestSaveFactory.Create());
        Assert.True(document.ReadCopy(SaveLayout.VisibleSlotBases[1]).Checksum.IsValid);
        Assert.True(document.ReadRedundantCopy().Checksum.IsValid);
    }

    [Fact]
    public void ValidationRejectsWrongSizeAndMissingHeaders()
    {
        Assert.Throws<SaveFormatException>(() => FfivSaveDocument.Parse("not a save"u8));
        Assert.Throws<SaveFormatException>(() => FfivSaveDocument.Parse(new byte[SaveLayout.SaveSize]));
        var damaged = TestSaveFactory.Create();
        damaged[SaveLayout.ChecksumRelative] ^= 0xFF;
        FfivSaveDocument.Parse(damaged); // Checksum damage must remain repairable.
    }

    [Fact]
    public void VisibleTargetIncludesOccupiedRedundantCopy()
    {
        var document = FfivSaveDocument.Parse(TestSaveFactory.Create());
        Assert.Equal(new[] { 0, SaveLayout.RedundantCopyBase }, document.SelectCopyBases(SlotTarget.Slot1));
    }

    [Fact]
    public void MaxPartyUpdatesDetailedQuickAndSourceValues()
    {
        var document = FfivSaveDocument.Parse(TestSaveFactory.Create());
        var result = document.MaxParty(SlotTarget.Slot1);
        Assert.Equal(new[] { 1 }, result[0]);

        var edited = document.ToArray();
        foreach (var copyBase in new[] { 0, SaveLayout.RedundantCopyBase })
        {
            var character = SaveLayout.CharacterBase(copyBase, 1);
            Assert.Equal(99, edited[character + SaveLayout.LevelRelative]);
            Assert.Equal(9_999u, TestSaveFactory.Read32(edited, character + SaveLayout.CurrentHpRelative));
            Assert.Equal(9_999, TestSaveFactory.Read16(edited, character + SaveLayout.HpCapSourceRelative));
            Assert.Equal(999u, TestSaveFactory.Read32(edited, character + SaveLayout.CurrentMpRelative));
            Assert.Equal(999, TestSaveFactory.Read16(edited, character + SaveLayout.MpCapSourceRelative));
            Assert.True(FfivSaveDocument.GetChecksumInfo(edited, copyBase).IsValid);
        }
    }

    [Fact]
    public void InventoryUpsertPreservesOrderQuantityAndUnknownBytes()
    {
        var source = TestSaveFactory.Create();
        var markerOffset = SaveLayout.FirstItemRelative + 100 * SaveLayout.ItemStride;
        source[markerOffset] = 0xA5;
        TestSaveFactory.Write32(source, SaveLayout.ChecksumRelative,
            FfivSaveDocument.CalculateChecksum(source, 0));
        var document = FfivSaveDocument.Parse(source);

        document.GiveItems(SlotTarget.Slot1, new ushort[] { 5001, 5002 }, 20);

        Assert.Equal(new[] { new InventoryEntry(5001, 20), new InventoryEntry(5002, 20) },
            document.ReadCopy(0).Inventory);
        Assert.Equal(0xA5, document.ToArray()[markerOffset]);
    }

    [Fact]
    public void InventoryFailureIsTransactionalAcrossCopies()
    {
        var source = TestSaveFactory.Create();
        var copyBase = SaveLayout.RedundantCopyBase;
        TestSaveFactory.Write32(source, copyBase + SaveLayout.ItemCountRelative, SaveLayout.InventoryCapacity);
        for (var index = 0; index < SaveLayout.InventoryCapacity; index++)
        {
            var offset = copyBase + SaveLayout.FirstItemRelative + index * SaveLayout.ItemStride;
            TestSaveFactory.Write16(source, offset, (ushort)(10_000 + index));
            TestSaveFactory.Write16(source, offset + 2, 1);
        }
        TestSaveFactory.Write32(source, copyBase + SaveLayout.ChecksumRelative,
            FfivSaveDocument.CalculateChecksum(source, copyBase));
        var document = FfivSaveDocument.Parse(source);

        Assert.Throws<InvalidOperationException>(() => document.GiveItems(SlotTarget.Slot1, new ushort[] { 5002 }, 20));
        Assert.Equal(source, document.ToArray());
    }

    [Fact]
    public void EquipBestAddsAndEquipsCecilLoadout()
    {
        var document = FfivSaveDocument.Parse(TestSaveFactory.Create());
        var changed = document.EquipBestFinalParty(SlotTarget.Slot1);
        Assert.Contains("Cecil@slot1", changed);
        Assert.Contains(document.ReadCopy(0).Inventory, x => x.ItemId == 6007);
        var bytes = document.ToArray();
        Assert.Equal(6007, TestSaveFactory.Read16(bytes,
            SaveLayout.CharacterBase(0, 1) + SaveLayout.RightHandRelative));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(100)]
    public void QuantityBoundsAreEnforcedWithoutMutation(int quantity)
    {
        var document = FfivSaveDocument.Parse(TestSaveFactory.Create());
        var original = document.ToArray();
        Assert.Throws<ArgumentOutOfRangeException>(() => document.GiveItems(SlotTarget.Slot1, new ushort[] { 5002 }, quantity));
        Assert.Equal(original, document.ToArray());
    }

    [Fact]
    public void ItemCatalogPreservesAllKnownIdsAndResolutionRules()
    {
        Assert.Equal(62, ItemCatalog.Items.Count);
        Assert.Equal(177, ItemCatalog.AllGear.Count);
        Assert.Equal(239, ItemCatalog.All.Count);
        Assert.Equal(6007, ItemCatalog.Resolve("Ragnarok"));
        Assert.Equal(6007, ItemCatalog.Resolve("0x1777"));
        Assert.Throws<ArgumentException>(() => ItemCatalog.Resolve("ring"));
    }
}
