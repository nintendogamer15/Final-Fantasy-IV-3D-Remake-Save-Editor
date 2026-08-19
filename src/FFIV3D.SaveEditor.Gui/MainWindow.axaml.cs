// SPDX-License-Identifier: LGPL-3.0-or-later
using Avalonia;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using Avalonia.Styling;
using FFIV3D.SaveEditor.Core;
using FFIV3D.SaveEditor.Gui.ViewModels;

namespace FFIV3D.SaveEditor.Gui;

public sealed partial class MainWindow : Window
{
    private readonly MainWindowViewModel _viewModel = new();
    private FfivSaveDocument? _document;
    private string? _savePath;

    public MainWindow() : this(null) { }

    public MainWindow(string? initialPath)
    {
        InitializeComponent();
        DataContext = _viewModel;
        if (!string.IsNullOrWhiteSpace(initialPath))
        {
            PathBox.Text = initialPath;
            Open(initialPath);
        }
    }

    private async void BrowseInput(object? sender, RoutedEventArgs e)
    {
        var files = await StorageProvider.OpenFilePickerAsync(new()
        {
            Title = "Open FFIV 3D SAVE.BIN",
            AllowMultiple = false,
            FileTypeFilter = [new("FFIV save") { Patterns = ["*.BIN", "*.bin"] }, FilePickerFileTypes.All],
        });
        var path = files.FirstOrDefault()?.Path.LocalPath;
        if (path is not null)
        {
            PathBox.Text = path;
            Open(path);
        }
    }

    private void LoadFile(object? sender, RoutedEventArgs e) => Open(PathBox.Text);

    private void ToggleTheme(object? sender, RoutedEventArgs e)
    {
        if (Application.Current is { } application)
            application.RequestedThemeVariant = application.ActualThemeVariant == ThemeVariant.Dark
                ? ThemeVariant.Light : ThemeVariant.Dark;
    }

    private void Open(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            Error("Choose a save file before loading.");
            return;
        }

        try
        {
            var fullPath = Path.GetFullPath(path.Trim());
            var candidate = FfivSaveDocument.Load(fullPath);
            _document = candidate;
            _savePath = fullPath;
            PathBox.Text = _savePath;
            OutputBox.Text = DefaultOutput(_savePath);
            _viewModel.Refresh(candidate);
            _viewModel.AppendLog($"Loaded {_savePath} ({SaveLayout.SaveSize:N0} bytes).");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or SaveFormatException
                                          or ArgumentException or NotSupportedException)
        {
            Error($"Could not open save: {exception.Message}");
        }
    }

    private void RefreshView(object? sender, RoutedEventArgs e)
    {
        if (_document is not null)
        {
            _viewModel.Refresh(_document);
            _viewModel.AppendLog("Refreshed save information.");
        }
    }

    private void MaxParty(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.MaxParty(Target);
        return "Maxed current-party characters.";
    });

    private void MaxAll(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.MaxAllCharacters(Target);
        return "Maxed all non-empty roster rows.";
    });

    private void GiveItems(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.GiveAllItems(Target, Quantity);
        return "Added all known non-equipment items.";
    });

    private void GiveGear(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.GiveAllGear(Target, Quantity);
        return "Added all known equipment and gear.";
    });

    private void GiveEverything(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.GiveEverything(Target, Quantity);
        return "Added all known items and gear.";
    });

    private void EquipBest(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        var changed = doc.EquipBestFinalParty(Target);
        return changed.Count == 0 ? "No matching late-game party rows were detected." : $"Equipped {string.Join(", ", changed)}.";
    });

    private void FixChecksum(object? sender, RoutedEventArgs e) => Edit(doc =>
    {
        doc.RepairChecksums(Target);
        return "Repaired selected checksums.";
    });

    private void AddItem(object? sender, RoutedEventArgs e)
    {
        var token = ItemBox.Text?.Trim();
        if (string.IsNullOrWhiteSpace(token))
        {
            Error("Enter or pick an item/gear name first.");
            return;
        }
        Edit(doc =>
        {
            var itemId = ItemCatalog.Resolve(token);
            doc.GiveItems(Target, [itemId], Quantity);
            return $"Added {ItemCatalog.All[itemId]} (0x{itemId:X4}) at quantity {Quantity}.";
        });
    }

    private void KnownItemSelected(object? sender, SelectionChangedEventArgs e)
    {
        if (KnownItemCombo.SelectedItem is string selected)
            ItemBox.Text = selected;
    }

    private async void BrowseOutput(object? sender, RoutedEventArgs e)
    {
        var file = await StorageProvider.SaveFilePickerAsync(new()
        {
            Title = "Write edited FFIV save",
            SuggestedFileName = _savePath is null ? "SAVE.edited.BIN" : Path.GetFileName(DefaultOutput(_savePath)),
            FileTypeChoices = [new("FFIV save") { Patterns = ["*.BIN", "*.bin"] }, FilePickerFileTypes.All],
        });
        if (file is not null)
            OutputBox.Text = file.Path.LocalPath;
    }

    private void WriteNew(object? sender, RoutedEventArgs e)
    {
        if (_document is null || _savePath is null)
        {
            Error("Load a save before writing.");
            return;
        }
        var output = string.IsNullOrWhiteSpace(OutputBox.Text) ? DefaultOutput(_savePath) : OutputBox.Text!.Trim();
        try
        {
            SafeFileWriter.WriteNew(_savePath, output, _document);
            _viewModel.AppendLog($"Wrote edited copy: {output}");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Error($"Write failed: {exception.Message}");
        }
    }

    private async void WriteInPlace(object? sender, RoutedEventArgs e)
    {
        if (_document is null || _savePath is null)
        {
            Error("Load a save before writing.");
            return;
        }
        if (!await ConfirmDialog.Ask(this, $"Overwrite {_savePath}?\nA new numbered .bak backup will be written first."))
            return;
        try
        {
            var backup = SafeFileWriter.WriteInPlaceWithBackup(_savePath, _document);
            _viewModel.AppendLog($"Wrote in place; backup: {backup}");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Error($"In-place write failed: {exception.Message}");
        }
    }

    private void Edit(Func<FfivSaveDocument, string> operation)
    {
        if (_document is null)
        {
            Error("Load a save before editing.");
            return;
        }
        try
        {
            var message = operation(_document);
            _viewModel.Refresh(_document);
            _viewModel.AppendLog(message + " Checksums were recalculated and verified.");
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            Error($"Edit failed: {exception.Message}");
        }
    }

    private SlotTarget Target => _viewModel.SelectedTarget.Value;
    private int Quantity => (int)(QuantityBox.Value ?? 99);
    private void Error(string message) => _viewModel.AppendLog("ERROR: " + message);
    private static string DefaultOutput(string path) => Path.Combine(Path.GetDirectoryName(path)!,
        Path.GetFileNameWithoutExtension(path) + ".edited" + Path.GetExtension(path));
}
