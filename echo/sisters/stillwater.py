"""STILLWATER (prototype): the caves below the Deep, on the same night as Echo Delve.

The world
- The limestone under Hollowmere drinks every sound. Generations ago people sheltered here; the
  stone swallowed their voices, the dark swallowed the way out, and they stayed: the Still. They
  have never seen their home. They live by touch, and speak by writing ripples on water.
- A skin of limestone from their caves runs the Spindle, the bore through which the golden thread
  carries each day up to the town. Sealed in rock, it never let out a glimmer; the Still never knew
  it was there. Worn thin by the Guild's hoarding, the thread snapped right there, and the day it
  was carrying burst through the wall and sank into the Still's water, where it settled like silt.
  Still water looks black; stir it and the light rises in rings. For the first time, the Still can
  see. The hole it broke is also the first way out of their caves in
  generations: through it into the Spindle, and down it, a long slide, into the hall of the Loom,
  where a light they did not make is waiting, and the stair that Aurel is lighting on his way down.
- Stirred light is slow to settle: wherever you wade, the water remembers you for a while, a
  glowing WAKE that others can follow.
- Tarn's chapters: PROLOGUE (The Long Night) before his first chamber; INTERLUDES before the first
  chamber past the tutorial (the old ones and the children) and before the last (the break itself).
- There is only ever one day. When Aurel ties the thread, the new day replaces the old: the Loom
  draws the spilled light back up to weave the morning, and the water goes black again. The Still
  must be out before then: the NIGHT is the run's clock (in The Long Night, the shared clock).

The rules (deterministic, turn based)
- Tiles: '#' limestone, '.' dry ledge, '~' water, 'S' start, 'E' the way on, 'a'..'c' the float
  of a float-gate (water), 'A'..'C' the float-gate itself (a stone curtain across water),
  'e' an eel, 'p' a pebble, 's' a Still stranded in the dark.
- Actions: move, wait (silent), touch the water (a wide ripple), throw a pebble, climb out (on 'E').
- Wading makes a small ripple; ledges are silent. Ripples spread about a tile per turn in
  near-circles through water (diagonals cost DIAGONAL, no corner-cutting) and light what they
  cross. Lit tiles stay visible, to you and to the Still, for WAKE turns.
- The Still who walk with you follow you, one tile per turn, but only through tiles they can see:
  your wake, and the tiles right around you. Leave them in the dark and they stop. Wading Still
  make small ripples of their own. A stranded Still joins you when you reach them.
- A ripple reaching a float lifts its gate for GATE_OPEN turns.
- Eels are blind. They feel ripples passing within FEEL tiles and swim to where they began.
  An eel that reaches you ends the attempt; one that reaches a Still takes them.
- Climbing out ends the chamber: everyone who reached the way on is saved; anyone left is lost.
- EELS go where they are fair: a generated chamber places them only where the guide's own route gets
  past them at any light, just out of earshot of it, so straying is what wakes them. If one finds
  you anyway, you can step back a few turns (the screen keeps them; the turns stay spent).
- THE WATER DIMS as the night runs down: a chamber is played at a light level between MIN_LIGHT and
  1, set by how much of the night is left when you enter it. Every ripple's reach and the wake's
  length are scaled by it, so later chambers are darker and harder. Generated chambers are checked
  at MIN_LIGHT, so they stay possible however late you reach them.
"""

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass, field

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
DIAGS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
DIAGONAL = 1.42
WADE_REACH = 4
FOLLOW_REACH = 2
TOUCH_REACH = 10
PEBBLE_REACH = 7
THROW_RANGE = 6
GATE_OPEN = 12                # (long enough for a line of the Still, single file, to pass)
FEEL = 1
WAKE = 6
NIGHT = 760              # turns of light for the whole run
MIN_LIGHT = 0.55         # how dim the water gets when the night is nearly gone
GENERATED = 5            # chambers after the handwritten ones

TITLE = "Stillwater"
HERO = "Tarn"
TAGLINE = "A lost day burst into your water. Stir it, and lead your people out by its light."

INTRO = [
    ("cave_dark", "Below Hollowmere, below even the Deep, the limestone drinks every sound. Long ago, people "
                  "sheltered down here. The stone swallowed their voices, the dark swallowed the way out, and they "
                  "stayed."),
    ("still_folk", "The Still are their children's children's children. They have lived in the caves so long that "
                   "nobody remembers there was ever a way out. They have never seen the sky, or each other. They "
                   "speak by touch: a hand on the water, a ripple, read by fingertips on the far shore."),
    ("spindle_whole", "Beyond a skin of limestone ran something they had never known: the Spindle, and in it the "
                      "golden thread that carries each new day up to the town. Sealed in stone, it never let out a "
                      "glimmer."),
    ("spindle", "Three hundred and twelve days ago the thread broke, right beside them. The day it was carrying "
                "burst through the wall and sank into their water, and settled there like silt."),
    ("pool_glow", "Still water looks black. Stir it, and the spilled light rises in rings. For the first time in "
                  "their lives the Still can see: their words as they travel, the walls they break against, each "
                  "other's faces."),
    ("wake", "Stirred light is slow to settle. Wherever you wade, the water remembers you for a while: a glowing "
             "wake that others can follow."),
    ("tarn", "You are Tarn. Your ripples carry farther than anyone's, so when the others move, they follow your "
             "light. They will not follow it into the dark."),
    ("dim", "Now the light is thinning. Somewhere far off, someone is mending what broke, and when it is whole, the "
            "water will go black. Across the caves is the hole the day broke. Bring your people through it before "
            "then."),
]

