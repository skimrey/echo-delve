# Echo Delve

A turn-based roguelike where **your past loops fight alongside you**. Pure Python + pygame-ce, CPU-only (no GPU needed, ~3-7 ms per animated frame in software).

You are Aurel Vell, the lamplighter's son. The Loom of Hours, which weaves each day, has snapped its thread, and Hollowmere has been stuck in one night for 312 days. Your mother went down to mend it and never came back. Her lantern was your sister Maren's to carry; she pressed it into your hands and ran. The loose end bound itself to your wrist: when a path fails, it pulls you back to the start of the floor and your steps stay behind as echoes. Tie the thread ten floors down before it runs out, or become a Warden like those who went before you. (All story text lives in `echo/story.py`.)

Echo Delve is one of three stories set on the same night, each with its own take on movement and time, and **The Long Night** (`--game=night`) plays all three as one game on one thread. The thread is the time that is left (what the Guild of Hours has not hoarded): every turn in any story shortens it, Aurel's unravels cut lengths of it, and it lengthens only when Maren lets the Guild's hours go. The water of the Still dims as it shortens, the Still climb home by the lamps Aurel lit, and when Aurel ties it the new day comes for everyone, ready or not. The night opens with each of the three once, each with their own prologue; after that you choose whose part to play next, and that is the main decision: whatever thread is left when Aurel ties it becomes the morning (the hub shows how long the day would be), and the order changes how much the night costs. The Guild sells its drum all night (faster the deeper Aurel goes), so Maren early saves more of it; in dim water every one of Tarn's turns costs more, so he is cheapest early (or by the light of Aurel's sconces); and tying the thread ends everything. Each of them also has interludes along the way, and the night ends with a scene for each. The shared world is in `docs/universe.md`. The two sister stories also play on their own:

- **Stillwater** (`--game=stillwater`): when the thread snapped, the day it carried spilled into the water under the Deep. Stir it and it glows; the light lingers as a wake. Lead the Still (who follow only the light they can see) to the way on, through the break and down the Spindle to the Loom, timing waves to lift float-gates and luring blind eels, before the night runs out. 3 tutorial chambers, then generated ones (eels only where a safe way past exists). If an eel finds you, step back a few turns (`B`) instead of starting the chamber over. *Your moves travel, and linger.*
- **The Tick** (`--game=tick`): above ground, Maren has stolen the Regulator, the Guild's pocket watch, and the alarm has barred the doors below: the only way out is up. The watch winds the whole clock tower (wardens, gear doors) back around her while she stays put. It runs on the hoard of hours the Guild kept when the day broke: every tick costs a minute. In the Drum Room at the top the Guildmaster is waiting with a bargain: her brother's safety for the ledger that proves what the Guild has done. She can open the brake instead. Free preview of any tick, a timeline of doors and danger, 3 tutorial floors, then generated ones. *The world moves; you don't.*

Every floor is sealed by numbered doors. Door N only opens while *something stands on plate N*. You can't be in two places, but your previous loops can: each loop you end becomes an **echo** that replays your exact keystrokes next loop. Send loop 1 to a plate and anchor there; from loop 2 on, your echo holds the plate while you walk through the door. Deeper floors need more doors, so more echoes, in the right order, while enemies hunt you and your echoes.

From floor 3, lettered **gates** join the numbered doors. Walking into lever A flips gate A for the rest of the loop, and echoes pull levers on the exact turn you did. Levers are placed as far as possible from their gates: too far to pull one and still reach the stairs in the same loop. So an echo has to pull it, early enough, and only once (a second pull shuts it again). The loop you spent exploring usually found the lever too late, which is what unravelling is for.

- 10 procedurally generated floors mixing plates and levers (a fixed schedule of what bars the way, from one plate on floor 1 to two far levers on floor 8), fog of war, 4 enemy types (crawler, archer, brute, warden), spikes, potions.
- Echoes are literal: they repeat inputs, not intentions. If the world differs, an echo may swing at air or bump a wall. Enemies reset every loop and attack echoes too.
- Mistakes are recoverable: **unravel** any echo (costs 1 thread) to free its slot, and your next loop is recorded in its place. You start with 2 threads and earn 1 per floor cleared. If your last loop ends short of the stairs with every slot full, you pick an echo to unravel; the run only ends when you have no threads left.
- Roguelite: pick 1 of 3 upgrades per floor; earn shards to buy permanent perks in the Echo Forge.
- Scored floors: every turn you take on a floor counts, in every loop. **Par** is the shortest clear of the intended solution (each echo walks straight to its plate; the last loop waits at each door exactly as long as needed), enemies aside. Grades run S+ (par or better) to D; S and S+ pay bonus shards. Par is verified by replaying it keystroke-for-keystroke in the real simulation. Clever plans (one echo holding two plates in turn) can beat it. Par also follows the sconces you light: each one raises it by what it costs to reach (planned and verified the same way), so lighting every sconce at par is an S+ and the best score on the floor.
- **Sconces:** walk within two steps of one to light it. Lit sconces stay lit from loop to loop, show what moves near them from anywhere on the floor, and add up to +200 to the floor's score. In The Long Night they matter more: the Still climb home up the stair by Aurel's lamps, and on the dark stretches some lose their way.
- Story scenes painted as pixel art (a cut through the whole world, the Counting House, the Drum Room, the break in the caves, and more), each a static layer painted once in the background plus animated light on top.
- Lamplit look: textured stone, torches in sconces that Aurel lights as he passes, his lantern and the torches as real light, smooth movement, an illustrated intro, a thread-rewind animation between loops, a victory scene with a score tally on every floor, and a dawn (or a snapped thread) at the end.
- Every generated floor is verified: a scripted bot clears it with the baseline kit before you ever see it, so no floor is a dead end.

## Run

**Full usage guide (every game, every key, The Long Night, the Story, dev mode): [`docs/usage.md`](docs/usage.md).**
**Design brief (the plot, the themes, how every mechanic ties in, the tone and art standards): [`docs/design.md`](docs/design.md).**

```
python3 -m venv .venv
./.venv/bin/pip install pygame-ce
./.venv/bin/python -m echo            # optional: --seed=123   --game=night | stillwater | tick
```

Headless (VM / CI): `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`

Dev mode (`--dev`, or `ECHO_DEV=1`): F9 finishes any level at par, F10 finishes it perfectly, F11 fails it; in The Long Night's hub F12 skips to everyone's last level and F5/F6 move the thread by an hour; and **Endings (dev)** on the Long Night's title lets you pick how a night went and see its ending. The Long Night's **The Story** plays the whole story front to back, with the Drum Room's choice played live. See `docs/dev.md`.

## Controls

Arrows/WASD move, strike, or pull a lever (walk into it), Space or `.` wait, `E` (twice) anchor and end the loop, `U` unravel an echo (pick with 1-9 or click, Enter confirms), Tab toggle echo paths, click an adjacent tile to step, right-click to inspect, `H` help, Esc menu. Bumping a wall or sealed door costs no turn.

## Test

```
./.venv/bin/python -m unittest discover -s tests
```

Covers the simulation (doors, echoes, enemies, spikes), floor generation properties and bot-solvability, run/meta logic, par and scoring, and the UI (including the intro, victory scenes and animations) through real input events, plus random-input storms (including one through the whole Long Night).

Font: TeX Gyre Pagella, bundled in `echo/assets/fonts/` under the GUST Font License (see the license file there).

MIT licensed.
