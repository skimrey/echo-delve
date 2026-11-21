# Usage guide

Four games in one package: **Echo Delve** (Aurel), **Stillwater** (Tarn), **The Tick** (Maren), and
**The Long Night**, which plays all three as one game on one shared thread of time.

## Install

Python 3.10 or newer. From the project folder:

```
python3 -m venv .venv
./.venv/bin/pip install pygame-ce
```

## Run

```
./.venv/bin/python -m echo                      # Echo Delve (Aurel)
./.venv/bin/python -m echo --game=stillwater    # Stillwater (Tarn)
./.venv/bin/python -m echo --game=tick          # The Tick (Maren)
./.venv/bin/python -m echo --game=night         # The Long Night (all three, one thread)
```

Options (any game):

| Option | What it does |
|---|---|
| `--seed=123` | fixed seed: the same generated levels every time |
| `--dev` | dev mode: keys to finish or fail any level, the endings picker (see `docs/dev.md`) |
| `ECHO_DEV=1` (environment) | the same as `--dev` |
| `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` (environment) | run headless (CI, no display) |

Progress (shards, forge perks, best scores, which story scenes you have seen) is saved in
`~/.echo_delve/meta.json`. Delete it to start fresh.

## Menus

| Screen | Keys |
|---|---|
| Echo Delve title | **N** new run, **S** the story, **F** Echo Forge (permanent perks), **H** how to play, **Esc** quit |
| Stillwater / The Tick title | **N** play, **S** the story, **H** how to play, **Esc** quit |
| The Long Night title | **N** begin the night, **S** the Story, **H** how to play, **Esc** quit (dev mode: **E** endings) |
| Story scenes (cutscenes) | **Enter/Space/click** finish the line, then next; **Left/Backspace** back; **Esc** skip |
| Cards (level intros, results, choices) | **Enter/Space** continue; **1 / 2** pick a choice |

## Echo Delve (Aurel)

Reach the gold stairs on each of 10 floors. Numbered doors open only while something stands on their
plate; lettered gates flip when their lever is pulled. You can't be in two places at once, but your
past loops can: every loop you end becomes an **echo** that replays your exact moves next loop.

| Key | Action |
|---|---|
| Arrows / WASD | move, attack, or pull a lever (walk into it) |
| Space or `.` | wait a turn |
| E (twice) | anchor: end this loop here (your echo will stand here) |
| U | unravel an echo (pick with 1-9 or click, Enter confirms): frees its slot, costs a thread |
| Tab | show / hide echo paths |
| Click a neighbouring tile | step there |
| Right-click | inspect a tile |
| H | help |
| Esc | menu (resume, abandon run) |

- **Sconces:** walk within two steps of a sconce to light it. It stays lit every loop, shows what moves
  near it, and is worth points. Par rises by what each sconce costs to reach, so lighting every sconce
  at par is the best score on a floor.
- **Score:** every turn counts, in every loop. Grades run S+ (par or better) to D; S and S+ earn shards.
- After each floor, pick one of three upgrades. Shards buy permanent perks in the Echo Forge.

## Stillwater (Tarn)

Lead the Still to the way on (the pale shaft of light) in each chamber. They follow only light they
can see: your glowing wake, and the shoulder of the one in front of them.

| Key | Action |
|---|---|
| Arrows | move (wading stirs a ripple that lights the water) |
| Space | wait (silent) |
| T | touch the water: a ripple that travels much further |
| F, then a direction | throw a pebble (draws eels away) |
| Enter | go on (from the way on) |
| B | step back 5 turns (an eel found you, or a wrong turn); the time stays spent |
| R | start the chamber over |
| H | rules |
| Esc | leave |

- **Float-gates** rise when a ripple reaches their float, then sink again: send the wave, then bring
  everyone through. A long line takes time to pass.
