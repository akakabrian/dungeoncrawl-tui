# dungeoncrawl-tui — design decisions

## 0. Licensing — clean-room, Sir-Tech / Drinian IP

Wizardry: Proving Grounds of the Mad Overlord (Sir-Tech, Apple II, 1981,
designers Andrew Greenberg & Robert Woodhead) is **not open source**.
The series IP passed through Sir-Tech → 1259190 Ontario Inc. → Aeria →
Drinian Studios; the "Wizardry" brand today is controlled by Drinian
(WizardryGold and related). An official remaster shipped in 2024.

This project is a **clean-room reimplementation** from publicly
available design documentation: GameFAQs mechanics guides, retrospectives,
the Data-Driven Gamer breakdown, the CRPG Addict write-ups, and general
knowledge of the roguelike/crawler genre. **No Sir-Tech assets, no
decompiled binary data, no sprite rips.** All text, names, monster
tables, and level layouts are original prose inspired by the public
mechanical description.

Same clean-room approach used across the sibling TUI batch
(`~/AI/projects/tui-games/`): ff1-tui (FF1 mechanics, original
strings), dragon-quest-tui (DQ1 mechanics, renamed), crimson-fields-tui
(Advance Wars-style), julius-tui (Caesar III-style). Rules are mechanics,
mechanics aren't copyrightable; specific expression (monster names,
spell names, level text) is ours.

**Name swaps from the original game:**

- Title: "Proving Grounds of the Mad Overlord" → "The Mad Overlord's
  Deep" (our subtitle). Keep "wizardry" lowercase as a genre word.
- Werdna (the villain wizard) → **Andrew the Unmade** (generic
  fallen-mage villain; name nods the designer the same way Werdna did
  but is distinct prose).
- Trebor (the Mad Overlord) → **King Robart the Unraveled**.
- Spells: Wizardry used 6-letter Mage/Priest names (HALITO, KATINO,
  DIOS, MOGREF etc.) pseudo-drawn from Hebrew/Latin roots. We use
  **original 4-6 letter names** in the same sound-family: CINDR,
  QUELL, MEND, WARD, BOLT, HAVOC, BURST, LIGHT, RAISE, DISPL, etc.
  The Wizardry *system* (Mage + Priest, 7 spell levels, slot pools
  per level) is the copyrightable-adjacent part but the level/slot
  count is a pure mechanic; the exact names are where we deviate.
- Monster names: generic fantasy nouns (Kobold, Orc, Wererat,
  Creeping Coin, Gas Dragon, Bishop, Lich). Where a name would be
  too Sir-Tech-specific we shift (Murphy's Ghosts → "Murphys" →
  **"Echo Wraiths"**).
- Town shops: Boltac's → **Bolt & Sons**. Temple of Cant → **Temple
  of Cant** (generic Catholic-adjacent monastic name, not unique to
  Sir-Tech). Adventurer's Inn → **Vagrant's Rest**. Training Grounds
  → **Training Grounds** (generic). Gilgamesh's Tavern → **The Lion
  & Lantern**. Castle → **King's Keep**.

## 1. Engine strategy: pure-Python sim

Open-source Wizardry reimplementations exist (wizardry-lazarus, a handful
of "WizFree" ports, browser-based clones), but **they all redistribute
copyrighted Sir-Tech assets** (monster names, spell names, level text).
Vendoring any of them triggers the same IP problem we're avoiding.

**Decision:** pure-Python sim, no vendored engine, no SWIG. Wizardry
mechanics are small — single-digit-thousands of lines to reimplement
faithfully. Sibling projects (ff1-tui, dragon-quest-tui, crimson-fields-
tui) took the same path.

## 2. The signature view: ASCII wireframe first-person

This is Wizardry's iconic look and the #1 design-risk of the project. The
original Apple II rendered a 3-depth vector wireframe of corridors with
doors/walls visible ahead. We reproduce it using **Unicode box-drawing
characters** in a fixed ~40×15-column ASCII art frame:

