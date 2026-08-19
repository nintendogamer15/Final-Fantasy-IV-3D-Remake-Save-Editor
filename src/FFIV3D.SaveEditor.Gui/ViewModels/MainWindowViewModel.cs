// SPDX-License-Identifier: LGPL-3.0-or-later
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using FFIV3D.SaveEditor.Core;

namespace FFIV3D.SaveEditor.Gui.ViewModels;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    private SlotViewModel? _selectedCopy;
    private TargetChoice _selectedTarget;
    private string _redundantSummary = "Redundant copy: no file loaded";
    private string _log = "Ready. Choose SAVE.BIN and press Load.";

    public MainWindowViewModel()
    {
        Targets =
        [
            new("Slot 1", SlotTarget.Slot1),
            new("Slot 2", SlotTarget.Slot2),
            new("Slot 3", SlotTarget.Slot3),
            new("All occupied slots", SlotTarget.AllOccupied),
        ];
        _selectedTarget = Targets[0];
        KnownItems = ItemCatalog.All.OrderBy(x => x.Value).Select(x => x.Value).ToArray();
    }

    public ObservableCollection<SlotViewModel> Copies { get; } = [];
    public IReadOnlyList<TargetChoice> Targets { get; }
    public IReadOnlyList<string> KnownItems { get; }

    public SlotViewModel? SelectedCopy
    {
        get => _selectedCopy;
        set => Set(ref _selectedCopy, value);
    }

    public TargetChoice SelectedTarget
    {
        get => _selectedTarget;
        set => Set(ref _selectedTarget, value);
    }

    public string RedundantSummary
    {
        get => _redundantSummary;
        private set => Set(ref _redundantSummary, value);
    }

    public string Log
    {
        get => _log;
        private set => Set(ref _log, value);
    }

    public void Refresh(FfivSaveDocument document)
    {
        var selectedBase = SelectedCopy?.CopyBase;
        Copies.Clear();
        foreach (var copy in document.ReadVisibleCopies())
            Copies.Add(new(copy));
        SelectedCopy = Copies.FirstOrDefault(x => x.CopyBase == selectedBase) ?? Copies.FirstOrDefault();

        var redundant = document.ReadRedundantCopy();
        var partner = document.GetRedundantPartner();
        var pairing = partner.VisibleSlot is not null
            ? $"paired with slot {partner.VisibleSlot} ({partner.DifferingBodyBytes} body-byte differences)"
            : partner.DifferingBodyBytes is not null
                ? $"no confident pair (closest difference: {partner.DifferingBodyBytes})"
                : "not occupied";
        RedundantSummary = $"Redundant copy at 0x{redundant.CopyBase:X4}: " +
                           $"{(redundant.IsOccupied ? "occupied; " : string.Empty)}{pairing}. " +
                           "Visible-slot edits include it when occupied.";
    }

    public void AppendLog(string message) => Log = string.IsNullOrEmpty(Log) ? message : $"{Log}{Environment.NewLine}{message}";

    public event PropertyChangedEventHandler? PropertyChanged;

    private void Set<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
            return;
        field = value;
        PropertyChanged?.Invoke(this, new(propertyName));
    }
}

public sealed record TargetChoice(string Label, SlotTarget Value);

public sealed class SlotViewModel
{
    public SlotViewModel(SaveCopyInfo copy)
    {
        CopyBase = copy.CopyBase;
        Label = copy.Label.Replace("slot", "Slot ", StringComparison.OrdinalIgnoreCase);
        Status = $"Base 0x{copy.CopyBase:X4} · {(copy.IsOccupied ? "occupied" : "empty/inactive")} · " +
                 $"checksum {(copy.Checksum.IsValid ? "OK" : "BAD")}\n" +
                 $"Stored 0x{copy.Checksum.Stored:X8} · calculated 0x{copy.Checksum.Calculated:X8}";
        Party = copy.Party;
        Inventory = copy.Inventory;
    }

    public int CopyBase { get; }
    public string Label { get; }
    public string Status { get; }
    public IReadOnlyList<PartyMemberInfo> Party { get; }
    public IReadOnlyList<InventoryEntry> Inventory { get; }
}
