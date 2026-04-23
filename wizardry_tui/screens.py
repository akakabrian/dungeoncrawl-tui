"""Modal screens — Title, Help, CharCreate, Training, PartyAssemble,
Inn, Temple, Shop, Combat, GameOver, Victory, PartyStatus.

Screens talk to the App (access via `self.app.sim`) and return via
`self.dismiss()` which the App handles through optional callbacks.
"""
from __future__ import annotations

import random
from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from . import data as D
from . import sim as S


# ---- Title --------------------------------------------------------------

class TitleScreen(ModalScreen):
    BINDINGS = [
        Binding("n", "new_game", "New Game"),
        Binding("l", "load_game", "Load"),
        Binding("escape", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(Text.from_markup(
                "\n[bold yellow]wizardry-tui[/]\n\n"
                "[dim]The Mad Overlord's Deep[/]\n\n"
                "A king's daughter is taken.  The deep beneath the Keep breathes.\n"
                "Gather six brave souls and descend.\n\n"
                "[bold]N[/] New Game    [bold]L[/] Load Save\n\n"
                "Press [bold]escape[/] to close this and roam the castle menu."
            ), id="title-text")

    def action_new_game(self) -> None:
        self.app.start_new_game()   # type: ignore[attr-defined]
        self.dismiss()

    def action_load_game(self) -> None:
        ok = self.app.load_savefile()   # type: ignore[attr-defined]
        if ok:
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


# ---- Help ---------------------------------------------------------------

class HelpScreen(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("q", "close", show=False)]

    def compose(self) -> ComposeResult:
        body = Text.from_markup(
            "[bold yellow]wizardry-tui — help[/]\n\n"
            "[bold]Castle:[/]\n"
            "  [bold]1[/] Training Grounds — create or review characters\n"
            "  [bold]2[/] Tavern — form an active party of up to 6\n"
            "  [bold]3[/] Inn — rest, refill slots, heal\n"
            "  [bold]4[/] Temple — raise the dead, cure status\n"
            "  [bold]5[/] Shop — buy gear, sell loot\n"
            "  [bold]6[/] Descend — enter the dungeon (party must be set)\n\n"
            "[bold]Dungeon:[/]\n"
            "  [bold]W / ↑[/]  step forward      [bold]S / ↓[/]  step back\n"
            "  [bold]A / ←[/]  turn left          [bold]D / →[/]  turn right\n"
            "  [bold]space / enter[/]  interact (stairs, door)\n"
            "  [bold]M[/]  party menu     [bold]escape[/]  back / exit\n\n"
            "[bold]Global:[/]  [bold]F2[/] save   [bold]F3[/] load   "
            "[bold]?[/] help   [bold]q[/] quit"
        )
        with Vertical():
            yield Static(body)

    def action_close(self) -> None:
        self.dismiss()


# ---- CharCreate ---------------------------------------------------------

class CharCreateScreen(ModalScreen):
    """Compact character creator.

    Flow: auto-rolls a set of stats; lets the player cycle race, alignment,
    class; commits to roster.
    """

    BINDINGS = [
        Binding("escape", "close", "Cancel"),
        Binding("enter", "commit", "Commit", priority=True),
        Binding("r", "reroll", "Reroll"),
        Binding("tab", "next_class", "Next class"),
        Binding("n", "next_race", "Next race"),
        Binding("a", "next_align", "Align"),
    ]

    def __init__(self, on_done: Callable[[S.Character | None], None] | None = None) -> None:
        super().__init__()
        self.on_done = on_done
        self._name = "Hero"
        self._name_idx = 0
        self._race_idx = 0
        self._align_idx = 0
        self._class_idx = 0
        self._stats: dict[str, int] = {}
        self._bonus: int = 0
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="cc-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]Training Grounds — create a character[/]\n"
                "[dim]enter: commit  r: reroll stats  n: next race  "
                "a: cycle alignment  tab: next class  esc: cancel[/]\n"
            ))
            yield Static("[bold]Name:[/] (type to edit)", id="cc-name-label")
            yield Input(value=self._name, id="cc-name-input")
            yield self._out

    def on_mount(self) -> None:
        self.action_reroll()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._name = event.value.strip() or "Hero"
        self._refresh()

    def action_reroll(self) -> None:
        rng = random.Random()
        race_key = list(D.RACES.keys())[self._race_idx % len(D.RACES)]
        self._stats, self._bonus = S._roll_stats(rng, D.RACES[race_key].mods)
        self._refresh()

    def action_next_race(self) -> None:
        self._race_idx = (self._race_idx + 1) % len(D.RACES)
        # Recompute stats for new race mods.
        self.action_reroll()

    def action_next_align(self) -> None:
        self._align_idx = (self._align_idx + 1) % 3
        self._refresh()

    def action_next_class(self) -> None:
        self._class_idx = (self._class_idx + 1) % len(D.CLASS_ORDER)
        self._refresh()

    def _current(self) -> tuple[str, str, str]:
        race = list(D.RACES.keys())[self._race_idx % len(D.RACES)]
        align = ["G", "N", "E"][self._align_idx % 3]
        cls = D.CLASS_ORDER[self._class_idx % len(D.CLASS_ORDER)]
        return race, align, cls

    def _refresh(self) -> None:
        if self._out is None:
            return
        race, align, cls_key = self._current()
        race_name = D.RACES[race].name
        align_name = {"G": "Good", "N": "Neutral", "E": "Evil"}[align]
        cls = D.CLASSES[cls_key]
        # Auto-assigned stats (preview).
        final = S.auto_assign_bonus(self._stats, self._bonus, cls_key)
        eligible = D.meets_class_req(cls, final, align)
        t = Text()
        t.append(f"Name: {self._name}\n", style="bold")
        t.append(f"Race: {race_name}   ", style="yellow")
        t.append(f"Alignment: {align_name}\n", style="yellow")
        t.append(f"Class: {cls.name} — ", style="bold")
        t.append(f"{cls.desc}\n", style="dim")
        t.append("\n[Base stats]  ", style="dim")
        t.append(" ".join(f"{k}:{v}" for k, v in self._stats.items()) + f"   bonus: {self._bonus}\n",
                 style="bright_white")
        t.append("[Final]       ", style="dim")
        t.append(" ".join(f"{k}:{v}" for k, v in final.items()) + "\n",
                 style="bright_cyan")
        if cls.req:
            t.append("Reqs: ", style="dim")
            for k, need in cls.req.items():
                col = "green" if final.get(k, 0) >= need else "red"
                t.append(f"{k}≥{need} ", style=col)
            t.append("\n")
        t.append("Alignments: " + ", ".join(cls.alignments) + "\n", style="dim")
        if eligible:
            t.append("\n[bold green]Eligible — press enter to commit.[/]\n")
        else:
            t.append("\n[bold red]Not eligible.  Reroll (r) or change class/align.[/]\n")
        self._out.update(t)

    def action_commit(self) -> None:
        race, align, cls_key = self._current()
        final = S.auto_assign_bonus(self._stats, self._bonus, cls_key)
        cls = D.CLASSES[cls_key]
        if not D.meets_class_req(cls, final, align):
            return
        ch = S.make_character(self._name, race, align, cls_key, final,
                              self.app.sim.rng)   # type: ignore[attr-defined]
        if self.on_done:
            self.on_done(ch)
        self.dismiss()

    def action_close(self) -> None:
        if self.on_done:
            self.on_done(None)
        self.dismiss()


