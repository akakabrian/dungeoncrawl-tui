"""Textual app shell — wizardry-tui.

Two modes, one app:

  Castle mode  — main screen shows castle menu; modals for each building.
  Dungeon mode — ASCII wireframe first-person view + minimap + party panel.
"""
from __future__ import annotations

import sys
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, RichLog, Static

from . import data as D
from . import render3d as R3
from . import screens as SC
from . import sim as S
from . import tiles as T


SAVE_PATH = Path.home() / ".wizardry_tui_save.json"


# ---- Wireframe view ----------------------------------------------------

class WireframeView(Static):
    """First-person ASCII wireframe + minimap banner below."""

    def __init__(self, sim: S.Sim) -> None:
        super().__init__()
        self.sim = sim
        self.border_title = "DUNGEON"

    def refresh_view(self) -> None:
        if not self.sim.in_dungeon or not self.sim.grid:
            self.update(Text("(castle)\n\nChoose a building and descend when ready."))
            return
        light = self.sim.active_party_light_turns > 0
        # Check nearby dark tiles: if current cell's feature is FEAT_DARK,
        # or any adjacent forward is, render dimmed unless LIGHT active.
        cur_feat = self.sim.current_feature()
        dark = (cur_feat == T.FEAT_DARK) and not light
        frame = R3.render_wireframe(self.sim.grid, self.sim.px, self.sim.py,
                                    self.sim.facing, dark=dark)
        mini = R3.render_minimap(self.sim.grid, self.sim.px, self.sim.py,
                                 self.sim.facing, radius=3)
        t = Text()
        for row in frame:
            t.append(row + "\n", style="bold rgb(220,200,120)")
        t.append("\n")
        t.append(f"Floor {self.sim.floor_key}    "
                 f"({self.sim.px},{self.sim.py})   "
                 f"facing {T.DIR_NAME[self.sim.facing]}    "
                 f"steps {self.sim.steps}",
                 style="dim")
        t.append("\n\n")
        # Minimap aligned under the frame.
        for row in mini:
            t.append("    " + row + "\n", style="rgb(180,180,220)")
        if light:
            t.append(f"\n[LIGHT active — {self.sim.active_party_light_turns} more steps]\n",
                     style="bold yellow")
        self.update(t)


# ---- Castle menu (default home screen) --------------------------------

class CastleView(Static):
    def __init__(self, sim: S.Sim) -> None:
        super().__init__()
        self.sim = sim
        self.border_title = "CASTLE"

    def refresh_view(self) -> None:
        t = Text()
        t.append("\n  King's Keep\n", style="bold yellow")
        t.append("\n  The Keep sits above the Deep.  Choose a building:\n\n",
                 style="dim")
        t.append("    [1] Training Grounds   — create / review characters\n")
        t.append("    [2] Tavern              — form the active party\n")
        t.append("    [3] Vagrant's Rest      — rest and restore\n")
        t.append("    [4] Temple of Cant      — raise the dead\n")
        t.append("    [5] Bolt & Sons          — buy arms and armor\n")
        t.append("    [6] Descend               — ", style="")
        if any(i >= 0 for i in self.sim.party_slots):
            t.append("enter the dungeon ↓\n", style="bold green")
        else:
            t.append("(set a party first)\n", style="dim")
        t.append("\n")
        t.append(f"  Pool gold: {self.sim.gold}\n", style="yellow")
        t.append(f"  Roster:  {len(self.sim.roster)} / {D.MAX_ROSTER}\n", style="dim")
        party = self.sim.party_active()
        if party:
            t.append("\n  Active party:\n", style="dim")
            for i, p in enumerate(party):
                row = "F" if i < 3 else "B"
                t.append(
                    f"    {i+1}{row}  {p.name:<14} {D.CLASSES[p.class_key].short} "
                    f"Lv{p.level:<2}  HP {p.hp:>3}/{p.hp_max:<3}\n",
                    style="bold green" if p.is_alive() else "red",
                )
        else:
            t.append("\n  [dim]No party assembled.[/]\n")
        self.update(t)


