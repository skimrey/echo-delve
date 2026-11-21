"""Loop bookkeeping (FloorPlay), the roguelite run (Run) and persistent progress (Meta)."""

import json
import os
import random
import threading
from dataclasses import dataclass

from .consts import (BASE_ATK, BASE_GHOST_HP, BASE_HP, BASE_SIGHT, BASE_SLOTS, BASE_THREADS, LAMP_REACH, MAX_FLOOR,
                     PERKS, SLOT_CAP, THREADS_PER_FLOOR, UPGRADES)
from .floor import generate_floor
from .score import GRADE_SHARDS, floor_score, grade_for, lamp_bonus, lamp_info, par_turns
from .sim import GhostScript, LoopSim, Mods
from .vision import clear_line, visible_tiles

UNRAVEL_LENGTH = 20      # minutes of the shared thread an unravel cuts (The Long Night)
LAMP_GLOW = 3            # a lit sconce shows the floor this far around it, wherever you are


class FloorPlay:
    """The loops of a single floor: your recorded loops come back as echoes.

    Each loop that ends short of the stairs becomes an echo in a free echo slot. Once every
    slot is full, the next loop is the last: if it also ends short of the stairs the well
    overflows (status "full") and one echo must be unravelled before play can go on.
    """

    def __init__(self, floor, mods, slots):
        self.floor, self.mods, self.slots = floor, mods, slots
        self.scripts = []                # sorted by label
        self.loop_no = 1                 # loops begun on this floor, including restarted ones
        self.status = "playing"          # playing | cleared | full
        self.last_end = None
        self.last_end_pos = None
        self.last_label = None           # label of the most recently recorded echo
        self.turns_spent = 0             # every turn taken on this floor, in every loop (for the score)
        self.sim = LoopSim(floor, [], mods)

    @property
    def last_loop(self):
        """True when every echo slot is taken, so ending this loop short of the stairs overflows."""
        return len(self.scripts) >= self.slots

    def free_label(self):
        """The slot the next recorded loop will take: the lowest unused echo number."""
        used = {s.label for s in self.scripts}
        n = 1
        while n in used:
            n += 1
        return n

    def script(self, label):
        for s in self.scripts:
            if s.label == label:
                return s
        return None

    def act(self, action):
        ev = self.sim.step(action)
        if action[0] != "a":
            self.turns_spent += 1
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
        overflow = self.last_loop
        script = GhostScript(list(self.sim.record), ending, self.free_label(), self.loop_no, self.sim.player.pos,
                             tuple(self.sim.pulls))
        self.scripts.append(script)
        self.scripts.sort(key=lambda s: s.label)
        self.last_label = script.label
        if overflow:
            self.status = "full"
            return
        self._next_loop()

    def _next_loop(self):
        self.loop_no += 1
        self.sim = LoopSim(self.floor, self.scripts, self.mods)

    def unravel(self, label):
        """Erase echo `label`. The past has changed, so a fresh loop begins without it
        (a loop in progress is discarded, not recorded). The next loop you end takes its slot."""
        if self.status == "cleared":
            raise ValueError("the floor is already cleared")
        s = self.script(label)
        if s is None:
            raise ValueError("no echo %r to unravel" % (label,))
        self.scripts.remove(s)
        self.status = "playing"
        self._next_loop()
        return s


@dataclass
class Result:
    events: list
    ended: str          # how the loop ended this call, or None
    message: str        # why nothing happened (a bump costs no turn), or ""


@dataclass
class FloorResult:
    floor: int
    spent: int          # turns taken on the floor, across every loop
    par: int            # par for what you did: the fastest clear that lights as many sconces (score.py)
    score: int
    grade: str
    loops: int
    bonus: int          # bonus shards for the grade
    lamps: int = 0      # sconces lit on the floor
    lamps_total: int = 0
    par_fast: int = 0   # the fastest clear, sconces aside

    @property
    def lamp_points(self):
        return lamp_bonus(self.lamps, self.lamps_total)