# ---- TrainingGrounds ----------------------------------------------------

class TrainingGroundsScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("c", "create", "Create"),
        Binding("d", "delete", "Delete"),
        Binding("up", "prev", show=False, priority=True),
        Binding("down", "next", show=False, priority=True),
        Binding("j", "next", show=False),
        Binding("k", "prev", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sel = 0
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="tg-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]Training Grounds[/]\n"
                "[dim]↑/↓ select  c: create  d: delete  esc: back[/]\n"
            ))
            yield self._out

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._out is None:
            return
        sim = self.app.sim   # type: ignore[attr-defined]
        t = Text()
        if not sim.roster:
            t.append("\n  The roster is empty.  Press [bold]c[/] to create a hero.\n",
                     style="dim")
        else:
            for i, ch in enumerate(sim.roster):
                mark = "▶" if i == self._sel else " "
                line = (
                    f"{mark} {ch.name:<14} "
                    f"{D.RACES[ch.race].name[:5]:<5} "
                    f"{D.CLASSES[ch.class_key].short} "
                    f"{ch.alignment} "
                    f"Lv{ch.level:<2} "
                    f"HP {ch.hp:>3}/{ch.hp_max:<3} "
                    f"AC {ch.ac:>2}  "
                    f"xp {ch.xp:>5}"
                )
                col = "bold green" if ch.is_alive() else "red"
                t.append(line + "\n", style=col if i == self._sel else "")
        self._out.update(t)

    def action_prev(self) -> None:
        if self.app.sim.roster:   # type: ignore[attr-defined]
            self._sel = (self._sel - 1) % len(self.app.sim.roster)   # type: ignore[attr-defined]
            self._refresh()

    def action_next(self) -> None:
        if self.app.sim.roster:   # type: ignore[attr-defined]
            self._sel = (self._sel + 1) % len(self.app.sim.roster)   # type: ignore[attr-defined]
            self._refresh()

    def action_create(self) -> None:
        def _done(ch: S.Character | None) -> None:
            if ch is not None:
                self.app.sim.add_to_roster(ch)   # type: ignore[attr-defined]
                self._refresh()

        self.app.push_screen(CharCreateScreen(on_done=_done))

    def action_delete(self) -> None:
        sim = self.app.sim   # type: ignore[attr-defined]
        if 0 <= self._sel < len(sim.roster):
            sim.delete_from_roster(self._sel)
            self._sel = max(0, self._sel - 1)
            self._refresh()

    def action_close(self) -> None:
        self.dismiss()


