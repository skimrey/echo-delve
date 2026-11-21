"""Floor scores: how close you came to clearing a floor in the fewest turns.

Every turn you take on a floor counts, across all of its loops: waiting, fighting, loops that
ended badly and loops you unravelled. The target is PAR, the shortest clear of the intended
solution: one loop per lock (walk the shortest route to its plate and stand there, or to its
lever and pull it), and a last loop that walks to the stairs, waiting at each door or gate
exactly until the echo that opens it has done its part.

Par ignores enemies and spikes, so it is a clean-room target. It is not a proof of optimality:
a clever player can beat it (for example one echo holding plate 1, then walking on to plate 2
once you are through door 1). Beating par is rewarded, not capped away.
"""

import heapq

from .floor import neighbors
from .sim import WAIT, move

SCORE_MAX = 1000
# (minimum fraction of par-efficiency, grade); the first match wins
# S+ means par or better. The rest is tuned for a human who has to explore through the fog:
# a perfect-knowledge bot that fights everything in its way lands around 0.9 (S).
GRADES = [(1.0, "S+"), (0.85, "S"), (0.7, "A"), (0.55, "B"), (0.4, "C"), (0.0, "D")]
GRADE_SHARDS = {"S+": 2, "S": 1}          # bonus forge shards for a great clear
GRADE_COLORS = {"S+": (255, 226, 140), "S": (250, 206, 110), "A": (150, 222, 140), "B": (130, 190, 240),
                "C": (200, 170, 230), "D": (190, 150, 150)}


def _route(floor, goal, open_at, pull=False):
    """Fewest actions from the entrance to `goal` (or, with pull=True, to a tile beside the lever at
    `goal` followed by the pull). open_at[("door", i)] / open_at[("gate", j)] is the first action
    index on which that lock can be entered (missing: it stays shut). Waiting is allowed; levers
    are solid. Moving into an open lock is legal once the echo opening it has made that many
    moves, because you act first. Returns (turns, actions) or None."""
    start = floor.start
    levers = floor.lever_at
    targets = {goal} if not pull else {n for n in neighbors(*goal) if not floor.is_wall(*n) and n not in levers}
    best = {start: 0}
    prev = {start: None}
    heap = [(0, start)]
    found = None
    while heap:
        t, cur = heapq.heappop(heap)
        if cur in targets:
            found = cur
            break
        if t > best.get(cur, 1 << 30):
            continue
        for n in neighbors(*cur):
            if floor.is_wall(*n) or n in levers:
                continue
            depart = t
            lock = ("door", floor.door_at[n]) if n in floor.door_at else \
                   ("gate", floor.gate_at[n]) if n in floor.gate_at else None
            if lock is not None:
                opens = open_at.get(lock)
                if opens is None:
                    continue
                depart = max(t, opens)
            arrive = depart + 1
            if arrive < best.get(n, 1 << 30):
                best[n] = arrive
                prev[n] = (cur, depart)
                heapq.heappush(heap, (arrive, n))
    if found is None:
        return None
    steps, cur = [], found
    while prev[cur] is not None:
        p, depart = prev[cur]
        steps.append((p, cur, depart))
        cur = p
    actions, t = [], 0
    for p, n, depart in reversed(steps):
        actions.extend([WAIT] * (depart - t))
        actions.append(move(n[0] - p[0], n[1] - p[1]))
        t = depart + 1
    if pull:
        actions.append(move(goal[0] - found[0], goal[1] - found[1]))
    return len(actions), actions


def par_routes(floor):
    """The par solution as keystrokes: one list per lock (walk to its plate and stand, or walk to
    its lever and pull), in the order the locks bar the way, then the final walk to the stairs.
    Each lock's loop is followed by an anchor. None if the floor cannot be solved this way."""
    open_at, routes = {}, []
    for kind, i in floor.lock_order:
        if kind == "door":
            r = _route(floor, floor.plates[i], open_at)
        else:
            r = _route(floor, floor.levers[i], open_at, pull=True)
        if r is None:
            return None
        routes.append(r[1])
        open_at[(kind, i)] = r[0]      # the echo holds the plate / has pulled the lever from then on
    r = _route(floor, floor.exit, open_at)
    if r is None:
        return None
    routes.append(r[1])
    return routes


