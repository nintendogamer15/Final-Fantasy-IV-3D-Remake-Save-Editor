// SPDX-License-Identifier: LGPL-3.0-or-later
using FFIV3D.SaveEditor.Core;

return Cli.Run(args);

internal static class Cli
{
    public static int Run(string[] args)
    {
        try
        {
            var options = Parse(args);
            if (options.Help)
            {
                PrintHelp();
                return 0;
            }
            if (options.ListKnown is not null)
            {
                foreach (var item in ItemCatalog.All.Where(x =>
                             string.IsNullOrEmpty(options.ListKnown)
                             || x.Value.Contains(options.ListKnown, StringComparison.OrdinalIgnoreCase)
                             || $"0x{x.Key:X4}".Contains(options.ListKnown, StringComparison.OrdinalIgnoreCase)))
                    Console.WriteLine($"0x{item.Key:X4}  {item.Value}");
                return 0;
            }
            if (options.Interactive)
                return RunInteractive(options.Path);
            if (string.IsNullOrWhiteSpace(options.Path))
                throw new ArgumentException("SAVE.BIN path required unless using --list-known or --interactive.");

            var document = FfivSaveDocument.Load(options.Path);
            var edited = ApplyOptions(document, options);
            if (options.InspectAll)
                Inspect(document, document.ReadVisibleCopies().Append(document.ReadRedundantCopy()));
            else if (options.Inspect || !edited)
                Inspect(document, document.SelectCopyBases(options.Target).Select(document.ReadCopy));

            if (edited)
            {
                if (options.InPlace)
                {
                    var backup = SafeFileWriter.WriteInPlaceWithBackup(options.Path, document);
                    Console.WriteLine($"wrote in-place; backup: {backup}");
                }
                else
                {
                    var output = options.Output ?? DefaultOutput(options.Path);
                    SafeFileWriter.WriteNew(options.Path, output, document);
                    Console.WriteLine($"wrote: {output}");
                    Console.WriteLine("Copy/rename that file to SAVE.BIN when you are ready to test it.");
                }
            }
            return 0;
        }
        catch (FileNotFoundException exception)
        {
            Console.Error.WriteLine($"error: could not read save: {exception.Message}");
            return 1;
        }
        catch (IOException exception)
        {
            Console.Error.WriteLine($"error: I/O failure: {exception.Message}");
            return 1;
        }
        catch (UnauthorizedAccessException exception)
        {
            Console.Error.WriteLine($"error: access denied: {exception.Message}");
            return 1;
        }
        catch (Exception exception) when (exception is ArgumentException or SaveFormatException or InvalidOperationException
                                          or FormatException or OverflowException)
        {
            Console.Error.WriteLine($"error: {exception.Message}");
            return 2;
        }
    }

    private static bool ApplyOptions(FfivSaveDocument document, Options options)
    {
        var edited = false;
        if (options.MaxParty)
        {
            var changed = document.MaxParty(options.Target);
            Console.WriteLine("maxed current-party roster rows: " + Summary(changed));
            edited = true;
        }
        if (options.MaxAllCharacters)
        {
            var changed = document.MaxAllCharacters(options.Target);
            Console.WriteLine("maxed non-empty roster rows: " + Summary(changed));
            edited = true;
        }
        var itemIds = new List<ushort>();
        if (options.GiveAllItems || options.GiveEverything)
            itemIds.AddRange(ItemCatalog.Items.Keys);
        if (options.GiveAllGear || options.GiveEverything)
            itemIds.AddRange(ItemCatalog.AllGear.Keys);
        itemIds.AddRange(options.AddItems.Select(ItemCatalog.Resolve));
        if (itemIds.Count != 0)
        {
            document.GiveItems(options.Target, itemIds, options.Quantity);
            Console.WriteLine($"added/updated {itemIds.Distinct().Count()} inventory entries to quantity >= {options.Quantity}");
            edited = true;
        }
        if (options.EquipBest)
        {
            var changed = document.EquipBestFinalParty(options.Target);
            Console.WriteLine("equipped tested strong gear for: " +
                              (changed.Count == 0 ? "no matching late-game party rows detected" : string.Join(", ", changed)));
            edited = true;
        }
        if (options.FixChecksum)
        {
            document.RepairChecksums(options.Target);
            Console.WriteLine("fixed checksums for selected save copies");
            edited = true;
        }
        return edited;
    }

    private static string Summary(IReadOnlyDictionary<int, IReadOnlyList<int>> values) =>
        string.Join("; ", values.Select(x => $"{SaveLayout.LabelForBase(x.Key)}=[{string.Join(',', x.Value)}]"));

