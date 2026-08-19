// SPDX-License-Identifier: LGPL-3.0-or-later
// Item/equipment IDs are adapted from KingCyrus20/FFIV-Save-Editor.
namespace FFIV3D.SaveEditor.Core;

public static class ItemCatalog
{
    public static IReadOnlyDictionary<ushort, string> Items { get; } = Parse(ItemsData);
    public static IReadOnlyDictionary<ushort, string> HandGear { get; } = Parse(HandGearData);
    public static IReadOnlyDictionary<ushort, string> HeadGear { get; } = Parse(HeadGearData);
    public static IReadOnlyDictionary<ushort, string> BodyGear { get; } = Parse(BodyGearData);
    public static IReadOnlyDictionary<ushort, string> ArmGear { get; } = Parse(ArmGearData);
    public static IReadOnlyDictionary<ushort, string> AllGear { get; } = Merge(HandGear, HeadGear, BodyGear, ArmGear);
    public static IReadOnlyDictionary<ushort, string> All { get; } = Merge(Items, AllGear);

    public static bool TryGetName(ushort itemId, out string name) => All.TryGetValue(itemId, out name!);

    public static ushort Resolve(string token)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(token);
        var value = token.Trim();
        if (TryParseId(value, out var numeric))
            return ValidateId(numeric);

        var exact = All.FirstOrDefault(x => string.Equals(x.Value, value, StringComparison.OrdinalIgnoreCase));
        if (!exact.Equals(default(KeyValuePair<ushort, string>)))
            return exact.Key;

