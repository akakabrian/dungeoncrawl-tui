"""End-to-end Pilot playtest — boot, party, descend, encounter, combat, quit.

    python -m tests.playtest

A single scripted session exercising the full game loop through the
Textual Pilot, using only real key presses + state assertions.  Saves
screenshots for each major beat under tests/out/playtest-*.svg.
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from wizardry_tui import data as D
from wizardry_tui import sim as S
from wizardry_tui import tiles as T
from wizardry_tui.app import WizApp


OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)


def _build_party(sim: S.Sim) -> None:
    rng = sim.rng
    classes = ["F", "F", "T", "P", "M", "B"]
    races = ["H", "D", "B", "G", "E", "H"]
    aligns = ["G", "N", "N", "G", "G", "N"]
    names = ["Agni", "Brom", "Cael", "Dior", "Elen", "Finn"]
    for nm, race, align, ck in zip(names, races, aligns, classes):
        stats, bonus = S._roll_stats(rng, D.RACES[race].mods)
        if ck == "B":
            stats["IQ"] = max(stats["IQ"], 12)
            stats["PIE"] = max(stats["PIE"], 12)
        final = S.auto_assign_bonus(stats, bonus, ck)
        ch = S.make_character(nm, race, align, ck, final, rng)
        sim.add_to_roster(ch)
    sim.set_party([0, 1, 2, 3, 4, 5])


async def _snap(app: WizApp, name: str) -> None:
    try:
        app.save_screenshot(str(OUT / f"playtest-{name}.svg"))
    except Exception:
        pass


async def _run(pilot) -> None:
    app: WizApp = pilot.app   # type: ignore[assignment]

    # Beat 1: boot — title screen should be up (start_with_title=True).
    await pilot.pause()
    assert app.screen.__class__.__name__ == "TitleScreen", \
        f"expected TitleScreen, got {app.screen.__class__.__name__}"
    await _snap(app, "01-title")

    # Dismiss title with escape (we seed the sim below programmatically
    # rather than exercising the char-create flow, which is covered by
    # the QA harness).
    await pilot.press("escape")
    await pilot.pause()
    assert app.screen.__class__.__name__ != "TitleScreen"
    await _snap(app, "02-castle")

    # Beat 2: populate roster + party (headless — faster than typing).
    # Use a fixed-seed sim so encounter rolls during movement are
    # deterministic and the scripted flow is stable.
    app.sim = S.Sim.new_game(seed=2026)
    _build_party(app.sim)
    app._rebind_panels()
    app.refresh_panels()
    await pilot.pause()
    assert len(app.sim.roster) == 6
    assert app.sim.party_active()
    await _snap(app, "03-party-ready")

    # Beat 3: open help, close help.
    await pilot.press("question_mark")
    await pilot.pause()
    assert app.screen.__class__.__name__ == "HelpScreen"
    await pilot.press("escape")
    await pilot.pause()
    assert app.screen.__class__.__name__ != "HelpScreen"

    # Beat 4: descend into B1.
    await pilot.press("6")
    await pilot.pause()
    assert app.sim.in_dungeon, "descend did not enter dungeon"
    assert app.sim.floor_key == "B1"
    await _snap(app, "04-dungeon-b1")

    # Beat 5: move around — turn, step forward a few times.  If a random
    # encounter fires, dismiss the CombatScreen by resolving it (covered
    # in beat 7); here we just make sure movement happens and no crash.
    async def _dismiss_any_combat() -> None:
        if app.screen.__class__.__name__ == "CombatScreen":
            # Just bail on this combat by running — quickest path back.
            for _ in range(6):
                await pilot.press("r")
                await pilot.pause()
            for _ in range(10):
                if app.screen.__class__.__name__ != "CombatScreen":
                    break
                await pilot.press("space")
                await pilot.pause()

    await pilot.press("d")  # turn right
    await pilot.pause()
    await _dismiss_any_combat()
    for _ in range(5):
        await pilot.press("w")
        await pilot.pause()
        await _dismiss_any_combat()
    # Also step back once to exercise step_back.
    await pilot.press("s")
    await pilot.pause()
    await _dismiss_any_combat()
    assert app.sim.steps >= 1, "no movement recorded"
    await _snap(app, "05-moved")

    # Beat 6: party status screen (only if not in some other modal).
    if app.sim.in_dungeon and app.screen.__class__.__name__ not in (
        "PartyStatusScreen", "CombatScreen",
    ):
        await pilot.press("m")
        await pilot.pause()
        if app.screen.__class__.__name__ == "PartyStatusScreen":
            await pilot.press("escape")
            await pilot.pause()

    # Beat 7: encounter + combat round.  Ensure no modal is up, then
    # force a combat encounter.  This exercises the same code path the
    # random encounter trigger uses.
    while app.screen.__class__.__name__ != "Screen":
        await pilot.press("escape")
        await pilot.pause()
        if app.screen.__class__.__name__ == "CombatScreen":
            # Flee-spam to clear it.
            for _ in range(6):
                await pilot.press("r")
                await pilot.pause()
            for _ in range(10):
                if app.screen.__class__.__name__ != "CombatScreen":
                    break
                await pilot.press("space")
                await pilot.pause()

    from wizardry_tui import screens as SC
    groups = [
        S.MonsterGroup("kobold", [
            S.MonsterInstance("kobold", 4, 4),
            S.MonsterInstance("kobold", 4, 4),
            S.MonsterInstance("kobold", 4, 4),
        ]),
    ]
    combat = S.Combat(app.sim, groups)
    result_holder: dict[str, object] = {}

    def _done(r):
        result_holder["r"] = r

    app.push_screen(SC.CombatScreen(combat, _done))
    await pilot.pause()
    assert app.screen.__class__.__name__ == "CombatScreen"
    await _snap(app, "06-combat-start")

    # Queue fight for all 6, then resolve repeatedly until done.
    for _round in range(20):
        if app.screen.__class__.__name__ != "CombatScreen":
            break
        # Press 'f' six times (one per slot).  Back-rank slots auto-target
        # group 0, so 'f' alone suffices for them; front slots prompt for
        # a target when multiple groups exist — we only have 1 group, so
        # 'f' resolves immediately there too.
        for _ in range(6):
            await pilot.press("f")
            await pilot.pause()
        # Resolve round.
        await pilot.press("space")
        await pilot.pause()

    # By now combat should have ended — either win or loss.
    assert "r" in result_holder, "combat did not complete within 20 rounds"
    outcome = result_holder["r"].outcome   # type: ignore[attr-defined]
    assert outcome in ("win", "loss", "flee"), f"unexpected outcome: {outcome}"
    await _snap(app, "07-combat-done")

    # Beat 8: return to castle via escape (debug convenience).
    if app.sim.in_dungeon:
        await pilot.press("escape")
        await pilot.pause()
    assert not app.sim.in_dungeon
    await _snap(app, "08-back-in-castle")

    # Beat 9: quit.
    await pilot.press("q")
    await pilot.pause()


async def main_async() -> int:
    app = WizApp(start_with_title=True)
    try:
        async with app.run_test(size=(180, 60)) as pilot:
            try:
                await _run(pilot)
                print("  PASS  playtest — boot → party → descend → combat → quit")
                return 0
            except AssertionError as e:
                await _snap(app, "FAIL")
                print(f"  FAIL  playtest — {e}")
                traceback.print_exc()
                return 1
            except Exception:
                await _snap(app, "FAIL")
                print("  FAIL  playtest — unhandled exception")
                traceback.print_exc()
                return 1
    except Exception as e:
        print(f"  FAIL  harness crash: {e}")
        traceback.print_exc()
        return 2


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
