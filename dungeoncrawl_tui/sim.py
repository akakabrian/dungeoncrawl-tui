"""Core sim — characters, party, dungeon state, combat engine.

Clean-room Wizardry mechanics.  Deterministic given the RNG seed.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from . import data as D
from . import maps as M
from . import tiles as T


# ---- character ----------------------------------------------------------

STAT_KEYS = ("STR", "IQ", "PIE", "VIT", "AGI", "LUC")


@dataclass(eq=False)
class Character:
    name: str
    race: str
    alignment: str
    class_key: str
    level: int = 1
    xp: int = 0
    age: int = 18            # weeks in our simplified model
    hp: int = 0
    hp_max: int = 0
    ac: int = 10
    stats: dict[str, int] = field(default_factory=dict)
    # spell slots per level 1..7, and max slots
    mage_slots: list[int] = field(default_factory=lambda: [0] * 7)
    mage_slots_max: list[int] = field(default_factory=lambda: [0] * 7)
    priest_slots: list[int] = field(default_factory=lambda: [0] * 7)
    priest_slots_max: list[int] = field(default_factory=lambda: [0] * 7)
    # known spell ids per level per school
    mage_spells: list[list[str]] = field(default_factory=lambda: [[] for _ in range(7)])
    priest_spells: list[list[str]] = field(default_factory=lambda: [[] for _ in range(7)])
    # equipment
    weapon: str = ""
    armor: str = ""
    shield: str = ""
    helm: str = ""
    status: list[str] = field(default_factory=list)   # "dead", "poison", "paralyze", "asleep"
    # personal inventory (post-combat loot may go here; for v1 pooled inventory at Sim level)
    personal: list[str] = field(default_factory=list)

    # --- derived ------------------------------------------------------

    def cls(self) -> D.CharClass:
        return D.CLASSES[self.class_key]

    def race_data(self) -> D.Race:
        return D.RACES[self.race]

    def is_alive(self) -> bool:
        return "dead" not in self.status and self.hp > 0

    def can_act(self) -> bool:
        if not self.is_alive():
            return False
        for s in ("paralyze", "asleep", "stoned"):
            if s in self.status:
                return False
        return True

    def weapon_item(self) -> D.Item | None:
        return D.ITEMS.get(self.weapon) if self.weapon else None

    def armor_bonus(self) -> int:
        total = 0
        for slot in (self.armor, self.shield, self.helm):
            if slot and slot in D.ITEMS:
                total += D.ITEMS[slot].power
        return total

    def compute_ac(self) -> int:
        """AC: lower is better.  Base 10 - armor - AGI bonus."""
        ac = 10 - self.armor_bonus()
        # AGI bonus: every 3 AGI above 10 = -1 AC.
        ac -= max(0, (self.stats.get("AGI", 10) - 10) // 3)
        if self.class_key == "N":
            # Ninja gets level-scaling AC bonus even without armor.
            ac -= self.level // 2
        return ac

    def hit_bonus(self) -> int:
        base = (self.stats.get("STR", 10) - 10) // 2
        base += self.level // 3
        if self.class_key in ("F", "S", "L", "N"):
            base += 2
        w = self.weapon_item()
        if w:
            base += w.hit
        return base

    def weapon_damage_roll(self, rng: random.Random) -> int:
        w = self.weapon_item()
        die = w.dmg_die if w else 3
        pwr = w.power if w else 0
        str_bonus = (self.stats.get("STR", 10) - 10) // 3
        return max(1, rng.randint(1, die) + pwr + str_bonus)

    def swings(self) -> int:
        """Number of swings per fight turn."""
        if self.class_key in ("F", "S", "L"):
            return 1 + max(0, self.level // 4)
        if self.class_key == "N":
            return 1 + max(0, self.level // 3)
        return 1

    # --- equip --------------------------------------------------------

    def can_equip(self, item_id: str) -> bool:
        if not item_id or item_id not in D.ITEMS:
            return False
        it = D.ITEMS[item_id]
        if it.kind == "consumable":
            return False
        return bool(set(it.tags) & set(self.cls().can_use))

    def equip(self, item_id: str) -> tuple[bool, str]:
        if not self.can_equip(item_id):
            return False, f"{self.name} can't wield that."
        it = D.ITEMS[item_id]
        if it.kind == "weapon":
            self.weapon = item_id
        elif it.kind == "armor":
            self.armor = item_id
        elif it.kind == "shield":
            self.shield = item_id
        elif it.kind == "helm":
            self.helm = item_id
        else:
            return False, "Not equipable."
        self.ac = self.compute_ac()
        return True, f"{self.name} equips {it.name}."

    # --- spell slots & learning --------------------------------------

    def recompute_slots(self) -> None:
        self.mage_slots_max = D.slots_for_school(self.class_key, self.level, "mage")
        self.priest_slots_max = D.slots_for_school(self.class_key, self.level, "priest")
        # Clamp current slots to max (never boost on recompute — only fill on rest).
        self.mage_slots = [min(c, m) for c, m in zip(self.mage_slots, self.mage_slots_max)]
        self.priest_slots = [min(c, m) for c, m in zip(self.priest_slots, self.priest_slots_max)]

    def learn_default_spells(self) -> None:
        """When a character is created, give them their starting known spells."""
        cls = self.cls()
        if cls.can_cast_mage and self.mage_slots_max[0] > 0:
            # Know all L1 mage spells.
            self.mage_spells[0] = [s.id for s in D.spells_for("mage", 1)]
        if cls.can_cast_priest and self.priest_slots_max[0] > 0:
            self.priest_spells[0] = [s.id for s in D.spells_for("priest", 1)]

    def rest(self, refill_slots: bool = True) -> None:
        """Inn rest — full HP + slots refill + status clear."""
        self.hp = self.hp_max
        if "dead" in self.status:
            self.status.remove("dead")
        for bad in ("poison", "paralyze", "asleep", "silence"):
            while bad in self.status:
                self.status.remove(bad)
        if refill_slots:
            self.mage_slots = list(self.mage_slots_max)
            self.priest_slots = list(self.priest_slots_max)

    # --- level up -----------------------------------------------------

    def grant_xp(self, xp: int, rng: random.Random) -> list[str]:
        msgs: list[str] = []
        self.xp += xp
        while self.xp >= D.xp_to_next(self.level):
            self.xp -= D.xp_to_next(self.level)
            self.level += 1
            hp_gain = rng.randint(1, self.cls().hp_die) + max(0, (self.stats.get("VIT", 10) - 10) // 3)
            hp_gain = max(1, hp_gain)
            self.hp_max += hp_gain
            self.hp += hp_gain
            # Stat change roll: each stat 1-in-4 chance to +1 (Wizardry-ish).
            for s in STAT_KEYS:
                if rng.random() < 0.22:
                    self.stats[s] = min(18, self.stats.get(s, 10) + 1)
            # Learn new spells at the new class level.
            self._maybe_learn_spells()
            # Recompute slots, then fill to new max.
            self.recompute_slots()
            self.mage_slots = list(self.mage_slots_max)
            self.priest_slots = list(self.priest_slots_max)
            self.ac = self.compute_ac()
            msgs.append(f"{self.name} reaches lv {self.level}! (+{hp_gain} HP)")
        return msgs

    def _maybe_learn_spells(self) -> None:
        """Learn new spells at level-up.  Limit 3 per spell-level per school."""
        cls = self.cls()
        # Add all remaining L1 spells at class level 1, then one new spell at
        # each subsequent level, rising up through cap as slots open.
        for school, slots_max, known in (
            ("mage", self.mage_slots_max, self.mage_spells),
            ("priest", self.priest_slots_max, self.priest_spells),
        ):
            for lvl in range(1, 8):
                if slots_max[lvl - 1] <= 0:
                    continue
                pool = D.spells_for(school, lvl)
                already = set(known[lvl - 1])
                for spell in pool:
                    if spell.id not in already and len(known[lvl - 1]) < 3:
                        known[lvl - 1].append(spell.id)


def _roll_stats(rng: random.Random, race_mods: dict[str, int]) -> tuple[dict[str, int], int]:
    """Roll base stats (each 3d6), apply race mods, compute bonus pool.

    Returns (base_stats, bonus_points).  The player assigns bonus_points
    to stats of their choice (per Wizardry character creation).
    """
    stats: dict[str, int] = {}
    for s in STAT_KEYS:
        v = rng.randint(1, 6) + rng.randint(1, 6) + rng.randint(1, 6)
        v += race_mods.get(s, 0)
        stats[s] = max(3, min(18, v))
    # Bonus roll: typically 7-10, with small chance to spike to 17-28
    # (elite classes).
    bonus = 7 + rng.randint(0, 3)
    spike = rng.random()
    if spike < 0.03:
        bonus += 20
    elif spike < 0.10:
        bonus += 10
    return stats, bonus


def make_character(name: str, race: str, alignment: str, class_key: str,
                   stats: dict[str, int], rng: random.Random) -> Character:
    cls = D.CLASSES[class_key]
    c = Character(
        name=name, race=race, alignment=alignment, class_key=class_key,
        stats=dict(stats),
    )
    # HP: start at hp_die + VIT bonus.
    c.hp_max = cls.hp_die + max(0, (stats.get("VIT", 10) - 10) // 2)
    c.hp = c.hp_max
    # Starter gear.
    w = D.STARTER_WEAPONS.get(class_key)
    a = D.STARTER_ARMOR.get(class_key)
    if w:
        c.weapon = w
    if a:
        c.armor = a
    c.ac = c.compute_ac()
    c.recompute_slots()
    c.learn_default_spells()
    return c


def auto_assign_bonus(stats: dict[str, int], bonus: int,
                      class_key: str) -> dict[str, int]:
    """Auto-assign the bonus pool toward the requirements for a target class.

    This is a convenience used by the v1 CharCreate screen — the player
    picks a class; we distribute the bonus toward hitting its minimum
    requirements first, then toward that class's "best" stats.
    """
    cls = D.CLASSES[class_key]
    out = dict(stats)
    pool = bonus
    # Pass 1: meet requirements.
    for stat, need in cls.req.items():
        cur = out.get(stat, 0)
        if cur < need and pool > 0:
            spend = min(pool, need - cur, 18 - cur)
            if spend > 0:
                out[stat] = cur + spend
                pool -= spend
    # Pass 2: dump remainder into the class's priority stat.
    priority = {
        "F": ["STR", "VIT", "AGI"],
        "M": ["IQ", "AGI", "LUC"],
        "P": ["PIE", "VIT", "STR"],
        "T": ["AGI", "LUC", "STR"],
        "B": ["IQ", "PIE", "LUC"],
        "S": ["STR", "VIT", "IQ"],
        "L": ["STR", "PIE", "VIT"],
        "N": ["AGI", "STR", "LUC"],
    }[class_key]
    i = 0
    while pool > 0 and i < 200:
        stat = priority[i % len(priority)]
        cur = out.get(stat, 10)
        if cur < 18:
            out[stat] = cur + 1
            pool -= 1
        i += 1
    return out


# ---- combat -------------------------------------------------------------

@dataclass(eq=False)
class MonsterInstance:
    def_id: str
    hp: int
    hp_max: int
    status: list[str] = field(default_factory=list)

    def cdef(self) -> D.MonsterDef:
        return D.MONSTERS[self.def_id]

    def is_alive(self) -> bool:
        return self.hp > 0 and "dead" not in self.status


@dataclass(eq=False)
class MonsterGroup:
    def_id: str
    members: list[MonsterInstance]

    def alive_members(self) -> list[MonsterInstance]:
        return [m for m in self.members if m.is_alive()]

    def is_alive(self) -> bool:
        return any(m.is_alive() for m in self.members)

    def name(self) -> str:
        n = len(self.alive_members())
        cdef = D.MONSTERS[self.def_id]
        if n <= 1:
            return cdef.name
        return f"{n} {cdef.plural}"


@dataclass(eq=False)
class CombatAction:
    """Queued combat action for a party member."""
    kind: str                    # "fight" | "parry" | "spell" | "use" | "run"
    target_group: int = 0        # for fight / spell_enemy
    target_ally: int = 0         # for spell_ally / heal
    spell_id: str = ""
    item_id: str = ""


@dataclass(eq=False)
class CombatResult:
    outcome: str                 # "win" | "loss" | "flee"
    xp: int = 0
    gold: int = 0
    drops: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


def roll_encounter(rng: random.Random, floor_key: str,
                   forced_id: str = "") -> list[MonsterGroup]:
    """Roll 1-4 monster groups for an encounter on the given floor."""
    if forced_id:
        cdef = D.MONSTERS[forced_id]
        n = rng.randint(cdef.hp_min // 4 or 1, max(1, cdef.hp_min // 3))
        n = max(1, min(3, n))
        return [MonsterGroup(
            forced_id,
            [MonsterInstance(forced_id, rng.randint(cdef.hp_min, cdef.hp_max),
                             cdef.hp_max)
             for _ in range(n)]
        )]
    table = D.ENCOUNTER_TABLES.get(floor_key, [])
    if not table:
        return []
    num_groups = 1 + (1 if rng.random() < 0.45 else 0)   # 1 or 2 usually
    if rng.random() < 0.15:
        num_groups += 1
    groups: list[MonsterGroup] = []
    total_w = sum(w for _, w, _, _ in table)
    for _ in range(min(num_groups, 4)):
        pick = rng.randint(1, total_w)
        running = 0
        chosen = table[0]
        for entry in table:
            running += entry[1]
            if pick <= running:
                chosen = entry
                break
        mid, _w, lo, hi = chosen
        cdef = D.MONSTERS[mid]
        count = rng.randint(lo, hi)
        members = [MonsterInstance(mid, rng.randint(cdef.hp_min, cdef.hp_max),
                                   cdef.hp_max) for _ in range(count)]
        groups.append(MonsterGroup(mid, members))
    return groups


class Combat:
    """Runs one encounter from queued-action round to conclusion."""

    def __init__(self, sim: "Sim", groups: list[MonsterGroup],
                 is_boss: bool = False, boss_name: str = "") -> None:
        self.sim = sim
        self.groups = groups
        self.party = sim.party_active()
        self.log: list[str] = []
        self.is_boss = is_boss
        self.boss_name = boss_name
        self.round_idx = 0
        self._last_run_success = False

    def alive_groups(self) -> list[int]:
        return [i for i, g in enumerate(self.groups) if g.is_alive()]

    def alive_party(self) -> list[int]:
        return [i for i, p in enumerate(self.party) if p.is_alive()]

    def is_over(self) -> str | None:
        if not self.alive_party():
            return "loss"
        if not self.alive_groups():
            return "win"
        return None

    def _get_any_target_in_group(self, group_idx: int) -> MonsterInstance | None:
        if group_idx < 0 or group_idx >= len(self.groups):
            return None
        alive = self.groups[group_idx].alive_members()
        if not alive:
            return None
        return alive[0]

    def resolve_round(self, actions: list[CombatAction | None]) -> None:
        self.round_idx += 1
        rng = self.sim.rng
        init: list[tuple[int, str, int]] = []
        for i, p in enumerate(self.party):
            if p.can_act():
                init.append((p.stats.get("AGI", 10) + rng.randint(1, 5), "p", i))
        for gi, g in enumerate(self.groups):
            if g.is_alive():
                init.append((g.members[0].cdef().agi + rng.randint(1, 5), "m", gi))
        init.sort(key=lambda t: -t[0])

        queued: dict[int, CombatAction] = {}
        for i, act in enumerate(actions):
            if act is not None:
                queued[i] = act

        self._last_run_success = False
        ran = False

        for _init, kind, idx in init:
            if self.is_over() is not None or ran:
                break
            if kind == "p":
                p = self.party[idx]
                if not p.can_act():
                    continue
                act = queued.get(idx)
                if act is None:
                    continue
                self._do_party_action(idx, act)
                if act.kind == "run" and self._last_run_success:
                    ran = True
            else:
                self._do_monster_group(idx)
        # After-round status ticks.
        self._status_tick()

    def _do_party_action(self, i: int, act: CombatAction) -> None:
        p = self.party[i]
        rng = self.sim.rng
        if act.kind == "fight":
            gi = act.target_group
            if gi < 0 or gi >= len(self.groups) or not self.groups[gi].is_alive():
                alive_gs = self.alive_groups()
                if not alive_gs:
                    self.log.append(f"{p.name} swings — nothing left to hit.")
                    return
                gi = alive_gs[0]
            # Front row (slots 0-2) can fight at any group.  Back row (3-5)
            # fight at reduced hit; preserving Wizardry: back row can only
            # fight group 0 at -4 to hit.
            if i >= 3 and gi != 0:
                self.log.append(f"{p.name} is in the back rank — can't reach.")
                return
            self._resolve_physical(p, gi, back_rank=(i >= 3))
        elif act.kind == "parry":
            self.log.append(f"{p.name} braces — armor tightens.")
            p.status.append("parrying")
        elif act.kind == "spell":
            self._resolve_spell(p, act)
        elif act.kind == "use":
            self._resolve_use(p, act)
        elif act.kind == "run":
            self._resolve_run(p)

    def _resolve_physical(self, attacker: Character, gi: int,
                          back_rank: bool = False) -> None:
        rng = self.sim.rng
        group = self.groups[gi]
        target = group.alive_members()[0] if group.alive_members() else None
        if target is None:
            return
        cdef = target.cdef()
        total = 0
        hits = 0
        for _ in range(attacker.swings()):
            if not group.alive_members():
                break
            target = group.alive_members()[0]
            cdef = target.cdef()
            # To-hit: d20 + hit_bonus > 10 + AC (lower AC is harder to hit;
            # we add the difference between 10 and AC to the target number,
            # so a -2 AC is effectively 22 to hit).
            roll = rng.randint(1, 20) + attacker.hit_bonus()
            back_pen = 4 if back_rank else 0
            tgt_num = 10 + (10 - cdef.ac) + back_pen
            if roll < tgt_num:
                continue
            dmg = attacker.weapon_damage_roll(rng)
            total += dmg
            hits += 1
            target.hp -= dmg
            if target.hp <= 0:
                target.hp = 0
                target.status.append("dead")
                # Shift to next alive member of the group (implicitly on next
                # swing since we re-query alive_members()).
        if hits == 0:
            self.log.append(f"{attacker.name} attacks {group.name()} — miss.")
        else:
            fallen = sum(1 for m in group.members if "dead" in m.status)
            self.log.append(
                f"{attacker.name} strikes {group.name()} × {hits} — {total} dmg."
            )
            if not group.is_alive():
                self.log.append(f"  {cdef.name} group falls.")
            elif fallen > 0:
                self.log.append(f"  {fallen} fall.")

    def _resolve_spell(self, caster: Character, act: CombatAction) -> None:
        spl = D.SPELLS.get(act.spell_id)
        if not spl:
            self.log.append(f"{caster.name}: the words slip away.")
            return
        lvl = spl.level
        if spl.school == "mage":
            slot_list = caster.mage_slots
        else:
            slot_list = caster.priest_slots
        if slot_list[lvl - 1] <= 0:
            self.log.append(f"{caster.name}: L{lvl} focus exhausted.")
            return
        slot_list[lvl - 1] -= 1
        rng = self.sim.rng
        # Damage spells.
        if spl.effect == "damage":
            int_bonus = (caster.stats.get("IQ" if spl.school == "mage" else "PIE", 10) - 10) // 2
            base = spl.power + int_bonus
            # Target selection.
            if spl.target == "one_enemy":
                target = self._get_any_target_in_group(act.target_group)
                if target is not None:
                    dmg = max(1, base + rng.randint(0, base // 2))
                    target.hp -= dmg
                    cdef = target.cdef()
                    self.log.append(f"{caster.name} casts {spl.name} — {cdef.name} {dmg} dmg.")
                    if target.hp <= 0:
                        target.hp = 0
                        target.status.append("dead")
                        self.log.append(f"  {cdef.name} falls.")
            elif spl.target == "group_enemy":
                if 0 <= act.target_group < len(self.groups):
                    g = self.groups[act.target_group]
                    self.log.append(f"{caster.name} casts {spl.name} on {g.name()}!")
                    for m in g.alive_members():
                        dmg = max(1, base + rng.randint(0, base // 3))
                        m.hp -= dmg
                        if m.hp <= 0:
                            m.hp = 0
                            m.status.append("dead")
                    self.log.append(f"  group takes damage.")
            elif spl.target == "all_enemy":
                self.log.append(f"{caster.name} casts {spl.name} — all foes!")
                for g in self.groups:
                    for m in g.alive_members():
                        dmg = max(1, base + rng.randint(0, base // 3))
                        m.hp -= dmg
                        if m.hp <= 0:
                            m.hp = 0
                            m.status.append("dead")
            return
        # Heal spells.
        if spl.effect == "heal":
            amount = spl.power + rng.randint(0, spl.power // 2 + 1)
            if spl.target == "one_ally":
                if 0 <= act.target_ally < len(self.party):
                    t = self.party[act.target_ally]
                    heal = min(amount, t.hp_max - t.hp)
                    t.hp += heal
                    self.log.append(f"{caster.name} casts {spl.name} → {t.name} +{heal}.")
            elif spl.target == "all_ally":
                self.log.append(f"{caster.name} casts {spl.name} — party glows.")
                for t in self.party:
                    if t.is_alive():
                        heal = min(amount, t.hp_max - t.hp)
                        t.hp += heal
                        self.log.append(f"  {t.name} +{heal}")
            return
        # Status spells.
        if spl.effect == "status":
            self.log.append(f"{caster.name} casts {spl.name} — the air shifts.")
            tag = {"SNOOZE": "asleep", "QUELL": "dull", "MAZE": "mazed",
                   "DEPORT": "deported", "FEAR": "feared",
                   "SILENCE": "silenced", "PURGE": "purged",
                   "VOID": "dead"}.get(spl.id, "dazed")
            if spl.target == "group_enemy" and 0 <= act.target_group < len(self.groups):
                g = self.groups[act.target_group]
                for m in g.alive_members():
                    if rng.random() < 0.55:
                        m.status.append(tag)
                        if tag == "dead" or tag == "deported":
                            m.hp = 0
            elif spl.target == "all_enemy":
                for g in self.groups:
                    for m in g.alive_members():
                        if rng.random() < 0.35:
                            m.status.append(tag)
            return
        # Buff — v1 minimal: flash a message + mark "buffed".
        if spl.effect == "buff":
            self.log.append(f"{caster.name} casts {spl.name} — allies hum.")
            return
        # Light — flips the sim.dark flag off on current tile.
        if spl.effect == "light":
            self.sim.active_party_light_turns = 20
            self.log.append(f"{caster.name} casts {spl.name} — walls brighten.")
            return
        # Revive — in combat this can rescue a just-fallen ally.
        if spl.effect == "revive":
            if 0 <= act.target_ally < len(self.party):
                t = self.party[act.target_ally]
                if "dead" in t.status:
                    t.status.remove("dead")
                    t.hp = max(1, spl.power)
                    self.log.append(f"{caster.name}: {spl.name} — {t.name} returns!")
            return

    def _resolve_use(self, user: Character, act: CombatAction) -> None:
        iid = act.item_id or "potion"
        inv = self.sim.inventory
        if inv.get(iid, 0) <= 0:
            self.log.append(f"{user.name}: no {iid}.")
            return
        it = D.ITEMS.get(iid)
        if not it:
            return
        self.sim.remove_item(iid, 1)
        if iid == "potion":
            tgt = user if not (0 <= act.target_ally < len(self.party)) else self.party[act.target_ally]
            heal = min(it.power, tgt.hp_max - tgt.hp)
            tgt.hp += heal
            self.log.append(f"{user.name} uses {it.name} → {tgt.name} +{heal}.")
        elif iid == "antidote":
            tgt = user if not (0 <= act.target_ally < len(self.party)) else self.party[act.target_ally]
            if "poison" in tgt.status:
                tgt.status.remove("poison")
                self.log.append(f"{user.name} uses {it.name} → {tgt.name} cured.")

    def _resolve_run(self, runner: Character) -> None:
        rng = self.sim.rng
        if self.is_boss:
            self.log.append(f"{runner.name} tries to flee — but this is no ordinary foe!")
            self._last_run_success = False
            return
        party_agi = max((p.stats.get("AGI", 10) for p in self.party if p.is_alive()), default=10)
        mon_agi = sum(m.cdef().agi for g in self.groups for m in g.alive_members())
        total_mon = max(1, sum(len(g.alive_members()) for g in self.groups))
        mon_avg = mon_agi // total_mon
        if (party_agi + rng.randint(1, runner.level + 1)) * 2 > mon_avg:
            self._last_run_success = True
            self.log.append(f"{runner.name} flees — the party escapes!")
        else:
            self._last_run_success = False
            self.log.append(f"{runner.name} stumbles — can't escape!")

    def _do_monster_group(self, gi: int) -> None:
        g = self.groups[gi]
        rng = self.sim.rng
        for m in g.alive_members():
            if "asleep" in m.status or "paralyze" in m.status or "mazed" in m.status:
                continue
            cdef = m.cdef()
            # Spell?
            if cdef.spells and rng.randint(1, 100) <= cdef.spell_chance:
                spell_id = rng.choice(list(cdef.spells))
                spl = D.SPELLS.get(spell_id)
                if spl:
                    alive = [i for i, p in enumerate(self.party) if p.is_alive()]
                    if not alive:
                        return
                    target_idx = rng.choice(alive)
                    dmg = spl.power + rng.randint(0, spl.power // 2 + 1)
                    self.party[target_idx].hp -= max(1, dmg)
                    self.log.append(
                        f"{cdef.name} casts {spl.name} on "
                        f"{self.party[target_idx].name} — {dmg} dmg."
                    )
                    if self.party[target_idx].hp <= 0:
                        self.party[target_idx].hp = 0
                        self.party[target_idx].status.append("dead")
                        self.log.append(f"{self.party[target_idx].name} falls.")
                    continue
            # Physical.
            alive = [i for i, p in enumerate(self.party) if p.is_alive()]
            if not alive:
                return
            # Prefer front-row targets.
            front_alive = [i for i in alive if i < 3]
            pool = front_alive if front_alive else alive
            target_idx = rng.choice(pool)
            p = self.party[target_idx]
            for _ in range(cdef.swings):
                roll = rng.randint(1, 20) + cdef.hit
                tgt_num = 10 + (10 - p.compute_ac())
                if "parrying" in p.status:
                    tgt_num += 3
                if roll < tgt_num:
                    self.log.append(f"{cdef.name} swings at {p.name} — miss.")
                    continue
                dmg = rng.randint(cdef.dmg_min, cdef.dmg_max)
                dmg = max(1, dmg)
                p.hp -= dmg
                self.log.append(f"{cdef.name} hits {p.name} — {dmg} dmg.")
                if "poison" in cdef.traits and rng.random() < 0.25 and "poison" not in p.status:
                    p.status.append("poison")
                    self.log.append(f"  {p.name} is poisoned!")
                if p.hp <= 0:
                    p.hp = 0
                    p.status.append("dead")
                    self.log.append(f"{p.name} falls.")
                    break

    def _status_tick(self) -> None:
        # Remove parrying (one-round effect).
        for p in self.party:
            while "parrying" in p.status:
                p.status.remove("parrying")
        # Poison damage.
        for p in self.party:
            if p.is_alive() and "poison" in p.status:
                p.hp -= 2
                if p.hp <= 0:
                    p.hp = 0
                    p.status.append("dead")
                    self.log.append(f"{p.name} succumbs to poison.")

    def finish(self) -> CombatResult:
        outcome = self.is_over() or "flee"
        if outcome == "win":
            xp = 0
            gold = 0
            for g in self.groups:
                for m in g.members:
                    cdef = m.cdef()
                    xp += cdef.xp
                    if cdef.gold_max > 0:
                        gold += self.sim.rng.randint(cdef.gold_min, cdef.gold_max)
            survivors = [p for p in self.party if p.is_alive()]
            if survivors:
                each = max(1, xp // len(survivors))
                for p in survivors:
                    for m in p.grant_xp(each, self.sim.rng):
                        self.log.append(m)
            self.sim.gold += gold
            self.log.append(f"Victory! +{xp} xp, +{gold} g.")
            return CombatResult("win", xp=xp, gold=gold, log=list(self.log))
        if outcome == "flee":
            self.log.append("Escaped!")
            return CombatResult("flee", log=list(self.log))
        self.log.append("The party is slain.")
        return CombatResult("loss", log=list(self.log))


# ---- Sim ---------------------------------------------------------------

@dataclass(eq=False)
class Flags:
    andrew_slain: bool = False
    princess_freed: bool = False
    lich_slain: bool = False


@dataclass(eq=False)
class Sim:
    """Top-level state.  One Sim per playthrough."""

    roster: list[Character] = field(default_factory=list)
    # Indices into roster for the active 6-slot party (slots 0-5; 0-2 front, 3-5 back).
    # -1 means empty slot.
    party_slots: list[int] = field(default_factory=lambda: [-1] * 6)
    gold: int = 0           # party pool (Wizardry uses shared gold too)
    inventory: dict[str, int] = field(default_factory=dict)
    flags: Flags = field(default_factory=Flags)
    # location
    in_dungeon: bool = False
    floor_key: str = ""
    grid: list[list[int]] = field(default_factory=list)
    px: int = 0
    py: int = 0
    facing: int = 0        # N=0, E=1, S=2, W=3
    steps: int = 0
    # rng
    seed: int = 0
    rng: random.Random = field(default_factory=random.Random)
    # Light turns remaining for LIGHT spell.
    active_party_light_turns: int = 0
    # UI cross-cutting: message log collected while not in a scene.
    message_log: list[str] = field(default_factory=list)
    # serial that UI watches for map-change redraws
    map_serial: int = 0

    # --- class methods -----------------------------------------------

    @classmethod
    def new_game(cls, seed: int | None = None) -> "Sim":
        s = cls()
        s.seed = seed if seed is not None else random.randrange(2 ** 31)
        s.rng = random.Random(s.seed)
        s.gold = D.STARTER_GOLD
        s.inventory = {"potion": 2, "ration": 3}
        return s

    # --- roster / party -----------------------------------------------

    def add_to_roster(self, ch: Character) -> int:
        if len(self.roster) >= D.MAX_ROSTER:
            return -1
        self.roster.append(ch)
        return len(self.roster) - 1

    def delete_from_roster(self, idx: int) -> bool:
        if not (0 <= idx < len(self.roster)):
            return False
        # Unbind from party slots.
        for i, ri in enumerate(self.party_slots):
            if ri == idx:
                self.party_slots[i] = -1
            elif ri > idx:
                self.party_slots[i] = ri - 1
        del self.roster[idx]
        return True

    def party_active(self) -> list[Character]:
        out = []
        for ri in self.party_slots:
            if 0 <= ri < len(self.roster):
                out.append(self.roster[ri])
        return out

    def set_party(self, roster_indices: list[int]) -> None:
        """Set the active party from up to 6 roster indices."""
        self.party_slots = [-1] * 6
        for i, ri in enumerate(roster_indices[:6]):
            self.party_slots[i] = ri

    # --- movement ------------------------------------------------------

    def enter_dungeon(self, floor_key: str = "B1") -> None:
        grid, start, _ = M.build_floor(floor_key)
        self.grid = grid
        self.floor_key = floor_key
        self.in_dungeon = True
        self.px, self.py = start
        self.facing = T.DIR_N
        self.map_serial += 1

    def leave_dungeon(self) -> None:
        self.in_dungeon = False
        self.floor_key = ""
        self.grid = []
        self.map_serial += 1

    def change_floor(self, new_key: str) -> None:
        grid, start, _ = M.build_floor(new_key)
        self.grid = grid
        self.floor_key = new_key
        # Try to keep same position if passable; else start at stairs.
        if (self.py < len(grid) and self.px < len(grid[0])
                and not T.is_void(grid[self.py][self.px])):
            pass
        else:
            self.px, self.py = start
        self.map_serial += 1

    def forward_cell(self) -> tuple[int, int]:
        dx, dy = T.DIR_DELTA[self.facing]
        return self.px + dx, self.py + dy

    def can_step_forward(self) -> tuple[bool, str]:
        if not self.in_dungeon:
            return False, "not in dungeon"
        c = self.grid[self.py][self.px]
        bit = T.DIR_BIT[self.facing]
        if T.has_door(c, bit):
            return True, ""
        if T.has_wall(c, bit):
            return False, "wall"
        return True, ""

    def step_forward(self) -> tuple[bool, str, str]:
        """Try step forward.  Returns (moved, flash_msg, event).

        Event can be: "" / "encounter" / "stairs_up" / "stairs_down" /
        "exit" / "chute" / "spinner" / "teleport" / "pit" / "boss".
        """
        ok, msg = self.can_step_forward()
        if not ok:
            return False, msg, ""
        nx, ny = self.forward_cell()
        if not (0 <= nx < len(self.grid[0]) and 0 <= ny < len(self.grid)):
            return False, "edge", ""
        if T.is_void(self.grid[ny][nx]):
            return False, "void", ""
        self.px, self.py = nx, ny
        self.steps += 1
        if self.active_party_light_turns > 0:
            self.active_party_light_turns -= 1
        feat = T.feature(self.grid[ny][nx])
        event = ""
        if feat == T.FEAT_CHUTE:
            event = "chute"
        elif feat == T.FEAT_SPINNER:
            self.facing = self.rng.randint(0, 3)
            event = "spinner"
        elif feat == T.FEAT_TELEPORT:
            event = "teleport"
        elif feat == T.FEAT_PIT:
            event = "pit"
        elif feat == T.FEAT_BOSS:
            event = "boss"
        # Encounter roll (per-step probability).
        if event == "":
            rate = 10 if self.in_dungeon else 0
            if self.rng.randint(1, 100) <= rate:
                event = "encounter"
        return True, "", event

    def step_back(self) -> tuple[bool, str]:
        """Step backward one tile (doesn't rotate; classic Wizardry allows
        backstep).  Returns (moved, msg)."""
        back = T.dir_back(self.facing)
        bit = T.DIR_BIT[back]
        c = self.grid[self.py][self.px]
        if T.has_wall(c, bit) and not T.has_door(c, bit):
            return False, "wall"
        dx, dy = T.DIR_DELTA[back]
        nx, ny = self.px + dx, self.py + dy
        if not (0 <= nx < len(self.grid[0]) and 0 <= ny < len(self.grid)):
            return False, "edge"
        if T.is_void(self.grid[ny][nx]):
            return False, "void"
        self.px, self.py = nx, ny
        self.steps += 1
        return True, ""

    def turn_left(self) -> None:
        self.facing = T.dir_left(self.facing)

    def turn_right(self) -> None:
        self.facing = T.dir_right(self.facing)

    def current_feature(self) -> int:
        if not self.in_dungeon:
            return 0
        return T.feature(self.grid[self.py][self.px])

    # --- inventory -----------------------------------------------------

    def add_item(self, item_id: str, qty: int = 1) -> None:
        self.inventory[item_id] = self.inventory.get(item_id, 0) + qty
        if self.inventory[item_id] <= 0:
            del self.inventory[item_id]

    def remove_item(self, item_id: str, qty: int = 1) -> bool:
        if self.inventory.get(item_id, 0) < qty:
            return False
        self.add_item(item_id, -qty)
        return True

    # --- save / load ---------------------------------------------------

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "version": 1,
            "seed": self.seed,
            "rng_state": _rng_state(self.rng),
            "gold": self.gold,
            "inventory": dict(self.inventory),
            "roster": [asdict(c) for c in self.roster],
            "party_slots": list(self.party_slots),
            "flags": asdict(self.flags),
            "in_dungeon": self.in_dungeon,
            "floor_key": self.floor_key,
            "px": self.px, "py": self.py, "facing": self.facing,
            "steps": self.steps,
        }
        return d

    def save_to(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1))
        return path

    @classmethod
    def from_dict(cls, d: dict) -> "Sim":
        s = cls()
        s.seed = d.get("seed", 0)
        s.rng = random.Random()
        st = d.get("rng_state")
        if st:
            _rng_restore(s.rng, st)
        s.gold = d.get("gold", 0)
        s.inventory = dict(d.get("inventory", {}))
        for cd in d.get("roster", []):
            ch = Character(**cd)
            s.roster.append(ch)
        ps = d.get("party_slots", [-1] * 6)
        s.party_slots = list(ps) + [-1] * (6 - len(ps))
        flags_d = d.get("flags", {})
        s.flags = Flags(**{k: v for k, v in flags_d.items()
                           if k in Flags.__dataclass_fields__})
        if d.get("in_dungeon"):
            s.enter_dungeon(d.get("floor_key", "B1"))
            s.px = d.get("px", s.px)
            s.py = d.get("py", s.py)
            s.facing = d.get("facing", s.facing)
        s.steps = d.get("steps", 0)
        return s

    @classmethod
    def load_from(cls, path: Path) -> "Sim":
        return cls.from_dict(json.loads(Path(path).read_text()))


def _rng_state(rng: random.Random):
    st = rng.getstate()
    return (st[0], list(st[1]), st[2])


def _rng_restore(rng: random.Random, data):
    v, internal, gnext = data
    rng.setstate((v, tuple(internal), gnext))