# ---- Side panels -------------------------------------------------------

class PartyPanel(Static):
    def __init__(self, sim: S.Sim) -> None:
        super().__init__()
        self.sim = sim
        self.border_title = "PARTY"

    def refresh_panel(self) -> None:
        t = Text()
        party = self.sim.party_active()
        if not party:
            t.append("(no party yet)\n", style="dim")
        for i, p in enumerate(party):
            row = "F" if i < 3 else "B"
            col = "green" if p.is_alive() else "red"
            t.append(f"{i+1}{row} ", style="bold")
            t.append(f"{p.name:<10}", style="bold " + col)
            t.append(f" {D.CLASSES[p.class_key].short} Lv{p.level}  ", style="bright_white")
            bar = _bar(p.hp, p.hp_max, 8)
            t.append_text(bar)
            t.append(f" {p.hp:>3}/{p.hp_max:<3}\n", style=col)
            # Slot line (compact).
            if any(p.mage_slots_max):
                m = " ".join(f"{c}" for c, mx in zip(p.mage_slots, p.mage_slots_max) if mx > 0)
                t.append(f"   mage [{m}]\n", style="cyan")
            if any(p.priest_slots_max):
                pri = " ".join(f"{c}" for c, mx in zip(p.priest_slots, p.priest_slots_max) if mx > 0)
                t.append(f"   prst [{pri}]\n", style="magenta")
        self.update(t)


class PositionPanel(Static):
    def __init__(self, sim: S.Sim) -> None:
        super().__init__()
        self.sim = sim
        self.border_title = "POSITION"

    def refresh_panel(self) -> None:
        t = Text()
        if self.sim.in_dungeon:
            t.append(f"Floor: {self.sim.floor_key}\n", style="yellow")
            t.append(f"({self.sim.px},{self.sim.py})  facing {T.DIR_NAME[self.sim.facing]}\n",
                     style="bright_white")
            t.append(f"steps: {self.sim.steps}\n", style="dim")
            feat = self.sim.current_feature()
            if feat != T.FEAT_NONE:
                t.append(f"here: {T.feature_name(self.sim.grid[self.sim.py][self.sim.px])}\n",
                         style="bold magenta")
        else:
            t.append("Castle: King's Keep\n", style="yellow")
        t.append(f"\nPool gold: {self.sim.gold}\n", style="yellow")
        t.append(f"Bag: {len(self.sim.inventory)} kinds\n", style="dim")
        self.update(t)


HINTS_CASTLE = (
    "[bold]1-6[/] building       [bold]?[/] help\n"
    "[bold]F2[/] save  [bold]F3[/] load  [bold]q[/] quit"
)

HINTS_DUNGEON = (
    "[bold]w/↑[/] fwd  [bold]s/↓[/] back\n"
    "[bold]a/←[/] turn L  [bold]d/→[/] turn R\n"
    "[bold]space[/] interact (stairs/door)\n"
    "[bold]m[/] party  [bold]esc[/] back to castle\n"
    "[bold]F2[/] save  [bold]F3[/] load"
)


class HintsPanel(Static):
    def __init__(self) -> None:
        super().__init__()
        self.border_title = "KEYS"

    def refresh_panel(self, dungeon: bool) -> None:
        self.update(Text.from_markup(HINTS_DUNGEON if dungeon else HINTS_CASTLE))