- **Eels** are blind: they feel ripples (yours and your people's) and swim to where they began.
- **The water dims** as the night runs down, and in dim water every turn costs more.
- **At the break** (the last chamber) you choose: take your people through, or let them stay.

## The Tick (Maren)

Get out of the Guild's clock tower with the stolen Regulator. The doors below are barred, so the only
way is up: reach the stair (X) on each floor without being seen.

| Key | Action |
|---|---|
| Arrows | move (turns the tower's clock on by one tick) |
| Space | wait a tick |
| Q (hold) | wind the whole tower back a tick at a time, while you stay put (a minute of the hoard each) |
| [ and ] | look at other ticks for free (ghost wardens and their sight cones) |
| Enter | wind the tower to the tick you are looking at |
| R | retry the floor |
| H | rules |
| Esc | leave |

- Wardens see in a cone ahead of their lanterns. Being seen, walking into one, or still being on the
  floor when the Quarter Bell rings snaps you back four moves (if the hoard can pay) or restarts the floor.
- The timeline at the bottom shows when each door is open (gold) and when your tile is watched (red).
- **In the Drum Room** at the top, the Guildmaster offers a bargain. Open the brake, or take it.

## The Long Night

All three stories on one **thread**: the time that is left. Every turn in any story spends a minute of
it. Whatever is left when Aurel ties the thread becomes the first morning (the hub shows how long a day
it would make right now).

1. **Begin the Night** (N). The night is built (a few seconds), then you choose how much thread is left:
   **1** long, **2** measured, **3** short. Each card shows the minimum a perfect night needs (the mark
   on the thread) and how much room is left over.
2. The night opens with each of the three once, in turn, each with their own story first.
3. Then the **hub**: **1** Maren (the Tick, above), **2** Aurel (the Deep), **3** Tarn (the caves), in
   any order. **Esc** returns to the title. Leaving a level part-way is allowed: the minutes spent stay
   spent, and you resume where you left off. In Echo Delve, Esc then **A** goes back to the night.

**The order is the main decision:**

- The Guild sells its drum of hoarded hours all night, faster the deeper Aurel goes. The sooner Maren
  reaches the Drum Room, the more there is to let go back into the thread.
- In dim water every one of Tarn's turns costs more. The water dims as the thread shortens, and Aurel's
  lit sconces brighten it again.
- Aurel's last floor, the Loom, ends the night for everyone (the game warns you first). Anyone still in
  the caves is lost, and the hoard left on the drum goes back to the Loom.
- If the thread runs out before it is tied, there is no morning at all.

The ending plays a scene for each of the three, then the record of the night. A perfect night: every
sconce lit, every one of the Still home, the hoard let go.

## The Story

On The Long Night's title, **S** plays the whole story front to back as its painted scenes, with the
two choices (Tarn's at the break, Maren's in the Drum Room) played live over their scenes.

| Key | Action |
|---|---|
| Enter / Space / click | finish the line, then next |
| Left / Backspace | back a panel (across chapters) |
| 1-9, or click a chapter along the bottom | jump back to a chapter you have seen |
| Esc | back to the title |

Going back past a choice and on again asks it again, so you can see every branch.

## Dev mode

Run any game with `--dev` (or `ECHO_DEV=1`). A DEV badge appears; **F1** shows the keys.

| Key | Where | Action |
|---|---|---|
| F9 | any level | finish it at par (the time par would cost is still spent) |
| F10 | any level | finish it perfectly (every sconce / everyone saved / no hoard spent) |
| F11 | any level | fail it |
| F12 | Long Night hub | skip ahead: all three at their last level |
| F5 / F6 | Long Night hub | thread +1 hour / -1 hour |
| E | Long Night title | the endings picker: choose how a night went, and see its ending |

In dev mode the Story also asks, before its ending, how the rest of the night went. Full details and
recipes are in `docs/dev.md`.

## Tests

```
./.venv/bin/python -m unittest discover -s tests      # about 3-5 minutes
./.venv/bin/python -m unittest discover -s tests -p "test_dev.py"   # one file
```

## More

- `docs/design.md`: the design brief: plot, themes, how the mechanics tie together, tone and art standards.
- `docs/universe.md`: the world, the characters, and how the games fit together.
- `docs/dev.md`: dev mode and the Story in detail.
