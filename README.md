# Echo Delve

A turn-based roguelike where **your past loops fight alongside you**. Pure Python + pygame-ce, CPU-only (no GPU needed, ~0.5 ms per frame in software).

Every floor is sealed by numbered doors. Door N only opens while *something stands on plate N*. You can't be in two places, but your previous loops can: each loop you end becomes an **echo** that replays your exact keystrokes next loop. Send loop 1 to a plate and anchor there; from loop 2 on, your echo holds the plate while you walk through the door. Deeper floors need more doors, so more echoes, in the right order, while enemies hunt you and your echoes.

- 6 procedurally generated floors, fog of war, 4 enemy types (crawler, archer, brute, warden), spikes, potions.
- Echoes are literal: they repeat inputs, not intentions. If the world differs, an echo may swing at air or bump a wall. Enemies reset every loop and attack echoes too.
- Roguelite: pick 1 of 3 upgrades per floor; earn shards to buy permanent perks in the Echo Forge.
- Every generated floor is verified: a scripted bot clears it with the baseline kit before you ever see it, so no floor is a dead end.

## Run

```
python3 -m venv .venv
./.venv/bin/pip install pygame-ce
./.venv/bin/python -m echo            # optional: --seed=123
```

Headless (VM / CI): `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`

## Controls

Arrows/WASD move or strike, Space or `.` wait, `E` (twice) anchor and end the loop, Tab toggle echo paths, click an adjacent tile to step, right-click to inspect, `H` help, Esc menu. Bumping a wall or sealed door costs no turn.

## Test

```
./.venv/bin/python -m unittest discover -s tests
```

Covers the simulation (doors, echoes, enemies, spikes), floor generation properties and bot-solvability, run/meta logic, and the UI through real input events including a random-input storm.

MIT licensed.