```
╔══════════════════════════╗
║╲                        ╱║
║ ╲ ╔══════════════════╗ ╱ ║
║  ╲║╲                ╱║╱  ║
║   ║ ╔════════════╗   ║   ║
║   ║ ║            ║   ║   ║
║   ║ ╚════════════╝   ║   ║
║  ╱║╱                ╲║╲  ║
║ ╱ ╚══════════════════╝ ╲ ║
║╱                        ╲║
╚══════════════════════════╝
```

Depth rings at ~3 tiles ahead; left/right branches sketched when a door
or opening exists. We **do not** try to render an open room interior;
only the corridor template + overlays for door / wall / dead-end /
stairs-up / stairs-down / opening.

Implementation: pre-rendered ASCII-art "slots" per (depth, side,
feature) plus an overlay compositor. Details in `render3d.py`.

## 3. Scope: vertical slice, 3 of 10 floors

The original shipped 10 dungeon floors culminating in Andrew's lair on
B10. We ship **floors B1, B2, B3** as a vertical slice — same mechanical
vocabulary (doors, stairs, one-way doors, spinners, chutes, dark areas)
but only three floors of content. This keeps the build in the skill's
12-16h window while still demonstrating the iconic features.

## 4. Party: 6 characters, 8 classes (with alignment+stat gates)

- Fighter, Mage, Priest, Thief — basic four, no gate.
- Bishop — cast both Mage & Priest spells; needs IQ 12, PIE 12.
- Samurai — fighter+mage hybrid; needs STR 15, IQ 11, PIE 10, VIT 14,
  AGI 10; Good or Neutral alignment.
- Lord — fighter+priest hybrid; needs STR 15, IQ 12, PIE 12, VIT 15,
  AGI 14, LUC 15; Good alignment only.
- Ninja — all stats ≥ 17; Evil alignment only.

Stat generation: 8+3d5 bonus roll distributed across STR/IQ/PIE/VIT/AGI/
LUC per classic Wizardry. Bonus occasionally spikes to 10-19 (Wizardry's
famous "bonus roll" where you reroll for a shot at the elite classes).

Alignment: Good / Neutral / Evil — gates certain classes; party of mixed
Good/Evil ok but Good+Evil together has tavern restrictions (we drop
this rule for v1 simplicity — Evil characters can party with Good).

Race: Human / Elf / Dwarf / Gnome / Hobbit — stat modifiers (Elf +IQ/PIE,
Dwarf +STR/VIT, etc.).

## 5. Stats

**Core 6:** STR / IQ / PIE / VIT / AGI / LUC (3-18 base, bonus can go
higher). Derived:

- HP: class HP-die per level; Fighter d10, Priest d8, Mage d4, etc.
- AC: base 10 − armor (lower = better). Classic D&D-style.
- Mage MP: slots per level 1..7, grows with class level.
- Priest MP: slots per level 1..7, grows with class level.
- Bishop learns both tracks but slower.
- Samurai gets Mage track at class level 4. Lord gets Priest at class
  level 4. Ninja never learns spells (but high base AC from no armor).

## 6. Spells: Mage + Priest, 7 levels each, slot pools

Wizardry's distinctive spell system preserved faithfully:

- 7 spell **levels** (not player levels — spell levels 1-7).
- Each caster tracks **slots per spell level** (e.g. a L5 Mage might
  have slots = `[4, 3, 2, 1, 0, 0, 0]`).
- Slots regenerate on Inn rest (tiered inn — expensive inn heals more
  per day).
- Learning: classes get 1-2 new spells per class-level, per school
  they have access to, until their max (9 per level per school in
  the original; we cap at 3 for a cleaner UI — Wizardry accurate, but
  modernised).

**Our spell list (all original names):**

Mage levels 1-7 (3 per level):
- L1: CINDR (fire), SHIELD, SNOOZE
- L2: STATIC, VANISH, QUELL
- L3: BOLT, BURST, MAZE
- L4: INFER, FROST, BLINK
- L5: HAVOC, FEAR, DEPORT
- L6: LANCE, SEAL, VANISHX
- L7: UNMAKE, DRAIN, VOID

