"""A simple scripted player. It proves every generated floor can be cleared.

Strategy: one loop per lock, in the order the locks bar the way. For a door, walk to its plate,
fight anything awake nearby, then anchor so the echo holds the plate. For a gate, walk to its
lever, pull it and anchor at once, so the echo pulls it as early as possible. The final loop
walks to the exit, waiting at anything still shut.
"""

from .consts import BASE_SLOTS
from .floor import bfs_path
from .run import FloorPlay
from .sim import ANCHOR, WAIT, Mods, move


def _dir(a, b):
    return move(b[0] - a[0], b[1] - a[1])


def lock_goal(floor, done):
    """(goal tile, kind) for the first lock not yet handled: kind is "plate" or "lever";
    (exit, None) once every lock is handled. `done` holds indices into floor.lock_order."""
    for idx, (kind, i) in enumerate(floor.lock_order):
        if idx not in done:
            return (floor.plates[i], "plate") if kind == "door" else (floor.levers[i], "lever")
    return floor.exit, None


def bot_action(sim, goal, kind, state):
    """kind: "plate" (stand on goal and anchor), "lever" (pull the lever at goal, then anchor),
    None (walk to the exit). True/False are accepted for "plate"/None."""
    kind = "plate" if kind is True else (None if kind is False else kind)
    p = sim.player
    floor = sim.floor
    avoid = frozenset(q for q in floor.lever_at if q != goal or kind != "lever")
    if kind == "lever" and state.get("pulled"):
        return ANCHOR
    adj = [e for e in sim.enemies if e.alive and e.awake and abs(e.x - p.x) + abs(e.y - p.y) == 1]
    if adj:
        adj.sort(key=lambda e: (e.hp, e.key))
        return _dir(p.pos, adj[0].pos)
    if p.pos == goal and kind == "plate":
        awake = [e for e in sim.enemies if e.alive and e.awake]
        if awake and sim.turn < sim.limit - 3:
            tgt = min(awake, key=lambda e: abs(e.x - p.x) + abs(e.y - p.y))
            path = bfs_path(floor.walls, p.pos, tgt.pos, blocked=avoid)
            if path and len(path) > 1:
                return _dir(p.pos, path[1])
            return WAIT
        return ANCHOR
    path = bfs_path(floor.walls, p.pos, goal, blocked=avoid)
    if not path or len(path) < 2:
        return WAIT
    nxt = path[1]
    if kind == "lever" and nxt == goal:
        state["pulled"] = True
        return _dir(p.pos, nxt)
    if sim.door_closed_at(nxt):
        return WAIT
    if (nxt in floor.spikes and floor.spike_active(nxt, sim.turn)
            and not (p.pos in floor.spikes and floor.spike_active(p.pos, sim.turn))
            and state.get("spike_waits", 0) < 3):
        state["spike_waits"] = state.get("spike_waits", 0) + 1
        return WAIT
    state["spike_waits"] = 0
    return _dir(p.pos, nxt)


def play_floor(floor, mods=None, slots=BASE_SLOTS, max_turns=400):
    """Drive a FloorPlay with the bot, never unravelling. Returns the FloorPlay (check .status)."""
    loops_max = slots + 1
    fp = FloorPlay(floor, mods or Mods(), slots)
    done = set()
    guard = 0
    while fp.status == "playing" and guard < max_turns * (loops_max + 1):
        idx = next((k for k in range(len(floor.lock_order)) if k not in done), None)
        goal, kind = lock_goal(floor, done)
        loop_before = fp.loop_no
        state = {}
        while fp.status == "playing" and fp.loop_no == loop_before:
            fp.act(bot_action(fp.sim, goal, kind, state))
            guard += 1
            if guard >= max_turns * (loops_max + 1):
                break
        if kind == "plate" and fp.last_end in ("anchor", "timeout") and fp.last_end_pos == goal:
            done.add(idx)
        elif kind == "lever" and state.get("pulled") and fp.last_end == "anchor":
            done.add(idx)
    return fp


def floor_is_solvable(floor):
    return play_floor(floor).status == "cleared"