class Run:
    def __init__(self, seed=None, perks=None, thread=None, floors=None, prebuilt=None):
        """thread: the shared thread of The Long Night (the time left): every turn spends a minute of
        it, and unravelling an echo cuts UNRAVEL_LENGTH minutes (instead of spending a thread).
        floors: which floors to play, in order (default 1..MAX_FLOOR). prebuilt: {floor: Floor}."""
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        self.thread = thread
        self.guild_pays = False           # The Long Night: Maren took the Guild's bargain (unravels cost nothing)
        self.floor_seq = list(floors or range(1, MAX_FLOOR + 1))
        self.prebuilt = dict(prebuilt or {})
        perks = perks or {}
        self.max_hp = BASE_HP + perks.get("hp", 0)
        self.atk = BASE_ATK + (1 if perks.get("atk", 0) else 0)
        self.slots = min(SLOT_CAP, BASE_SLOTS + perks.get("slots", 0))
        self.limit_bonus = 8 * perks.get("time", 0)
        self.sight = BASE_SIGHT
        self.ghost_hp = BASE_GHOST_HP
        self.threads = BASE_THREADS
        self.rng = random.Random(self.seed * 31 + 7)
        self.floor_no = self.floor_seq[0]
        self.cleared = 0
        self.state = "playing"            # playing | unravel (well full: must unravel an echo) | upgrade | dead | won
        self.reason = ""
        self.options = []
        self.picked = []
        self.seen = set()
        self.lit = set()                  # sconces lit on this floor (they stay lit from loop to loop)
        self.scores = []                  # one FloorResult per cleared floor
        self.bonus_shards = 0             # earned by great floor grades
        self._prefetch = None             # (index, thread, result box) for the next floor
        self.start_floor()

    # -- setup
    def mods(self):
        return Mods(self.atk, self.max_hp, self.ghost_hp, self.limit_bonus)

    def prefetch_next_floor(self):
        """Generate the next floor in the background (it takes up to a couple of seconds on deep
        floors); the victory scene plays meanwhile. Generation is deterministic, so the result is
        identical to generating it on demand."""
        index = self.next_floor_no()
        if index is None or index in self.prebuilt or (self._prefetch and self._prefetch[0] == index):
            return
        box = []
        def work():
            f = generate_floor(self.seed, index)
            lamp_info(f)                          # (and plan its sconces, while we're at it)
            box.append(f)
        t = threading.Thread(target=work, daemon=True)
        t.start()
        self._prefetch = (index, t, box)

    def next_floor_no(self):
        i = self.floor_seq.index(self.floor_no)
        return self.floor_seq[i + 1] if i + 1 < len(self.floor_seq) else None

    @property
    def last_floor(self):
        return self.floor_no == self.floor_seq[-1]

    def _take_floor(self, index):
        if index in self.prebuilt:
            return self.prebuilt[index]
        pf = self._prefetch
        if pf and pf[0] == index:
            pf[1].join()
            self._prefetch = None
            if pf[2]:
                return pf[2][0]
        return generate_floor(self.seed, index)

    def start_floor(self):
        self.floor = self._take_floor(self.floor_no)
        self.play = FloorPlay(self.floor, self.mods(), self.slots)
        self.seen = set()
        self.lit = set()
        self.state = "playing"
        self.light_lamps()

    @property
    def sim(self):
        return self.play.sim

    @property
    def par(self):
        """Par for the current floor (computed once per floor object, so it can never go stale)."""
        f = self.floor
        if getattr(f, "_par_cache", None) is None or f._par_cache[0] is not f:
            f._par_cache = (f, par_turns(f))
        return f._par_cache[1]

    def par_for(self, lamps):
        """Par for a clear that lights `lamps` sconces: the fastest clear if it lights that many
        on its way anyway, and more by what each further sconce is worth (score.LampPlan)."""
        f = self.floor
        mine = getattr(f, "_torch_cache", None)
        if mine is not None and mine[0] is f:                  # (sconces placed by hand: no plan)
            return self.par
        p = lamp_info(f).par_for(lamps)
        return p if p is not None else self.par

    # -- the lamps of the stair
    @property
    def torches(self):
        """The sconces on the current floor: every one can be reached (score.lamp_info)."""
        f = self.floor
        mine = getattr(f, "_torch_cache", None)
        if mine is not None and mine[0] is f:
            return mine[1]
        return lamp_info(f).sconces

    def light_lamps(self, pos=None):
        """Light every cold sconce within LAMP_REACH of `pos` (default: where you stand) with
        nothing solid in between. Lit sconces stay lit for the rest of the floor. Returns the new ones."""
        px, py = self.sim.player.pos if pos is None else pos
        new = []
        for tp in self.torches:
            if tp in self.lit or (tp[0] - px) ** 2 + (tp[1] - py) ** 2 > LAMP_REACH ** 2:
                continue
            if clear_line((px, py), tp, self.sim.blocks_sight):
                self.lit.add(tp)
                new.append(tp)
        return new

    def lamp_glow(self):
        """Tiles shown by the lit sconces: you can see what moves near them from anywhere."""
        out = set()
        for tx, ty in self.lit:
            out |= visible_tiles((tx, ty + 1), LAMP_GLOW, self.sim.blocks_sight)    # from the floor below it
        return out

    # -- acting
    def act(self, action):
        if self.state == "unravel":
            return Result([], None, "Your echo slots are full. Unravel an echo to go on.")
        if self.state != "playing":
            return Result([], None, "The run is not in a playable state.")
        msg = self.sim.validate(action)
        if msg:
            return Result([], None, msg)
        before = self.play.loop_no, self.play.status
        ev = self.play.act(action)
        if self.thread is not None and action[0] != "a":
            self.thread.spend(1)                  # the night does not wait (The Long Night)
        ended = None
        if self.play.status != "playing" or self.play.loop_no != before[0]:
            ended = self.play.last_end
            self.light_lamps(self.play.last_end_pos)      # where the loop ended, before the rewind
        self.light_lamps()
        if self.play.status == "cleared":
            self._floor_cleared()
        elif self.play.status == "full":
            if self.can_afford_unravel():
                self.state = "unravel"
            else:
                self.state = "dead"
                self.reason = ("You fell on your last loop with no threads left to unravel an echo."
                               if ended == "dead" else
                               "Your last loop ended with no threads left to unravel an echo.")
        return Result(ev, ended, "")

    # -- unravelling
    def unravel_problem(self):
        """None when an echo can be unravelled right now, else the reason it can't."""
        if self.state not in ("playing", "unravel"):
            return "There is nothing to unravel right now."
        if not self.play.scripts:
            return "No echoes to unravel yet. End a loop first."
        if not self.can_afford_unravel():
            if self.thread is not None:
                return "The thread is too short: unravelling an echo cuts %d minutes of it." % UNRAVEL_LENGTH
            return "No threads left to unravel an echo. You earn one for each floor you clear."
        return None

    def can_afford_unravel(self):
        if self.guild_pays:
            return True
        if self.thread is not None:
            return self.thread.minutes >= UNRAVEL_LENGTH
        return self.threads > 0

    def thread_left_text(self):
        """What is left to unravel with: minutes of the shared thread, or a count of threads."""
        if self.thread is not None:
            return "%s of thread left" % self.thread.hm()
        return "%d thread%s left" % (self.threads, "" if self.threads == 1 else "s")

    def unravel_cost_short(self):
        if self.guild_pays:
            return "nothing (the Guild pays)"
        return "%d minutes of thread" % UNRAVEL_LENGTH if self.thread is not None else "1 thread"

    def unravel_cost_text(self):
        if self.guild_pays:
            return "The Guild pays for it, as it promised. %s left." % self.thread.hm()
        if self.thread is not None:
            return "Cuts %d minutes of the thread. %s left." % (UNRAVEL_LENGTH, self.thread.hm())
        return "Costs 1 thread. You have %d." % self.threads

    def unravel(self, label):
        """Spend a thread to erase echo `label`; a fresh loop begins without it."""
        problem = self.unravel_problem()
        if problem:
            raise ValueError(problem)
        self.play.unravel(label)
        if self.guild_pays:
            pass                                  # (the Guild sends the slack, as it promised Maren)
        elif self.thread is not None:
            self.thread.spend(UNRAVEL_LENGTH)
        else:
            self.threads -= 1
        self.state = "playing"

    def _floor_cleared(self):
        self.cleared += 1
        if self.thread is None:                   # (in The Long Night the thread is shared, and only
            self.threads += THREADS_PER_FLOOR     #  lengthens when the Guild's hours are let go)
        spent = self.play.turns_spent
        lamps, lamps_total = len(self.lit), len(self.torches)
        par = self.par_for(lamps)
        grade = grade_for(spent, par)
        result = FloorResult(self.floor_no, spent, par, floor_score(spent, par) + lamp_bonus(lamps, lamps_total),
                             grade, self.play.loop_no, GRADE_SHARDS.get(grade, 0), lamps, lamps_total, self.par)
        self.scores.append(result)
        self.bonus_shards += result.bonus
        if not self.last_floor:
            self.prefetch_next_floor()
        if self.last_floor:
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
        self.floor_no = self.next_floor_no()
        self.start_floor()

    @property
    def total_score(self):
        return sum(r.score for r in self.scores)

    @property
    def last_result(self):
        return self.scores[-1] if self.scores else None

    def shards_earned(self):
        return self.cleared + (3 if self.state == "won" else 0) + self.bonus_shards


class Meta:
    """Progress that survives between runs (shards and forge perks)."""

    def __init__(self, path=None):
        self.path = path
        self.data = {"runs": 0, "wins": 0, "best_floor": 0, "shards": 0, "perks": {},
                     "best_score": 0, "seen_intro": False, "seen_intro_stillwater": False,
                     "seen_intro_tick": False, "seen_intro_night": False, "seen_scenes": []}
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
        d["best_score"] = max(d["best_score"], run.total_score)
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
