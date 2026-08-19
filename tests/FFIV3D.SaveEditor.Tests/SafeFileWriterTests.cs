using FFIV3D.SaveEditor.Core;

namespace FFIV3D.SaveEditor.Tests;

public sealed class SafeFileWriterTests
{
    [Fact]
    public void NewOutputRefusesInputAndInPlacePreservesNumberedBackups()
    {
        var directory = Path.Combine(Path.GetTempPath(), $"ffiv-tests-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        try
        {
            var path = Path.Combine(directory, "SAVE.BIN");
            var original = TestSaveFactory.Create();
            File.WriteAllBytes(path, original);
            var first = FfivSaveDocument.Parse(original);
            first.MaxParty(SlotTarget.Slot1);

            Assert.Throws<IOException>(() => SafeFileWriter.WriteNew(path, path, first));
            Assert.Equal(original, File.ReadAllBytes(path));

            var firstBackup = SafeFileWriter.WriteInPlaceWithBackup(path, first);
            var firstEdit = File.ReadAllBytes(path);
            var second = FfivSaveDocument.Parse(firstEdit);
            second.GiveItems(SlotTarget.Slot1, new ushort[] { 5002 }, 20);
            var secondBackup = SafeFileWriter.WriteInPlaceWithBackup(path, second);

            Assert.Equal("SAVE.BIN.bak", Path.GetFileName(firstBackup));
            Assert.Equal("SAVE.BIN.bak.1", Path.GetFileName(secondBackup));
            Assert.Equal(original, File.ReadAllBytes(firstBackup));
            Assert.Equal(firstEdit, File.ReadAllBytes(secondBackup));
            Assert.Equal(second.ToArray(), File.ReadAllBytes(path));
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }
}
