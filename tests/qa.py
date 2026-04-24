"""Headless QA harness — Pilot-driven scenarios for dungeoncrawl-tui.

    python -m tests.qa             # all scenarios
    python -m tests.qa combat      # filter by substring
"""
from __future__ import annotations

import asyncio
import random
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from dungeoncrawl_tui import data as D
from dungeoncrawl_tui import render3d as R3
from dungeoncrawl_tui import sim as S
from dungeoncrawl_tui import tiles as T
from dungeoncrawl_tui.app import WizApp


OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


@dataclass
class Scenario:
    name: str
    fn: Callable[[WizApp, object], Awaitable[None]]


# ---- helpers ----------------------------------------------------------

def _make_sim(seed: int = 42) -> S.Sim:
    """Build a sim with a valid 6-member party for testing."""
    sim = S.Sim.new_game(seed=seed)
    rng = sim.rng
    # Create 6 pre-rolled characters; dodge class eligibility by picking
    # base classes with loose requirements.
    classes = ["F", "F", "T", "M", "P", "B"]
    races = ["H", "D", "B", "E", "H", "G"]
    aligns = ["G", "N", "N", "G", "G", "N"]
    names = ["Agni", "Brom", "Cael", "Dior", "Elen", "Finn"]
    for nm, race, align, ck in zip(names, races, aligns, classes):
        stats, bonus = S._roll_stats(rng, D.RACES[race].mods)
        # Boost required stats for Bishop.
        if ck == "B":
            stats["IQ"] = max(stats["IQ"], 12)
            stats["PIE"] = max(stats["PIE"], 12)
        final = S.auto_assign_bonus(stats, bonus, ck)
        ch = S.make_character(nm, race, align, ck, final, rng)
        sim.add_to_roster(ch)
    sim.set_party([0, 1, 2, 3, 4, 5])
    return sim


async def setup_game(pilot, seed: int = 42) -> None:
    app: WizApp = pilot.app   # type: ignore
    app.sim = _make_sim(seed)
    app._rebind_panels()
    app.refresh_panels()
    await pilot.pause()


# ---- scenarios --------------------------------------------------------

async def s_mount_clean(app, pilot):
    """App mounts without exceptions; all panels exist."""
    assert app.sim is not None
    assert app.wire_view is not None
    assert app.castle_view is not None
    assert app.party_panel is not None


async def s_new_game_empty_roster(app, pilot):
    """Fresh sim has empty roster and empty party."""
    assert app.sim is not None
    assert len(app.sim.roster) == 0
    assert all(i == -1 for i in app.sim.party_slots)


async def s_character_creation_works(app, pilot):
    """Rolling stats and making a character populates the roster."""
    await setup_game(pilot)
    assert len(app.sim.roster) == 6
    ch0 = app.sim.roster[0]
    assert ch0.hp_max > 0
    assert ch0.hp > 0
    assert ch0.class_key == "F"


async def s_starter_gear_equipped(app, pilot):
    await setup_game(pilot)
    for ch in app.sim.roster:
        assert ch.weapon != "" or ch.class_key == "N", f"{ch.name} has no weapon"


async def s_party_active_returns_6(app, pilot):
    await setup_game(pilot)
    assert len(app.sim.party_active()) == 6


async def s_enter_dungeon_sets_floor(app, pilot):
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    app.refresh_panels()
    await pilot.pause()
    assert app.sim.in_dungeon
    assert app.sim.floor_key == "B1"
    assert app.sim.grid
    # Starting position should be passable (cell has PASS_BIT set).
    assert not T.is_void(app.sim.grid[app.sim.py][app.sim.px])


async def s_dungeon_movement_turn_and_step(app, pilot):
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    app.refresh_panels()
    await pilot.pause()
    start = (app.sim.px, app.sim.py, app.sim.facing)
    # Turn right, check facing rotated.
    app.sim.turn_right()
    assert app.sim.facing == (start[2] + 1) % 4
    # Try to step forward: may be blocked; just check it doesn't crash.
    moved, _, _ = app.sim.step_forward()
    # Attempt many directions; at least one should be walkable from start.
    any_moved = moved
    for _ in range(4):
        app.sim.turn_right()
        moved, _, _ = app.sim.step_forward()
        if moved:
            any_moved = True
            break
    assert any_moved, "player stuck — no walkable neighbour"


async def s_wireframe_renders_with_non_blank_chars(app, pilot):
    """Wireframe for a valid cell produces box-drawing glyphs."""
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    frame = R3.render_wireframe(app.sim.grid, app.sim.px, app.sim.py,
                                app.sim.facing)
    assert len(frame) == R3.FRAME_H
    assert all(len(row) == R3.FRAME_W for row in frame)
    joined = "".join(frame)
    # At least some box-drawing chars present.
    assert any(ch in joined for ch in "╔╗╚╝═║"), "no box-drawing chars in wireframe"


