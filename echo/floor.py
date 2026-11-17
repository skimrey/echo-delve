"""Floor data and procedural generation.

Every generated floor is a chain of locked doors on the only route from the
start to the exit. Door k opens only while something stands on plate k, and
plate k always lies in the part of the dungeon reachable before door k. So an
echo (a replay of an earlier loop of yours) can always be the one to hold it.

generate_floor() also plays the floor with a simple bot (bot.py) and re-rolls
until the bot clears it with the baseline kit, so a floor is never a dead end.
"""

import random
from collections import deque
from dataclasses import dataclass, field

from .consts import (DIRS, DOORS_PER_FLOOR, GRID_H, GRID_W, MAX_FLOOR,
                     SPIKE_HALF)


class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def contains(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def grown(self, n):
        return Rect(self.x - n, self.y - n, self.w + 2 * n, self.h + 2 * n)

    def intersects(self, o):
        return not (self.x + self.w <= o.x or o.x + o.w <= self.x or
                    self.y + self.h <= o.y or o.y + o.h <= self.y)

    def tiles(self):
        for yy in range(self.y, self.y + self.h):
            for xx in range(self.x, self.x + self.w):
                yield (xx, yy)


@dataclass
class Floor:
    index: int
    seed: int
    walls: list
    start: tuple
    exit: tuple
    doors: list
    plates: list
    spikes: dict
    potions: list
    spawns: list
    limit: int
    rooms: list
    attempts: int = 1
    verified: bool = False
    door_at: dict = field(default_factory=dict)
    plate_at: dict = field(default_factory=dict)

    def __post_init__(self):
        self.door_at = {p: i for i, p in enumerate(self.doors)}
        self.plate_at = {p: i for i, p in enumerate(self.plates)}

    def is_wall(self, x, y):
        return not (0 <= x < GRID_W and 0 <= y < GRID_H) or self.walls[y][x]

    def spike_active(self, pos, turn):
        phase = self.spikes[pos]
        return ((turn // SPIKE_HALF) + phase) % 2 == 0


# ---------------------------------------------------------------- graph helpers

def neighbors(x, y):
    for dx, dy in DIRS:
        yield (x + dx, y + dy)


def bfs_dist(walls, src, blocked=frozenset()):
    """Distance from src over floor tiles, treating `blocked` tiles as walls."""
    dist = {src: 0}
    q = deque([src])
    while q:
        cur = q.popleft()
        for n in neighbors(*cur):
            if n in dist or n in blocked:
                continue
            x, y = n
            if not (0 <= x < GRID_W and 0 <= y < GRID_H) or walls[y][x]:
                continue
            dist[n] = dist[cur] + 1
            q.append(n)
    return dist


def bfs_path(walls, src, dst, blocked=frozenset()):
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        if cur == dst:
            break
        for n in neighbors(*cur):
            if n in prev or n in blocked:
                continue
            x, y = n
            if not (0 <= x < GRID_W and 0 <= y < GRID_H) or walls[y][x]:
                continue
            prev[n] = cur
            q.append(n)
    if dst not in prev:
        return None
    path, cur = [], dst
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]


# ---------------------------------------------------------------- generation

def _carve_corridor(walls, a, b, rng):
    (x1, y1), (x2, y2) = a, b
    if rng.random() < 0.5:
        corner = (x2, y1)
    else:
        corner = (x1, y2)
    for (sx, sy), (ex, ey) in ((a, corner), (corner, b)):
        x, y = sx, sy
        while True:
            walls[y][x] = False
            if (x, y) == (ex, ey):
                break
            if x != ex:
                x += 1 if ex > x else -1
            else:
                y += 1 if ey > y else -1


def _layout(rng, n_rooms):
    walls = [[True] * GRID_W for _ in range(GRID_H)]
    rooms = []
    for _ in range(400):
        if len(rooms) >= n_rooms:
            break
        w, h = rng.randint(4, 9), rng.randint(4, 6)
        r = Rect(rng.randint(1, GRID_W - w - 2), rng.randint(1, GRID_H - h - 2), w, h)
        if any(r.grown(2).intersects(o) for o in rooms):
            continue
        rooms.append(r)
    for r in rooms:
        for x, y in r.tiles():
            walls[y][x] = False
    if len(rooms) < 2:
        return walls, rooms
    connected, rest = [0], set(range(1, len(rooms)))
    while rest:
        best = None
        for i in connected:
            for j in rest:
                (ax, ay), (bx, by) = rooms[i].center, rooms[j].center
                d = abs(ax - bx) + abs(ay - by)
                if best is None or d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        _carve_corridor(walls, rooms[i].center, rooms[j].center, rng)
        connected.append(j)
        rest.discard(j)
    return walls, rooms


def _in_room(rooms, p):
    return any(r.contains(*p) for r in rooms)


def _straight_corridor(walls, p):
    x, y = p
    open_n = [d for d in DIRS if not (walls[y + d[1]][x + d[0]])]
    if len(open_n) != 2:
        return False
    (ax, ay), (bx, by) = open_n
    return ax == -bx and ay == -by


def _try_build(rng, index):
    n_doors = DOORS_PER_FLOOR[min(index, MAX_FLOOR) - 1]
    n_rooms = min(6 + index // 2 + 1, 10)
    walls, rooms = _layout(rng, n_rooms)
    if len(rooms) < 6:
        return None

    a = rng.choice(rooms)
    d1 = bfs_dist(walls, a.center)
    exit_room = max(rooms, key=lambda r: d1.get(r.center, -1))
    d2 = bfs_dist(walls, exit_room.center)
    start_room = max(rooms, key=lambda r: d2.get(r.center, -1))
    if start_room is exit_room or start_room.center not in d2:
        return None
    start, exit_ = start_room.center, exit_room.center
    path = bfs_path(walls, start, exit_)
    if path is None or len(path) < 14 + 8 * n_doors:
        return None

    # door candidates: straight corridor tiles on the path whose loss cuts the exit off
    cands = []
    for idx in range(3, len(path) - 3):
        p = path[idx]
        if _in_room(rooms, p) or not _straight_corridor(walls, p):
            continue
        if exit_ in bfs_dist(walls, start, blocked={p}):
            continue
        cands.append((idx, p))
    if len(cands) < n_doors:
        return None
    chosen = [cands[len(cands) * (k + 1) // (n_doors + 1)] for k in range(n_doors)]
    chosen = sorted(set(chosen))
    if len(chosen) < n_doors or any(chosen[i + 1][0] - chosen[i][0] < 4 for i in range(len(chosen) - 1)):
        return None
    doors = [p for _, p in chosen]

    used = {start, exit_, *doors}
    plates, region_dists = [], []
    for k in range(n_doors):
        region = bfs_dist(walls, start, blocked=set(doors[k:]))
        opts = []
        for p, d in region.items():
            if p in used or d < 5 or not _in_room(rooms, p):
                continue
            if any(abs(p[0] - q[0]) + abs(p[1] - q[1]) <= 3 for q in doors):
                continue
            if start_room.contains(*p):
                continue
            opts.append((d, p))
        if not opts:
            return None
        opts.sort()
        pool = opts[len(opts) // 2:] or opts
        d, p = rng.choice(pool)
        plates.append(p)
        used.add(p)
        region_dists.append(d)

    dist_exit = len(path) - 1
    limit = int(max([dist_exit] + region_dists) * 1.6) + 16

    # everything else goes on free room tiles
    start_d = bfs_dist(walls, start)
    free = [p for r in rooms for p in r.tiles() if p not in used]

    def take(pred, count=1):
        picks = []
        pool = [p for p in free if pred(p)]
        rng.shuffle(pool)
        for p in pool[:count]:
            picks.append(p)
            free.remove(p)
            used.add(p)
        return picks

    spikes = {}
    if index >= 2:
        for p in take(lambda p: start_d.get(p, 0) >= 5, index + 1):
            spikes[p] = rng.randint(0, 1)
        # spikes in corridors make timing matter on the route itself
        corr = [p for p in path[4:-4] if p not in used and not _in_room(rooms, p)
                and all(abs(p[0] - q[0]) + abs(p[1] - q[1]) > 2 for q in doors)]
        for p in rng.sample(corr, min(len(corr), index // 2)):
            spikes[p] = rng.randint(0, 1)
            used.add(p)

    potions = take(lambda p: start_d.get(p, 0) >= 3, 1 + index // 3)

    kinds = ["crawler"] + (["archer"] if index >= 2 else []) + (["brute"] if index >= 3 else [])
    spawns = []
    for p in take(lambda p: start_d.get(p, 0) >= 8 and p not in spikes, min(1 + index, 7)):
        spawns.append((rng.choice(kinds), p[0], p[1]))
    if index >= 2:
        for plate in plates:
            if rng.random() < 0.5:
                room = next(r for r in rooms if r.contains(*plate))
                spot = take(lambda p: room.contains(*p) and 2 <= abs(p[0] - plate[0]) + abs(p[1] - plate[1]) <= 5
                            and p not in spikes)
                if spot:
                    spawns.append((rng.choice(kinds), spot[0][0], spot[0][1]))
    if index >= MAX_FLOOR:
        spot = take(lambda p: exit_room.contains(*p) and abs(p[0] - exit_[0]) + abs(p[1] - exit_[1]) in (2, 3)
                    and p not in spikes)
        if spot:
            spawns.append(("warden", spot[0][0], spot[0][1]))

    return Floor(index=index, seed=0, walls=walls, start=start, exit=exit_, doors=doors,
                 plates=plates, spikes=spikes, potions=potions, spawns=spawns, limit=limit,
                 rooms=rooms)


def generate_floor(seed, index, verify=True, max_attempts=40):
    """Build floor `index` for `seed`. With verify=True the floor is re-rolled until a
    bot can clear it with the baseline kit (see bot.floor_is_solvable)."""
    last = None
    for attempt in range(max_attempts):
        rng = random.Random(seed * 7919 + index * 104729 + attempt * 15485863)
        floor = _try_build(rng, index)
        if floor is None:
            continue
        floor.seed, floor.attempts = seed, attempt + 1
        last = floor
        if not verify:
            return floor
        from .bot import floor_is_solvable
        if floor_is_solvable(floor):
            floor.verified = True
            return floor
    if last is None:
        raise RuntimeError("could not build floor %d for seed %r" % (index, seed))
    return last


def loops_needed(floor):
    """Echoes needed to hold every plate, plus the final run."""
    return len(floor.doors) + 1