# The Long Night: the world has already been told, so Tarn's own chapter begins with his people.
PROLOGUE = [
    ("still_folk", "Below the Deep, in caves nobody in Hollowmere knows are there, live the Still: the grandchildren's "
                   "grandchildren of people who sheltered there once, and lost the way out. They have never seen the "
                   "sky, or each other. They speak by touch: a hand on the water, a ripple, read on the far shore."),
    ("pool_glow", "Then the wall beside them broke, and a day poured into their water. Stir it, and it glows. For "
                  "three hundred and twelve days the Still have watched their words travel, and seen each other's "
                  "faces."),
    INTRO[6],
    INTRO[7],
]

# told before a chamber (by its index, or "last"), here and in The Long Night
INTERLUDES = {
    3: [
        ("wake", "The old ones remember the dark. They walk with a hand on the shoulder in front and their eyes "
                 "closed, as if the light were something that could be taken back."),
        ("children", "The children have never known anything else. They keep touching the water, just to see it "
                     "answer."),
    ],
    "last": [
        ("ascent", "The stone is warm here, and the water runs one way, toward a sound like wind in a chimney. The "
                   "break. Beyond it is nothing any of you have ever touched."),
        ("ascent", "Beyond it is the Spindle, and at the bottom of that, a hall, and a stair that climbs to the sky, if "
                   "anyone lights it. If nobody does, your people will be at the bottom of the world in the dark, "
                   "without even the water. Or they could stay here, in the light, for as long as it lasts."),
    ],
}

ENDING_ALL = ("Through the break, into the Spindle, and down: one by one the Still slide into a hall full of "
              "golden light, and land in a heap. The Loom. For the first time in their lives they see a light they "
              "did not make. Beside it, a stair climbs into the dark, and far up it, someone's lamps are burning.")
ENDING_ALL_DARK = ("Through the break, into the Spindle, and down: one by one the Still slide into a hall full of "
                   "golden light, and land in a heap. The Loom. Beside it, a stair climbs into the dark. Nobody has lit "
                   "it in a long time. They sit at the bottom of it, and wait for whoever is coming down.")
ENDING_STAY = ("You take your hand out of the water. They stay, in the last of the light, as long as it lasts; and "
               "you stay with them.")
ENDING_SOME = ("Through the break, into the Spindle, and down into the Loom's hall. Not everyone made it. Behind "
               "you, the water is still glowing, for now.")
ENDING_DAWN = ("The water goes black around you. Far above, the thread is tied and the morning is being woven "
               "from the light you were standing in.")

ENEMY_LORE = "A blind eel. It feels the water move, and swims to where the movement began."

# handwritten chambers (the tutorial), then generated ones
CHAMBERS = [
    dict(name="Stir the Water", followers=2, pebbles=0,
         hint="Find the way on (the draught of air on the far side) and bring the Still with you. They follow "
              "your glowing wake, but only while they can see it.",
         rows=[
             "############################",
             "#.....###########....s######",
             "#S....~~~~~~~~~~~~~~~~.....#",
             "#.....~~~~~~~~~~~~~~~~....E#",
             "#.....~~~~~~~~~~~~~~~~.....#",
             "######~~~~~~~~~~~~~~~~######",
             "############################",
         ]),
    dict(name="The Float-Gate", followers=2, pebbles=0,
         hint="A float-gate rises when a ripple reaches its float, and sinks again soon after. Touch the water "
              "(T) to send a wave, then get everyone through while the gate is up.",
         rows=[
             "##############################",
             "#S..........................##",
             "#...~~~~~~~~~~~~~~~~~~~~~~..##",
             "#...~~~~~~~~~~~~~~~~~~~~~~..##",
             "#...~~~~~~~~~~~~~~~~~~~~~~..##",
             "#...~~~~~~~~~~~~~~~~~~~~~a..##",
             "#...~~~~~~~~~~~~~~~~~~~~~~..##",
             "###########################A##",
             "###########################~##",
             "########################...~.#",
             "########################.E...#",
             "##############################",
         ]),
    dict(name="The Listeners", followers=2, pebbles=2,
         hint="Eels are blind: they feel ripples and swim to where they began. Walk the dry pier (ledges make no "
              "ripples), throw a pebble (F, then a direction) to draw them off, then cross.",
         rows=[
             "##############################",
             "############.~~~~~~~~~~~~~~~~#",
             "############.~~~~~~~~~~~~~~~~#",
             "############.~~~~~~~~~~~~~~~~#",
             "############.~~~~~~~~~~~~~~~~#",
             "############.~~~~~~~~~~~~~~~~#",
             "#S...........~~~~e~~~~~~~~~~~#",
             "#............~~~~~~~~~~~~~~~~#",
             "############.~~~~~~~~e~~~~~~~#",
             "############.~~~~~~~~~~~~~~.E#",
             "##############################",
         ]),
]

CHAMBER_NAMES = ["The Drowned Hall", "The Narrows", "The Ribbed Gallery", "The Black Mirror", "The Long Wade",
                 "The Dripping Stair", "The Hollow Lung", "The Salt Teeth", "The Quiet Fold", "The Last Pool"]


