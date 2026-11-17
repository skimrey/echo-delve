"""One loop of one floor. Fully deterministic: same scripts + same actions = same result.

Actions: ("w",) wait, ("m",dx,dy) move, ("f",dx,dy) strike, ("a",) anchor (end the loop here).

Turn order: you, then each echo (replaying a recorded loop), then the enemies,
then spikes. Echoes and you pass through each other; enemies are solid.
A door is open while anything stands on its plate or in its doorway.
"""

from collections import deque
from dataclasses import dataclass

from .consts import (BASE_ATK, BASE_GHOST_HP, BASE_HP, CHASE, ENEMIES, POTION_HEAL, WAKE)
from .floor import neighbors
from .vision import clear_line

WAIT = ("w",)
ANCHOR = ("a",)


def move(dx, dy):
    return ("m", dx, dy)


@dataclass
class Mods:
    atk: int = BASE_ATK
    max_hp: int = BASE_HP
    ghost_hp: int = BASE_GHOST_HP
    limit_bonus: int = 0


@dataclass
class GhostScript:
    actions: list
    ending: str          # "anchor": stays where it ended; "dead": fades when the recording ends
    label: int           # 1-based echo number


class Actor:
    def __init__(self, key, team, kind, x, y, hp, dmg):
        self.key, self.team, self.kind = key, team, kind
        self.x, self.y = x, y
        self.hp = self.max_hp = hp
        self.dmg = dmg
        self.awake = False
        self.cd = 0
        self.script = None

    @property
    def pos(self):
        return (self.x, self.y)

    @property
    def alive(self):
        return self.hp > 0


