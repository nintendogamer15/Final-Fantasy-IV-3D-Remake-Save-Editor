using System.Buffers.Binary;
using FFIV3D.SaveEditor.Core;

namespace FFIV3D.SaveEditor.Tests;

internal static class TestSaveFactory
{
    public static byte[] Create()
    {
        var save = new byte[SaveLayout.SaveSize];
        foreach (var copyBase in new[] { SaveLayout.VisibleSlotBases[1], SaveLayout.RedundantCopyBase })
        {
            SaveLayout.CopyMagic.CopyTo(save.AsSpan(copyBase));
            var party = copyBase + SaveLayout.PartyEntryRelative;
            save[party + SaveLayout.PartyIndexRelative] = 1;
            var quick = party + SaveLayout.PartyHpMpRelative;
            Write16(save, quick, 320);
            Write16(save, quick + 2, 400);
            Write16(save, quick + 4, 48);
            Write16(save, quick + 6, 60);

            var character = SaveLayout.CharacterBase(copyBase, 1);
            save[character + SaveLayout.LevelRelative] = 20;
            Write32(save, character + SaveLayout.ExperienceRelative, 123_456);
            Write16(save, character + SaveLayout.HpCapSourceRelative, 400);
            Write32(save, character + SaveLayout.CurrentHpRelative, 320);
            Write32(save, character + SaveLayout.MaximumHpRelative, 400);
            Write32(save, character + SaveLayout.CurrentMpRelative, 48);
            Write32(save, character + SaveLayout.MaximumMpRelative, 60);
            save[character + SaveLayout.StrengthRelative] = 30;
            save[character + SaveLayout.StaminaRelative] = 28;
            save[character + SaveLayout.SpeedRelative] = 25;
            save[character + SaveLayout.IntellectRelative] = 18;
            save[character + SaveLayout.SpiritRelative] = 22;
            Write16(save, character + SaveLayout.MpCapSourceRelative, 60);

            Write32(save, copyBase + SaveLayout.ItemCountRelative, 1);
            Write16(save, copyBase + SaveLayout.FirstItemRelative, 5001);
            Write16(save, copyBase + SaveLayout.FirstItemRelative + 2, 5);
            Write32(save, copyBase + SaveLayout.ChecksumRelative,
                FfivSaveDocument.CalculateChecksum(save, copyBase));
        }
        return save;
    }

    public static ushort Read16(byte[] data, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(offset));
    public static uint Read32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(offset));
    public static void Write16(byte[] data, int offset, ushort value) => BinaryPrimitives.WriteUInt16LittleEndian(data.AsSpan(offset), value);
    public static void Write32(byte[] data, int offset, uint value) => BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(offset), value);
}
