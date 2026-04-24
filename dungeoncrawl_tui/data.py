"""Static data tables — classes, races, spells, monsters, items.

Clean-room: all strings are original, all tables derived from public
design documentation of Wizardry's mechanics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

STARTER_GOLD = 100
MAX_PARTY = 6
MAX_ROSTER = 20


# ---- race / class -------------------------------------------------------

@dataclass(eq=False)
class Race:
    key: str
    name: str
    # base stat mods applied to 3d6 rolls
    mods: dict[str, int] = field(default_factory=dict)


RACES: dict[str, Race] = {
    "H": Race("H", "Human", {}),
    "E": Race("E", "Elf", {"STR": -1, "IQ": +2, "PIE": +1, "VIT": -2, "AGI": +1}),
    "D": Race("D", "Dwarf", {"STR": +2, "IQ": -1, "PIE": +2, "VIT": +2, "AGI": -2}),
    "G": Race("G", "Gnome", {"STR": -1, "IQ": -1, "PIE": +2, "VIT": +1, "AGI": +1}),
    "B": Race("B", "Bobbit", {"STR": -2, "IQ": +1, "PIE": -1, "VIT": +1, "AGI": +3, "LUC": +1}),
}


@dataclass(eq=False)
class CharClass:
    key: str
    name: str
    short: str                      # 3-letter tag for tight UIs
    hp_die: int                     # HP gained per level = d(hp_die) + VIT bonus
    can_cast_mage: bool = False
    mage_cap_level: int = 0         # max spell level for Mage spells
    mage_start_level: int = 1       # class level at which mage casting starts
    can_cast_priest: bool = False
    priest_cap_level: int = 0
    priest_start_level: int = 1
    # stat requirements (min values)
    req: dict[str, int] = field(default_factory=dict)
    alignments: tuple[str, ...] = ("G", "N", "E")
    # equipment tags this class can use (matches Item.tags)
    can_use: tuple[str, ...] = ()
    # descriptor for UI
    desc: str = ""


CLASSES: dict[str, CharClass] = {
    "F": CharClass(
        key="F", name="Fighter", short="FIG", hp_die=10,
        can_use=("sword", "axe", "mace", "bow", "heavy", "light", "shield", "helm"),
        desc="Front-line brawler. Heavy armor, any weapon, no spells.",
    ),
    "M": CharClass(
        key="M", name="Mage", short="MAG", hp_die=4,
        can_cast_mage=True, mage_cap_level=7,
        can_use=("dagger", "staff", "cloth"),
        desc="Offensive caster. Cinders and bolts. Fragile.",
    ),
    "P": CharClass(
        key="P", name="Priest", short="PRI", hp_die=8,
        can_cast_priest=True, priest_cap_level=7,
        can_use=("mace", "staff", "light", "shield", "helm"),
        desc="Heal, ward, raise. No bladed weapons by vow.",
    ),
    "T": CharClass(
        key="T", name="Thief", short="THI", hp_die=6,
        can_use=("dagger", "sword", "light", "cloak"),
        desc="Disarm traps, pick locks, strike from shadow.",
    ),
    "B": CharClass(
        key="B", name="Bishop", short="BIS", hp_die=6,
        can_cast_mage=True, mage_cap_level=7, mage_start_level=1,
        can_cast_priest=True, priest_cap_level=7, priest_start_level=4,
        req={"IQ": 12, "PIE": 12},
        can_use=("mace", "staff", "light", "shield", "helm", "cloth"),
        desc="Both schools. Appraises items. Req IQ 12, PIE 12.",
    ),
    "S": CharClass(
        key="S", name="Samurai", short="SAM", hp_die=8,
        can_cast_mage=True, mage_cap_level=4, mage_start_level=4,
        req={"STR": 15, "IQ": 11, "PIE": 10, "VIT": 14, "AGI": 10},
        alignments=("G", "N"),
        can_use=("sword", "bow", "heavy", "light", "helm"),
        desc="Fighter+Mage. Req STR15 IQ11 PIE10 VIT14 AGI10. G/N only.",
    ),
    "L": CharClass(
        key="L", name="Lord", short="LRD", hp_die=10,
        can_cast_priest=True, priest_cap_level=7, priest_start_level=4,
        req={"STR": 15, "IQ": 12, "PIE": 12, "VIT": 15, "AGI": 14, "LUC": 15},
        alignments=("G",),
        can_use=("sword", "axe", "mace", "heavy", "light", "shield", "helm"),
        desc="Fighter+Priest. Req 15/12/12/15/14/15. Good only.",
    ),
    "N": CharClass(
        key="N", name="Ninja", short="NIN", hp_die=6,
        req={"STR": 17, "IQ": 17, "PIE": 17, "VIT": 17, "AGI": 17, "LUC": 17},
        alignments=("E",),
        can_use=("sword", "dagger", "light", "cloak"),
        desc="All stats ≥17. Evil only. Lethal unarmored strikes.",
    ),
}

# Display order for UI.
CLASS_ORDER = ["F", "M", "P", "T", "B", "S", "L", "N"]


def meets_class_req(cls: CharClass, stats: dict[str, int], alignment: str) -> bool:
    if alignment not in cls.alignments:
        return False
    for stat, val in cls.req.items():
        if stats.get(stat, 0) < val:
            return False
    return True


# ---- spells -------------------------------------------------------------

@dataclass(eq=False)
class Spell:
    id: str
    name: str
    school: str     # "mage" | "priest"
    level: int      # 1-7
    effect: str     # "damage" | "heal" | "status" | "buff" | "revive" | "light"
    target: str     # "one_enemy" | "group_enemy" | "all_enemy" | "one_ally" | "all_ally" | "self" | "party"
    power: int = 0
    element: str = ""
    combat_only: bool = True
    desc: str = ""


# All spell names are original (see DECISIONS.md).
SPELL_LIST: list[Spell] = [
    # Mage L1
    Spell("CINDR", "Cindr", "mage", 1, "damage", "group_enemy", 5, "fire", desc="Flicker of flame on one group."),
    Spell("SHIELD", "Shield", "mage", 1, "buff", "party", 0, desc="-2 AC for party, one fight."),
    Spell("SNOOZE", "Snooze", "mage", 1, "status", "group_enemy", 0, desc="Sleep one group."),
    # Mage L2
    Spell("STATIC", "Static", "mage", 2, "damage", "one_enemy", 12, "shock", desc="Crack of lightning."),
    Spell("VANISH", "Vanish", "mage", 2, "buff", "one_ally", 0, desc="Target can walk through illusion."),
    Spell("QUELL", "Quell", "mage", 2, "status", "all_enemy", 0, desc="Dull the blades of foes."),
    # Mage L3
    Spell("BOLT", "Bolt", "mage", 3, "damage", "group_enemy", 18, "shock", desc="Arc of lightning through a group."),
    Spell("BURST", "Burst", "mage", 3, "damage", "all_enemy", 14, "fire", desc="Scatter flame across the field."),
    Spell("MAZE", "Maze", "mage", 3, "status", "group_enemy", 0, desc="Lost — no action this round."),
    # Mage L4
    Spell("INFER", "Infer", "mage", 4, "damage", "group_enemy", 28, "fire", desc="Inferno on a group."),
    Spell("FROST", "Frost", "mage", 4, "damage", "all_enemy", 22, "cold", desc="Killing frost across the field."),
    Spell("BLINK", "Blink", "mage", 4, "buff", "party", 0, desc="Party shifts half a step — evade surges."),
    # Mage L5
    Spell("HAVOC", "Havoc", "mage", 5, "damage", "group_enemy", 40, "", desc="Raw force shredding a group."),
    Spell("FEAR", "Fear", "mage", 5, "status", "all_enemy", 0, desc="All foes recoil in dread."),
    Spell("DEPORT", "Deport", "mage", 5, "status", "group_enemy", 0, desc="Teleport a group out of the fight."),
    # Mage L6
    Spell("LANCE", "Lance", "mage", 6, "damage", "one_enemy", 60, "cold", desc="Icicle spear — one foe, huge damage."),
    Spell("SEAL", "Seal", "mage", 6, "buff", "party", 0, desc="Spell-shield — enemy magic weaker."),
    Spell("VANIX", "Vanix", "mage", 6, "buff", "party", 0, desc="Whole party walks half-invisible."),
    # Mage L7
    Spell("UNMAKE", "Unmake", "mage", 7, "damage", "all_enemy", 80, "", desc="Annihilate all enemy groups."),
    Spell("DRAIN", "Drain", "mage", 7, "damage", "one_enemy", 90, "", desc="Siphon essence — huge single-target."),
    Spell("VOID", "Void", "mage", 7, "status", "all_enemy", 0, desc="Snuff life. Save or perish."),
    # Priest L1
    Spell("MEND", "Mend", "priest", 1, "heal", "one_ally", 10, desc="Restore 8-16 HP."),
    Spell("WARD", "Ward", "priest", 1, "buff", "party", 0, desc="-2 AC, lasts fight."),
    Spell("LIGHT", "Light", "priest", 1, "light", "party", 0, combat_only=False, desc="Reveal dark corridors."),
    # Priest L2
    Spell("CURE", "Cure", "priest", 2, "heal", "one_ally", 0, combat_only=False, desc="Remove poison."),
    Spell("BLESS", "Bless", "priest", 2, "buff", "party", 0, desc="+1 to hit, lasts fight."),
    Spell("SILENCE", "Silence", "priest", 2, "status", "group_enemy", 0, desc="No casting from this group."),
    # Priest L3
    Spell("REMOVE", "Remove", "priest", 3, "status", "one_ally", 0, combat_only=False, desc="Remove paralysis."),
    Spell("FIND", "Find", "priest", 3, "buff", "party", 0, combat_only=False, desc="Reveal the layout nearby."),
    Spell("PRAY", "Pray", "priest", 3, "heal", "all_ally", 12, desc="Restore 10-14 HP to all."),
    # Priest L4
    Spell("HEAL", "Heal", "priest", 4, "heal", "one_ally", 30, desc="Restore ~30 HP."),
    Spell("PURGE", "Purge", "priest", 4, "status", "all_enemy", 0, desc="Expel undead/evil."),
    Spell("DIVINE", "Divine", "priest", 4, "damage", "group_enemy", 24, "holy", desc="Smite a group with radiance."),
    # Priest L5
    Spell("RAISE", "Raise", "priest", 5, "revive", "one_ally", 1, combat_only=False, desc="Raise a dead ally (risky)."),
    Spell("SANCT", "Sanct", "priest", 5, "buff", "party", 0, desc="Hallow the field — -4 AC."),
    Spell("JUDGE", "Judge", "priest", 5, "damage", "all_enemy", 30, "holy", desc="Divine judgment on all."),
    # Priest L6
    Spell("REVIVE", "Revive", "priest", 6, "revive", "one_ally", 10, combat_only=False, desc="Safer raise."),
    Spell("BIGWARD", "Bigward", "priest", 6, "buff", "party", 0, desc="Heavy ward — large AC drop."),
    Spell("SMITE", "Smite", "priest", 6, "damage", "one_enemy", 70, "holy", desc="Single-target holy wrath."),
    # Priest L7
    Spell("RESURR", "Resurr", "priest", 7, "revive", "one_ally", 999, combat_only=False, desc="True resurrection."),
    Spell("HOLY", "Holy", "priest", 7, "damage", "all_enemy", 80, "holy", desc="Annihilate evil."),
    Spell("WRATH", "Wrath", "priest", 7, "damage", "all_enemy", 90, "", desc="Raw divine wrath."),
]

SPELLS: dict[str, Spell] = {s.id: s for s in SPELL_LIST}


def spells_for(school: str, level: int) -> list[Spell]:
    return [s for s in SPELL_LIST if s.school == school and s.level == level]


# Slot progression.  Lookups: slots_for_school(class_level, school) → list[7].
# Curves: a pure caster gets faster slot growth; hybrids slower.
_MAGE_FULL = [
    [0, 0, 0, 0, 0, 0, 0],
    [2, 0, 0, 0, 0, 0, 0],     # lvl 1
    [3, 1, 0, 0, 0, 0, 0],
    [3, 2, 1, 0, 0, 0, 0],
    [4, 2, 2, 1, 0, 0, 0],
    [4, 3, 2, 2, 1, 0, 0],     # lvl 5
    [5, 3, 3, 2, 2, 1, 0],
    [5, 4, 3, 3, 2, 2, 1],
    [6, 4, 4, 3, 3, 2, 2],
    [6, 5, 4, 4, 3, 3, 2],
    [7, 5, 5, 4, 4, 3, 3],     # lvl 10
]

_PRIEST_FULL = _MAGE_FULL   # same curve

_BISHOP_MAGE = [
    [0] * 7,
    [1, 0, 0, 0, 0, 0, 0],
    [2, 1, 0, 0, 0, 0, 0],
    [2, 1, 1, 0, 0, 0, 0],
    [3, 2, 1, 1, 0, 0, 0],
    [3, 2, 2, 1, 1, 0, 0],
    [4, 3, 2, 2, 1, 1, 0],
    [4, 3, 3, 2, 2, 1, 1],
    [5, 4, 3, 3, 2, 2, 1],
    [5, 4, 4, 3, 3, 2, 2],
    [6, 5, 4, 4, 3, 3, 2],
]

_BISHOP_PRIEST_OFFSET = 3   # starts at class level 4

_SAMURAI_MAGE_OFFSET = 3   # starts at class level 4

_LORD_PRIEST_OFFSET = 3   # starts at class level 4


def _curve_at(curve: list[list[int]], idx: int) -> list[int]:
    if idx < 0:
        return [0] * 7
    if idx >= len(curve):
        return list(curve[-1])
    return list(curve[idx])


def slots_for_school(class_key: str, class_level: int, school: str) -> list[int]:
    cls = CLASSES[class_key]
    if school == "mage":
        if not cls.can_cast_mage:
            return [0] * 7
        if class_key == "B":
            slots = _curve_at(_BISHOP_MAGE, class_level)
        elif class_key == "S":
            slots = _curve_at(_BISHOP_MAGE, class_level - _SAMURAI_MAGE_OFFSET)
        else:
            slots = _curve_at(_MAGE_FULL, class_level)
        # cap at mage_cap_level
        for i in range(cls.mage_cap_level, 7):
            slots[i] = 0
        return slots
    if school == "priest":
        if not cls.can_cast_priest:
            return [0] * 7
        if class_key == "B":
            slots = _curve_at(_BISHOP_MAGE, class_level - _BISHOP_PRIEST_OFFSET)
        elif class_key == "L":
            slots = _curve_at(_BISHOP_MAGE, class_level - _LORD_PRIEST_OFFSET)
        else:
            slots = _curve_at(_PRIEST_FULL, class_level)
        for i in range(cls.priest_cap_level, 7):
            slots[i] = 0
        return slots
    return [0] * 7


# ---- monsters -----------------------------------------------------------

@dataclass(eq=False)
class MonsterDef:
    id: str
    name: str
    plural: str
    hp_min: int
    hp_max: int
    ac: int
    hit: int         # to-hit bonus
    dmg_min: int
    dmg_max: int
    swings: int = 1
    agi: int = 4
    xp: int = 10
    gold_min: int = 0
    gold_max: int = 0
    spells: tuple[str, ...] = ()
    spell_chance: int = 0   # percent per turn
    traits: tuple[str, ...] = ()
    art: str = "%"          # single-glyph token for combat banner
    desc: str = ""


MONSTERS_LIST: list[MonsterDef] = [
    MonsterDef("kobold", "Kobold", "Kobolds", 3, 6, 10, 2, 1, 3, 1, 5, 4, 1, 6,
               art="k", desc="Scrawny dog-faced scavenger."),
    MonsterDef("orc", "Orc", "Orcs", 5, 10, 9, 3, 2, 5, 1, 5, 8, 3, 12,
               art="o", desc="Tusked raider with a crude axe."),
    MonsterDef("zombie", "Zombie", "Zombies", 8, 14, 9, 3, 2, 6, 1, 3, 10, 2, 8,
               traits=("undead",), art="z", desc="Shambling corpse. Slow but sturdy."),
    MonsterDef("creep_coin", "Creeping Coin", "Creeping Coins", 4, 8, 7, 2, 1, 4, 1, 6, 18, 30, 60,
               art="$", desc="Animate gold pile. Striking it yields silver."),
    MonsterDef("wererat", "Wererat", "Wererats", 10, 18, 7, 5, 3, 7, 1, 7, 20, 0, 10,
               art="r", desc="Plague-bearing beast that walks on two feet."),
    MonsterDef("bushi", "Bushi", "Bushi", 14, 22, 6, 6, 3, 9, 1, 8, 28, 5, 18,
               art="B", desc="Disciplined sword-warrior."),
    MonsterDef("gas_cloud", "Gas Cloud", "Gas Clouds", 12, 20, 5, 5, 2, 5, 2, 6, 32, 0, 0,
               traits=("poison",), art="~", desc="Hissing green vapor."),
    MonsterDef("echo_wraith", "Echo Wraith", "Echo Wraiths", 15, 25, 4, 7, 3, 8, 1, 7, 48, 0, 0,
               traits=("undead", "ethereal"), spells=("STATIC",), spell_chance=30,
               art="W", desc="Mirror of a fallen adventurer."),
    MonsterDef("chant_priest", "Dark Chanter", "Dark Chanters", 18, 26, 5, 6, 2, 6, 1, 8, 42, 10, 30,
               spells=("CINDR",), spell_chance=45, art="&",
               desc="Robed cleric, mouth sewn in prayer."),
    MonsterDef("lesser_lich", "Lesser Lich", "Lesser Liches", 40, 60, 2, 9, 5, 14, 1, 10, 180, 50, 120,
               traits=("undead",), spells=("BOLT", "STATIC"), spell_chance=60, art="L",
               desc="Robed skeleton wrapped in cold fire.  Floor-3 boss-class."),
    MonsterDef("andrew_shade", "Shade of Andrew", "Shades", 120, 160, -2, 12, 8, 20, 2, 14, 800, 200, 500,
               traits=("undead", "boss"), spells=("BOLT", "HAVOC"), spell_chance=75, art="@",
               desc="A hollow echo of Andrew the Unmade.  Not the man — "
                    "yet.  This is what guards the way down."),
]

MONSTERS: dict[str, MonsterDef] = {m.id: m for m in MONSTERS_LIST}


# Per-floor encounter tables.  Each entry: (monster_id, weight, min_count, max_count)
ENCOUNTER_TABLES: dict[str, list[tuple[str, int, int, int]]] = {
    "B1": [
        ("kobold", 40, 2, 5),
        ("orc", 25, 1, 3),
        ("zombie", 15, 1, 3),
        ("creep_coin", 10, 1, 2),
        ("wererat", 10, 1, 2),
    ],
    "B2": [
        ("orc", 25, 2, 4),
        ("zombie", 20, 2, 4),
        ("wererat", 20, 1, 3),
        ("gas_cloud", 15, 1, 2),
        ("bushi", 10, 1, 2),
        ("chant_priest", 10, 1, 2),
    ],
    "B3": [
        ("bushi", 25, 2, 3),
        ("echo_wraith", 20, 1, 3),
        ("chant_priest", 15, 1, 2),
        ("gas_cloud", 15, 1, 3),
        ("lesser_lich", 10, 1, 1),
        ("zombie", 15, 3, 6),
    ],
}


# ---- items --------------------------------------------------------------

@dataclass(eq=False)
class Item:
    id: str
    name: str
    kind: str           # "weapon" | "armor" | "shield" | "helm" | "consumable"
    tags: tuple[str, ...] = ()
    power: int = 0
    hit: int = 0
    dmg_die: int = 4    # for weapons: 1d(dmg_die) + power
    price: int = 10
    cursed: bool = False
    desc: str = ""


ITEMS_LIST: list[Item] = [
    # Weapons
    Item("short_sword", "Short Sword", "weapon", ("sword",), 1, 2, 6, 25),
    Item("long_sword", "Long Sword", "weapon", ("sword",), 2, 3, 8, 110),
    Item("dagger", "Dagger", "weapon", ("dagger",), 0, 2, 4, 15),
    Item("staff", "Staff", "weapon", ("staff",), 0, 2, 6, 20),
    Item("mace", "Mace", "weapon", ("mace",), 1, 2, 6, 30),
    Item("hand_axe", "Hand Axe", "weapon", ("axe",), 1, 1, 8, 35),
    Item("war_axe", "War Axe", "weapon", ("axe",), 3, 3, 10, 180),
    Item("short_bow", "Short Bow", "weapon", ("bow",), 1, 2, 6, 40),
    # Armor
    Item("robe", "Cloth Robe", "armor", ("cloth",), 1, price=15),
    Item("leather", "Leather Cuirass", "armor", ("light",), 2, price=40),
    Item("chain", "Chain Mail", "armor", ("heavy",), 3, price=120),
    Item("plate", "Plate Mail", "armor", ("heavy",), 5, price=450),
    Item("cloak", "Shadowed Cloak", "armor", ("cloak",), 2, price=75),
    # Shields
    Item("buckler", "Buckler", "shield", ("shield",), 1, price=35),
    Item("kite", "Kite Shield", "shield", ("shield",), 2, price=120),
    # Helms
    Item("cap", "Leather Cap", "helm", ("helm", "light"), 1, price=20),
    Item("helm", "Iron Helm", "helm", ("helm",), 2, price=70),
    # Consumables
    Item("potion", "Healing Draught", "consumable", (), 20, price=40,
         desc="Restores ~20 HP."),
    Item("antidote", "Antidote", "consumable", (), 0, price=25,
         desc="Cures poison."),
    Item("ration", "Ration", "consumable", (), 0, price=5),
    Item("ash_scroll", "Scroll of Ashes", "consumable", (), 0, price=200,
         desc="Incinerate one enemy group."),
]

ITEMS: dict[str, Item] = {it.id: it for it in ITEMS_LIST}


STARTER_WEAPONS = {
    "F": "short_sword", "M": "staff", "P": "mace", "T": "dagger",
    "B": "staff", "S": "short_sword", "L": "mace", "N": "dagger",
}

STARTER_ARMOR = {
    "F": "leather", "M": "robe", "P": "leather", "T": "leather",
    "B": "robe", "S": "leather", "L": "chain", "N": "cloak",
}


# ---- shop stock per town ---
SHOP_STOCK = [
    "short_sword", "long_sword", "dagger", "staff", "mace", "hand_axe",
    "war_axe", "short_bow",
    "robe", "leather", "chain", "plate", "cloak",
    "buckler", "kite", "cap", "helm",
    "potion", "antidote", "ration",
]


# ---- Inn rest tiers ---
INN_TIERS = [
    # (name, gold, hp_per_day, full_slot_refill, days)
    ("Stables", 0, 0, False, 1),
    ("Bronze Cot", 10, 1, False, 7),
    ("Silver Cot", 50, 3, False, 3),
    ("Gold Cot", 200, 7, True, 1),
    ("Royal Suite", 500, 999, True, 1),
]


# ---- XP curve ---
def xp_to_next(class_level: int) -> int:
    """XP required to reach (class_level + 1)."""
    return max(1000, int(1000 * (class_level ** 1.8)))
