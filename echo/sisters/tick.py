"""THE TICK (prototype): the clock tower above Hollowmere, on the same night as Echo Delve.

The world
- The Tick is Hollowmere's great clock, the seat of the Guild of Hours; the day's golden thread comes
  up out of the Deep and winds onto its brass drum. When the thread snapped, the last day it carried
  was half wound on. The Guild kept it: a HOARD of hours, sold back to the town by the minute.
- There is only ever one day: each night the Loom unpicks the old day and weaves the next from the
  same thread. If the thread is tied, the Loom takes back everything left of the old day, the hoard with it. So the
  Guild keeps the night: as long as it lasts they hold the only light left, and whoever holds the
  only hours decides what happens in them.
- The Guild spends its hours through the REGULATOR, a pocket watch. Whoever holds it can turn the
  tower's hours back around themselves while they stay exactly where they are.
- The thread is the time that is left: what the Guild has not taken. For years they wound a little
  off every day onto their drum, thinning it, until it snapped under the weight of a day. In The
  Long Night the thread is shared by everyone; every hour of the Guild's let go lengthens it.
- Maren Vell, the lamplighter's daughter, should have carried her mother's lantern into the Deep.
  She had seen the stair take people. She put the lantern into her brother Aurel's hands on the
  doorstep and ran, telling herself he would never be fool enough to go down. Since then she has
  bought her light by the minute from the Guild, like everyone else. Tonight (her PROLOGUE) she
  steals the Regulator FOR HERSELF, to leave Hollowmere and carry her own day with her. The alarm
  bars the doors below; the only way out of the Tick is up, through the works, past the Drum Room,
  to the roof. On the way she learns (BEATS, INTERLUDES) that someone has taken up the broken end
  and is carrying it down, and who; and that the Guild feels every tug on the thread and is afraid.
  In the Drum Room she decides who the hoard is for. Until then, saving time reads either way.

The rules (deterministic)
- Everything in the tower is clockwork: wardens walk fixed rounds, gear doors open on fixed ticks.
  The tower's state is a pure function of its clock, the tick. Moving or waiting advances it.
- Tiles: '#' wall, '.' floor, 'S' start, 'X' the stair up, 'W' a watch to pick up (unused), 'r' an hour
  reel (+REEL minutes), '1'..'4' gear doors. A door is either ("once", start, length): open only
  on ticks start..start+length-1, or ("every", period, open_for, phase).
- Rewinding (with the watch) turns the tick back by one and costs a minute of the hoard; you stay
  put. Not past tick 0, and not while standing in a door that was shut then.
- Wardens see a cone ahead of their lantern (RANGE deep, widening), blocked by walls and shut doors.
  Being seen at any tick you pass through, including while rewinding, or walking into a warden, or
  still being on the floor when the Quarter Bell rings, means you are caught.
- Caught with the watch and enough hoard: the watch snaps you and the tower back SNAP_STEPS moves
  (SNAP_COST minutes). Otherwise the floor starts over; the minutes already spent stay spent.
"""

import random
import threading
from collections import deque
from dataclasses import dataclass

RANGE = 5
REEL = 8
SNAP_STEPS = 4
SNAP_COST = 6
HOARD = 60               # minutes the run starts with
GENERATED = 4            # floors after the handwritten ones
T_MAX = 170              # the solver never looks past this tick

TITLE = "The Tick"
HERO = "Maren Vell"
TAGLINE = "The whole tower keeps time. You have stolen the watch that spends it."

