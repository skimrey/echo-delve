"""Shared test helpers. Importing this module forces headless SDL."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from echo.consts import GRID_H, GRID_W  # noqa: E402
from echo.floor import Floor, Rect  # noqa: E402
from echo.sim import GhostScript, LoopSim, Mods, move  # noqa: E402

KINDS = {"C": "crawler", "A": "archer", "B": "brute", "W": "warden"}


def make_floor(rows, limit=60, index=1):
    """Build a Floor from ASCII art placed at the top-left of the grid.

    # wall   . floor   S start   E exit   1-4 door k   a-d plate k
    ^ spike (phase 0)   v spike (phase 1)   p potion   C A B W enemies
    """
    walls = [[True] * GRID_W for _ in range(GRID_H)]
    start = exit_ = None
    doors, plates, spikes, potions, spawns = {}, {}, {}, [], []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                continue
            walls[y][x] = False
            if ch == "S":
                start = (x, y)
            elif ch == "E":
                exit_ = (x, y)
            elif ch in "1234":
                doors[int(ch) - 1] = (x, y)
            elif ch in "abcd":
                plates["abcd".index(ch)] = (x, y)
            elif ch == "^":
                spikes[(x, y)] = 0
            elif ch == "v":
                spikes[(x, y)] = 1
            elif ch == "p":
                potions.append((x, y))
            elif ch in KINDS:
                spawns.append((KINDS[ch], x, y))
    assert start is not None, "map needs an S"
    if exit_ is None:
        exit_ = (GRID_W - 2, GRID_H - 2)
        walls[exit_[1]][exit_[0]] = False
    n = len(doors)
    return Floor(index=index, seed=0, walls=walls, start=start, exit=exit_,
                 doors=[doors[i] for i in range(n)], plates=[plates[i] for i in range(n)],
                 spikes=spikes, potions=potions, spawns=spawns, limit=limit,
                 rooms=[Rect(0, 0, GRID_W, GRID_H)])


def new_sim(rows, scripts=(), mods=None, **kw):
    return LoopSim(make_floor(rows, **kw), list(scripts), mods or Mods())


def run_actions(sim, actions):
    out = []
    for a in actions:
        out.extend(sim.step(a))
        if sim.over:
            break
    return out


def kinds(events):
    return [e[0] for e in events]


R, L, U, D = move(1, 0), move(-1, 0), move(0, -1), move(0, 1)
