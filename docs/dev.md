# Dev mode and the Story

## Running in dev mode

```
./.venv/bin/python -m echo --dev --game=night     # The Long Night, with dev keys
./.venv/bin/python -m echo --dev                  # Echo Delve on its own
./.venv/bin/python -m echo --dev --game=stillwater
./.venv/bin/python -m echo --dev --game=tick
ECHO_DEV=1 ./.venv/bin/python -m echo --game=night   # the same, from the environment
```

A small **DEV** badge sits in the bottom-right corner. Press **F1** to show the keys.

## Keys

| Key | Where | What it does |
|---|---|---|
| F1 | anywhere | show or hide the dev keys |
| F9 | any level | **finish it**: a clean clear at par. The turns par would have cost are spent from the thread (or the night), so budgets stay realistic |
| F10 | any level | **finish it perfectly**: Echo Delve lights every sconce first (and spends the all-sconces par); Stillwater saves everyone, stranded too; The Tick spends none of the hoard |
| F11 | any level | **fail it**: Aurel's thread runs out (the run ends, or in The Long Night he is woven in); an eel finds Tarn (B steps back, R retries); a warden sees Maren (R retries) |
| F12 | The Long Night's hub | **skip ahead**: the opening counts as told, and all three are at their last level (Aurel at the Loom, Maren at the Drum Room, Tarn at the last chamber) |
| F5 / F6 | The Long Night's hub | lengthen / shorten the thread by an hour |

Nothing else changes in dev mode: levels, saves and scores behave as usual. Finishing a level with F9
or F10 still plays its victory scene and card, so the flow after it can be tested too.

Some quick recipes:

- **See the Drum Room choice:** `--dev --game=night`, begin a night, F12 at the hub, play Maren (1),
  F9 to the top. The Guildmaster's interlude plays, then the choice.
- **See Aurel's Loom and a real ending:** F12, then F10 through Tarn's and Maren's last levels, then
  Aurel (2): the Loom warning, then F10. The ending scenes follow from what you did.
- **Test a short thread running out:** F6 a few times at the hub, then play anything.
- **See every interlude:** they play the first time each level is reached (and once per save in the
  games on their own; delete `~/.echo_delve/meta.json`, or its `seen_scenes`, to see them again).

## The Story

On The Long Night's title, **The Story** plays the whole of it, front to back, as its painted scenes:

1. the world (the Loom, the summer the Guild began keeping a little back, the winter they sold it, the
   Spindle, the snap, the light in the water, the Guild's arithmetic, the three of them awake);
2. each of the three in turn: Aurel's, Maren's and Tarn's prologues;
3. the middle of the night: Maren finding the ledger, the first sconce lit again, the old ones and the
   children, Aurel resting with his echoes;
4. **the break**: Tarn's choice, played (not told) over the animated scene: take them through (they
   slide down the Spindle and land in a heap at the Loom), or let them stay;
5. **the Drum Room**: the Guildmaster's offer, then Maren's choice: open the brake, or take his bargain;
6. Aurel at the Loom's door, and the ending that follows from both choices (everything else as on a
   perfect night), then the record.

**Chapters** appear one at a time along the dark strip at the bottom as you reach them: click one (or
press its number, 1 to 9) to go back to it. **Back** (Left / Backspace) goes back a panel, across
chapters. Going back past a choice and on again asks it again, and the rest of the Story follows the new
answer, so every branch can be seen. Enter finishes a line, then goes on; Esc returns to the title.

### Every ending (dev)

In dev mode the Story asks, just before its ending, **how did the night go?**, and the Long Night's
title has **Endings (dev)** (key E) to go straight there. Pick:

| Row | Options |
|---|---|
| How the night ends | Morning / The thread ran out / Aurel was woven in |
| Aurel's sconces | Every one lit / About half / None |
| The Still | Everyone home / Some lost on the way / Many left in the caves / Tarn never reached them / Tarn let them stay |
| Maren | Opened the brake / Took the Guild's bargain / Caught on the stairs / Never reached the drum |
| The first morning | A long day / Until noon / Barely a morning |

Up/Down choose a row, Left/Right change it, **P** sets a perfect night, **X** the worst morning, Enter
plays that ending (its scenes, then the record). The picker says whether the pick makes a perfect
night. Every combination is covered by a test (`tests/test_dev.py`).

## Where the pieces live

- `echo/dev.py`: the dev keys and the badge.
- `echo/story_reel.py`: the Story, and the endings picker (`OutcomeScreen`, `outcome_for`).
- `echo/ending.py`: how a night ends, from a `NightOutcome` (what happened). The Long Night builds one
  from the night that was played (`Campaign.outcome()`); the Story builds one from its choices.