INTRO = [
    ("town", "Hollowmere, the three hundred and twelfth night without a morning. Over the rooftops stands the "
             "Tick, the Guild's great clock, and high inside it a brass drum, wound with the last day there was."),
    ("summer", "It began as a kindness. When the thread was thick and summer evenings lasted until midnight, the "
               "Guild of Hours kept a little of each long day back, on that drum."),
    ("winter", "And in winter, when the days were short and the nights were long, they sold it back to the town a "
               "lampful at a time. But thread burned in a lamp never goes back to the Loom. Every morning was woven "
               "from a little less, the shorter days sold more lamps, and the thread wore thin, and broke."),
    ("clock", "Half a day was caught on the drum when it broke. A day is a great deal of light, and sold by the "
              "minute, half of one lasts for years. No morning has come since, and the price of an hour goes up every "
              "night."),
    ("ledgers", "There is only ever one day: each night the Loom unpicks the old one and weaves the next from the same "
                "thread. Mend it, and the Loom will take the hoard back too. So the Guild keeps the night. They have "
                "done the arithmetic: there is enough on the drum to keep them warm for the rest of their lives."),
    ("doorstep", "You are Maren Vell. When your mother didn't come back from the Deep, her lantern came to you, the "
                 "way it always comes to the daughter. You had seen the stair. You put the lantern in your "
                 "brother's hands and ran, and told yourself he would never be fool enough to go down."),
    ("clerk", "In a town without mornings, the only people hiring were the people selling the light. For a year "
              "you have kept the Guild's books in the Counting House, a minute at a time, and watched the "
              "Guildmaster take out a pocket watch whenever a delivery ran late, and turn the whole tower back."),
    ("watch", "The Regulator. Wind it back, and the tower turns backwards around whoever holds it, wardens and gears "
              "and all, while they stand still. Every tick of it is a minute of the Guild's hoard, spent."),
    ("counting_house", "You have planned it for months. Tonight, when the last clerk has gone home, you take it from "
                       "his desk: the watch, and every hour it can reach. Enough to leave Hollowmere, and carry your "
                       "own day with you."),
    ("tick_stair", "You did not know the watch was tied to the bell. Below you it begins to ring, and the doors of the "
                   "Tick are barred. There is only one way out now: up, through the works, past the drum, to the "
                   "roof."),
]

# The Long Night: the world has already been told, so Maren's own chapter begins at the door.
PROLOGUE = INTRO[5:]

# told before a floor (by its index, or "last" for the Drum Room), here and in The Long Night
INTERLUDES = {
    2: [
        ("clock_window", "From behind one of the great clock faces the whole of Hollowmere lies below you: a few "
                         "lamps, bought by the minute, and the black mouth of the Deep. On the stair inside it, the "
                         "first sconce is burning."),
        ("clock_window", "Nobody has lit it since your mother went down. You tell yourself it could be anyone. You "
                         "don't look at it again."),
    ],
    "last": [
        ("drum", "The Drum Room. The last day hangs wound on the great drum, humming. The thread runs off it and down "
                 "through the floor, taut, twitching: pulled a step at a time by someone far below."),
        ("drum_master", "The Guildmaster is waiting by the brake. He does not call the wardens. 'You don't know what "
                        "you're holding,' he says. 'Open that, and the thread will take every hour of it, and your "
                        "brother with it. It has a way of tying people down.'"),
        ("drum_master", "'Leave the brake to us. We will send him what he needs to tie it, and not a minute more "
                        "for him to lose himself in. He comes home. You keep the watch, and go wherever you like, "
                        "warm. All we ask for is the ledger.' He holds out his hand. Somewhere below, the thread "
                        "twitches."),
    ],
}

# what Maren learns as she climbs, told on the card after each floor. She steals the watch for
# herself: nobody comes back from the Deep, so this is all the time there is. On the way up she
# finds out who is on the other end of the thread. Until the Drum Room, "saving time" could mean
# either thing; the choice there decides which.
BEATS = [
    "The watch ticks against your pulse, out of step with the tower. Behind you the Counting House fills with "
    "lanterns. Nobody comes back from the Deep. This is all the time there is.",
    "In the archive above the Counting House, where clerks are never sent, a ledger lies open, in a careful hand: "
    "'The broken end has been taken up from the first landing. It is going down the stair. Watch the drum.' The "
    "pages go back for generations: every hour kept back, every day, and what it sold for. You kept their books "
    "for a year and never saw these. You take it with you. You are not sure why.",
    "Through a grate you glimpse the drum's great axle. It shudders, and turns a notch the wrong way. Something "
    "far below is pulling.",
    "The wardens walk faster now. The Guild can feel every tug on the thread, and they are afraid of the day it "
    "might bring.",
    "Every tick you wind back, the drum turns a little the wrong way, and somewhere far below the thread goes "
    "slack in his hand.",
]