def _bar(cur: int, mx: int, width: int = 8) -> Text:
    if mx <= 0:
        return Text("░" * width, style="dim")
    n = max(0, min(width, cur * width // mx))
    t = Text()
    t.append("█" * n, style="bold green" if cur > mx // 3 else "bold red")
    t.append("░" * (width - n), style="dim")
    return t


# ---- App --------------------------------------------------------------

class WizApp(App):
    CSS_PATH = "tui.tcss"
    TITLE = "wizardry-tui"
    SUB_TITLE = "The Mad Overlord's Deep"

    MSG_NEW_GAME = "new_game"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("question_mark", "help", show=False),
        Binding("f2", "save_game", "Save"),
        Binding("f3", "load_game", "Load"),
        # Castle shortcuts.
        Binding("1", "castle_go(1)", show=False),
        Binding("2", "castle_go(2)", show=False),
        Binding("3", "castle_go(3)", show=False),
        Binding("4", "castle_go(4)", show=False),
        Binding("5", "castle_go(5)", show=False),
        Binding("6", "castle_go(6)", show=False),
        # Dungeon movement — arrows and wasd.
        Binding("up", "dungeon_forward", show=False, priority=True),
        Binding("w", "dungeon_forward", show=False, priority=True),
        Binding("down", "dungeon_back", show=False, priority=True),
        Binding("s", "dungeon_back", show=False, priority=True),
        Binding("left", "dungeon_turn_left", show=False, priority=True),
        Binding("a", "dungeon_turn_left", show=False, priority=True),
        Binding("right", "dungeon_turn_right", show=False, priority=True),
        Binding("d", "dungeon_turn_right", show=False, priority=True),
        Binding("space", "interact", show=False, priority=True),
        Binding("enter", "interact", show=False, priority=True),
        Binding("m", "party_menu", show=False),
        Binding("escape", "dungeon_exit", show=False),
    ]

    def __init__(self, start_with_title: bool = True) -> None:
        super().__init__()
        self.sim = S.Sim.new_game()
        self._start_with_title = start_with_title
        self.wire_view = WireframeView(self.sim)
        self.castle_view = CastleView(self.sim)
        self.party_panel = PartyPanel(self.sim)
        self.position_panel = PositionPanel(self.sim)
        self.hints_panel = HintsPanel()
        self.message_log = RichLog(id="log", markup=True, highlight=False,
                                   wrap=False, max_lines=500)
        self.message_log.border_title = "LOG"
        self.flash_bar = Static(" ", id="flash-bar")
        self._flash_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            with Vertical(id="main-col"):
                # Both views mounted; we toggle display in refresh_panels.
                self.wire_view.id = "view-wire"
                self.castle_view.id = "view-castle"
                yield self.wire_view
                yield self.castle_view
                yield self.flash_bar
                yield self.message_log
            with Vertical(id="side"):
                yield self.party_panel
                yield self.position_panel
                yield self.hints_panel
        yield Footer()

    async def on_mount(self) -> None:
        self.refresh_panels()
        if self._start_with_title:
            self.push_screen(SC.TitleScreen())
        self.set_interval(0.5, self.refresh_panels)

    # --- panel refresh ------------------------------------------------

    def refresh_panels(self) -> None:
        in_dungeon = self.sim.in_dungeon
        self.wire_view.display = in_dungeon
        self.castle_view.display = not in_dungeon
        if in_dungeon:
            self.wire_view.refresh_view()
        else:
            self.castle_view.refresh_view()
        self.party_panel.refresh_panel()
        self.position_panel.refresh_panel()
        self.hints_panel.refresh_panel(in_dungeon)

    # --- logging / flash ---------------------------------------------

    def log_msg(self, msg: str, level: str = "info") -> None:
        icon = {"info": "ℹ", "warn": "⚠", "error": "✗",
                "combat": "⚔", "quest": "★", "success": "✓"}.get(level, "•")
        self.message_log.write(f"[bold]{icon}[/] {msg}")

    def flash_status(self, msg: str, seconds: float = 2.0) -> None:
        self.flash_bar.update(Text.from_markup(msg))
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self._flash_timer = self.set_timer(seconds, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash_timer = None
        self.flash_bar.update(" ")

    # --- new game / save / load --------------------------------------

    def start_new_game(self) -> None:
        self.sim = S.Sim.new_game()
        self._rebind_panels()
        self.refresh_panels()
        self.log_msg("[yellow]New game — visit Training Grounds (1) to create heroes.[/]")
        self.flash_status("[green]New game.[/]")

    def _rebind_panels(self) -> None:
        self.wire_view.sim = self.sim
        self.castle_view.sim = self.sim
        self.party_panel.sim = self.sim
        self.position_panel.sim = self.sim

    def load_savefile(self) -> bool:
        if not SAVE_PATH.exists():
            self.flash_status("[red]No save file.[/]")
            return False
        try:
            self.sim = S.Sim.load_from(SAVE_PATH)
        except Exception as e:
            self.log_msg(f"[red]Load failed:[/] {e}", level="error")
            return False
        self._rebind_panels()
        self.refresh_panels()
        self.flash_status("[green]Loaded.[/]")
        return True

    def action_save_game(self) -> None:
        try:
            self.sim.save_to(SAVE_PATH)
            self.flash_status(f"[green]Saved[/] → {SAVE_PATH}")
        except OSError as e:
            self.flash_status(f"[red]Save failed:[/] {e}")

    def action_load_game(self) -> None:
        self.load_savefile()

    # --- actions (global / modal dispatch) ---------------------------

    def action_help(self) -> None:
        self.push_screen(SC.HelpScreen())

    def action_castle_go(self, n: str) -> None:
        if self.sim.in_dungeon:
            return
        num = int(n)
        if num == 1:
            self.push_screen(SC.TrainingGroundsScreen())
        elif num == 2:
            if not self.sim.roster:
                self.flash_status("[red]Create characters first.[/]")
                return
            self.push_screen(SC.PartyAssembleScreen())
        elif num == 3:
            self.push_screen(SC.InnScreen())
        elif num == 4:
            self.push_screen(SC.TempleScreen())
        elif num == 5:
            self.push_screen(SC.ShopScreen())
        elif num == 6:
            if not any(i >= 0 for i in self.sim.party_slots):
                self.flash_status("[red]Party not set — visit the Tavern (2).[/]")
                return
            self._descend_to_dungeon()

    def _descend_to_dungeon(self) -> None:
        self.sim.enter_dungeon("B1")
        self.log_msg("[yellow]You descend into the Deep.[/]", level="quest")
        self.refresh_panels()

    # --- dungeon actions ---------------------------------------------

    def action_dungeon_forward(self) -> None:
        if not self.sim.in_dungeon:
            return
        moved, msg, event = self.sim.step_forward()
        self.refresh_panels()
        if not moved:
            self.flash_status(f"[dim]{msg}[/]")
            return
        self._handle_dungeon_event(event)

    def action_dungeon_back(self) -> None:
        if not self.sim.in_dungeon:
            return
        moved, msg = self.sim.step_back()
        if not moved:
            self.flash_status(f"[dim]{msg}[/]")
        self.refresh_panels()

    def action_dungeon_turn_left(self) -> None:
        if not self.sim.in_dungeon:
            return
        self.sim.turn_left()
        self.refresh_panels()

    def action_dungeon_turn_right(self) -> None:
        if not self.sim.in_dungeon:
            return
        self.sim.turn_right()
        self.refresh_panels()

    def action_interact(self) -> None:
        if not self.sim.in_dungeon:
            return
        feat = self.sim.current_feature()
        if feat == T.FEAT_STAIRS_DOWN:
            from . import maps as M
            nxt = M.next_floor_down(self.sim.floor_key)
            if nxt:
                self.sim.change_floor(nxt)
                self.log_msg(f"You descend to {nxt}.", level="quest")
                self.refresh_panels()
        elif feat == T.FEAT_STAIRS_UP:
            from . import maps as M
            nxt = M.next_floor_up(self.sim.floor_key)
            if nxt:
                self.sim.change_floor(nxt)
                self.log_msg(f"You climb to {nxt}.", level="quest")
                self.refresh_panels()
        elif feat == T.FEAT_EXIT:
            self.sim.leave_dungeon()
            self.log_msg("You emerge into the Keep.", level="quest")
            self.refresh_panels()
        elif feat == T.FEAT_BOSS:
            self._start_boss_fight()

    def action_party_menu(self) -> None:
        if any(i >= 0 for i in self.sim.party_slots):
            self.push_screen(SC.PartyStatusScreen())

    def action_dungeon_exit(self) -> None:
        """Escape from dungeon mode (debug convenience)."""
        if self.sim.in_dungeon:
            # Escape returns to castle via ASCEND-equivalent (simplified).
            self.sim.leave_dungeon()
            self.log_msg("The party retreats to the Keep.", level="info")
            self.refresh_panels()

    def _handle_dungeon_event(self, event: str) -> None:
        if event == "":
            return
        if event == "encounter":
            self._trigger_encounter()
        elif event == "chute":
            self.log_msg("A CHUTE drops the party one floor down!", level="warn")
            from . import maps as M
            nxt = M.next_floor_down(self.sim.floor_key)
            if nxt:
                self.sim.change_floor(nxt)
                self.refresh_panels()
        elif event == "spinner":
            self.log_msg("The floor spins — your facing is lost.", level="warn")
            self.flash_status("[yellow]spinner![/]")
        elif event == "teleport":
            # Random passable tile.
            grid = self.sim.grid
            w, h = len(grid[0]), len(grid)
            for _ in range(100):
                x = self.sim.rng.randint(0, w - 1)
                y = self.sim.rng.randint(0, h - 1)
                if not T.is_void(grid[y][x]):
                    self.sim.px = x
                    self.sim.py = y
                    break
            self.log_msg("A TELEPORT rune flares — reality shifts.", level="warn")
            self.refresh_panels()
        elif event == "pit":
            self.log_msg("A PIT yawns underfoot — the party bruises.", level="warn")
            for ch in self.sim.party_active():
                dmg = self.sim.rng.randint(2, 6)
                ch.hp = max(0, ch.hp - dmg)
                if ch.hp <= 0 and "dead" not in ch.status:
                    ch.status.append("dead")
            self.refresh_panels()
        elif event == "boss":
            self._start_boss_fight()

    def _trigger_encounter(self) -> None:
        groups = S.roll_encounter(self.sim.rng, self.sim.floor_key)
        if not groups:
            return
        names = ", ".join(g.name() for g in groups)
        self.log_msg(f"⚔ Encounter — {names}", level="combat")
        combat = S.Combat(self.sim, groups)
        self.push_screen(SC.CombatScreen(combat, self._on_combat_complete))

    def _start_boss_fight(self) -> None:
        groups = S.roll_encounter(self.sim.rng, self.sim.floor_key,
                                  forced_id="andrew_shade")
        if not groups:
            return
        self.log_msg("A hollow echo rises to bar the way.", level="quest")
        combat = S.Combat(self.sim, groups, is_boss=True,
                          boss_name="Shade of Andrew")
        self.push_screen(SC.CombatScreen(combat, self._on_boss_complete))

    def _on_combat_complete(self, result: S.CombatResult) -> None:
        for line in result.log:
            self.log_msg(line, level="combat")
        if result.outcome == "loss":
            self.push_screen(SC.GameOverScreen())
        self.refresh_panels()

    def _on_boss_complete(self, result: S.CombatResult) -> None:
        for line in result.log:
            self.log_msg(line, level="combat")
        if result.outcome == "win":
            self.sim.flags.andrew_slain = True
            self.push_screen(SC.VictoryScreen())
        elif result.outcome == "loss":
            self.push_screen(SC.GameOverScreen())
        self.refresh_panels()

    # --- message passing --------------------------------------------

    def on_screen_resume(self) -> None:
        # Called by Textual whenever a screen resumes.
        self.refresh_panels()


# ---- entry ------------------------------------------------------------

def run() -> None:
    app = WizApp()
    try:
        app.run()
    finally:
        sys.stdout.write(
            "\033[?1000l\033[?1002l\033[?1003l\033[?1006l\033[?1015l\033[?25h"
        )
        sys.stdout.flush()
