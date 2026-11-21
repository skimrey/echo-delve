# The Long Night: design brief

Read this before changing anything. It explains what the games are *for*: the story, what it is about,
how every mechanic expresses that, and the tone and standards the project has been held to. The
details live elsewhere (`docs/universe.md` for the world, `docs/usage.md` for controls, `docs/dev.md`
for testing tools); this is the why.

---

## 1. In one paragraph

Hollowmere has had no morning for 312 days. The Loom of Hours, at the bottom of the Deep, weaves each
day onto a golden thread; for generations the Guild of Hours kept a little of every day back and sold
it as lamplight, until the thread wore thin and snapped. On the three hundred and twelfth night, three
people are awake: **Aurel**, a lamplighter's son going down the stair with a lantern that was never
meant for him; his sister **Maren**, running on stolen time; and **Tarn**, one of the Still, people who
have lived in the dark caves beside the thread for generations and have only just learned what light
is. Each has their own game. **The Long Night** plays all three on one shared thread of time: every
turn anywhere spends it, and what is left when Aurel ties the thread becomes the first morning.

## 2. What it is about

The games are about **time as a shared, finite thing, and what people do with it.**

- **Hoarding vs. sharing.** The Guild did not break the world with malice but with a kindness that
  compounded: keeping a little summer back for winter. Every lamp they sold burned a little of tomorrow;
  the shorter the days grew, the more lamps the town bought. They sold the cure for a cold they were
  making, so slowly that nobody alive remembered it any other way. The villainy is arithmetic.
- **Duty that was handed to you.** The lantern passes mother to daughter. Maren, afraid, put it in her
  brother's hands and ran. Aurel, untrained, stopped waiting for someone else and went down. Neither
  is a hero; both are people deciding, late, what they owe.
- **Light is not neutral.** The same event that saves the town (tying the thread) takes the light away
  from the Still. Nobody's good ending is free.
- **Truth is what ends the cycle.** Nothing physical stops the Guild starting again. What ends it is the
  town understanding: Maren's stolen ledger, nailed to the door of the Tick.

Every mechanic should be readable as one of these ideas. If a new mechanic can't be, it doesn't belong.

## 3. The world's rules (keep these consistent)

1. **There is only ever one day.** Every night the Loom unpicks the day that ended and weaves the same
   thread into the next morning (Penelope's loom).
2. **Thread burned in a lamp never goes back.** The only way to destroy it.
3. **A day is a great deal of light.** Half of one, sold a lampful at a time, lasts for years.

From these: since the snap nothing is rewoven, so every minute spends thread for good; the remaining
thread is "the time that is left"; tying it lets the Loom take back everything left of the old day
(the Guild's hoard, the light in the Still's water, hours kept in a watch) to weave the morning; the
first morning is only as long as the share of the last day that survived the night; and it can never
be as long as the old summers again, because too much was burned.

If you add lore, check it against these three rules. Contradictions have been caught and fixed many
times (e.g. "what's left of the day" when no day was left; midnight days that would need burned hours
back; a promise nobody heard the Guild make). The user reads closely.

## 4. The three games, and what each mechanic means

### Echo Delve: Aurel (the duty he picked up)
- **Echoes.** The broken end of the thread bound itself to his wrist: when a loop fails, it pulls him
  back, and his past steps keep walking beside him. You solve floors by coordinating with your own
  past: send loop 1 to hold a plate, walk through the door in loop 2. *You cannot be in two places;
  your past can.*
- **Unravel.** Erase an echo to free its slot. In the Long Night it cuts 20 minutes of the shared
  thread: correcting the past costs everyone time.
- **Sconces.** The Vells light the stair so whoever has to go down can find the way. Walking close
  lights one; it stays lit every loop and shows what moves near it. In the Long Night the lit share of
  the stair is how the Still find their way home, and it brightens their water through the keeper's
  windows. Par rises with each sconce (a planner computes the cheapest clear for every count, checked by
  replaying it), so the completionist's perfect (every sconce at par) scores best, not worst.
- **Wardens** are the people who ran out of thread before him. One carries his mother's lantern.

### Stillwater: Tarn (getting everyone out, in time)
- **Light you make.** The spilled day sleeps in the water; wading stirs ripples that light it. Ledges
  are dry and silent. The cave exists on screen only where it has been lit.
- **The Still follow your wake**, never crowding one tile, each stepping only where they can see the
  light or beside someone ahead of them who can: *a hand on the shoulder in front.* More followers
  means a longer line, more of them wading, more ripples for eels to hear, and more time to pass a
  float-gate. The line is the difficulty.
- **Eels** are blind and hunt movement. Pebbles draw them off.
- **The water dims** as the thread shortens; in dim water every turn costs more (1/light minutes).
- **Step back** undoes five turns; the time stays spent. Mistakes cost time, not the chamber.
- **The choice at the break:** take them through (a bet on Aurel: the sun if he ties it, the dark at
  the bottom of the world if not) or let them stay (the hedge: the light never leaves if no morning
  comes; the water goes black if it does).

### The Tick: Maren (what she does with stolen time)
- **She worked for the Guild** (the only people hiring in a town without mornings), kept their books,
  planned the theft for months. What she didn't know: the watch is tied to the bell. The game is her
  escape, upward, because the doors below are barred.
- **The Regulator** winds the whole tower back around her while she stands still. Every tick costs a
  minute of the hoard: using stolen time is spending someone's time.
- **Hour reels** she cuts loose go into the shared thread in the Long Night.
- **The Drum Room.** The Guildmaster offers a bargain for the ledger: her brother's safety (slack sent
  down, his unravels paid for), and the watch, warm. It is real, and late in a night it can be worth
  more minutes than the brake. It is never worth the mornings after: the watch goes cold at dawn (they
  knew), and by nightfall the brake is shut again. Opening the brake sends every hour down the thread,
  and she nails the ledger to the door.