def duration(minutes):
    """'5 hours and 10 minutes', '40 minutes'."""
    h, m = divmod(int(minutes), 60)
    if not h:
        return "%d minute%s" % (m, "" if m == 1 else "s")
    hours = "%d hour%s" % (h, "" if h == 1 else "s")
    return hours if not m else "%s and %d minute%s" % (hours, m, "" if m == 1 else "s")


def beat(floor_index):
    """The story told after clearing floor `floor_index` (0-based)."""
    return BEATS[min(floor_index, len(BEATS) - 1)]


ENDING_RELEASE = ("You don't answer him. You open the brake. The hoard unwinds, every hour the Guild has left, and pours "
                  "down the thread into the Deep. Somewhere far below, your brother feels the slack in his hand. You climb out "
                  "onto the roof and down the old lamplighters' ladder on the outside of the Tick, that nobody has "
                  "used since the Guild took the lamps, with nothing in your hands but the Guild's ledger.")
ENDING_BARGAIN = ("You give him the ledger. He closes his hand around it, and sends a little slack down the thread: "
                  "enough, he says. A Guild coach takes you to the edge of Hollowmere with the watch ticking warm "
                  "against your pulse. You do not look back at the Tick. You are not sure you could stand to.")
ENDING_SPENT = "The hoard is spent. The wardens find you on the stair, holding a watch that will not turn."

FLOORS = [
    dict(name="The Counting House",
         hint="The watch is in your hand and the alarm is ringing: reach the stair up (X) unseen. Wardens see in "
              "a cone ahead of their lanterns. Moving or waiting turns the tower's clock; wait for a back to turn.",
         rows=[
             "##############################",
             "#S.......#########...........#",
             "#........#########...........#",
             "#........#########...........#",
             "#............................#",
             "#............................#",
             "#........#########...........#",
             "#........#########.........X.#",
             "##############################",
         ],
         guards=[([(8, 4), (20, 4), (20, 5), (8, 5)], 0)], doors={}, bell=None),
    dict(name="The Escapement",
         hint="Door 1 opens once, on tick 15, and you cannot reach it by then. Walk up to it anyway. Then hold Q: "
              "the Regulator winds the whole tower back, tick by tick, while you stay put. Stop when it reads 15, "
              "and step through. Each tick costs a minute of the hoard.",
         rows=[
             "##############################",
             "#S...........................#",
             "############################1#",
             "#X...........................#",
             "##############################",
         ],
         guards=[], doors={"1": ("once", 15, 2)}, bell=None),
    dict(name="The Quarter Bell",
         hint="The Quarter Bell rings on tick 70: be gone by then. Rewinding walks the wardens backwards too, so "
              "choose where you stand before you turn the clock. Use [ and ] to look at other ticks for free; "
              "Enter winds the tower to the tick you are looking at.",
         rows=[
             "##############################",
             "#S.....#.....................#",
             "#......#.....................#",
             "#............................#",
             "#......#......#####......##1##",
             "#......#......#####......#.X.#",
             "##############################",
         ],
         guards=[([(8, 1), (28, 1), (28, 3), (8, 3)], 0)], doors={"1": ("once", 12, 2)}, bell=70),
]

FLOOR_NAMES = ["The Pendulum Hall", "The Chime Loft", "The Gearworks", "The Ledger Stair", "The Escapement Gallery",
               "The Regulator", "The Weight Room", "The Hour Hall"]