@dataclass
class Ripple:
    origin: tuple
    born: int
    reach: int
    dist: dict              # tile -> distance from origin (through water at birth), up to reach
    source: str = "wade"    # wade | touch | pebble | follow

    def arrival(self, p):
        """Turns after its birth at which this ripple reaches tile p (None if it never does)."""
        d = self.dist.get(p)
        return None if d is None else math.ceil(d - 1e-6)

    def front(self, turn):
        age = turn - self.born
        if age < 0 or age > self.reach:
            return ()
        return [p for p, d in self.dist.items() if math.ceil(d - 1e-6) == age]

    def alive(self, turn):
        return turn - self.born <= self.reach


@dataclass
class Eel:
    pos: tuple
    target: tuple = None
    key: str = ""


@dataclass
class Kin:
    """One of the Still."""
    pos: tuple
    state: str = "following"   # stranded | following | saved | lost
    key: str = ""


@dataclass
class Chamber:
    name: str
    hint: str
    walls: set
    water: set
    start: tuple
    exit: tuple
    basins: list            # float j lifts gate j
    gates: list
    eels: list
    pebbles_on_floor: set
    pebbles: int
    size: tuple
    kin: list               # starting positions of the Still who walk with you
    stranded: list
    gate_at: dict = field(default_factory=dict)

    def __post_init__(self):
        self.gate_at = {p: j for j, p in enumerate(self.gates)}

    @property
    def population(self):
        return len(self.kin) + len(self.stranded)


def parse_chamber(spec):
    rows = spec["rows"]
    walls, water, basins, gates, eels, pebbles, stranded = set(), set(), {}, {}, [], set(), []
    start = exit_ = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            p = (x, y)
            if ch == "#":
                walls.add(p)
            elif ch == "~":
                water.add(p)
            elif ch == "S":
                start = p
            elif ch == "E":
                exit_ = p
            elif ch in "abc":
                basins["abc".index(ch)] = p
                water.add(p)
            elif ch in "ABC":
                gates["ABC".index(ch)] = p
                water.add(p)
            elif ch == "e":
                eels.append(p)
                water.add(p)
            elif ch == "p":
                pebbles.add(p)
            elif ch == "s":
                stranded.append(p)
    n = len(basins)
    assert start and exit_ and set(basins) == set(gates), spec.get("name")
    size = (max(len(r) for r in rows), len(rows))
    kin = _kin_spots(start, spec.get("followers", 0), walls, water, size)
    return Chamber(spec["name"], spec.get("hint", ""), walls, water, start, exit_,
                   [basins[j] for j in range(n)], [gates[j] for j in range(n)], eels, pebbles,
                   spec.get("pebbles", 0), size, kin, stranded)


def _kin_spots(start, n, walls, water, size):
    """The Still who start with you stand on the dry ledge nearest the start."""
    out, seen, q = [], {start}, deque([start])
    while q and len(out) < n:
        cur = q.popleft()
        for dx, dy in DIRS + DIAGS:
            p = (cur[0] + dx, cur[1] + dy)
            if p in seen or p in walls or not (0 <= p[0] < size[0] and 0 <= p[1] < size[1]):
                continue
            seen.add(p)
            if p not in water:
                out.append(p)
                if len(out) == n:
                    break
                q.append(p)
    return out


def spread(is_water, origin, reach):
    """Distances through water from origin (diagonals allowed, no corner-cutting), up to reach."""
    dist = {origin: 0.0}
    heap = [(0.0, origin)]
    steps = [(v, 1.0) for v in DIRS] + [(v, DIAGONAL) for v in DIAGS]
    while heap:
        d, cur = heapq.heappop(heap)
        if d > dist.get(cur, 1e9):
            continue
        for (dx, dy), cost in steps:
            n = (cur[0] + dx, cur[1] + dy)
            if not is_water(n):
                continue
            if cost != 1.0 and not (is_water((cur[0] + dx, cur[1])) and is_water((cur[0], cur[1] + dy))):
                continue
            nd = d + cost
            if nd <= reach + 1e-6 and nd < dist.get(n, 1e9):
                dist[n] = nd
                heapq.heappush(heap, (nd, n))
    return dist


def light_for(left, start):
    """The light level (MIN_LIGHT..1) when `left` of `start` of the night remains."""
    frac = max(0.0, min(1.0, left / max(1, start)))
    return MIN_LIGHT + (1 - MIN_LIGHT) * frac


def minutes_per_turn(light):
    """In dim water the Still move slowly, feeling for each other's hands, and every turn takes longer:
    a turn costs 1/light minutes of the night (1 at full light, nearly 2 at the dimmest)."""
    return 1.0 / max(MIN_LIGHT, light)


def scaled(base, light):
    return max(1, int(round(base * light)))