async def s_wireframe_shows_features(app, pilot):
    """Stairs-down feature tag shows up in the frame label."""
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    # Find a stairs-down tile and jump there.
    found = False
    for y, row in enumerate(app.sim.grid):
        for x, c in enumerate(row):
            if T.feature(c) == T.FEAT_STAIRS_DOWN:
                app.sim.px, app.sim.py = x, y
                found = True
                break
        if found:
            break
    assert found, "no stairs_down on B1"
    frame = R3.render_wireframe(app.sim.grid, app.sim.px, app.sim.py,
                                app.sim.facing)
    joined = "\n".join(frame)
    assert "STAIRS DOWN" in joined


async def s_encounter_produces_groups(app, pilot):
    """roll_encounter returns at least one MonsterGroup on valid floors."""
    await setup_game(pilot)
    sim = app.sim
    rng = random.Random(1)
    for _ in range(10):
        groups = S.roll_encounter(rng, "B1")
        assert len(groups) >= 1
        for g in groups:
            assert g.is_alive()
            assert len(g.members) >= 1


async def s_combat_resolves_one_round(app, pilot):
    """One combat round with all-fight actions doesn't crash and
    decrements monster HP or party HP."""
    await setup_game(pilot)
    groups = [
        S.MonsterGroup("kobold", [
            S.MonsterInstance("kobold", 5, 5),
            S.MonsterInstance("kobold", 5, 5),
        ])
    ]
    combat = S.Combat(app.sim, groups)
    actions = [S.CombatAction(kind="fight", target_group=0) for _ in range(6)]
    before_mon_hp = sum(m.hp for g in groups for m in g.members)
    before_party_hp = sum(p.hp for p in app.sim.party_active())
    combat.resolve_round(actions)  # type: ignore[arg-type]
    after_mon_hp = sum(m.hp for g in groups for m in g.members)
    after_party_hp = sum(p.hp for p in app.sim.party_active())
    assert (after_mon_hp < before_mon_hp) or (after_party_hp < before_party_hp), \
        "combat round produced no damage either side"


async def s_combat_finishes_on_monster_wipe(app, pilot):
    await setup_game(pilot)
    # Tiny encounter, fight until over.
    groups = [S.MonsterGroup("kobold", [S.MonsterInstance("kobold", 1, 1)])]
    combat = S.Combat(app.sim, groups)
    actions = [S.CombatAction(kind="fight", target_group=0) for _ in range(6)]
    combat.resolve_round(actions)  # type: ignore[arg-type]
    assert combat.is_over() == "win"
    result = combat.finish()
    assert result.outcome == "win"
    assert result.xp > 0


async def s_save_load_roundtrip(app, pilot, tmp_path=None):
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    tmp = OUT / "save-test.json"
    app.sim.save_to(tmp)
    loaded = S.Sim.load_from(tmp)
    assert len(loaded.roster) == len(app.sim.roster)
    assert loaded.floor_key == app.sim.floor_key
    assert loaded.in_dungeon == app.sim.in_dungeon
    assert loaded.party_slots == app.sim.party_slots


async def s_help_opens_and_closes(app, pilot):
    await pilot.press("question_mark")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "HelpScreen"
    await pilot.press("escape")
    await pilot.pause()
    assert app.screen.__class__.__name__ != "HelpScreen"


async def s_castle_shortcuts_open_screens(app, pilot):
    await setup_game(pilot)
    await pilot.press("1")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "TrainingGroundsScreen"
    await pilot.press("escape")
    await pilot.pause()


async def s_descend_puts_party_in_dungeon(app, pilot):
    await setup_game(pilot)
    await pilot.press("6")
    await pilot.pause()
    assert app.sim.in_dungeon
    assert app.sim.floor_key == "B1"


async def s_level_up_grants_hp(app, pilot):
    await setup_game(pilot)
    ch = app.sim.roster[0]
    before_level = ch.level
    before_hp_max = ch.hp_max
    # Grant enough XP for multiple level ups.
    ch.grant_xp(10_000, app.sim.rng)
    assert ch.level > before_level
    assert ch.hp_max > before_hp_max


async def s_spell_slots_populate_for_mage(app, pilot):
    await setup_game(pilot)
    mage = next(c for c in app.sim.roster if c.class_key == "M")
    assert mage.mage_slots_max[0] >= 1
    assert mage.mage_spells[0], "mage starts knowing L1 spells"