FINAL_NAME = "The Drum Room"


def _expand(waypoints):
    """Waypoints (looped) -> one position per tick, walking straight lines between them."""
    out = []
    n = len(waypoints)
    for i in range(n):
        (x0, y0), (x1, y1) = waypoints[i], waypoints[(i + 1) % n]
        dx = (x1 > x0) - (x1 < x0)
        dy = (y1 > y0) - (y1 < y0)
        x, y = x0, y0
        while (x, y) != (x1, y1):
            out.append((x, y))
            x, y = x + dx, y + dy
    return out or [waypoints[0]]


@dataclass
class Guard:
    route: list
    phase: int = 0

    def at(self, t):
        return self.route[(t + self.phase) % len(self.route)]

    def facing(self, t):
        n = len(self.route)
        for k in range(n):
            a = self.route[(t + self.phase - k) % n]
            b = self.route[(t + self.phase - k + 1) % n]
            if a != b:
                return (b[0] - a[0], b[1] - a[1])
        return (1, 0)


class TickLevel:
    def __init__(self, spec):
        self.name, self.hint = spec["name"], spec.get("hint", "")
        self.bell = spec.get("bell")
        rows = spec["rows"]
        self.size = (max(len(r) for r in rows), len(rows))
        self.walls, self.doors, self.reels = set(), {}, set()
        self.start = self.goal = self.watch = None
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    self.walls.add((x, y))
                elif ch == "S":
                    self.start = (x, y)
                elif ch == "X":
                    self.goal = (x, y)
                elif ch == "W":
                    self.watch = (x, y)
                elif ch == "r":
                    self.reels.add((x, y))
                elif ch in "1234":
                    self.doors[(x, y)] = (ch,) + tuple(spec["doors"][ch])
        self.guards = [Guard(_expand(w), ph) for w, ph in spec["guards"]]
        self.min_cost = spec.get("min_cost", 0)
        assert self.start and self.goal, self.name

    def door_open(self, pos, t):
        d = self.doors[pos]
        if d[1] == "once":
            return d[2] <= t < d[2] + d[3]
        _, _, period, open_for, phase = d
        return (t + phase) % period < open_for

    def door_label(self, pos):
        d = self.doors[pos]
        if d[1] == "once":
            return "opens once, tick %d" % d[2] if d[3] == 1 else "open once, ticks %d-%d" % (d[2], d[2] + d[3] - 1)
        return "opens every %d ticks" % d[2]