def par_plan(floor):
    """[turns for each plate loop..., turns for the final loop], or None if unsolvable."""
    routes = par_routes(floor)
    return [len(a) for a in routes] if routes else None


def par_turns(floor):
    plan = par_plan(floor)
    return sum(plan) if plan else None


def grade_for(spent, par):
    ratio = par / max(1, spent) if par else 0.0
    for threshold, g in GRADES:
        if ratio >= threshold:
            return g
    return GRADES[-1][1]


LAMP_BONUS = 200         # points for lighting every sconce on a floor (pro rata)


def lamp_bonus(lit, total):
    """Points for the sconces lit on a floor: LAMP_BONUS for all of them, pro rata for fewer."""
    return round(LAMP_BONUS * lit / total) if total else 0


def floor_score(spent, par):
    """Points for one floor: 1000 at par, scaled by par/spent; beating par earns a bonus
    of 50 points per turn saved (so finding a cleverer solution always shows)."""
    if not par:
        return 0
    if spent <= par:
        return SCORE_MAX + 50 * (par - spent)
    return round(SCORE_MAX * par / spent)


# ---------------------------------------------------------------- par with the sconces lit
#
# Lighting sconces takes turns the fastest clear does not, so a single par would make lighting
# them a loss. Instead par follows what you did: LAMP PAR is the fewest turns to clear the floor
# AND light a given number of sconces, found by the same clean-room planner as par (enemies aside),
# adding the sconces one at a time, cheapest first. A floor's par curve goes from the fastest clear
# (with whatever sconces it passes anyway) to the clear that lights every sconce it can reach.

def lamp_spots(floor, torches, reach):
    """For each sconce, the tiles it can be lit from (within reach, nothing solid in between;
    doors and gates count as solid, since they may be shut)."""
    from .vision import clear_line

    def blocks(x, y):
        return floor.is_wall(x, y) or (x, y) in floor.door_at or (x, y) in floor.gate_at
    out = []
    r = int(reach) + 1
    for tx, ty in torches:
        spots = set()
        for y in range(ty - r, ty + r + 1):
            for x in range(tx - r, tx + r + 1):
                if (x - tx) ** 2 + (y - ty) ** 2 > reach * reach or blocks(x, y) or (x, y) in floor.lever_at:
                    continue
                if clear_line((x, y), (tx, ty), blocks):
                    spots.add((x, y))
        out.append(frozenset(spots))
    return out


def _route_via(floor, stops, goal, open_at, pull=False):
    """Like _route, but passing through one tile of each set in `stops`, in order, on the way.
    `goal` may also be a set of tiles (end on any of them). Never steps on the stairs early."""
    start = floor.start
    levers = floor.lever_at
    if isinstance(goal, (set, frozenset)):
        targets = goal
    else:
        targets = {goal} if not pull else {n for n in neighbors(*goal) if not floor.is_wall(*n) and n not in levers}
    n = len(stops)

    def advance(pos, stage):
        while stage < n and pos in stops[stage]:
            stage += 1
        return stage
    s0 = (start, advance(start, 0))
    best = {s0: 0}
    prev = {s0: None}
    heap = [(0, s0)]
    found = None
    while heap:
        t, st = heapq.heappop(heap)
        cur, stage = st
        if stage == n and cur in targets:
            found = st
            break
        if t > best.get(st, 1 << 30):
            continue
        for nb in neighbors(*cur):
            if floor.is_wall(*nb) or nb in levers:
                continue
            depart = t
            lock = ("door", floor.door_at[nb]) if nb in floor.door_at else \
                   ("gate", floor.gate_at[nb]) if nb in floor.gate_at else None
            if lock is not None:
                opens = open_at.get(lock)
                if opens is None:
                    continue
                depart = max(t, opens)
            nst = (nb, advance(nb, stage))
            if nb == floor.exit and not (nst[1] == n and nb in targets):
                continue                                # (stepping on the stairs ends the floor)
            arrive = depart + 1
            if arrive < best.get(nst, 1 << 30):
                best[nst] = arrive
                prev[nst] = (st, depart)
                heapq.heappush(heap, (arrive, nst))
    if found is None:
        return None
    steps, cur = [], found
    while prev[cur] is not None:
        p, depart = prev[cur]
        steps.append((p[0], cur[0], depart))
        cur = p
    actions, t = [], 0
    path = [start]
    for p, nb, depart in reversed(steps):
        actions.extend([WAIT] * (depart - t))
        actions.append(move(nb[0] - p[0], nb[1] - p[1]))
        path.append(nb)
        t = depart + 1
    if pull:
        actions.append(move(goal[0] - found[0][0], goal[1] - found[0][1]))
    return len(actions), actions, path