## 5. The Long Night: how it all ties together

**One resource: the thread.** Every turn in any story spends a minute. Aurel's unravels cut it. Only
the Guild's hours let go can lengthen it. It is sized against this night's own *perfect par* (every
sconce lit, every one of the Still home, Maren out): long 2.2x, measured 1.7x, short 1.35x, so a perfect
night is always possible on a long thread and choices bite on a short one.

**What is left becomes the morning.** The first day's daylight is the surviving share of the last day
(thread + unsold hoard + watch, out of what there was at nightfall) times a full old summer day. The hub
always shows it: "Tied now, it would make a day until 4:30 in the afternoon."

**Order is the main decision.** After an opening that visits each of the three once (each with their
own prologue), you choose whose part to play next, and the order changes what the night costs:

| | Why earlier | Why later |
|---|---|---|
| **Maren** | the Guild sells the drum all night (faster the deeper Aurel goes): earlier, more to let go | (the bargain is worth a fixed amount, so arriving late makes it tempting) |
| **Tarn** | brighter water: cheaper turns, easier chambers | Aurel's sconces brighten it too; and Aurel near the Loom means the stair is lit when the Still arrive |
| **Aurel** | lit sconces brighten Tarn's water | he is the biggest spender; each floor makes the Guild sell faster; his last floor ends the night |

Measured on one night: a good order leaves about 12½ hours of thread on a measured thread, a bad one
about 8; on a short thread, 5½ hours versus 36 minutes.