# ---- PartyAssemble ------------------------------------------------------

class PartyAssembleScreen(ModalScreen):
    """Select up to 6 roster members into active party slots."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("up", "prev", show=False, priority=True),
        Binding("down", "next", show=False, priority=True),
        Binding("space", "toggle", "Toggle", priority=True),
        Binding("enter", "confirm", "Done", priority=True),
        Binding("j", "next", show=False),
        Binding("k", "prev", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sel = 0
        self._chosen: list[int] = []
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="pa-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]The Lion & Lantern — form a party[/]\n"
                "[dim]↑/↓ select, space: add/remove, enter: confirm, esc: cancel[/]\n"
                "[dim]First 3 selected = front row; 4-6 = back row.[/]\n"
            ))
            yield self._out

    def on_mount(self) -> None:
        # Prefill with current party.
        cur = [i for i in self.app.sim.party_slots if i >= 0]   # type: ignore[attr-defined]
        self._chosen = list(cur)
        self._refresh()

    def _refresh(self) -> None:
        if self._out is None:
            return
        sim = self.app.sim   # type: ignore[attr-defined]
        t = Text()
        for i, ch in enumerate(sim.roster):
            mark = "▶" if i == self._sel else " "
            in_party = i in self._chosen
            checkbox = "[×]" if in_party else "[ ]"
            col = "bold green" if ch.is_alive() else "red"
            slot_str = ""
            if in_party:
                slot_num = self._chosen.index(i) + 1
                slot_str = f" slot {slot_num}"
            line = (f"{mark} {checkbox} {ch.name:<14} "
                    f"{D.CLASSES[ch.class_key].short} "
                    f"Lv{ch.level:<2}  HP {ch.hp:>3}/{ch.hp_max:<3}{slot_str}")
            t.append(line + "\n", style=col)
        t.append(f"\nChosen: {len(self._chosen)}/6  — press enter when done.\n",
                 style="yellow")
        self._out.update(t)

    def action_prev(self) -> None:
        if self.app.sim.roster:   # type: ignore[attr-defined]
            self._sel = (self._sel - 1) % len(self.app.sim.roster)   # type: ignore[attr-defined]
            self._refresh()

    def action_next(self) -> None:
        if self.app.sim.roster:   # type: ignore[attr-defined]
            self._sel = (self._sel + 1) % len(self.app.sim.roster)   # type: ignore[attr-defined]
            self._refresh()

    def action_toggle(self) -> None:
        if self._sel in self._chosen:
            self._chosen.remove(self._sel)
        elif len(self._chosen) < 6:
            self._chosen.append(self._sel)
        self._refresh()

    def action_confirm(self) -> None:
        if not self._chosen:
            return
        self.app.sim.set_party(self._chosen)   # type: ignore[attr-defined]
        self.app.refresh_panels()   # type: ignore[attr-defined]
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


# ---- Inn ---------------------------------------------------------------

class InnScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("1", "rest(1)", show=False),
        Binding("2", "rest(2)", show=False),
        Binding("3", "rest(3)", show=False),
        Binding("4", "rest(4)", show=False),
        Binding("5", "rest(5)", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="inn-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]Vagrant's Rest[/]\n"
                "[dim]Choose a room; gold is deducted from the pool.[/]\n"
            ))
            yield self._out

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._out is None:
            return
        sim = self.app.sim   # type: ignore[attr-defined]
        t = Text()
        for i, (name, cost, hp_per, refill, days) in enumerate(D.INN_TIERS, 1):
            affordable = sim.gold >= cost
            col = "bold" if affordable else "dim"
            refill_tag = " (+slots)" if refill else ""
            t.append(f"  [{i}] {name:<12} {cost:>4}g — {hp_per}/day × {days}d{refill_tag}\n",
                     style=col)
        t.append(f"\n  Pool gold: {sim.gold}\n", style="yellow")
        party = sim.party_active()
        t.append("\n  Party status:\n", style="dim")
        for p in party:
            col = "green" if p.is_alive() else "red"
            t.append(f"    {p.name:<14} HP {p.hp:>3}/{p.hp_max:<3}  mage slots {sum(p.mage_slots)}  priest slots {sum(p.priest_slots)}\n",
                     style=col)
        self._out.update(t)

    def action_rest(self, tier: str) -> None:
        idx = int(tier) - 1
        if not (0 <= idx < len(D.INN_TIERS)):
            return
        name, cost, hp_per, refill, days = D.INN_TIERS[idx]
        sim = self.app.sim   # type: ignore[attr-defined]
        if sim.gold < cost:
            self.app.flash_status(f"[red]Not enough gold for {name}.[/]")   # type: ignore[attr-defined]
            return
        sim.gold -= cost
        for p in sim.party_active():
            if refill:
                p.rest(refill_slots=True)
            else:
                # hp per day * days, clamp to max
                p.hp = min(p.hp_max, p.hp + hp_per * days)
        self.app.flash_status(f"[green]Rested at {name}.[/]")   # type: ignore[attr-defined]
        self.app.refresh_panels()   # type: ignore[attr-defined]
        self._refresh()

    def action_close(self) -> None:
        self.dismiss()


# ---- Temple ------------------------------------------------------------

class TempleScreen(ModalScreen):
    """Revive dead party members; cost scales with level."""

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("up", "prev", show=False, priority=True),
        Binding("down", "next", show=False, priority=True),
        Binding("enter", "raise_selected", "Raise", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sel = 0
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="temple-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]Temple of Cant[/]\n"
                "[dim]↑/↓ select a fallen soul, enter to pay for raising.[/]\n"
            ))
            yield self._out

    def on_mount(self) -> None:
        self._refresh()

    def _dead(self) -> list[int]:
        sim = self.app.sim   # type: ignore[attr-defined]
        return [i for i, ch in enumerate(sim.roster) if not ch.is_alive()]

    def _refresh(self) -> None:
        if self._out is None:
            return
        sim = self.app.sim   # type: ignore[attr-defined]
        dead = self._dead()
        t = Text()
        if not dead:
            t.append("\n  No souls need raising.  Peace, pilgrim.\n", style="dim")
        else:
            for k, i in enumerate(dead):
                ch = sim.roster[i]
                cost = ch.level * 250
                mark = "▶" if k == self._sel else " "
                t.append(f"{mark} {ch.name:<14} Lv{ch.level:<2} cost {cost} g\n")
            t.append(f"\n  Pool gold: {sim.gold}\n", style="yellow")
        self._out.update(t)

    def action_prev(self) -> None:
        n = len(self._dead())
        if n:
            self._sel = (self._sel - 1) % n
            self._refresh()

    def action_next(self) -> None:
        n = len(self._dead())
        if n:
            self._sel = (self._sel + 1) % n
            self._refresh()

    def action_raise_selected(self) -> None:
        sim = self.app.sim   # type: ignore[attr-defined]
        dead = self._dead()
        if not dead:
            return
        idx = dead[self._sel % len(dead)]
        ch = sim.roster[idx]
        cost = ch.level * 250
        if sim.gold < cost:
            self.app.flash_status(f"[red]Not enough gold.[/]")   # type: ignore[attr-defined]
            return
        sim.gold -= cost
        # 90 - (100 - VIT*5) success chance, simplified:
        chance = 60 + ch.stats.get("VIT", 10) * 2
        if sim.rng.randint(1, 100) <= chance:
            ch.status = [s for s in ch.status if s != "dead"]
            ch.hp = max(1, ch.hp_max // 2)
            self.app.flash_status(f"[green]{ch.name} rises again.[/]")   # type: ignore[attr-defined]
        else:
            self.app.flash_status(f"[red]The rite fails. {ch.name} remains dead.[/]")   # type: ignore[attr-defined]
        self.app.refresh_panels()   # type: ignore[attr-defined]
        self._refresh()

    def action_close(self) -> None:
        self.dismiss()


# ---- Shop --------------------------------------------------------------

class ShopScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("up", "prev", show=False, priority=True),
        Binding("down", "next", show=False, priority=True),
        Binding("enter", "buy", "Buy", priority=True),
        Binding("s", "sell", "Sell one"),
        Binding("j", "next", show=False),
        Binding("k", "prev", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._sel = 0
        self._out: Static | None = None

    def compose(self) -> ComposeResult:
        self._out = Static("", id="shop-out")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold yellow]Bolt & Sons — Arms & Armaments[/]\n"
                "[dim]↑/↓ select, enter to buy, s to sell one.[/]\n"
            ))
            yield self._out

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._out is None:
            return
        sim = self.app.sim   # type: ignore[attr-defined]
        t = Text()
        for i, iid in enumerate(D.SHOP_STOCK):
            it = D.ITEMS[iid]
            mark = "▶" if i == self._sel else " "
            t.append(
                f"{mark} {it.name:<20} {it.kind:<9} {it.price:>5}g\n",
                style="bold" if sim.gold >= it.price else "dim",
            )
        t.append(f"\n  Pool gold: {sim.gold}\n", style="yellow")
        t.append("  Bag: ", style="dim")
        t.append(", ".join(f"{iid}×{n}" for iid, n in sim.inventory.items()) or "—",
                 style="cyan")
        t.append("\n")
        self._out.update(t)

    def action_prev(self) -> None:
        self._sel = (self._sel - 1) % len(D.SHOP_STOCK)
        self._refresh()

    def action_next(self) -> None:
        self._sel = (self._sel + 1) % len(D.SHOP_STOCK)
        self._refresh()

    def action_buy(self) -> None:
        iid = D.SHOP_STOCK[self._sel]
        it = D.ITEMS[iid]
        sim = self.app.sim   # type: ignore[attr-defined]
        if sim.gold < it.price:
            self.app.flash_status(f"[red]Not enough gold.[/]")   # type: ignore[attr-defined]
            return
        sim.gold -= it.price
        sim.add_item(iid)
        self.app.flash_status(f"[green]+{it.name}[/]")   # type: ignore[attr-defined]
        self._refresh()

    def action_sell(self) -> None:
        iid = D.SHOP_STOCK[self._sel]
        it = D.ITEMS[iid]
        sim = self.app.sim   # type: ignore[attr-defined]
        if sim.inventory.get(iid, 0) <= 0:
            self.app.flash_status(f"[red]You have none to sell.[/]")   # type: ignore[attr-defined]
            return
        sim.remove_item(iid, 1)
        refund = max(1, it.price // 2)
        sim.gold += refund
        self.app.flash_status(f"[yellow]Sold {it.name} (+{refund}g)[/]")   # type: ignore[attr-defined]
        self._refresh()

    def action_close(self) -> None:
        self.dismiss()


# ---- PartyStatus -------------------------------------------------------

class PartyStatusScreen(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Back")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._render(), id="ps-out")

    def _render(self) -> Text:
        sim = self.app.sim   # type: ignore[attr-defined]
        t = Text()
        t.append("[bold yellow]Party Status[/]\n\n", style="")
        for slot_idx, ri in enumerate(sim.party_slots):
            if ri < 0:
                t.append(f"  slot {slot_idx+1}  — empty —\n", style="dim")
                continue
            ch = sim.roster[ri]
            row = " front" if slot_idx < 3 else " back "
            t.append(
                f"  slot {slot_idx+1}{row}  {ch.name:<12} "
                f"{D.CLASSES[ch.class_key].short} Lv{ch.level:<2}  "
                f"HP {ch.hp:>3}/{ch.hp_max:<3}  AC {ch.ac:>2}  "
                f"xp {ch.xp:>5}  status: {','.join(ch.status) or 'ok'}\n",
                style="bold green" if ch.is_alive() else "red",
            )
            if any(ch.mage_slots_max):
                t.append("     Mage   ", style="dim")
                t.append(" ".join(f"L{i+1}:{c}/{m}"
                                   for i, (c, m) in enumerate(zip(ch.mage_slots, ch.mage_slots_max))
                                   if m > 0) + "\n", style="cyan")
            if any(ch.priest_slots_max):
                t.append("     Priest ", style="dim")
                t.append(" ".join(f"L{i+1}:{c}/{m}"
                                   for i, (c, m) in enumerate(zip(ch.priest_slots, ch.priest_slots_max))
                                   if m > 0) + "\n", style="magenta")
        return t

    def action_close(self) -> None:
        self.dismiss()


# ---- GameOver / Victory ------------------------------------------------

class GameOverScreen(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(Text.from_markup(
                "\n[bold red]The party has fallen.[/]\n\n"
                "The living survivors, if any, return to the castle.\n"
                "The dead may be brought back at the Temple of Cant.\n\n"
                "[dim]press enter to continue[/]"
            ))

    def action_close(self) -> None:
        sim = self.app.sim   # type: ignore[attr-defined]
        # Push dead characters to the Temple (status stays "dead"; roster keeps them).
        sim.leave_dungeon()
        self.app.refresh_panels()   # type: ignore[attr-defined]
        self.dismiss()


class VictoryScreen(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(Text.from_markup(
                "\n[bold yellow]The Shade of Andrew crumbles.[/]\n\n"
                "The wrought chamber goes silent.  You return to the Keep\n"
                "bearing the mark of the deep.  There is still more below,\n"
                "but for tonight the King's halls are safe.\n"
            ))

    def action_close(self) -> None:
        self.dismiss()


# ---- Combat ------------------------------------------------------------

class CombatScreen(ModalScreen):
    """Turn-based combat.

    Select an action per alive party member in order, then resolve the
    round.  Rounds continue until win/loss/flee.
    """

    BINDINGS = [
        Binding("f", "fight", "Fight", priority=True),
        Binding("p", "parry", "Parry", priority=True),
        Binding("s", "spell", "Spell", priority=True),
        Binding("u", "use", "Use", priority=True),
        Binding("r", "run", "Run", priority=True),
        Binding("1", "target(1)", show=False),
        Binding("2", "target(2)", show=False),
        Binding("3", "target(3)", show=False),
        Binding("4", "target(4)", show=False),
        Binding("escape", "cancel_target", show=False),
        Binding("space", "continue", show=False, priority=True),
    ]

    def __init__(self, combat: S.Combat,
                 on_done: Callable[[S.CombatResult], None] | None = None) -> None:
        super().__init__()
        self.combat = combat
        self.on_done = on_done
        self._actions: list[S.CombatAction | None] = [None] * 6
        self._current_slot = 0
        self._pending_action: str | None = None
        self._pending_spell: str | None = None
        self._phase = "select"   # "select" | "targeting" | "resolving"
        self._out: Static | None = None
        self._log_widget: Static | None = None
        self._round_log: list[str] = []

    def compose(self) -> ComposeResult:
        self._out = Static("", id="combat-out")
        self._log_widget = Static("", id="combat-log")
        with Vertical():
            yield Static(Text.from_markup(
                "[bold red]⚔ COMBAT[/]  [dim]f:fight  p:parry  s:spell  u:use  r:run  "
                "1-4 target group   space: resolve round[/]\n"
            ))
            yield self._out
            yield self._log_widget

    def on_mount(self) -> None:
        self._advance_to_next_actor()
        self._refresh()

    def _advance_to_next_actor(self) -> None:
        """Skip past dead/paralysed slots to the next living party member."""
        while self._current_slot < 6:
            p = self._party_member(self._current_slot)
            if p is None or not p.can_act():
                self._actions[self._current_slot] = None
                self._current_slot += 1
                continue
            break

    def _party_member(self, slot: int) -> S.Character | None:
        if slot < 0 or slot >= 6:
            return None
        ri = self.combat.sim.party_slots[slot]
        if ri < 0 or ri >= len(self.combat.sim.roster):
            return None
        return self.combat.sim.roster[ri]

    def _refresh(self) -> None:
        if self._out is None or self._log_widget is None:
            return
        t = Text()
        # Render monster groups banner.
        for gi, g in enumerate(self.combat.groups):
            alive = g.alive_members()
            col = "yellow" if alive else "dim"
            banner = D.MONSTERS[g.def_id].art * max(1, len(alive))
            t.append(f"  Group {gi+1}: {banner}  {g.name()}\n", style=col)
        t.append("\n")
        # Render party with queued actions.
        for slot in range(6):
            p = self._party_member(slot)
            act = self._actions[slot]
            if p is None:
                t.append(f"  slot {slot+1}  — empty —\n", style="dim")
                continue
            arrow = "►" if slot == self._current_slot and self._phase == "select" else " "
            col = "bold green" if p.is_alive() else "red"
            queued = "[dim](waiting)[/]" if act is None else f"[bold]{act.kind}[/]"
            t.append(
                f"{arrow} slot {slot+1} {'F' if slot < 3 else 'B'}  "
                f"{p.name:<12} {D.CLASSES[p.class_key].short} Lv{p.level:<2}  "
                f"HP {p.hp:>3}/{p.hp_max:<3}  ",
                style=col,
            )
            t.append_text(Text.from_markup(queued + "\n"))
        # Phase help.
        if self._phase == "targeting":
            t.append("\n  Choose target group: ", style="yellow")
            for i, g in enumerate(self.combat.groups):
                if g.is_alive():
                    t.append(f"[{i+1}] {g.name()}  ", style="bold")
            t.append("  (escape to cancel)\n")
        elif self._phase == "select":
            if self._current_slot >= 6:
                t.append("\n  [bold yellow]All actions queued.  Press space to resolve.[/]\n")
            else:
                p = self._party_member(self._current_slot)
                if p is not None:
                    t.append(f"\n  [bold yellow]{p.name}[/] — choose: ", style="")
                    t.append("f)ight  ", style="white")
                    t.append("p)arry  ", style="white")
                    if any(p.mage_slots) or any(p.priest_slots):
                        t.append("s)pell  ", style="white")
                    t.append("u)se  ", style="white")
                    t.append("r)un\n", style="white")
        self._out.update(t)
        # Log panel.
        lg = Text()
        for line in self._round_log[-14:]:
            lg.append(line + "\n")
        self._log_widget.update(lg)

    # --- action selection -------------------------------------------

    def _queue_action_and_advance(self, kind: str, target_group: int = 0,
                                  spell_id: str = "", item_id: str = "") -> None:
        act = S.CombatAction(kind=kind, target_group=target_group,
                             spell_id=spell_id, item_id=item_id)
        self._actions[self._current_slot] = act
        self._current_slot += 1
        self._advance_to_next_actor()
        self._phase = "select"
        self._pending_action = None
        self._pending_spell = None
        self._refresh()

    def action_fight(self) -> None:
        if self._phase != "select" or self._current_slot >= 6:
            return
        # Back row auto-targets group 0; front row prompts for group.
        if self._current_slot >= 3:
            self._queue_action_and_advance("fight", target_group=0)
            return
        alive_gs = [i for i, g in enumerate(self.combat.groups) if g.is_alive()]
        if len(alive_gs) <= 1:
            self._queue_action_and_advance("fight", target_group=alive_gs[0] if alive_gs else 0)
            return
        self._pending_action = "fight"
        self._phase = "targeting"
        self._refresh()

    def action_parry(self) -> None:
        if self._phase != "select" or self._current_slot >= 6:
            return
        self._queue_action_and_advance("parry")

    def action_spell(self) -> None:
        if self._phase != "select" or self._current_slot >= 6:
            return
        p = self._party_member(self._current_slot)
        if p is None:
            return
        # Pick the first usable offensive spell the caster has.
        # v1: auto-select first known spell with an available slot.
        for sid in _flatten_known(p):
            spl = D.SPELLS.get(sid)
            if not spl:
                continue
            if spl.school == "mage" and p.mage_slots[spl.level - 1] <= 0:
                continue
            if spl.school == "priest" and p.priest_slots[spl.level - 1] <= 0:
                continue
            if not spl.combat_only and spl.effect in ("light", "revive", "buff"):
                continue
            self._pending_spell = sid
            # Decide targeting.
            if spl.target == "one_enemy" or spl.target == "group_enemy":
                self._pending_action = "spell"
                self._phase = "targeting"
                self._refresh()
                return
            elif spl.target in ("one_ally", "all_ally", "party", "all_enemy", "self"):
                self._queue_action_and_advance("spell", spell_id=sid,
                                               target_group=0)
                return
        self.app.flash_status(f"[red]{p.name} has no ready combat spell.[/]")   # type: ignore[attr-defined]

    def action_use(self) -> None:
        if self._phase != "select" or self._current_slot >= 6:
            return
        if self.combat.sim.inventory.get("potion", 0) > 0:
            self._queue_action_and_advance("use", item_id="potion")
        else:
            self.app.flash_status("[red]No potions to use.[/]")   # type: ignore[attr-defined]

    def action_run(self) -> None:
        if self._phase != "select" or self._current_slot >= 6:
            return
        self._queue_action_and_advance("run")

    def action_target(self, group: str) -> None:
        if self._phase != "targeting":
            return
        gi = int(group) - 1
        if not (0 <= gi < len(self.combat.groups)) or not self.combat.groups[gi].is_alive():
            return
        if self._pending_action == "fight":
            self._queue_action_and_advance("fight", target_group=gi)
        elif self._pending_action == "spell":
            self._queue_action_and_advance("spell", spell_id=self._pending_spell or "",
                                           target_group=gi)

    def action_cancel_target(self) -> None:
        if self._phase == "targeting":
            self._phase = "select"
            self._pending_action = None
            self._pending_spell = None
            self._refresh()

    def action_continue(self) -> None:
        """Resolve the round (only if all actions queued)."""
        if self._phase != "select" or self._current_slot < 6:
            return
        # Clear log buffer and run.
        before = len(self.combat.log)
        self.combat.resolve_round(self._actions)
        for line in self.combat.log[before:]:
            self._round_log.append(line)
        outcome = self.combat.is_over()
        if outcome is not None:
            result = self.combat.finish()
            for line in self.combat.log[before:]:
                # already appended; skip duplicates
                pass
            # Append any post-finish lines.
            for line in self.combat.log[len(self._round_log):]:
                self._round_log.append(line)
            self.app.refresh_panels()   # type: ignore[attr-defined]
            self._refresh()
            if self.on_done:
                self.on_done(result)
            self.dismiss()
            return
        # Reset for next round.
        self._actions = [None] * 6
        self._current_slot = 0
        self._advance_to_next_actor()
        self._phase = "select"
        self._refresh()


def _flatten_known(p: S.Character) -> list[str]:
    """Return all spell ids known by this caster, ordered by power."""
    out = []
    # Priest spells typically include direct-damage + heals.  Keep declared order.
    for lvl in range(6, -1, -1):  # prefer higher-level first
        out.extend(p.priest_spells[lvl])
        out.extend(p.mage_spells[lvl])
    return out
