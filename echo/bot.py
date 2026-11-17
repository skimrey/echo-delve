"""A simple scripted player. It proves every generated floor can be cleared.

Strategy: loop k walks to plate k, fights anything awake nearby, then anchors
there so the echo holds the plate; the final loop walks to the exit.
"""

from .consts import BASE_SLOTS
from .floor import bfs_path
from .run import FloorPlay
from .sim import ANCHOR, WAIT, Mods, move


def _dir(a, b):
    return move(b[0] - a[0], b[1] - a[1])


def bot_action(sim, goal, anchor, state):
    p = sim.player
    adj = [e for e in sim.enemies if e.alive and e.awake and abs(e.x - p.x) + abs(e.y - p.y) == 1]
    if adj:
        adj.sort(key=lambda e: (e.hp, e.key))
        return _dir(p.pos, adj[0].pos)
    if p.pos == goal and anchor:
        awake = [e for e in sim.enemies if e.alive and e.awake]
        if awake and sim.turn < sim.limit - 3:
            tgt = min(awake, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
            path = bfs_path(sim.floor.walls, p.pos, tgt.pos)
            if path and len(path) > 1:
                return _dir(p.pos, path[1])
            return WAIT
        return ANCHOR
    path = bfs_path(sim.floor.walls, p.pos, goal)
    if not path or len(path) < 2:
        return WAIT
    nxt = path[1]
    if sim.door_closed_at(nxt):
        return WAIT
    if (nxt in sim.floor.spikes and sim.floor.spike_active(nxt, sim.turn)
            and not (p.pos in sim.floor.spikes and sim.floor.spike_active(p.pos, sim.turn))
            and state.get("spike_waits", 0) < 3):
        state["spike_waits"] = state.get("spike_waits", 0) + 1
        return WAIT
    state["spike_waits"] = 0
    return _dir(p.pos, nxt)


def play_floor(floor, mods=None, loops_max=BASE_SLOTS + 1, max_turns=400):
    """Drive a FloorPlay with the bot. Returns the FloorPlay (check .status)."""
    fp = FloorPlay(floor, mods or Mods(), loops_max)
    done = set()
    guard = 0
    while fp.status == "playing" and guard < max_turns * (loops_max + 1):
        remaining = [k for k in range(len(floor.plates)) if k not in done]
        target = remaining[0] if remaining else None
        goal = floor.plates[target] if target is not None else floor.exit
        loop_before = fp.loop_no
        state = {}
        while fp.status == "playing" and fp.loop_no == loop_before:
            fp.act(bot_action(fp.sim, goal, target is not None, state))
            guard += 1
            if guard >= max_turns * (loops_max + 1):
                break
        if target is not None and fp.last_end in ("anchor", "timeout") and fp.last_end_pos == goal:
            done.add(target)
    return fp


def floor_is_solvable(floor):
    return play_floor(floor).status == "cleared"