        var matches = All.Where(x => x.Value.Contains(value, StringComparison.OrdinalIgnoreCase)).Take(13).ToArray();
        return matches.Length switch
        {
            0 => throw new ArgumentException($"Unknown item/gear name: {token}", nameof(token)),
            1 => matches[0].Key,
            _ => throw new ArgumentException(
                $"Ambiguous item/gear name '{token}'. Matches: " +
                string.Join(", ", matches.Take(12).Select(x => $"{x.Value}=0x{x.Key:X4}")), nameof(token)),
        };
    }

    public static ushort ValidateId(int itemId)
    {
        if (itemId is < 1 or > ushort.MaxValue || itemId == SaveLayout.EmptyItemId)
            throw new ArgumentOutOfRangeException(nameof(itemId), $"Item ID 0x{itemId:X} is not a usable 16-bit item ID");
        return (ushort)itemId;
    }

    private static bool TryParseId(string value, out int itemId)
    {
        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            return int.TryParse(value.AsSpan(2), System.Globalization.NumberStyles.HexNumber,
                System.Globalization.CultureInfo.InvariantCulture, out itemId);
        return int.TryParse(value, out itemId);
    }

    private static IReadOnlyDictionary<ushort, string> Parse(string source)
    {
        var result = new Dictionary<ushort, string>();
        foreach (var line in source.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var separator = line.IndexOf('|');
            result.Add(ushort.Parse(line.AsSpan(0, separator)), line[(separator + 1)..]);
        }
        return result;
    }

    private static IReadOnlyDictionary<ushort, string> Merge(params IReadOnlyDictionary<ushort, string>[] sources)
    {
        var result = new Dictionary<ushort, string>();
        foreach (var source in sources)
            foreach (var pair in source)
                result[pair.Key] = pair.Value;
        return result;
    }

    private const string ItemsData = """
        5001|Potion
        5002|Hi-Potion
        5003|X-Potion
        5004|Ether
        5005|Dry Ether
        5006|Elixir
        5007|Megalixir
        5008|Phoenix Down
        5009|Gold Needle
        5010|Maiden's Kiss
        5011|Mallet
        5012|Diet Ration
        5013|Echo Herbs
        5014|Eye Drops
        5015|Antidote
        5016|Cross
        5017|Remedy
        5018|Alarm Clock
        5019|Unicorn Horn
        5020|Tent
        5021|Cottage
        5022|Emergency Exit
        5023|Gnomish Bread
        5024|Gysahl Greens
        5025|Gysahl Whistle
        5026|Golden Apple
        5027|Silver Apple
        5028|Soma Drop
        5029|Siren
        5030|Lustful Lali-Ho
        5031|Ninja Sutra
        5035|Red Fang
        5036|White Fang
        5037|Blue Fang
        5038|Bomb Fragment
        5039|Bomb Crank
        5040|Antarctic Wind
        5041|Arctic Wind
        5042|Zeus' Wrath
        5043|Heavenly Wrath
        5044|Gaia Drum
        5045|Bomb Core
        5046|Stardust
        5047|Lilith's Kiss
        5048|Vampire Fang
        5049|Spider Silk
        5050|Silent Bell
        5051|Coeurl Whisker
        5052|Bestiary
        5053|Bronze Hourglass
        5054|Silver Hourglass
        5055|Gold Hourglass
        5056|Bacchus's Wine
        5057|Hermes Sandals
        5058|Decoy
        5059|Light Curtain
        5060|Lunar Curtain
        5061|Crystal
        5062|Member's Writ
        5191|Rainbow Pudding
        7401|Shuriken
        7402|Fuma Shuriken
        """;

    private const string HandGearData = """
        6001|Dark Sword
        6002|Shadowblade
        6003|Deathbringer
        6004|Mythgraven Sword
        6005|Lustrous Sword
        6006|Excalibur
        6007|Ragnarok
        6008|Ancient Sword
        6009|Blood Sword
        6010|Mythril Sword
        6011|Sleep Blade
        6012|Flame Sword
        6013|Icebrand
        6014|Stone Blade
        6015|Avenger
        6016|Defender
        6017|Fireshard
        6018|Frostshard
        6019|Thundershard
        6020|Onion Sword
        6101|Spear
        6102|Wind Spear
        6103|Flame Lance
        6104|Ice Lance
        6105|Blood Lance
        6106|Gungnir
        6107|Wyvern Lance
        6108|Holy Lance
        6201|Mythril Knife
        6202|Dancing Dagger
        6203|Mage Masher
        6204|Knife
        6301|Dream Harp
        6302|Lamia Harp
        6401|Flame Claw
        6402|Ice Claw
        6403|Lightning Claw
        6404|Faerie Claw
        6405|Hell Claw
        6406|Cat Claw
        6501|Wooden Hammer
        6502|Mythril Hammer
        6503|Gaia Hammer
        6601|Dwarven Axe
        6602|Ogrekiller
        6603|Poison Axe
        6604|Rune Axe
        6701|Kunai
        6702|Ashura
        6703|Kotetsu
        6704|Kiku-ichimonji
        6705|Murasame
        6706|Masamune
        6801|Rod
        6802|Flame Rod
        6803|Ice Rod
        6804|Thunder Rod
        6805|Lilith Rod
        6806|Polymorph Rod
        6807|Faerie Rod
        6808|Stardust Rod
        6901|Staff
        6902|Healing Staff
        6903|Mythril Staff
        6904|Power Staff
        6905|Aura Staff
        6906|Sage's Staff
        6907|Rune Staff
        7001|Bow
        7002|Power Bow
        7003|Great Bow
        7004|Killer Bow
        7005|Elven Bow
        7006|Yoichi Bow
        7007|Artemis Bow
        7101|Medusa Arrows
        7102|Iron Arrows
        7103|Holy Arrows
        7104|Fire Arrows
        7105|Ice Arrows
        7106|Lightning Arrows
        7107|Blinding Arrows
        7108|Poison Arrows
        7109|Silencing Arrows
        7110|Angel Arrows
        7111|Yoichi Arrows
        7112|Artemis Arrows
        7201|Whip
        7202|Chain Whip
        7203|Blitz Whip
        7204|Flame Whip
        7205|Dragon Whisker
        7301|Boomerang
        7302|Moonring Blade
        8001|Iron Shield
        8002|Dark Shield
        8003|Demon Shield
        8004|Lustrous Shield
        8005|Mythril Shield
        8006|Flame Shield
        8007|Ice Shield
        8008|Diamond Shield
        8009|Aegis Shield
        8010|Genji Shield
        8011|Dragon Shield
        8012|Crystal Shield
        8013|Onion Shield
        """;

    private const string HeadGearData = """
        8101|Leather Cap
        8102|Headband
        8103|Feathered Cap
        8104|Iron Helm
        8105|Wizard's Hat
        8106|Green Beret
        8107|Dark Helm
        8108|Hades Helm
        8109|Sage's Miter
        8110|Black Cowl
        8111|Demon Helm
        8112|Lustrous Helm
        8113|Gold Hairpin
        8114|Mythril Helm
        8115|Diamond Helm
        8116|Ribbon
        8117|Genji Helm
        8118|Dragon Helm
        8119|Crystal Helm
        8120|Glass Mask
        8121|Onion Helm
        """;

    private const string BodyGearData = """
        8201|Clothing
        8202|Prison Garb
        8203|Leather Clothing
        8204|Bard's Tunic
        8205|Gaia Gear
        8206|Iron Armor
        8207|Dark Armor
        8208|Sage's Surplice
        8209|Kenpo Gi
        8210|Hades Armor
        8211|Black Robe
        8212|Demon Armor
        8213|Black Belt Gi
        8214|Knight's Armor
        8215|Luminous Robe
        8216|Mythril Armor
        8217|Flame Mail
        8218|Power Sash
        8219|Ice Armor
        8220|White Robe
        8221|Diamond Armor
        8222|Minerva Bustier
        8223|Genji Armor
        8224|Dragon Mail
        8225|Black Garb
        8226|Crystal Mail
        8227|Adamant Armor
        8228|Onion Armor
        """;

    private const string ArmGearData = """
        8301|Ruby Ring
        8302|Cursed Ring
        8303|Iron Gloves
        8304|Dark Gloves
        8305|Iron Armlet
        8306|Power Armlet
        8307|Hades Gloves
        8308|Demon Gloves
        8309|Silver Armlet
        8310|Gauntlets
        8311|Rune Armlet
        8312|Mythril Gloves
        8313|Diamond Armlet
        8314|Diamond Gloves
        8315|Genji Gloves
        8316|Dragon Gloves
        8317|Giant's Gloves
        8318|Crystal Gloves
        8319|Protect Ring
        8320|Crystal Ring
        8321|Onion Gloves
        """;
}
