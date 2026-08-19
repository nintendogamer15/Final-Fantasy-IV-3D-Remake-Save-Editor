// SPDX-License-Identifier: LGPL-3.0-or-later
namespace FFIV3D.SaveEditor.Core;

public static class SafeFileWriter
{
    public static void WriteNew(string inputPath, string outputPath, FfivSaveDocument document)
    {
        if (SamePath(inputPath, outputPath))
            throw new IOException("Output path is the loaded input file; use in-place mode for a backed-up overwrite.");
        AtomicWrite(outputPath, document.ToArray());
    }

    public static string WriteInPlaceWithBackup(string path, FfivSaveDocument document)
    {
        var target = ResolveFinalLink(path);
        var original = File.ReadAllBytes(target);
        var backup = AvailableBackupPath(target);
        AtomicWrite(backup, original);
        AtomicWrite(target, document.ToArray());
        return backup;
    }

    public static string AvailableBackupPath(string path)
    {
        var first = path + ".bak";
        if (!File.Exists(first))
            return first;
        for (var index = 1; ; index++)
        {
            var candidate = path + $".bak.{index}";
            if (!File.Exists(candidate))
                return candidate;
        }
    }

    internal static void AtomicWrite(string path, byte[] contents)
    {
        var fullPath = Path.GetFullPath(path);
        var parent = Path.GetDirectoryName(fullPath) ?? throw new IOException("Output has no parent directory.");
        if (!Directory.Exists(parent))
            throw new DirectoryNotFoundException($"Output directory does not exist: {parent}");
        var temporary = Path.Combine(parent, $".{Path.GetFileName(fullPath)}.{Guid.NewGuid():N}.tmp");
        try
        {
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                       128 * 1024, FileOptions.WriteThrough))
            {
                stream.Write(contents);
                stream.Flush(flushToDisk: true);
            }
            if (!File.ReadAllBytes(temporary).AsSpan().SequenceEqual(contents))
                throw new IOException("Temporary-file verification failed; destination was not replaced.");
            File.Move(temporary, fullPath, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }

    private static bool SamePath(string first, string second)
    {
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        return string.Equals(Path.GetFullPath(first), Path.GetFullPath(second), comparison);
    }

    private static string ResolveFinalLink(string path)
    {
        var fullPath = Path.GetFullPath(path);
        var info = new FileInfo(fullPath);
        return info.LinkTarget is null ? fullPath : info.ResolveLinkTarget(returnFinalTarget: true)?.FullName ?? fullPath;
    }
}