Priest levels 1-7 (3 per level):
- L1: MEND, WARD, LIGHT
- L2: CURE, BLESS, SILENCE
- L3: REMOVE, FIND, PRAY
- L4: HEAL, PURGE, DIVINE
- L5: RAISE, SANCT, JUDGE
- L6: REVIVE, SHIELD2, SMITE
- L7: RESURRECT, HOLY, WRATH

(Spells are populated with effect/power/target/element in `data.py`.
The UI shows them as 5-letter uppercase tags in combat.)

## 7. Dungeon tiles & features

Each floor is a 20×20 grid. Tile types:

- **Floor** (walkable)
- **Wall** (impassable)
- **Door** (walkable; some "secret doors" appear as wall until bumped)
- **One-way door** (walkable in one direction; party gets trapped
  briefly — classic)
- **Stairs up / down**
- **Chute** (step on → fall to next floor, often a random room)
- **Spinner** (step on → facing randomised)
- **Dark area** (doesn't change tile; flags the rendering module to
  dim the wireframe and print "darkness" in the log)
- **Teleport trap** (random destination on same floor)
- **Encounter marker** (fixed encounter; stat-gated monster)

Floor generation: hand-authored from compact text grids in `maps.py`.
Not procedural. Three floors: B1 "Dungeon proper" (classic 4-corridor
grid), B2 "Damp Hall" (dark areas, chute), B3 "Andrew's Door" (boss
encounter).

## 8. Combat: turn-based, 6-vs-4-groups-of-up-to-9

Original Wizardry combat surface:

- Up to 4 enemy groups. Each group has 1-9 identical creatures
  (e.g. "5 Kobolds, 3 Orcs, 1 Priest").
- Party action selection: per living member, pick {Fight / Parry /
  Spell / Use / Run}. Front row (slots 0-2) can Fight enemies in
  range; back row (slots 3-5) can't Fight but can Spell/Use.
- After all selections, resolve in initiative order (AGI + d5
  jitter, all combatants mixed).
- Fight: roll to-hit vs enemy AC, roll damage on weapon dice.
  Multiple swings per turn at high level.
- Spell: costs 1 slot of spell-level. Many targeting modes:
  one enemy, one group, all enemies, one ally, all allies.
- Parry: reduce damage taken by 1 class of AC for the round.
- Run: AGI check against enemy group. Failure wastes the round.
- Enemy AI: random target in reachable row, plus chance to cast
  spells drawn from its list.

Preserving the iconic Wizardry quirk: **if your target dies before
your attack resolves, the attack is wasted** (same as FF1).

## 9. Death — the classic punishment

When a character's HP hits 0:

- **Dead:** can be raised at the Temple for gold cost (fail chance
  based on VIT; fail → "ASHES"). Characters in the dungeon don't
  disappear — the body stays in the dungeon tile when a *whole party*
  dies; **rescuing a dead party** is one of the game's iconic loops.
- **Ashes:** Temple can attempt (riskier; fail → "LOST"). Costs more.
- **Lost:** permadead. Character gone.

For v1 we implement Dead + Temple Raise; Ashes + Rescue-party loop are
stubbed. Wipe = "return to town with survivors only, dead go into
cold storage at the temple." Full clean-room rescue mission would
require multi-party save state; v1 handwaves this (dead party members
are automatically recovered on wipe, costing gold at Temple).

## 10. Castle town (screens, not overworld)

Unlike FF1 / DQ, Wizardry has **no overworld**. The castle is a menu,
not a map. Each building is a modal screen:

- **Training Grounds** — roster management, create/edit/delete
  characters, review stats.
- **The Lion & Lantern** (tavern) — assemble the active party (up to
  6) from the roster.