    private static void Inspect(FfivSaveDocument document, IEnumerable<SaveCopyInfo> copies)
    {
        Console.WriteLine($"size: {document.ToArray().Length} / 0x{document.ToArray().Length:X}");
        var partner = document.GetRedundantPartner();
        if (partner.VisibleSlot is not null)
            Console.WriteLine($"redundant 0xB940 appears paired with visible slot {partner.VisibleSlot} " +
                              $"({partner.DifferingBodyBytes} differing body bytes)");
        foreach (var copy in copies)
        {
            Console.WriteLine($"checksum {copy.Label,-9} base=0x{copy.CopyBase:X4} " +
                              $"stored=0x{copy.Checksum.Stored:X8} calc=0x{copy.Checksum.Calculated:X8} " +
                              $"{(copy.Checksum.IsValid ? "OK" : "BAD")} {(copy.IsOccupied ? "occupied" : "empty/inactive")}");
            Console.WriteLine($"{copy.Label,-9} party roster indices: [{string.Join(',', copy.Party.Select(x => x.RosterIndex))}]  " +
                              $"inventory count: {copy.Inventory.Count}");
            foreach (var character in copy.Party)
                Console.WriteLine($"  row {character.RosterIndex,2}: level={character.Level} " +
                                  $"HP={character.CurrentHp}/{character.MaximumHp} " +
                                  $"MP={character.CurrentMp}/{character.MaximumMp} " +
                                  $"stats={character.Strength},{character.Speed},{character.Stamina},{character.Intellect},{character.Spirit}");
        }
    }

    private static int RunInteractive(string? initialPath)
    {
        Console.WriteLine("Final Fantasy IV 3D Remake Save Editor — interactive terminal mode");
        Console.Write("SAVE.BIN path" + (initialPath is null ? ": " : $" [{initialPath}]: "));
        var entered = Console.ReadLine()?.Trim();
        var path = string.IsNullOrWhiteSpace(entered) ? initialPath : entered;
        if (string.IsNullOrWhiteSpace(path))
            throw new ArgumentException("A save path is required.");
        var document = FfivSaveDocument.Load(path);
        var target = SlotTarget.Slot1;
        var changed = false;
        while (true)
        {
            Console.WriteLine();
            Console.WriteLine($"Target: {target}.  1 Inspect  2 Max party  3 Max roster  4 Give everything");
            Console.WriteLine("5 Equip best  6 Repair checksum  7 Add item  8 Change target  9 Write new  I Write in-place  0 Quit");
            Console.Write("> ");
            switch (Console.ReadLine()?.Trim())
            {
                case "1": Inspect(document, document.SelectCopyBases(target).Select(document.ReadCopy)); break;
                case "2": document.MaxParty(target); changed = true; Console.WriteLine("Party maxed."); break;
                case "3": document.MaxAllCharacters(target); changed = true; Console.WriteLine("Roster maxed."); break;
                case "4": document.GiveEverything(target); changed = true; Console.WriteLine("Known items and gear added."); break;
                case "5": document.EquipBestFinalParty(target); changed = true; Console.WriteLine("Late-game loadout applied."); break;
                case "6": document.RepairChecksums(target); changed = true; Console.WriteLine("Checksums repaired."); break;
                case "8":
                    target = PromptTarget();
                    break;
                case "7":
                    Console.Write("Item name or 0xID: ");
                    var itemId = ItemCatalog.Resolve(Console.ReadLine() ?? string.Empty);
                    Console.Write("Quantity [99]: ");
                    var quantityText = Console.ReadLine();
                    document.GiveItems(target, [itemId], string.IsNullOrWhiteSpace(quantityText) ? 99 : int.Parse(quantityText));
                    changed = true;
                    Console.WriteLine($"Added {ItemCatalog.All[itemId]}.");
                    break;
                case "9":
                    Console.Write($"Output [{DefaultOutput(path)}]: ");
                    var output = Console.ReadLine()?.Trim();
                    SafeFileWriter.WriteNew(path, string.IsNullOrWhiteSpace(output) ? DefaultOutput(path) : output, document);
                    Console.WriteLine("Edited copy written.");
                    changed = false;
                    break;
                case "I" or "i":
                    Console.Write("Type OVERWRITE to confirm: ");
                    if (Console.ReadLine() == "OVERWRITE")
                    {
                        Console.WriteLine($"Backup: {SafeFileWriter.WriteInPlaceWithBackup(path, document)}");
                        changed = false;
                    }
                    break;
                case "0":
                    if (changed)
                        Console.WriteLine("Unsaved in-memory changes were not written.");
                    return 0;
            }
        }
    }

