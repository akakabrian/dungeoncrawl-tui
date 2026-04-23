"""Performance benchmarks for hot paths.

    python -m tests.perf
"""
from __future__ import annotations

import random
import time

from wizardry_tui import data as D
from wizardry_tui import maps as M
from wizardry_tui import render3d as R3
from wizardry_tui import sim as S
from wizardry_tui import tiles as T


def _bench(label: str, fn, iters: int = 1000) -> None:
    # Warm.
    for _ in range(min(50, iters)):
        fn()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    t1 = time.perf_counter()
    per_ms = (t1 - t0) * 1000 / iters
    total_ms = (t1 - t0) * 1000
    print(f"  {label:<40} {per_ms:7.3f} ms/call   total {total_ms:8.1f} ms  (n={iters})")


def bench_wireframe_render() -> None:
    grid, start, facing = M.build_floor("B1")
    px, py = start

    def fn() -> None:
        R3.render_wireframe(grid, px, py, facing)

    _bench("wireframe render_wireframe (B1 start)", fn, iters=5000)


def bench_minimap() -> None:
    grid, start, facing = M.build_floor("B1")
    px, py = start

    def fn() -> None:
        R3.render_minimap(grid, px, py, facing, radius=3)

    _bench("minimap (r=3)", fn, iters=20000)


def bench_build_floor() -> None:
    def fn() -> None:
        M.build_floor("B2")

    _bench("build_floor B2", fn, iters=1000)


def bench_encounter_roll() -> None:
    rng = random.Random(1)

    def fn() -> None:
        S.roll_encounter(rng, "B1")

    _bench("roll_encounter B1", fn, iters=20000)


def bench_combat_round() -> None:
    sim = S.Sim.new_game(seed=7)
    rng = sim.rng
    for i in range(6):
        stats, bonus = S._roll_stats(rng, {})
        final = S.auto_assign_bonus(stats, bonus, "F")
        ch = S.make_character(f"F{i}", "H", "G", "F", final, rng)
        sim.add_to_roster(ch)
    sim.set_party([0, 1, 2, 3, 4, 5])

    def fn() -> None:
        groups = [S.MonsterGroup("kobold",
                                  [S.MonsterInstance("kobold", 5, 5) for _ in range(4)])]
        combat = S.Combat(sim, groups)
        actions = [S.CombatAction(kind="fight", target_group=0) for _ in range(6)]
        combat.resolve_round(actions)  # type: ignore[arg-type]

    _bench("combat one round (4 kobolds)", fn, iters=5000)


def main() -> None:
    print("wizardry-tui perf baseline")
    bench_build_floor()
    bench_wireframe_render()
    bench_minimap()
    bench_encounter_roll()
    bench_combat_round()


if __name__ == "__main__":
    main()