- **Vagrant's Rest** (inn) — rest at tiered prices (stables = free,
  no-HP; bronze = heal 1 HP/day; silver = 3; gold = 7; suite = full +
  spell slots). Each stay advances age; aging matters in the original
  (stat drain at high age). We track age but stat drain is deferred
  to v2.
- **Temple of Cant** — raise the dead, cure poison, cure paralysis.
- **Bolt & Sons** (shop) — buy/sell/identify/uncurse. Identify gates
  cursed items (Thief and Bishop have a chance to "insp" without
  paying).
- **King's Keep** (castle entrance) — descend to dungeon B1.

Castle is the default "home screen" — the main app shows the castle
menu as its dashboard; "Enter Dungeon" switches to the first-person
view.

## 11. Save / load

- JSON save at `~/.dungeoncrawl_tui_save.json`. Single slot in v1.
- Snapshots: roster (all characters), active party, inventory, gold,
  current map/floor/position/facing, story flags, RNG state.

## 12. UI layout

Two modes:

**Castle mode (default):**

```
+-------------------------------+----------------------+
|                               |  ROSTER              |
|       CASTLE MENU             |   6 characters       |
|  - Training Grounds           |   current party      |
|  - Tavern                     |   highlighted        |
|  - Inn                        |                      |
|  - Temple                     |  GOLD / POOL         |
|  - Shop                       |                      |
|  - Dungeon ↓                  |  KEYS / HINTS        |
|                               |                      |
+-------------------------------+----------------------+
| LOG (archaic tone, history)                          |
+------------------------------------------------------+
```

**Dungeon mode:**

```
+-------------------------------+----------------------+
|                               | PARTY                |
|   [ wireframe view ]          |   6 HP bars          |
|                               |   status flags       |
|   ~40x15 ASCII art            |                      |
|                               | POSITION             |
|                               |   floor / x,y / dir  |
|   (minimap bottom-left 7x7)   |                      |
|                               | KEYS                 |
+-------------------------------+----------------------+
| LOG                                                  |
+------------------------------------------------------+
```

## 13. Key bindings

Following skill convention (priority=True on movement):

| key                | dungeon action            | castle action       |
|--------------------|---------------------------|---------------------|
| w / up             | step forward              | menu ↑              |
| s / down           | step back                 | menu ↓              |
| a / left           | turn left                 | (unused)            |
| d / right          | turn right                | (unused)            |
| space / enter      | interact (door, stairs)   | select menu item    |
| m                  | open menu                 | (unused)            |
| escape             | back / close              | back                |
| F2                 | save                      | save                |
| F3                 | load                      | load                |
| ?                  | help                      | help                |
| q                  | quit (confirm)            | quit                |

## 14. Out of scope for MVP (v1)

- Ashes & Lost status.
- Rescue-party (bring a second party to retrieve corpses).
- Age-based stat drain.
- Identification in dungeon.
- Class change.
- 10-floor progression (we ship 3).
- Andrew the Unmade (boss; v1 ships a minor boss on B3 as
  demonstration).
- Sound / music.
- LLM advisor.
- Agent REST API — solo single-seat RPG, low agent value.

## 15. Directory layout

```
dungeoncrawl-tui/
├── wiz.py                        # argparse entry point
├── pyproject.toml
├── Makefile
├── DECISIONS.md                  # this file
├── README.md
└── dungeoncrawl_tui/
    ├── __init__.py
    ├── sim.py                    # character, party, dungeon, combat
    ├── data.py                   # classes, spells, monsters, items
    ├── maps.py                   # 3 floor layouts
    ├── render3d.py               # ASCII wireframe composer
    ├── tiles.py                  # tile id constants + glyph lookups
    ├── app.py                    # Textual App + Castle / DungeonView
    ├── screens.py                # modal screens (Training, Shop, Inn,
    │                             #   Temple, Tavern, Combat, Title,
    │                             #   CharCreate, Help, Legend)
    └── tui.tcss
└── tests/
    ├── __init__.py
    ├── qa.py                     # Pilot scenarios
    └── perf.py                   # render + combat benchmarks
```