async def s_minimap_renders(app, pilot):
    await setup_game(pilot)
    app.sim.enter_dungeon("B1")
    mini = R3.render_minimap(app.sim.grid, app.sim.px, app.sim.py,
                             app.sim.facing, radius=3)
    assert len(mini) == 7
    assert all(len(row) == 7 for row in mini)
    # Center should be the player glyph.
    assert mini[3][3] in "@NESW"


async def s_feature_codes_decode(app, pilot):
    """Each feature-encoded cell round-trips through accessors."""
    c = T.cell(walls_mask=T.WALL_N | T.WALL_E, doors_mask=T.DOOR_S,
               feat=T.FEAT_STAIRS_DOWN)
    assert T.feature(c) == T.FEAT_STAIRS_DOWN
    assert T.has_wall(c, T.WALL_N)
    assert T.has_wall(c, T.WALL_E)
    assert T.has_door(c, T.WALL_S)
    assert not T.has_wall(c, T.WALL_W)


SCENARIOS: list[Scenario] = [
    Scenario("mount_clean", s_mount_clean),
    Scenario("new_game_empty_roster", s_new_game_empty_roster),
    Scenario("character_creation_works", s_character_creation_works),
    Scenario("starter_gear_equipped", s_starter_gear_equipped),
    Scenario("party_active_returns_6", s_party_active_returns_6),
    Scenario("enter_dungeon_sets_floor", s_enter_dungeon_sets_floor),
    Scenario("dungeon_movement_turn_and_step", s_dungeon_movement_turn_and_step),
    Scenario("wireframe_renders_with_non_blank_chars", s_wireframe_renders_with_non_blank_chars),
    Scenario("wireframe_shows_features", s_wireframe_shows_features),
    Scenario("encounter_produces_groups", s_encounter_produces_groups),
    Scenario("combat_resolves_one_round", s_combat_resolves_one_round),
    Scenario("combat_finishes_on_monster_wipe", s_combat_finishes_on_monster_wipe),
    Scenario("save_load_roundtrip", s_save_load_roundtrip),
    Scenario("help_opens_and_closes", s_help_opens_and_closes),
    Scenario("castle_shortcuts_open_screens", s_castle_shortcuts_open_screens),
    Scenario("descend_puts_party_in_dungeon", s_descend_puts_party_in_dungeon),
    Scenario("level_up_grants_hp", s_level_up_grants_hp),
    Scenario("spell_slots_populate_for_mage", s_spell_slots_populate_for_mage),
    Scenario("minimap_renders", s_minimap_renders),
    Scenario("feature_codes_decode", s_feature_codes_decode),
]


# ---- harness ----------------------------------------------------------

async def run_scenario(scn: Scenario) -> tuple[str, bool, str]:
    app = WizApp(start_with_title=False)
    try:
        async with app.run_test(size=(180, 60)) as pilot:
            await pilot.pause()
            try:
                await scn.fn(app, pilot)
                try:
                    app.save_screenshot(str(OUT / f"{scn.name}.PASS.svg"))
                except Exception:
                    pass
                return (scn.name, True, "")
            except AssertionError as e:
                try:
                    app.save_screenshot(str(OUT / f"{scn.name}.FAIL.svg"))
                except Exception:
                    pass
                return (scn.name, False, f"AssertionError: {e}")
            except Exception:
                try:
                    app.save_screenshot(str(OUT / f"{scn.name}.FAIL.svg"))
                except Exception:
                    pass
                return (scn.name, False, traceback.format_exc())
    except Exception as e:
        return (scn.name, False, f"harness crash: {e}\n{traceback.format_exc()}")


async def main_async(filter_str: str = "") -> int:
    scenarios = SCENARIOS
    if filter_str:
        scenarios = [s for s in scenarios if filter_str in s.name]
        if not scenarios:
            print(f"No scenarios matched '{filter_str}'")
            return 2
    passes = 0
    fails: list[tuple[str, str]] = []
    for scn in scenarios:
        name, ok, err = await run_scenario(scn)
        mark = "  PASS" if ok else "  FAIL"
        print(f"{mark}  {name}")
        if ok:
            passes += 1
        else:
            fails.append((name, err))
    print()
    print(f"{passes}/{len(scenarios)} passed")
    if fails:
        print()
        for name, err in fails:
            print(f"--- {name} ---")
            print(err)
    return 0 if not fails else 1


def main() -> int:
    filter_str = sys.argv[1] if len(sys.argv) > 1 else ""
    return asyncio.run(main_async(filter_str))


if __name__ == "__main__":
    sys.exit(main())