class LampPlan:
    """The par curve for a floor with sconces. par_for(n): fewest turns (in the clean room) to
    clear the floor with at least n sconces lit. routes: the plan that lights the most of them."""

    def __init__(self, floor, torches, reach, limit=None, slots=4):
        self.floor = floor
        self.spots = lamp_spots(floor, torches, reach)
        self.limit = limit if limit is not None else floor.limit
        self.spare = max(0, slots - len(floor.lock_order))     # echo slots left over for lamp rounds
        self.goals = []
        for kind, i in floor.lock_order:
            self.goals.append((floor.plates[i], False, kind, i) if kind == "door" else (floor.levers[i], True, kind, i))
        self.goals.append((floor.exit, False, None, None))
        self.curve = {}                  # sconces lit -> fewest turns found
        self.routes = None
        self._plan()

    def _build(self, stops, first=0, cache=None):
        """Routes for every loop given its stops; loops before `first` are reused from `cache`
        (a previous build). None if any loop fails or runs past the floor's turn limit."""
        out = list(cache[:first]) if cache else []
        open_at = {}
        for k, r in enumerate(out):
            kind, i = self.goals[k][2], self.goals[k][3]
            open_at[(kind, i)] = r[0]
        for k in range(first, len(self.goals)):
            goal, pull, kind, i = self.goals[k]
            r = _route_via(self.floor, stops[k], goal, open_at, pull)
            if r is None or r[0] >= self.limit:
                return None
            out.append(r)
            if kind is not None:
                open_at[(kind, i)] = r[0]
        return out

    def _lit(self, routes):
        seen = set()
        for r in routes:
            seen.update(r[2])
        return {i for i, sp in enumerate(self.spots) if sp & seen}

    def _record(self, routes):
        lit = self._lit(routes)
        total = sum(r[0] for r in routes)
        n = len(lit)
        if total < self.curve.get(n, 1 << 30):
            self.curve[n] = total
        return lit, total

    def _plan(self):
        loops = len(self.goals)
        stops = [[] for _ in range(loops)]
        routes = self._build(stops)
        if routes is None:
            return
        lit, total = self._record(routes)
        dist = [self._distances(sp) for sp in self.spots]
        dead = set()
        while True:
            todo = [i for i in range(len(self.spots)) if i not in lit and i not in dead and self.spots[i]]
            if not todo:
                break
            ranked = []
            for i in todo:                              # a rough price: the round trip from the nearest step
                for k, r in enumerate(routes):
                    d = min((dist[i].get(p, 1 << 20) for p in r[2]), default=1 << 20)
                    if d < 1 << 20:
                        ranked.append((2 * d * (1 if k == loops - 1 else 2), i, k))
            ranked.sort()
            best = None
            for _, i, k in ranked[:5]:                  # then build the best few for real
                for at in range(len(stops[k]) + 1):
                    trial = [list(s) for s in stops]
                    trial[k].insert(at, self.spots[i])
                    new = self._build(trial, first=k, cache=routes)
                    if new is None:
                        continue
                    t = sum(r[0] for r in new)
                    if best is None or t < best[0]:
                        best = (t, trial, new, i)
            if best is None:
                dead.update(todo)
                break
            _, stops, routes, i = best
            lit, total = self._record(routes)
            if i not in lit:                            # (should not happen: it was a stop)
                dead.add(i)
        # whatever the loops cannot fit in their turns, a spare echo slot can: a lamp round, walked
        # just before the last loop (every lock open by then), that lights what is left and anchors
        rounds = []
        while self.spare > len(rounds):
            todo = [i for i in range(len(self.spots)) if i not in lit and self.spots[i]]
            if not todo:
                break
            rnd = self._lamp_round(todo, routes, dist)
            if rnd is None:
                break
            rounds.append(rnd)
            routes = routes[:-1] + [rnd] + routes[-1:]
            lit, total = self._record(routes)
        self.rounds = len(rounds)
        self.routes = [r[1] for r in routes]
        self.lit = lit

    def _lamp_round(self, todo, routes, dist):
        """A loop that walks from the entrance to as many of the unlit sconces as it can reach in
        its turns (nearest first), adding them one at a time; None if it can reach none."""
        open_at = {}
        for k, r in enumerate(routes[:len(self.goals) - 1]):         # the lock loops come first
            open_at[(self.goals[k][2], self.goals[k][3])] = r[0]
        stops, best, pos, left = [], None, self.floor.start, list(todo)
        while left:
            left.sort(key=lambda i: dist[i].get(pos, 1 << 20))
            i = left.pop(0)
            if dist[i].get(pos, 1 << 20) >= 1 << 20:
                continue
            trial = stops + [self.spots[i]]
            r = _route_via(self.floor, trial[:-1], trial[-1], open_at)
            if r is None or r[0] >= self.limit:
                continue
            stops, best, pos = trial, r, r[2][-1]
            lit = self._lit(routes + [r])
            left = [j for j in left if j not in lit]
            partial = routes[:-1] + [r] + routes[-1:]
            self._record(partial)
        return best

    def _distances(self, spots):
        """Steps from every floor tile to the nearest of `spots` (locks treated as open)."""
        from collections import deque
        dist = {p: 0 for p in spots}
        q = deque(spots)
        while q:
            cur = q.popleft()
            for nb in neighbors(*cur):
                if nb in dist or self.floor.is_wall(*nb) or nb in self.floor.lever_at:
                    continue
                dist[nb] = dist[cur] + 1
                q.append(nb)
        return dist

    @property
    def fastest(self):
        """(sconces the fastest clear lights on its way, its turns)."""
        if not self.curve:
            return 0, None
        total = min(self.curve.values())
        return min(n for n, t in self.curve.items() if t == total), total

    @property
    def most(self):
        return max(self.curve) if self.curve else 0

    def par_for(self, n):
        """Fewest turns to clear with at least n sconces lit (n beyond what the plan reaches counts
        as the most it reaches)."""
        if not self.curve:
            return None
        n = min(n, self.most)
        return min(t for k, t in self.curve.items() if k >= n)


