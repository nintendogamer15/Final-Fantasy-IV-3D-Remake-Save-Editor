// SPDX-License-Identifier: LGPL-3.0-or-later
namespace FFIV3D.SaveEditor.Core;

public static class SaveLayout
{
    public const int SaveSize = 0x10000;
    public static ReadOnlySpan<byte> CopyMagic => "cd1000\0"u8;
    public const ushort EmptyItemId = 0xFF9D;
    public const uint ChecksumConstant = 0x010FC266;
    public const uint InactiveChecksumSentinel = 0x01100002;

    public const int ChecksumRelative = 0x1C;
    public const int BodyStartRelative = 0x20;
    public const int BodyEndRelative = 0x3DC0;
    public const int RedundantCopyBase = 0xB940;
    public const int RedundantPairDifferenceThreshold = 512;

    public static IReadOnlyDictionary<int, int> VisibleSlotBases { get; } =
        new Dictionary<int, int> { [1] = 0x0000, [2] = 0x3DC0, [3] = 0x7B80 };

    public const int GilRelative = 0x88;
    public const int FirstCharacterRelative = 0x9C;
    public const int CharacterStride = 0x1D4;
    public const int CharacterCount = 14;

    public const int LevelRelative = 0x00;
    public const int ExperienceRelative = 0x04;
    public const int HpCapSourceRelative = 0x0A;
    public const int CurrentHpRelative = 0x0C;
    public const int MaximumHpRelative = 0x10;
    public const int CurrentMpRelative = 0x14;
    public const int MaximumMpRelative = 0x18;
    public const int RightHandRelative = 0x26;
    public const int LeftHandRelative = 0x28;
    public const int HeadRelative = 0x2A;
    public const int BodyRelative = 0x2C;
    public const int ArmsRelative = 0x2E;
    public const int StrengthRelative = 0x1CA;
    public const int StaminaRelative = 0x1CB;
    public const int SpeedRelative = 0x1CC;
    public const int IntellectRelative = 0x1CD;
    public const int SpiritRelative = 0x1CE;
    public const int MpCapSourceRelative = 0x1D0;

    public const int FirstItemRelative = 0x1AF0;
    public const int ItemCountRelative = 0x20F4;
    public const int ItemStride = 4;
    public const int InventoryCapacity = (ItemCountRelative - FirstItemRelative) / ItemStride;

    public const int PartyEntryRelative = 0x20;
    public const int PartyEntryStride = 0x14;
    public const int PartyIndexRelative = 0x04;
    public const int PartyHpMpRelative = 0x08;
    public const int PartySize = 5;

    public static int CharacterBase(int copyBase, int rosterIndex)
    {
        if ((uint)rosterIndex >= CharacterCount)
            throw new ArgumentOutOfRangeException(nameof(rosterIndex));
        return copyBase + FirstCharacterRelative + rosterIndex * CharacterStride;
    }

    public static string LabelForBase(int copyBase)
    {
        if (copyBase == RedundantCopyBase)
            return "redundant";
        foreach (var pair in VisibleSlotBases)
            if (pair.Value == copyBase)
                return $"slot{pair.Key}";
        return $"base_0x{copyBase:X}";
    }
}