class LoopSim:
    def __init__(self, floor, scripts, mods):
        self.floor = floor
        self.mods = mods
        self.turn = 0
        self.limit = floor.limit + mods.limit_bonus
        self.player = Actor("P", "p", "player", floor.start[0], floor.start[1], mods.max_hp, mods.atk)
        self.ghosts = []
        for s in scripts:
            g = Actor("G%d" % s.label, "g", "echo", floor.start[0], floor.start[1], mods.max_hp + mods.ghost_hp, mods.atk)
            g.script = s
            self.ghosts.append(g)
        self.enemies = []
        for i, (kind, x, y) in enumerate(floor.spawns):
            spec = ENEMIES[kind]
            self.enemies.append(Actor("E%d" % i, "e", kind, x, y, spec["hp"], spec["dmg"]))
        self.potions = set(floor.potions)
        self.over = None          # None | "exit" | "dead" | "anchor" | "timeout"
        self.record = []
        self.events = []

    # ------------------------------------------------------------ queries
    def all_actors(self):
        return [a for a in [self.player] + self.ghosts + self.enemies if a.alive]

    def friends(self):
        return [a for a in [self.player] + self.ghosts if a.alive]

    def occupied(self, pos):
        return any(a.pos == pos for a in self.all_actors())

    def enemy_at(self, x, y):
        for e in self.enemies:
            if e.alive and e.x == x and e.y == y:
                return e
        return None

    def door_open(self, i):
        return self.occupied(self.floor.plates[i]) or self.occupied(self.floor.doors[i])

    def plate_held(self, i):
        return self.occupied(self.floor.plates[i])

    def door_closed_at(self, pos):
        i = self.floor.door_at.get(pos)
        return i is not None and not self.door_open(i)

    def blocked(self, pos):
        return self.floor.is_wall(*pos) or self.door_closed_at(pos)

    def blocks_sight(self, x, y):
        return self.blocked((x, y))

    def door_states(self):
        return [self.door_open(i) for i in range(len(self.floor.doors))]

    # ------------------------------------------------------------ player input
    def validate(self, action):
        """None when the action is legal, else a message (a bump costs no turn)."""
        if self.over:
            return "This loop is over."
        if action[0] != "m":
            return None
        nx, ny = self.player.x + action[1], self.player.y + action[2]
        if self.floor.is_wall(nx, ny):
            return "A wall blocks the way."
        if self.door_closed_at((nx, ny)):
            n = self.floor.door_at[(nx, ny)] + 1
            return "Door %d is sealed. Something must stand on plate %d." % (n, n)
        return None

    # ------------------------------------------------------------ stepping
    def step(self, action):
        if self.over:
            raise RuntimeError("loop already over")
        ev = self.events = []
        doors_before = self.door_states()
        if action[0] == "a":
            self.over = "anchor"
            ev.append(("anchor", self.player.pos))
            return ev
        if action[0] == "m" and self.enemy_at(self.player.x + action[1], self.player.y + action[2]):
            action = ("f", action[1], action[2])      # walking into a foe is a strike, recorded as one
        self.record.append(action)
        self._friend_act(self.player, action, ev)
        if self.player.pos == self.floor.exit:
            self.over = "exit"
            ev.append(("exit",))
            return ev
        for g in self.ghosts:
            self._ghost_turn(g, ev)
        for e in self.enemies:
            self._enemy_turn(e, ev)
        for a in self.all_actors():
            if a.pos in self.floor.spikes and self.floor.spike_active(a.pos, self.turn):
                ev.append(("spike", a.key, a.pos))
                self._damage(a, 1, None, ev)
        self._reap(ev)
        for i, (before, after) in enumerate(zip(doors_before, self.door_states())):
            if before != after:
                ev.append(("door", i, after))
        self.turn += 1
        if self.over is None and self.turn >= self.limit:
            self.over = "timeout"
            ev.append(("timeout",))
        return ev

    def _friend_act(self, a, action, ev):
        """'m' only ever moves, 'f' only ever strikes, so an echo never wanders off when
        the world differs slightly from the loop it was recorded in."""
        if action[0] not in ("m", "f"):
            return "wait"
        nx, ny = a.x + action[1], a.y + action[2]
        if action[0] == "f":
            foe = self.enemy_at(nx, ny)
            if foe is None:
                ev.append(("swing", a.key, (nx, ny)))
                return "whiff"
            ev.append(("attack", a.key, foe.key, a.dmg, foe.pos))
            self._damage(foe, a.dmg, a, ev)
            return "attack"
        if self.floor.is_wall(nx, ny) or self.enemy_at(nx, ny) is not None:
            return "blocked"
        if self.door_closed_at((nx, ny)):
            return "blocked"
        a.x, a.y = nx, ny
        if a.team != "e" and a.pos in self.potions:
            self.potions.discard(a.pos)
            healed = min(POTION_HEAL, a.max_hp - a.hp)
            a.hp += healed
            ev.append(("potion", healed, a.pos))
        return "moved"

    def _ghost_turn(self, g, ev):
        if not g.alive:
            return
        s, t = g.script, self.turn
        if t >= len(s.actions):
            return
        if self._friend_act(g, s.actions[t], ev) == "blocked":
            ev.append(("blocked", g.key))
        if s.ending == "dead" and t == len(s.actions) - 1:
            g.hp = 0
            ev.append(("faded", g.key, g.pos))

    def _damage(self, target, dmg, src, ev):
        target.hp -= dmg
        ev.append(("hurt", target.key, dmg, target.pos))
        if target.team == "e":
            target.awake = True

    def _reap(self, ev):
        for e in self.enemies:
            if not e.alive and not getattr(e, "reaped", False):
                e.reaped = True
                ev.append(("died", e.key, e.kind, e.pos))
        for g in self.ghosts:
            if not g.alive and not getattr(g, "reaped", False):
                g.reaped = True
                if not any(x[0] == "faded" and x[1] == g.key for x in ev):
                    ev.append(("echo_lost", g.key, g.pos))
        if not self.player.alive:
            self.over = "dead"
            ev.append(("dead",))

    # ------------------------------------------------------------ enemies
    def _bfs_target(self, e, tpos):
        start = e.pos
        prev = {start: None}
        q = deque([(start, 0)])
        while q:
            cur, d = q.popleft()
            if cur in tpos and cur != start:
                step = cur
                while prev[step] != start:
                    step = prev[step]
                return d, step, tpos[cur]
            if d >= CHASE:
                continue
            for n in neighbors(*cur):
                if n in prev or self.blocked(n):
                    continue
                prev[n] = cur
                q.append((n, d + 1))
        return None

    def _enemy_turn(self, e, ev):
        if not e.alive:
            return
        spec = ENEMIES[e.kind]
        friends = self.friends()
        if not friends:
            return
        tpos = {}
        for a in friends:
            tpos.setdefault(a.pos, a)           # the player is listed first, so wins ties
        found = self._bfs_target(e, tpos)
        if not e.awake:
            if found and found[0] <= WAKE:
                e.awake = True
                ev.append(("wake", e.key))
            return
        if spec["period"] > 1 and self.turn % spec["period"] != 0:
            return
        if e.kind == "archer":
            if e.cd > 0:
                e.cd -= 1
            aligned = []
            for a in friends:
                same = (a.x == e.x) != (a.y == e.y)
                dist = abs(a.x - e.x) + abs(a.y - e.y)
                if same and dist <= spec["rng"] and clear_line(e.pos, a.pos, self.blocks_sight):
                    aligned.append((dist, 0 if a is self.player else 1, a))
            if aligned:
                aligned.sort(key=lambda t: (t[0], t[1]))
                target = aligned[0][2]
                if e.cd == 0:
                    ev.append(("shot", e.key, target.key, e.pos, target.pos))
                    self._damage(target, e.dmg, e, ev)
                    e.cd = spec["cd"]
                return
        if found is None:
            return
        dist, step, target = found
        if dist == 1:
            ev.append(("attack", e.key, target.key, e.dmg, target.pos))
            self._damage(target, e.dmg, e, ev)
            return
        if self.enemy_at(*step) is None and not self.blocked(step):
            e.x, e.y = step