class Still:
    """One attempt at one chamber, at a light level (1 = full, MIN_LIGHT = nearly dawn)."""

    def __init__(self, chamber, light=1.0):
        self.level = chamber
        self.light = light
        self.wake = max(3, scaled(WAKE, light))
        self.turn = 0
        self.player = chamber.start
        self.pebbles = chamber.pebbles
        self.floor_pebbles = set(chamber.pebbles_on_floor)
        self.ripples = []
        self.gate_until = [-1] * len(chamber.gates)
        self.eels = [Eel(p, None, "E%d" % i) for i, p in enumerate(chamber.eels)]
        self.kin = [Kin(p, "following", "K%d" % i) for i, p in enumerate(chamber.kin)] + \
                   [Kin(p, "stranded", "K%d" % (i + len(chamber.kin))) for i, p in enumerate(chamber.stranded)]
        self.over = None            # None | "caught" | "out"
        self.lit = {}               # tile -> turn it was last lit
        self.seen = set()
        self.events = []
        self._touch_seen()

    def clone(self):
        """A cheap copy for search and previews (ripples are never mutated once made)."""
        c = Still.__new__(Still)
        c.__dict__.update(self.__dict__)
        c.floor_pebbles = set(self.floor_pebbles)
        c.ripples = list(self.ripples)
        c.gate_until = list(self.gate_until)
        c.eels = [Eel(e.pos, e.target, e.key) for e in self.eels]
        c.kin = [Kin(k.pos, k.state, k.key) for k in self.kin]
        c.lit = dict(self.lit)
        c.seen = set(self.seen)
        c.events = []
        return c

    # ---------------------------------------------------------------- queries
    def in_bounds(self, p):
        w, h = self.level.size
        return 0 <= p[0] < w and 0 <= p[1] < h

    def is_wall(self, p):
        return not self.in_bounds(p) or p in self.level.walls

    def gate_open(self, j):
        return self.turn < self.gate_until[j]

    def gate_closed_at(self, p):
        j = self.level.gate_at.get(p)
        return j is not None and not self.gate_open(j)

    def is_water(self, p):
        return p in self.level.water and not self.gate_closed_at(p)

    def passable(self, p):
        return not self.is_wall(p) and not self.gate_closed_at(p)

    def visible_to_kin(self, p):
        """The Still can see your wake (anything lit in the last self.wake turns) and the tiles around you."""
        return (self.turn - self.lit.get(p, -999) <= self.wake or
                max(abs(p[0] - self.player[0]), abs(p[1] - self.player[1])) <= 1)

    def water_beside(self):
        """Where a touch lands: your own tile if it is water, else the first water beside you."""
        if self.is_water(self.player):
            return self.player
        for dx, dy in DIRS:
            q = (self.player[0] + dx, self.player[1] + dy)
            if self.is_water(q):
                return q
        return None

    def count(self, state):
        return sum(1 for k in self.kin if k.state == state)

    def validate(self, action):
        if self.over:
            return "This attempt is over."
        kind = action[0]
        if kind == "m":
            q = (self.player[0] + action[1], self.player[1] + action[2])
            if self.is_wall(q):
                return "Limestone. It swallows the bump without a sound."
            if self.gate_closed_at(q):
                c = "ABC"[self.level.gate_at[q]]
                return "Float-gate %s is down. A ripple reaching its float (%s) lifts it." % (c, c.lower())
        elif kind == "t":
            if self.water_beside() is None:
                return "There is no water within reach to touch."
        elif kind == "f":
            if self.pebbles <= 0:
                return "You have no pebbles left."
        elif kind == "x":
            if self.player != self.level.exit:
                return "You can only go on from the way on: the draught of air."
        return None

    # ---------------------------------------------------------------- stepping
    def _spread(self, origin, reach):
        return spread(self.is_water, origin, reach)

    def _ripple(self, origin, reach, source):
        r = Ripple(origin, self.turn, reach, self._spread(origin, reach), source)
        self.ripples.append(r)
        self.events.append(("ripple", origin, reach, source))
        return r

    def step(self, action):
        """("m", dx, dy) | ("w",) | ("t",) touch | ("f", dx, dy) throw | ("x",) climb out."""
        msg = self.validate(action)
        if msg:
            raise ValueError(msg)
        self.events = ev = []
        kind = action[0]
        if kind == "x":
            self._climb_out(ev)
            return ev
        if kind == "m":
            q = (self.player[0] + action[1], self.player[1] + action[2])
            self.player = q
            if q in self.floor_pebbles:
                self.floor_pebbles.discard(q)
                self.pebbles += 1
                ev.append(("pebble", q))
            if self.is_water(q):
                self._ripple(q, scaled(WADE_REACH, self.light), "wade")
        elif kind == "t":
            self._ripple(self.water_beside(), scaled(TOUCH_REACH, self.light), "touch")
        elif kind == "f":
            self.pebbles -= 1
            x, y = self.player
            land = self.player
            for _ in range(THROW_RANGE):
                n = (x + action[1], y + action[2])
                if self.is_wall(n) or self.gate_closed_at(n):
                    break
                x, y = land = n
            ev.append(("throw", self.player, land))
            if self.is_water(land):
                self._ripple(land, scaled(PEBBLE_REACH, self.light), "pebble")
        self._advance(ev)
        return ev

    def _climb_out(self, ev):
        for k in self.kin:
            if k.state in ("following", "stranded"):
                k.state = "lost"
                ev.append(("left_behind", k.key))
        self.over = "out"
        ev.append(("out",))

    def _advance(self, ev):
        """This turn's fronts light the water, lift floats and reach eels; eels swim; the Still
        follow; then time moves on."""
        if self._eel_on(self.player):
            return self._caught(ev)
        fronts = {}
        for r in self.ripples:
            for p in r.front(self.turn):
                fronts.setdefault(p, r)
        for p in fronts:
            self.lit[p] = self.turn
        for j, basin in enumerate(self.level.basins):
            if basin in fronts:
                opened = not self.gate_open(j)
                self.gate_until[j] = self.turn + 1 + GATE_OPEN
                if opened:
                    ev.append(("gate", j, True))
        for e in self.eels:
            felt = None
            for p, r in fronts.items():
                if abs(p[0] - e.pos[0]) + abs(p[1] - e.pos[1]) <= FEEL:
                    if felt is None or r.born > felt.born:
                        felt = r
            if felt is not None and felt.origin != e.target and felt.origin != e.pos:
                e.target = felt.origin
                ev.append(("eel_hears", e.key, felt.origin))
            if e.target is not None:
                step = self._eel_step(e)
                if step is not None:
                    e.pos = step
                if e.pos == e.target:
                    e.target = None
        self._kin_turn(ev)
        if self._eel_on(self.player):
            return self._caught(ev)
        self.turn += 1
        for j in range(len(self.gate_until)):
            if self.gate_until[j] == self.turn:
                ev.append(("gate", j, False))
        self.ripples = [r for r in self.ripples if r.alive(self.turn)]
        self._touch_seen()

    def _caught(self, ev):
        self.over = "caught"
        ev.append(("caught",))
        self.turn += 1

    def _eel_on(self, p):
        return any(e.pos == p for e in self.eels)

    def _hands(self):
        """Who can follow this turn: the Still who can see the light, and anyone with a hand on the
        shoulder of one who can (a line holds together as long as each of them touches the next)."""
        following = [k for k in self.kin if k.state == "following"]
        held = {k.key for k in following if self.visible_to_kin(k.pos)}
        grew = True
        while grew:
            grew = False
            for k in following:
                if k.key in held:
                    continue
                if any(o.key in held and max(abs(o.pos[0] - k.pos[0]), abs(o.pos[1] - k.pos[1])) <= 1
                       for o in following):
                    held.add(k.key)
                    grew = True
        self._held = {k.pos for k in following if k.key in held}
        return held

    def _kin_turn(self, ev):
        self._held_keys = self._hands()
        for k in self.kin:
            if k.state == "stranded":
                if max(abs(k.pos[0] - self.player[0]), abs(k.pos[1] - self.player[1])) <= 1:
                    k.state = "following"
                    ev.append(("found", k.key))
                continue
            if k.state != "following":
                continue
            if self._eel_on(k.pos):
                k.state = "lost"
                ev.append(("kin_taken", k.key, k.pos))
                continue
            if k.pos == self.level.exit:
                k.state = "saved"
                ev.append(("saved", k.key))
                continue
            step = self._kin_step(k)
            if step is None:
                continue
            k.pos = step
            if self._eel_on(k.pos):
                k.state = "lost"
                ev.append(("kin_taken", k.key, k.pos))
            elif k.pos == self.level.exit:
                k.state = "saved"
                ev.append(("saved", k.key))
            elif self.is_water(k.pos):
                self._ripple(k.pos, scaled(FOLLOW_REACH, self.light), "follow")

    def _kin_step(self, k):
        """One step toward you through tiles the Still can see (None: in the dark, already close, or
        the way is full: the Still never crowd onto one another's tile, so a long line needs a long
        wake to follow)."""
        goal = self.player
        if max(abs(k.pos[0] - goal[0]), abs(k.pos[1] - goal[1])) <= 1 and goal != self.level.exit:
            return None
        if k.key not in getattr(self, "_held_keys", {k.key}):
            return None
        taken = {o.pos for o in self.kin if o is not k and o.state in ("following", "stranded")}
        for avoid in (taken, None):                  # around the others if there is a way, else behind them
            step = self._path_step(k.pos, goal, avoid or set())
            if step is not None and step not in taken:
                return step
        return None

    def _can_see(self, p):
        """A tile the Still can step to: one they can see, or one beside someone in the line."""
        if self.visible_to_kin(p):
            return True
        return any(max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 1 for q in getattr(self, "_held", ()))

    def _path_step(self, start, goal, avoid):
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for dx, dy in DIRS:
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or n in avoid or not self.passable(n) or not self._can_see(n):
                    continue
                prev[n] = cur
                q.append(n)
        if goal not in prev:
            return None
        cur = goal
        while prev[cur] != start:
            cur = prev[cur]
        return cur

    def _eel_step(self, e):
        """One step along the shortest water route toward the eel's target (None if none)."""
        if e.pos == e.target:
            return None
        prev = {e.pos: None}
        q = deque([e.pos])
        while q:
            cur = q.popleft()
            if cur == e.target:
                break
            for dx, dy in DIRS:
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or not self.is_water(n):
                    continue
                prev[n] = cur
                q.append(n)
        if e.target not in prev:
            return None
        cur = e.target
        while prev[cur] != e.pos:
            cur = prev[cur]
        return cur

    def _touch_seen(self):
        """You can always feel the tiles around you; everything lit is remembered."""
        x, y = self.player
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                if self.in_bounds(p):
                    self.lit[p] = self.turn
        for p, t in self.lit.items():
            if p in self.seen:
                continue
            self.seen.add(p)
            if p in self.level.water:               # lit water shows its shore
                for dx, dy in DIRS:
                    q = (p[0] + dx, p[1] + dy)
                    if self.in_bounds(q):
                        self.seen.add(q)

    def eel_visible(self, e):
        return self.turn - self.lit.get(e.pos, -99) <= 1