    private static SlotTarget PromptTarget()
    {
        Console.Write("Target (1/2/3/all/backup): ");
        return ParseTarget(Console.ReadLine() ?? "1");
    }

    private static Options Parse(string[] args)
    {
        var options = new Options();
        for (var index = 0; index < args.Length; index++)
        {
            var argument = args[index];
            string Value() => ++index < args.Length ? args[index] : throw new ArgumentException($"Missing value for {argument}.");
            switch (argument)
            {
                case "-h" or "--help": options.Help = true; break;
                case "--interactive" or "--tui": options.Interactive = true; break;
                case "--slot": options.Target = ParseTarget(Value()); break;
                case "--inspect": options.Inspect = true; break;
                case "--inspect-all": options.InspectAll = true; break;
                case "--fix-checksum": options.FixChecksum = true; break;
                case "--max-party": options.MaxParty = true; break;
                case "--max-all-chars": options.MaxAllCharacters = true; break;
                case "--give-all-items": options.GiveAllItems = true; break;
                case "--give-all-gear": options.GiveAllGear = true; break;
                case "--give-everything": options.GiveEverything = true; break;
                case "--add-item": options.AddItems.Add(Value()); break;
                case "--equip-best": options.EquipBest = true; break;
                case "--quantity": options.Quantity = int.Parse(Value()); break;
                case "--out": options.Output = Value(); break;
                case "--in-place": options.InPlace = true; break;
                case "--list-known":
                    options.ListKnown = index + 1 < args.Length && !args[index + 1].StartsWith('-') ? args[++index] : "";
                    break;
                default:
                    if (argument.StartsWith('-'))
                        throw new ArgumentException($"Unknown option: {argument}");
                    if (options.Path is not null)
                        throw new ArgumentException("Only one SAVE.BIN path may be supplied.");
                    options.Path = argument;
                    break;
            }
        }
        if (options.InPlace && options.Output is not null)
            throw new ArgumentException("Use either --in-place or --out, not both.");
        if (options.Quantity is < 1 or > 99)
            throw new ArgumentException("Quantity must be from 1 through 99.");
        return options;
    }

    private static SlotTarget ParseTarget(string value) => value.ToLowerInvariant() switch
    {
        "active" or "default" or "1" => SlotTarget.Slot1,
        "2" => SlotTarget.Slot2,
        "3" => SlotTarget.Slot3,
        "all" => SlotTarget.AllOccupied,
        "backup" or "redundant" => SlotTarget.RedundantOnly,
        _ => throw new ArgumentException("--slot must be active, all, backup/redundant, or 1/2/3."),
    };

    private static string DefaultOutput(string path) =>
        Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path))!,
            Path.GetFileNameWithoutExtension(path) + ".edited" + Path.GetExtension(path));

    private static void PrintHelp() => Console.WriteLine("""
        FFIV3DSaveEditor.Cli SAVE.BIN [options]

          --slot active|1|2|3|all|backup   Select visible slot/copy
          --inspect / --inspect-all        Print save details
          --fix-checksum                   Repair selected checksums
          --max-party / --max-all-chars    Max current party or occupied roster rows
          --give-all-items / --give-all-gear / --give-everything
          --add-item NAME_OR_0xID           Add an item (repeatable)
          --equip-best                     Apply tested late-game equipment
          --quantity 1-99                  Quantity for inventory additions
          --out PATH                       Write a new edited file (default: *.edited.*)
          --in-place                       Overwrite with a numbered backup
          --list-known [FILTER]             List known item/equipment IDs
          --interactive, --tui             Interactive terminal interface
        """);

    private sealed class Options
    {
        public string? Path { get; set; }
        public SlotTarget Target { get; set; } = SlotTarget.Slot1;
        public bool Help { get; set; }
        public bool Interactive { get; set; }
        public string? ListKnown { get; set; }
        public bool Inspect { get; set; }
        public bool InspectAll { get; set; }
        public bool FixChecksum { get; set; }
        public bool MaxParty { get; set; }
        public bool MaxAllCharacters { get; set; }
        public bool GiveAllItems { get; set; }
        public bool GiveAllGear { get; set; }
        public bool GiveEverything { get; set; }
        public bool EquipBest { get; set; }
        public int Quantity { get; set; } = 99;
        public List<string> AddItems { get; } = [];
        public string? Output { get; set; }
        public bool InPlace { get; set; }
    }
}
