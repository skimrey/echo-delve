"""Loop bookkeeping (FloorPlay), the roguelite run (Run) and persistent progress (Meta)."""

import json
import os
import random
from dataclasses import dataclass

from .consts import (BASE_ATK, BASE_GHOST_HP, BASE_HP, BASE_SIGHT, BASE_SLOTS, MAX_FLOOR, PERKS,
                     SLOT_CAP, UPGRADES)
from .floor import generate_floor
from .sim import GhostScript, LoopSim, Mods


class FloorPlay:
    """The loops of a single floor: your recorded loops come back as echoes."""

    def __init__(self, floor, mods, loops_max):
        self.floor, self.mods, self.loops_max = floor, mods, loops_max
        self.scripts = []
        self.loop_no = 1
        self.status = "playing"          # playing | cleared | failed
        self.last_end = None
        self.last_end_pos = None
        self.sim = LoopSim(floor, [], mods)

    def act(self, action):
        ev = self.sim.step(action)
        if self.sim.over:
            self._end_loop()
        return ev

    def _end_loop(self):
        over = self.sim.over
        self.last_end = over
        self.last_end_pos = self.sim.player.pos
        if over == "exit":
            self.status = "cleared"
            return
        ending = "dead" if over == "dead" else "anchor"
        self.scripts.append(GhostScript(list(self.sim.record), ending, len(self.scripts) + 1))
        if self.loop_no >= self.loops_max:
            self.status = "failed"
            return
        self.loop_no += 1
        self.sim = LoopSim(self.floor, self.scripts, self.mods)


@dataclass
class Result:
    events: list
    ended: str          # how the loop ended this call, or None
    message: str        # why nothing happened (a bump costs no turn), or ""


class Run:
    def __init__(self, seed=None, perks=None):
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        perks = perks or {}
        self.max_hp = BASE_HP + perks.get("hp", 0)
        self.atk = BASE_ATK + (1 if perks.get("atk", 0) else 0)
        self.slots = min(SLOT_CAP, BASE_SLOTS + perks.get("slots", 0))
        self.limit_bonus = 8 * perks.get("time", 0)
        self.sight = BASE_SIGHT
        self.ghost_hp = BASE_GHOST_HP
        self.rng = random.Random(self.seed * 31 + 7)
        self.floor_no = 1
        self.cleared = 0
        self.state = "playing"            # playing | upgrade | dead | won
        self.reason = ""
        self.options = []
        self.picked = []
        self.seen = set()
        self.start_floor()

    # -- setup
    def mods(self):
        return Mods(self.atk, self.max_hp, self.ghost_hp, self.limit_bonus)

    def start_floor(self):
        self.floor = generate_floor(self.seed, self.floor_no)
        self.play = FloorPlay(self.floor, self.mods(), self.slots + 1)
        self.seen = set()
        self.state = "playing"

    @property
    def sim(self):
        return self.play.sim

    # -- acting
    def act(self, action):
        if self.state != "playing":
            return Result([], None, "The run is not in a playable state.")
        msg = self.sim.validate(action)
        if msg:
            return Result([], None, msg)
        before = self.play.loop_no, self.play.status
        ev = self.play.act(action)
        ended = None
        if self.play.status != "playing" or self.play.loop_no != before[0]:
            ended = self.play.last_end
        if self.play.status == "cleared":
            self._floor_cleared()
        elif self.play.status == "failed":
            self.state = "dead"
            self.reason = ("You fell with no echoes left." if ended == "dead"
                           else "The last loop collapsed with no echoes left.")
        return Result(ev, ended, "")

    def _floor_cleared(self):
        self.cleared += 1
        if self.floor_no >= MAX_FLOOR:
            self.state = "won"
            return
        pool = [k for k in UPGRADES if not (k == "slot" and self.slots >= SLOT_CAP)]
        self.options = self.rng.sample(pool, 3)
        self.state = "upgrade"

    def apply_upgrade(self, key):
        if self.state != "upgrade" or key not in self.options:
            raise ValueError("no such upgrade on offer")
        if key == "hp":
            self.max_hp += 2
        elif key == "atk":
            self.atk += 1
        elif key == "slot":
            self.slots = min(SLOT_CAP, self.slots + 1)
        elif key == "time":
            self.limit_bonus += 12
        elif key == "sight":
            self.sight += 2
        elif key == "guard":
            self.ghost_hp += 2
        self.picked.append(key)
        self.floor_no += 1
        self.start_floor()

    def shards_earned(self):
        return self.cleared + (3 if self.state == "won" else 0)


class Meta:
    """Progress that survives between runs (shards and forge perks)."""

    def __init__(self, path=None):
        self.path = path
        self.data = {"runs": 0, "wins": 0, "best_floor": 0, "shards": 0, "perks": {}}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    for k in self.data:
                        if k in loaded and type(loaded[k]) is type(self.data[k]):
                            self.data[k] = loaded[k]
            except (OSError, ValueError):
                pass

    def save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.data, f)
        except OSError:
            pass

    def record(self, run):
        d = self.data
        d["runs"] += 1
        d["wins"] += 1 if run.state == "won" else 0
        d["best_floor"] = max(d["best_floor"], run.cleared)
        d["shards"] += run.shards_earned()
        self.save()

    def level(self, perk):
        return self.data["perks"].get(perk, 0)

    def cost(self, perk):
        return PERKS[perk][3] + 2 * self.level(perk)

    def can_buy(self, perk):
        return self.level(perk) < PERKS[perk][2] and self.data["shards"] >= self.cost(perk)

    def buy(self, perk):
        if not self.can_buy(perk):
            return False
        self.data["shards"] -= self.cost(perk)
        self.data["perks"][perk] = self.level(perk) + 1
        self.save()
        return True