class Tick:
    """One attempt at one floor. The run's hoard is passed in and handed back."""

    def __init__(self, level, hoard=HOARD, has_watch=True):
        self.level = level
        self.t = 0
        self.player = level.start
        self.hoard = hoard
        self.has_watch = has_watch and level.watch is None
        self.reels = set(level.reels)
        self.history = []            # (player, t) before each move/wait/rewind, for the snap-back
        self.over = None             # None | "caught" | "out"
        self.caught_by = None
        self.spent = 0               # minutes spent on this floor (rewinds and snaps)
        self.events = []

    # ---------------------------------------------------------------- the clockwork
    def door_open(self, pos, t=None):
        return self.level.door_open(pos, self.t if t is None else t)

    def door_shut(self, pos, t=None):
        return pos in self.level.doors and not self.door_open(pos, t)

    def next_opening(self, pos, t=None):
        t = self.t if t is None else t
        for k in range(T_MAX * 2):
            if self.door_open(pos, t + k):
                return t + k
        return None

    def blocks_sight(self, p, t):
        return p in self.level.walls or self.door_shut(p, t)

    def sight(self, g, t):
        """Tiles warden g sees at tick t: a cone RANGE deep, widening by one every two tiles."""
        gx, gy = g.at(t)
        fx, fy = g.facing(t)
        out = set()
        for k in range(1, RANGE + 1):
            for lat in range(-(k // 2), k // 2 + 1):
                p = (gx + fx * k - fy * lat, gy + fy * k + fx * lat)
                if p in self.level.walls or not self._clear((gx, gy), p, t):
                    continue
                out.add(p)
        return out

    def _clear(self, a, b, t):
        (x0, y0), (x1, y1) = a, b
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
        err = dx - dy
        while (x0, y0) != (x1, y1):
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
            if (x0, y0) != (x1, y1) and self.blocks_sight((x0, y0), t):
                return False
        return True

    def seen_at(self, p, t):
        """The index of a warden that catches someone standing at p on tick t, or None."""
        for i, g in enumerate(self.level.guards):
            if g.at(t) == p or p in self.sight(g, t):
                return i
        return None

    # ---------------------------------------------------------------- acting
    def validate(self, action):
        if self.over:
            return "This attempt is over."
        kind = action[0]
        if kind == "m":
            q = (self.player[0] + action[1], self.player[1] + action[2])
            if q in self.level.walls:
                return "A wall. The tower does not care how late you are."
            if self.door_shut(q):
                n = self.next_opening(q)
                c = self.level.doors[q][0]
                if n is None or n > T_MAX:
                    return "Door %s is shut, and will not open again. Wind the tower back to when it was." % c
                return "Door %s is shut. It opens on tick %d." % (c, n)
        elif kind == "r":
            if not self.has_watch:
                return "You need the Regulator to turn the tower back."
            if self.t <= 0:
                return "The tower's clock is at tick 0, when you walked in; it winds back no further."
            if self.hoard <= 0:
                return "The hoard is empty. The watch will not turn."
            if self.door_shut(self.player, self.t - 1):
                return "You are standing in a door that was shut then. Step out first."
        return None

    def step(self, action):
        """("m", dx, dy) move | ("w",) wait | ("r",) rewind one tick."""
        msg = self.validate(action)
        if msg:
            raise ValueError(msg)
        self.events = ev = []
        self.history.append((self.player, self.t))
        kind = action[0]
        if kind == "m":
            old = self.player
            self.player = (old[0] + action[1], old[1] + action[2])
            self.t += 1
            for i, g in enumerate(self.level.guards):          # walking through a warden
                if g.at(self.t) == old and g.at(self.t - 1) == self.player:
                    return self._caught(i, ev)
            if self.player in self.reels:
                self.reels.discard(self.player)
                self.hoard += REEL
                ev.append(("reel", self.player, REEL))
            if self.player == self.level.watch and not self.has_watch:
                self.has_watch = True
                ev.append(("watch",))
        elif kind == "w":
            self.t += 1
        else:
            self.t -= 1
            self.hoard -= 1
            self.spent += 1
            ev.append(("rewind", self.t))
        i = self.seen_at(self.player, self.t)
        if i is not None:
            return self._caught(i, ev)
        if self.level.bell is not None and self.t >= self.level.bell and self.player != self.level.goal:
            return self._caught(-1, ev)
        if self.player == self.level.goal and (self.has_watch or self.level.watch is None):
            self.over = "out"
            ev.append(("out",))
        return ev

    def _caught(self, who, ev):
        """Seen (or the bell): snap back if the watch and the hoard allow it, else the attempt is over."""
        if self.has_watch and self.hoard >= SNAP_COST and self.history:
            back = self.history[max(0, len(self.history) - SNAP_STEPS)]
            del self.history[max(0, len(self.history) - SNAP_STEPS):]
            self.player, self.t = back
            self.hoard -= SNAP_COST
            self.spent += SNAP_COST
            ev.append(("snapback", who, SNAP_COST))
            return ev
        self.over = "caught"
        self.caught_by = who
        ev.append(("caught", who))
        return ev


# ---------------------------------------------------------------------- the run

class TickRun:
    def __init__(self, seed=None, thread=None, generated=GENERATED, prebuilt=None):
        """clock: the shared clock of The Long Night; every move or wait spends a minute of it (the
        hoard is separate: Maren's own). generated: floors after the handwritten ones."""
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        self.thread = thread
        self.generated = generated
        self.prebuilt = dict(prebuilt or {})
        self.index = 0
        self.hoard = HOARD
        self.has_watch = True       # (stolen before the first floor: see PROLOGUE)
        self.state = "playing"      # playing | climbed | spent
        self.results = []
        self._level = self._build(0)
        self._pending = None        # (thread, box): the next floor, built in the background

    @property
    def floors(self):
        return len(FLOORS) + self.generated

    def on_action(self, action):
        """Moving or waiting in the tower spends the shared thread (winding back spends the hoard)."""
        if self.thread is not None and action[0] in ("m", "w"):
            self.thread.spend(1)

    def on_step(self, action, events, sim):
        """After each step (The Long Night): time passes, and any hour reel Maren cuts loose
        unspools into the thread itself, for everyone, instead of into her watch."""
        self.on_action(action)
        if self.thread is None:
            return
        for e in events:
            if e[0] == "reel":
                sim.hoard -= e[2]
                self.thread.give(e[2])

    @property
    def level(self):
        if self._pending is not None:
            thread, box = self._pending
            thread.join()
            self._pending = None
            self._level = box[0]
        return self._level

    def _build(self, index):
        if index in self.prebuilt:
            return self.prebuilt[index]
        if index < len(FLOORS):
            lv = TickLevel(FLOORS[index])
            lv.min_cost = solve_cost(lv) or 0
            return lv
        return generate_floor(self.seed, index, final=index == self.floors - 1)

    def begin(self):
        return Tick(self.level, self.hoard, self.has_watch or self.index > 0)

    def settle(self, sim):
        """After an attempt: keep what the hoard now holds. Returns False if the run is lost."""
        self.hoard = sim.hoard
        self.has_watch = self.has_watch or sim.has_watch
        if sim.over == "out":
            self.results.append((self.level.name, sim.spent))
            self.index += 1
            if self.index >= self.floors:
                self.state = "climbed"
            else:                               # build the next floor while the player reads the card
                box, index = [], self.index
                thread = threading.Thread(target=lambda: box.append(self._build(index)), daemon=True)
                thread.start()
                self._pending = (thread, box)
        elif self.hoard < self.level.min_cost:
            self.state = "spent"
        return self.state != "spent"


# ---------------------------------------------------------------------- solving

def solve(level, has_watch=True, t_max=None, return_cost=False):
    """Cheapest way up (fewest minutes of the hoard, then fewest actions), ignoring snap-backs
    and reels: a search over (position, tick, holding the watch) where moving and waiting are free
    and rewinding costs a minute. has_watch=False on a floor without the watch to pick up means
    "no rewinding at all". Returns the action list (or its cost), or None."""
    import heapq
    t_max = min(T_MAX, level.bell if level.bell is not None else T_MAX)
    probe = Tick(level, 10 ** 6, has_watch)
    seen = [set() for _ in range(t_max + 1)]
    for t in range(t_max + 1):
        for g in level.guards:
            seen[t].add(g.at(t))
            seen[t] |= probe.sight(g, t)
    start = (level.start, 0, has_watch and level.watch is None)
    best = {start: (0, 0)}
    prev = {start: None}
    heap = [(0, 0, start)]
    moves = [("m", 0, -1), ("m", 1, 0), ("m", 0, 1), ("m", -1, 0), ("w",), ("r",)]
    while heap:
        cost, steps, state = heapq.heappop(heap)
        if (cost, steps) > best.get(state, (1 << 30, 0)):
            continue
        pos, t, key = state
        if pos == level.goal and (key or level.watch is None):
            if return_cost:
                return cost
            plan, cur = [], state
            while prev[cur] is not None:
                cur, a = prev[cur]
                plan.append(a)
            return plan[::-1]
        for a in moves:
            if a[0] == "r":
                if not key or t == 0 or probe.door_shut(pos, t - 1):
                    continue
                nxt, c = (pos, t - 1, key), cost + 1
            else:
                if t + 1 > t_max:
                    continue
                if a[0] == "m":
                    q = (pos[0] + a[1], pos[1] + a[2])
                    if q in level.walls or probe.door_shut(q, t):
                        continue
                    if any(g.at(t + 1) == pos and g.at(t) == q for g in level.guards):
                        continue
                else:
                    q = pos
                if level.bell is not None and t + 1 >= level.bell and q != level.goal:
                    continue
                nxt, c = (q, t + 1, key or q == level.watch), cost
            if nxt[1] <= t_max and nxt[0] in seen[nxt[1]]:
                continue
            if (c, steps + 1) < best.get(nxt, (1 << 30, 0)):
                best[nxt] = (c, steps + 1)
                prev[nxt] = (state, a)
                heapq.heappush(heap, (c, steps + 1, nxt))
    return None


def solve_cost(level, has_watch=True):
    return solve(level, has_watch, return_cost=True)


# ---------------------------------------------------------------------- generation

def generate_floor(seed, index, final=False, w=32, h=16):
    """A tower floor: rooms and corridors, gear doors on the way (one that opens only once, so the
    watch is needed), wardens walking their rounds, an hour reel or two in side rooms, and a Quarter
    Bell set from the floor's own best time. Each floor is solved: its cheapest clear (in minutes of
    the hoard) is known, and rerolled if too dear."""
    rng = random.Random(seed * 7907 + index * 104723 + 3)
    depth = index - len(FLOORS)
    for _ in range(300):
        spec = _try_floor(rng, depth, w, h)
        if spec is None:
            continue
        lv = TickLevel(spec)
        cost = solve_cost(lv)
        if cost is None or not (4 <= cost <= 14):
            continue
        plan = solve(lv)
        lv.bell = spec["bell"] = len(plan) + 24 + rng.randint(0, 8)
        lv.min_cost = cost
        lv.name = FINAL_NAME if final else FLOOR_NAMES[(seed + index) % len(FLOOR_NAMES)]
        lv.hint = ("The Drum Room: the hoard is kept here. Reach the stair to the drum." if final else
                   "Reach the stair up (X). Gear doors keep their own time; the Quarter Bell rings on tick %d."
                   % lv.bell)
        return lv
    raise RuntimeError("could not build a floor for seed %r" % seed)


def _try_floor(rng, depth, w, h):
    grid = [["#"] * w for _ in range(h)]
    rooms = []
    for _ in range(200):
        if len(rooms) >= 6:
            break
        rw, rh = rng.randint(4, 8), rng.randint(3, 5)
        x, y = rng.randint(1, w - rw - 2), rng.randint(1, h - rh - 2)
        if any(x - 2 < ox + ow and ox - 2 < x + rw and y - 2 < oy + oh and oy - 2 < y + rh
               for ox, oy, ow, oh in rooms):
            continue
        rooms.append((x, y, rw, rh))
    if len(rooms) < 5:
        return None
    for x, y, rw, rh in rooms:
        for yy in range(y, y + rh):
            for xx in range(x, x + rw):
                grid[yy][xx] = "."
    centers = [(x + rw // 2, y + rh // 2) for x, y, rw, rh in rooms]
    linked = [0]
    corridors = set()
    while len(linked) < len(rooms):
        best = None
        for i in linked:
            for j in range(len(rooms)):
                if j in linked:
                    continue
                d = abs(centers[i][0] - centers[j][0]) + abs(centers[i][1] - centers[j][1])
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        (x0, y0), (x1, y1) = centers[i], centers[j]
        corner = (x1, y0) if rng.random() < 0.5 else (x0, y1)
        for (ax, ay), (bx, by) in (((x0, y0), corner), (corner, (x1, y1))):
            x, y = ax, ay
            while True:
                if grid[y][x] == "#":
                    corridors.add((x, y))
                grid[y][x] = "."
                if (x, y) == (bx, by):
                    break
                if x != bx:
                    x += 1 if bx > x else -1
                else:
                    y += 1 if by > y else -1
        linked.append(j)
    open_tiles = {(x, y) for y in range(h) for x in range(w) if grid[y][x] == "."}
    a = min(range(len(rooms)), key=lambda i: centers[i][0])
    dist = _bfs(open_tiles, centers[a])
    b = max(range(len(rooms)), key=lambda i: dist.get(centers[i], -1))
    start, goal = centers[a], centers[b]
    if dist.get(goal, 0) < 18:
        return None
    path = _path(open_tiles, start, goal)
    path_set = set(path)
    # gear doors: corridor chokepoints on the route
    chokes = [p for p in path[3:-3] if p in corridors and goal not in _bfs(open_tiles, start, blocked={p})]
    if not chokes:
        return None
    n_doors = 1 + (depth >= 2 and len(chokes) > 6)
    doors = {}
    picks = sorted({chokes[len(chokes) * (k + 1) // (n_doors + 1)] for k in range(n_doors)}, key=path.index)
    for k, p in enumerate(picks):
        c = str(k + 1)
        arrive = path.index(p)
        if k == len(picks) - 1:                    # the last door opens once, before you can get there
            opens = max(2, arrive - rng.randint(6, 11))
            doors[c] = ("once", opens, 2)
        else:
            doors[c] = ("every", rng.randint(16, 26), 3, rng.randint(0, 15))
        grid[p[1]][p[0]] = c
    # wardens: rounds inside rooms along the way (never the start room)
    guards = []
    n_guards = min(3, 1 + depth // 2)
    order = sorted(range(len(rooms)), key=lambda i: rng.random())
    for i in order:
        if len(guards) >= n_guards:
            break
        if i == a:
            continue
        x, y, rw, rh = rooms[i]
        if rw < 4 or rh < 3:
            continue
        if not any((xx, yy) in path_set for xx in range(x, x + rw) for yy in range(y, y + rh)):
            continue
        loop = [(x, y), (x + rw - 1, y), (x + rw - 1, y + rh - 1), (x, y + rh - 1)]
        if rng.random() < 0.5:
            loop = loop[::-1]
        guards.append((loop, rng.randint(0, 2 * (rw + rh))))
    # an hour reel or two in side rooms
    reels = []
    for i in order:
        if len(reels) >= 2:
            break
        if i in (a, b):
            continue
        x, y, rw, rh = rooms[i]
        spot = (x + rng.randint(0, rw - 1), y + rng.randint(0, rh - 1))
        if spot not in path_set and grid[spot[1]][spot[0]] == ".":
            reels.append(spot)
    grid[start[1]][start[0]] = "S"
    grid[goal[1]][goal[0]] = "X"
    for r in reels:
        grid[r[1]][r[0]] = "r"
    spec = dict(name="", hint="", rows=["".join(row) for row in grid], guards=guards, doors=doors, bell=None)
    lv = TickLevel(spec)
    probe = Tick(lv)
    if any(probe.seen_at(start, t) is not None for t in range(6)):
        return None
    return spec


def _bfs(open_set, src, blocked=frozenset()):
    dist = {src: 0}
    q = deque([src])
    while q:
        cur = q.popleft()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (cur[0] + dx, cur[1] + dy)
            if n in dist or n not in open_set or n in blocked:
                continue
            dist[n] = dist[cur] + 1
            q.append(n)
    return dist


def _path(open_set, a, b):
    prev = {a: None}
    q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (cur[0] + dx, cur[1] + dy)
            if n not in prev and n in open_set:
                prev[n] = cur
                q.append(n)
    out, cur = [], b
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return out[::-1]