**The endings answer for everything.** A scene for Aurel (the Loom tied, or woven in), for the Still
(sunrise up the lit stair, the dark hall, or the water going black), for Maren (the reunion: he holds out
their mother's lantern, and this time she takes it; or the coach, and the cold road), the ledger or the
brake shut again, then the record. A perfect night gets its own scene (the whole stair burning, the Still
climbing it behind him at dawn).

## 6. Tone: the writing standard

The user has been precise about voice. Hold to it.

- **Haunting, restrained, concrete.** One person, one image: *"His sister, running on stolen time."*
  *"Then one of them reaches out, very slowly, and touches your hand, the way you might touch water."*
- **Don't explain what an image already says.** "The rest of that day burst through the wall" already
  implies a day was on the thread; "snapped with a whole day on it" was cut as clunky.
- **Omission is allowed.** Why Aurel went tonight is one line: *"For a long time you waited for someone
  else to go down it. Then you stopped waiting."* Not more.
- **No mechanics in the story text.** Keep numbers, keys and rules in cards and help, not in cutscenes.
  Amounts in the story are in hours and words, not "300 minutes".
- **No repetition** of words like "night" and "time" in consecutive lines; vary or cut.
- **Every pronoun needs an antecedent** ("whose grandchildren?" was a real bug).
- **Motivations must be legible and human.** Maren isn't greedy; she is afraid and grieving and had a
  plan. The Guild isn't cartoonish; it did the arithmetic.
- **Characters:** Aurel (he), Maren (she), Tarn (he), the Still, the Guildmaster, the Vells' mother
  (a Warden now). Never call a generic townsperson by a character's name.

## 7. Art direction

- **Pixel art with finesse, not diagrams or word art.** Scenes are painted on a 320x147 canvas and
  scaled 3x (nearest neighbour) so their pixels match the character sprites; static layers are painted
  once (textured rock, dithered light, baked lamplight) and cached, with animation and soft glow on top.
  No labels on pictures.
- **Characters** are the small sprites in `theme.py` (the user likes the little lamplighter). Reuse them.
- **Show, then tell.** If the text says the Still tumble in a heap, the scene shows them tumbling. If a
  child touches the water, the rings spread from that child.
- **Check every scene with a screenshot** (headless, `SDL_VIDEODRIVER=dummy`) and look at it before
  calling it done. Common faults caught: snow that floods downward, figures inside a dark fade, a hole
  that looked like a circuit board, labels that looked like word art.

## 8. Design principles (learned from the user's feedback)

- **Least punishing, still meaningful.** Mistakes cost time, not progress: unravel an echo instead of
  restarting a floor; step back in Stillwater; snap back in the Tick. The shared thread makes every
  mistake matter without ever locking you out.
- **Every generated level is proven solvable** by a bot, solver or guide before you see it (and eels are
  only placed where a safe way past exists). Never ship a level that could be impossible.
- **Completionists are rewarded, not punished.** A perfect run (every sconce, everyone saved, the hoard
  released) must be achievable, scored highest, and acknowledged in the ending.
- **Real choices have real trade-offs.** The bargain and Tarn's choice are each better in some
  situations. A choice with an obvious right answer is a cutscene, not a choice.
- **Order, not grind, is the strategy.** The budget is decided by sequencing and cleanness of play.
- **Everything visible.** If a number matters (thread left, drum left, cost per turn, the morning's
  length, sconces lit), it is on screen.

## 9. Code map

| Path | What |
|---|---|
| `echo/sim.py`, `floor.py`, `run.py`, `score.py`, `bot.py` | Echo Delve: simulation, generation, runs, par and the sconce planner, the bot |
| `echo/game_screen.py`, `cinematics.py`, `menus.py`, `unravel_screen.py` | Echo Delve screens; `cinematics.py` also holds the intro/cutscene screen |
| `echo/scenery.py` | every painted pixel-art scene (one class per scene, variants by argument) |
| `echo/story.py` | Aurel's text; `sisters/tick.py` and `sisters/stillwater.py` hold Maren's and Tarn's |
| `echo/sisters/` | The Tick and Stillwater: rules, generation, solvers, screens |
| `echo/campaign.py` | The Long Night: the thread, order effects, the drum, chapters, lengths |
| `echo/ending.py` | how a night ends, from a `NightOutcome` (used by the game and the Story) |
| `echo/night_screen.py` | title, length choice, hub, epilogue |
| `echo/story_reel.py` | the Story (front to back, with the two choices), and the dev endings picker |
| `echo/dev.py` | dev-mode keys |
| `tests/` | ~300 tests: simulation, generation, solvability, scoring, story canon, UI through real input, random-input storms |

## 10. Working conventions

- Run the tests (`./.venv/bin/python -m unittest discover -s tests`, a few minutes) before finishing.
- Lint with `pyflakes`. Keep docstrings and `docs/` in step with the code and lore.
- Make screenshots of anything visual and look at them.
- When the user asks a question, answer it honestly (including "this is a real gap" or "you are right"),
  then fix it. When a design question has a better answer than the one asked for, say so and explain.
- At the end of a session the games are relaunched for review: all four, with The Long Night in front.