# ---------------------------------------------------------------------- the run

class StillRun:
    """A whole night: the handwritten chambers, then generated ones, against one clock."""

    def __init__(self, seed=None, thread=None, generated=GENERATED, prebuilt=None):
        """clock: the shared clock of The Long Night (instead of this run's own night).
        generated: how many generated chambers follow the handwritten ones. prebuilt: {index: Chamber}."""
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        self.thread = thread
        self.generated = generated
        self.prebuilt = dict(prebuilt or {})
        self.index = 0
        self._night = NIGHT
        self.saved = 0
        self.lost = 0
        self.total = 0
        self.results = []
        self.state = "playing"      # playing | done | dawn
        self.lamplight = None       # The Long Night: extra light from Aurel's sconces (a callable)
        self._carry = 0.0           # fractions of a minute, carried from turn to turn
        self.choice = None          # at the break: "through" (take them with you) or "stay"
        self.chamber = self._build(0)

    @property
    def chambers(self):
        return len(CHAMBERS) + self.generated

    @property
    def night(self):
        return self.thread.minutes if self.thread is not None else self._night

    @property
    def night_start(self):
        return self.thread.start if self.thread is not None else NIGHT

    def light(self):
        """How bright the water is now (set when a chamber is entered): it dims as the night runs
        down, and in The Long Night the sconces Aurel has lit give some of it back."""
        base = light_for(self.night, self.night_start)
        if self.lamplight is not None:
            base = min(1.0, base + self.lamplight())
        return base

    def _build(self, index):
        if index in self.prebuilt:
            return self.prebuilt[index]
        if index < len(CHAMBERS):
            return parse_chamber(CHAMBERS[index])
        return generate_chamber(self.seed, index)

    def spend(self, turns, light=None):
        """The night moves on: `turns` turns, each costing minutes_per_turn(light) minutes (one, if no
        light is given). Returns True if the light is gone."""
        cost = turns * (minutes_per_turn(light) if light is not None else 1.0) + self._carry
        minutes = int(cost)
        self._carry = cost - minutes
        if self.thread is not None:
            self.thread.spend(minutes)
        else:
            self._night = max(0, self._night - minutes)
        if self.night == 0:
            self.state = "dawn"
        return self.state == "dawn"

    def finish(self, sim):
        saved = sim.count("saved")
        self.saved += saved
        self.lost += sim.count("lost")
        self.total += self.chamber.population
        self.results.append((self.chamber.name, saved, self.chamber.population))
        self.index += 1
        if self.index >= self.chambers:
            self.state = "done"
        else:
            self.chamber = self._build(self.index)