class LampInfo:
    """A floor's sconces (every one of them reachable by the plan) and its par curve."""

    def __init__(self, sconces, curve, rounds, fast_lamps):
        self.sconces = sconces
        self.curve = curve
        self.rounds = rounds                # spare echo loops the all-sconces plan uses
        self.fast_lamps = fast_lamps        # sconces the fastest clear lights on its way

    def par_for(self, n):
        if not self.curve:
            return None
        n = min(n, max(self.curve))
        return min(t for k, t in self.curve.items() if k >= n)

    @property
    def par_all(self):
        return self.par_for(len(self.sconces))


_LAMP_CACHE = {}


def lamp_info(floor):
    """The sconces and lamp par of a floor, planned once (per floor object, and per seed and index
    for generated floors, which are deterministic)."""
    from .consts import BASE_SLOTS, LAMP_REACH
    from .floor import place_torches
    mine = getattr(floor, "_lamps", None)
    if mine is not None and mine[0] is floor:
        return mine[1]
    key = (floor.seed, floor.index, getattr(floor, "attempts", 0)) if getattr(floor, "verified", False) else None
    info = _LAMP_CACHE.get(key) if key else None
    if info is None:
        torches = place_torches(floor)
        plan = LampPlan(floor, torches, LAMP_REACH, slots=BASE_SLOTS)
        if plan.curve:
            keep = sorted(plan.lit)
            sconces = [torches[i] for i in keep]
            info = LampInfo(sconces, dict(plan.curve), plan.rounds, plan.fastest[0])
        else:
            info = LampInfo(torches, {}, 0, 0)
        if key:
            _LAMP_CACHE[key] = info
    floor._lamps = (floor, info)
    return info