# ---------------------------------------------------------------------- generation

def _neighbors8(x, y):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                yield x + dx, y + dy


def _bfs(open_set, src, blocked=frozenset()):
    dist = {src: 0}
    q = deque([src])
    while q:
        cur = q.popleft()
        for dx, dy in DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n in dist or n not in open_set or n in blocked:
                continue
            dist[n] = dist[cur] + 1
            q.append(n)
    return dist


def generate_chamber(seed, index, w=32, h=16):
    """A cave chamber: cellular-automaton limestone, pools and ledges, a float-gate or two on the
    way, eels in the big pools, a stranded Still off the path. Every chamber is checked: the way
    up is reachable, and each float can be reached by a wave early enough to get everyone through."""
    rng = random.Random(seed * 9973 + index * 7919 + 11)
    depth = index - len(CHAMBERS)                       # 0 for the first generated chamber
    for _ in range(400):
        c = _try_chamber(rng, depth, w, h)
        if c is None:
            continue
        route = set()
        if not all(_clears(walkthrough(c, light=lt, trail=route), c) for lt in (MIN_LIGHT, 1.0)):
            continue                                                    # everyone, even at the dimmest
        _place_eels(rng, c, min(3, 1 + depth // 2), route)
        c.name = CHAMBER_NAMES[(seed + index) % len(CHAMBER_NAMES)]
        return c
    raise RuntimeError("could not build a chamber for seed %r" % seed)


def _clears(done, chamber):
    return done.over == "out" and done.count("saved") == chamber.population


def _place_eels(rng, c, n, route):
    """Eels in the larger pools, away from the start: as many as n, but only where the guide's
    route stays safe from them at any light (so there is always a way past that does not depend on
    luck). Pools just out of earshot of the route (measured through the water) are tried first: near
    enough to matter the moment you stray, far enough to be fair."""
    water = c.water
    wet_route = [p for p in route if p in water]
    dist = _water_dist(water, wet_route)
    start_d = _bfs(set(water) | {p for p in _all_tiles(c) if p not in c.walls}, c.start)
    used = {c.start, c.exit, *c.gates, *c.basins, *c.stranded, *c.pebbles_on_floor, *c.kin}
    pools = [p for p in water if p not in used and start_d.get(p, 0) >= 9 and
             sum((q in water) for q in _neighbors8(*p)) >= 6]
    rng.shuffle(pools)
    pools.sort(key=lambda p: -min(dist.get(p, 99), WADE_REACH + FEEL + 1))   # just out of earshot is far enough
    pools = pools[:24]                                                        # (each one tried costs two walks)
    for p in pools:
        if len(c.eels) >= n:
            break
        if not all(abs(p[0] - q[0]) + abs(p[1] - q[1]) >= 6 for q in c.eels + c.gates):
            continue
        c.eels.append(p)
        if not all(_clears(walkthrough(c, light=lt, eels=True), c) for lt in (MIN_LIGHT, 1.0)):
            c.eels.pop()


def _water_dist(water, sources):
    """Steps through the water from the nearest of `sources` (how far a ripple must travel)."""
    dist = {p: 0 for p in sources}
    q = deque(sources)
    while q:
        cur = q.popleft()
        for dx, dy in DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n in water and n not in dist:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist


def _try_chamber(rng, depth, w, h):
    wall = [[True] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            wall[y][x] = rng.random() < 0.42
    for _ in range(5):
        nxt = [row[:] for row in wall]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                n = sum(wall[j][i] for i, j in _neighbors8(x, y))
                nxt[y][x] = n >= 5 or (wall[y][x] and n >= 4)
        wall = nxt
    open_all = {(x, y) for y in range(h) for x in range(w) if not wall[y][x]}
    if not open_all:
        return None
    comp = max(_components(open_all), key=len)
    if len(comp) < w * h * 0.33:
        return None
    xs = [p[0] for p in comp]
    if min(xs) > 4 or max(xs) < w - 5:
        return None
    start = min(comp, key=lambda p: (p[0], abs(p[1] - h // 2)))
    exit_ = max(comp, key=lambda p: (p[0], -abs(p[1] - h // 2)))
    # water where a second automaton says so; ledges elsewhere; dry ground around start and exit
    water = {p for p in comp if rng.random() < 0.62}
    for _ in range(3):
        water = {p for p in comp if sum((q in water) for q in _neighbors8(*p) if q in comp) >= 4 or
                 (p in water and sum((q in water) for q in _neighbors8(*p) if q in comp) >= 3)}
    for cx, cy in (start, exit_):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                water.discard((cx + dx, cy + dy))
    if len(water) < len(comp) * 0.3:
        return None
    walls = {(x, y) for y in range(h) for x in range(w)} - comp
    dist_start = _bfs(comp, start)
    if exit_ not in dist_start or dist_start[exit_] < w * 0.7:
        return None
    # float-gates: a limestone rib across the cave with one flooded gap where the route crosses it
    n_gates = min(2, 1 + depth // 2)
    picks = []
    for k in range(n_gates):
        path = _path(comp, start, exit_)
        gx = int(w * (k + 1) / (n_gates + 1)) + rng.randint(-2, 2)
        crossing = [p for p in path if p[0] == gx]
        if not crossing:
            return None
        gap = crossing[0]
        if not ((gap[0] - 1, gap[1]) in comp and (gap[0] + 1, gap[1]) in comp):
            return None
        for y in range(h):
            if (gx, y) != gap:
                comp.discard((gx, y))
        comp = max((c for c in _components(comp) if start in c), key=len, default=set())
        if exit_ not in comp:
            return None
        picks.append(gap)
    water &= comp
    walls = {(x, y) for y in range(h) for x in range(w)} - comp
    dist_start = _bfs(comp, start)
    path = _path(comp, start, exit_)
    gates, basins = [], []
    for k, g in enumerate(picks):
        water.add(g)
        region = _bfs(comp, start, blocked=set(picks[k:]))
        region_water = {p for p in region if p in water}
        basin = _place_float(rng, region, region_water, g, comp)
        if basin is None:
            return None
        gates.append(g)
        basins.append(basin)
    used = {start, exit_, *gates, *basins}
    eels = []                                   # (placed once the guide's route is known: _place_eels)
    # a stranded Still on a ledge off the route, and pebbles
    path_set = set(path)
    ledges = [p for p in comp if p not in water and p not in used and p not in path_set
              and dist_start.get(p, 0) >= 6 and min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in path) >= 3]
    stranded = [rng.choice(ledges)] if ledges else []
    used.update(stranded)
    spots = [p for p in comp if p not in water and p not in used and dist_start.get(p, 0) >= 3]
    rng.shuffle(spots)
    pebbles_on_floor = set(spots[:2])
    return Chamber("", "Lead the Still to the way on, toward the break. Float-gates rise when a ripple reaches their float; eels "
                       "come to ripples. Leaving someone in the dark leaves them behind.",
                   walls, water, start, exit_, basins, gates, eels, pebbles_on_floor, 1, (w, h),
                   _kin_spots(start, 2 + (depth >= 2), walls, water, (w, h)), stranded)


def _components(tiles):
    left = set(tiles)
    while left:
        seed = left.pop()
        comp = {seed}
        q = deque([seed])
        while q:
            cur = q.popleft()
            for dx, dy in DIRS:
                n = (cur[0] + dx, cur[1] + dy)
                if n in left:
                    left.discard(n)
                    comp.add(n)
                    q.append(n)
        yield comp


def _path(open_set, a, b):
    prev = {a: None}
    q = deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for dx, dy in DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n not in prev and n in open_set:
                prev[n] = cur
                q.append(n)
    out, cur = [], b
    while cur is not None:
        out.append(cur)
        cur = prev[cur]
    return out[::-1]


def _place_float(rng, region, region_water, gate, comp):
    """A float on the near side of the gate, placed so that some water you can stand in (or beside)
    sends a wave to it early enough for a group to walk to the gate before it drops again."""
    walk_to_gate = _bfs(set(region) | {gate}, gate)
    options = [p for p in region_water if 5 <= walk_to_gate.get(p, 0) <= 16]
    rng.shuffle(options)
    for basin in options[:30]:
        dist = spread(region_water.__contains__, basin, scaled(TOUCH_REACH, MIN_LIGHT))   # from the float out
        for w_tile, d in dist.items():
            arrival = math.ceil(d - 1e-6)
            walk = walk_to_gate.get(w_tile)
            if walk is not None and walk + 3 <= arrival + GATE_OPEN:
                return basin
    return None


# ---------------------------------------------------------------------- verification

def walkthrough(chamber, max_turns=400, light=1.0, eels=False, trail=None):
    """A simple guide: for each float-gate, wade to a spot whose wave reaches the float in time,
    touch, walk to the gate, wait for it to rise, lead everyone through; then the way on. The guide
    never looks for eels: by default they are left out (this proves the chamber's shape and timing
    work); with eels=True it shows that its route is safe from them. `trail`, if a set, collects every
    tile you and the Still stood on. Returns the finished Still (check .over and .count("saved"))."""
    import copy
    calm = copy.copy(chamber)
    if not eels:
        calm.eels = []
    s = Still(calm, light)
    real_step = s.step

    def step(a):
        if s.over:
            return []
        ev = real_step(a)
        if trail is not None:
            trail.add(s.player)
            trail.update(k.pos for k in s.kin)
        return ev
    s.step = step                     # (only while the guide walks)
    try:
        _guide(s, calm, light, max_turns)
    finally:
        del s.step
    return s


def _guide(s, calm, light, max_turns):
    def path_to(goal, allow_water=True):
        prev = {s.player: None}
        q = deque([s.player])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for dx, dy in DIRS:
                n = (cur[0] + dx, cur[1] + dy)
                if n in prev or not s.passable(n) or (not allow_water and n in calm.water and n != goal):
                    continue
                prev[n] = cur
                q.append(n)
        if goal not in prev:
            return None
        out, cur = [], goal
        while prev[cur] is not None:
            out.append(cur)
            cur = prev[cur]
        return out[::-1]

    def go(tiles):
        for p in tiles or ():
            a = ("m", p[0] - s.player[0], p[1] - s.player[1])
            if s.over or s.turn > max_turns or s.validate(a):
                return
            s.step(a)

    def make_room(origin, k):
        """Walk on to a tile about k steps from `origin`, as far from it as the way allows."""
        open_tiles = {p for p in _all_tiles(calm) if s.passable(p) and p not in calm.gate_at}
        here = _bfs(open_tiles | {s.player}, s.player)
        back = _bfs(open_tiles | {origin}, origin)
        spots = [p for p, d in here.items() if d <= k]
        if spots:
            go(path_to(max(spots, key=lambda p: (back.get(p, 0), -here[p]))))

    def gather(limit=25):
        for _ in range(limit):
            if s.over or all(max(abs(k.pos[0] - s.player[0]), abs(k.pos[1] - s.player[1])) <= 1
                             for k in s.kin if k.state == "following"):
                return
            s.step(("w",))

    def fetch_stranded():
        for k in s.kin:                               # the stranded are off the route: go and get them
            if k.state == "stranded":
                route = path_to(k.pos)
                if route:
                    go(route[:-1])
                    gather()

    fetch_stranded()
    for j, gate in enumerate(calm.gates):
        near = [n for n in ((gate[0] + dx, gate[1] + dy) for dx, dy in DIRS) if s.passable(n) and
                path_to(n) is not None]
        if not near:
            return
        approach = min(near, key=lambda n: len(path_to(n)))
        open_tiles = {p for p in _all_tiles(calm) if s.passable(p)}
        from_me = _bfs(open_tiles, s.player)                       # three maps, each computed once
        to_gate = _bfs(open_tiles, approach)
        from_float = spread(s.is_water, calm.basins[j], scaled(TOUCH_REACH, light))  # ripples are symmetric
        best = None
        for t in from_me:
            if t in calm.water and s.is_water(t):
                origin = t
            else:
                origin = next((q for q in ((t[0] + dx, t[1] + dy) for dx, dy in DIRS) if s.is_water(q)), None)
            d = from_float.get(origin) if origin else None
            back = to_gate.get(t)
            margin = 2 + s.count("following") + s.count("stranded")          # a line takes time to pass
            if d is None or back is None or back + margin > math.ceil(d - 1e-6) + GATE_OPEN:
                continue
            if best is None or from_me[t] < best[0]:
                best = (from_me[t], t)
        if best is None:
            return
        go(path_to(best[1]))
        gather()
        s.step(("t",))
        go(path_to(approach))
        for _ in range(40):
            if s.gate_open(j) or s.over:
                break
            s.step(("w",))
        beyond = [n for n in ((gate[0] + dx, gate[1] + dy) for dx, dy in DIRS) if n != approach and s.passable(n)]
        if not beyond:
            return
        go([gate, beyond[0]])
        make_room(gate, 2 + s.count("following"))         # step on, so the line behind can come through
        gather(limit=14)
        fetch_stranded()
    go(path_to(calm.exit))
    for _ in range(40):                               # wait at the way on until everyone has gone
        if s.over or s.count("following") == 0:
            break
        s.step(("w",))
    if not s.over and not s.validate(("x",)):
        s.step(("x",))


def _all_tiles(chamber):
    w, h = chamber.size
    return ((x, y) for y in range(h) for x in range(w))
