"""THE LONG NIGHT: the three stories as one game, on one thread.

- THE WORLD'S THREE RULES: (1) there is only ever one day: every night the Loom unpicks the day
  that has ended and by morning has woven the same thread into the next; (2) thread burned in a
  lamp never goes back to the Loom; (3) a day is a great deal of light. The Guild began by keeping a
  little of each long summer day back to warm the winter nights; each morning was woven from a
  little less, the shorter days sold more lamps, and the thread thinned until it snapped. Half a
  day caught on their drum, sold a lampful at a time, lasts for years; tying the thread would let
  the Loom take it all back. So they keep the night.
- THE THREAD IS THE TIME THAT IS LEFT: since the snap the Loom has nothing to unpick, so every
  minute that passes spends thread for good. Every turn in any of the three stories spends a minute of it; Aurel's unravels cut lengths of it; it LENGTHENS whenever the
  Guild's hours are let go (Maren cutting an hour reel loose, or releasing the hoard at the top).
  You choose how long it starts (LENGTHS): a multiple of this night's perfect par. If it runs out,
  there is nothing left for the Loom to weave a morning from.
- The Guild broke it: for years they kept a little of every day back on their drum, thinning the
  thread until it snapped under the weight of a day. (It used to be thick as a wrist; the days were long.)
  It snapped halfway up the Spindle (the chimney-wide bore it climbs through the rock), right beside
  the Still's caves: the top half whipped up to the drum (the hoard), and the rest of the day burst
  through the thin wall, broke it open, and poured into the Still's water.
- AUREL (Echo Delve) ends the night: when he ties the thread on his last floor, the new day
  comes. There is only ever one day: the Loom weaves the morning out of everything left of the old
  one. It takes back the light in the Still's water (any of them not yet out are lost to the dark)
  and whatever is still wound on the Guild's drum, or kept in a watch.
- TARN (Stillwater) must bring the Still through before that, and before the thread runs out. The
  water dims as the thread shortens, so the later his chambers, the harder; but the sconces Aurel
  has lit shine through the keeper's windows, across the Spindle and through the break, and give
  some of the light back (LAMPLIGHT at a fully lit stair).
- MAREN (The Tick) spends her own hoard (the Regulator's minutes) to get up the tower. In the
  Drum Room she decides: release what is left into the thread (more time for everyone) or keep
  it. Kept hours go back to the Loom when the new day comes; she only learns that at the end.
- THE ORDER: the opening plays each story once (Aurel, Maren, Tarn), each with its own prologue;
  after that any order, and it matters: Tarn early means brighter water; Maren's freed hours
  lengthen the thread (and so brighten the water too); Aurel's lit sconces brighten it as well, and
  light the Still's way home; and Aurel tying the thread ends the night for everyone.
- THE LAMPS: the Still come out of the Spindle at the bottom, in the Loom's hall, and climb home
  by the Spindle stair, by the sconces Aurel lit on his way down. On the dark stretches some lose
  their way: the share of sconces left cold (DARK_LOSS of it) costs that share of the saved.
- If the thread runs out before it is tied, there is no morning at all.
"""

import random

from . import ending, story
from .floor import generate_floor
from .run import Run
from .score import lamp_info, par_turns
from .sisters import stillwater as sw
from .sisters import tick as tk

# how much thread is left (the difficulty, as a length): a multiple of this night's own par
# A multiple of this night's PERFECT par: the fewest minutes in which every sconce is lit, every
# one of the Still is brought through, and Maren climbs the tower (see Campaign.perfect_par).
LENGTHS = [
    ("long", "A long thread", 2.2, "Enough to light every sconce and go back for everyone, with room for mistakes."),
    ("measured", "A measured thread", 1.7, "Enough for everything, if you are careful where it goes."),
    ("short", "A short thread", 1.35, "Every minute matters. Someone will be left behind."),
]
ECHO_FLOORS = [1, 2, 3, 5, 7, 10]      # Aurel's way down: the Loom is always the last
STILL_GENERATED = 2
TICK_GENERATED = 2
PROLOGUE = ["echo", "tick", "still"]   # the opening order; after that, any order
TRACKS = ["tick", "echo", "still"]     # above, within, below
DARK_LOSS = 0.3                        # on a stair left wholly dark, this share of the saved Still lose their way
LAMPLIGHT = 0.2                        # how much a fully lit stair brightens the Still's water
BARGAIN_SHARE = 0.08                   # the Guild's offer: this share of a perfect night, sent down the thread
DRUM_SHARE = 0.3                       # the Guild's drum holds this share of a perfect night when the night begins
GUILD_RATE = 0.2                       # and they sell this many minutes of it for every minute of the night...
AUREL_SPUR = 0.25                      # ...faster by this much for every floor Aurel clears (they feel him coming)
CHAPTERS = {"echo": story, "tick": tk, "still": sw}
HEROES = {"echo": "Aurel", "tick": "Maren", "still": "Tarn"}

INTRO = [
    ("loom", "At the bottom of the Deep, the Loom of Hours weaves each day and sends it up to Hollowmere on a single "
             "golden thread. Every night it unpicks the day that has ended, and by morning it has woven the same "
             "thread into the next. There is only ever one day."),
    ("summer", "Once the thread was thick as a wrist, and summer evenings lasted until midnight. It began as a "
               "kindness: the Guild of Hours kept a little of each long summer day back, on the drum of their great "
               "clock, the Tick."),
    ("winter", "And in winter, when the days were short and the nights were long, they sold it back to the town, a "
               "lampful at a time, to keep the houses warm."),
    ("guild", "But thread burned in a lamp never goes back to the Loom. Each morning was woven from a little less. The "
              "shorter the days grew, the more lamps the town needed, and the more the Guild sold. The thread wore "
              "thin."),
    ("spindle_whole", "It climbs to the town through the Spindle, a shaft bored straight up through the rock, sealed "
                      "so well that the thread inside never let out a glimmer. Beside it winds the stair the "
                      "lamplighters keep. And halfway up, behind a skin of limestone, lie caves that no one in "
                      "Hollowmere knew were there."),
    ("spindle", "Three hundred and twelve days ago, where it had worn thinnest, the thread snapped. The top half "
                "whipped up onto the Guild's drum. The rest of that day burst through the wall, and sank into the "
                "black water of the caves."),
    ("pool_glow", "It settled there like silt. Still water looks black; stir it, and the spilled light rises in rings. "
                  "The people who lived in those caves had never seen light before."),
    ("spool", "Since then the Loom has had nothing to unpick. What is left of the thread is all the time there is, and "
              "every minute that passes spends it for good. A day is a great deal of light: sold a lampful at a "
              "time, the half on the Guild's drum will last for years, at a price that climbs every night."),
    ("ledgers", "Tie the thread, and the Loom can weave again. It will take back everything left of the old day, the "
                "hoard on the drum and the light in the water, and make a morning of it. The Guild has done the "
                "arithmetic: there is enough on the drum to keep them warm for the rest of their lives. They would "
                "rather keep the night."),
    ("three", "In all of Hollowmere, three people are awake. A lamplighter's son, going down the stair with a "
              "lantern that was never meant for him. His sister, running on stolen time. And in the rock beside the "
              "Spindle, someone stirring the water."),
]

ORDER_TITLE = "The rest of the night is yours"
ORDER_TEXT = ("From here the order is yours, and it decides how much thread is left. The Guild is selling the drum "
              "all night, faster the deeper Aurel goes: the sooner Maren reaches it, the more there is to let go. "
              "In dim water the Still move slowly and every turn costs more, so Tarn is cheapest early, or by the "
              "light of Aurel's sconces. When Aurel ties the thread the night ends, and whatever is left of it "
              "becomes the morning.")


class Thread:
    """The thread: the time that is left, in minutes. It shortens with every turn and lengthens
    whenever the Guild's hours are let go."""

    def __init__(self, minutes):
        self.minutes = self.start = int(minutes)
        self.listeners = []           # called with the minutes spent (the Guild, selling as the night goes)

    def spend(self, n=1):
        self.minutes = max(0, self.minutes - n)
        for cb in self.listeners:
            cb(n)
        return self.minutes == 0

    def give(self, n):
        self.minutes += n

    @property
    def empty(self):
        return self.minutes <= 0

    def hm(self, minutes=None):
        m = self.minutes if minutes is None else minutes
        return "%d:%02d" % divmod(m, 60)


class Campaign:
    def __init__(self, seed=None, length=None, perks=None):
        """Builds every level of the night up front (the thread is measured against them). The
        three stories begin once the thread is cut to a length: set_length(), or pass `length`."""
        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        self.perks = perks
        self._echo_floors = {f: generate_floor(self.seed, f) for f in ECHO_FLOORS}
        self.lamps_total = sum(len(lamp_info(f).sconces) for f in self._echo_floors.values())
        still_run = sw.StillRun(self.seed, generated=STILL_GENERATED)
        self._chambers = {i: still_run._build(i) for i in range(still_run.chambers)}
        tick_run = tk.TickRun(self.seed, generated=TICK_GENERATED)
        self._tick_floors = {i: tick_run._build(i) for i in range(tick_run.floors)}
        self.par = dict(
            echo=sum(par_turns(f) for f in self._echo_floors.values()),
            still=sum(sw.walkthrough(c).turn for c in self._chambers.values()),
            tick=sum(_tick_moves(lv, True) for lv in self._tick_floors.values()))
        # a perfect night: Aurel lights every sconce on the way down (the rest is already everyone)
        self.perfect_par = sum(self.par.values()) - self.par["echo"] + \
            sum(lamp_info(f).par_all or par_turns(f) for f in self._echo_floors.values())
        self.length = None
        if length is not None:
            self.set_length(length)

    def minutes_for(self, length):
        """How long the thread is at each length: a multiple of this night's perfect par."""
        mult = {d[0]: d[2] for d in LENGTHS}[length]
        return int(mult * self.perfect_par)

    def set_length(self, length):
        """Cut the thread, and start the three stories on it."""
        self.length = length
        self.thread = Thread(self.minutes_for(length))
        self.echo = Run(self.seed, perks=self.perks, thread=self.thread, floors=ECHO_FLOORS,
                        prebuilt=self._echo_floors)
        self.still = sw.StillRun(self.seed, thread=self.thread, generated=STILL_GENERATED, prebuilt=self._chambers)
        self.tick = tk.TickRun(self.seed, thread=self.thread, generated=TICK_GENERATED, prebuilt=self._tick_floors)
        self.state = "night"          # night | morning | endless | woven
        self.hoard_choice = None      # None (never reached the drum) | "released" | "bargain"
        self.released = 0
        self.tick_failed = False
        self.drum_f = self.drum_start = DRUM_SHARE * self.perfect_par     # the Guild's hoard, on the drum
        self.still_choice = None      # at the break, Tarn takes them "through", or lets them "stay"
        self.kept = 0                 # hours Maren kept in her watch (the morning will take them back)
        self.thread.listeners.append(self._guild_sells)
        self.told = set()             # chapters of the story already told this night
        self.order_told = False       # the card that opens the rest of the night
        self.ending_told = False
        self.still.lamplight = lambda: LAMPLIGHT * self.stair_lit()   # Aurel's sconces, through the break

    # ---------------------------------------------------------------- progress
    def done(self, track):
        if track == "echo":
            return self.echo.cleared
        if track == "still":
            return self.still.index
        return self.tick.index

    def total(self, track):
        return {"echo": len(ECHO_FLOORS), "still": self.still.chambers, "tick": self.tick.floors}[track]

    def finished(self, track):
        if track == "tick":
            return self.tick.state in ("climbed", "spent")
        if track == "still":
            return self.still.state == "done"
        return self.echo.state == "won"

    @property
    def prologue_next(self):
        """During the opening, the one story that must be played next (else None)."""
        for track in PROLOGUE:
            if self.done(track) == 0 and not self.finished(track):
                return track
        return None

    def available(self, track):
        if self.state != "night" or self.finished(track):
            return False
        p = self.prologue_next
        return p is None or p == track

    def next_level_name(self, track):
        if track == "echo":
            from . import story
            return story.floor_name(self.echo.floor_no)
        if track == "still":
            return self.still.chamber.name
        return self.tick.level.name

    @property
    def aurel_on_last_floor(self):
        return self.echo.last_floor and self.echo.state in ("playing", "unravel")

    def still_below(self):
        """How many of the Still have not come up yet (including chambers not yet reached)."""
        if self.still.state == "done":
            return 0
        here = self.still.chamber.population
        later = sum(self.still._build(i).population for i in range(self.still.index + 1, self.still.chambers))
        return here + later

    def lamps_lit(self):
        """Sconces Aurel has lit on the whole stair: every floor he cleared, and the one he is on."""
        lit = sum(r.lamps for r in self.echo.scores)
        if self.echo.state in ("playing", "unravel"):
            lit += len(self.echo.lit)
        return lit

    def stair_lit(self):
        """The share of the stair's sconces that are lit (0..1)."""
        return self.lamps_lit() / self.lamps_total if self.lamps_total else 1.0

    def still_climb(self):
        """(climbed, lost on the stair): the saved Still climb home by Aurel's lamps, and on the
        dark stretches some lose their way."""
        saved = self.still.saved
        lost = int(saved * (1.0 - self.stair_lit()) * DARK_LOSS)
        return saved - lost, lost

    # ---------------------------------------------------------------- the story, told as it goes
    def chapter_key(self, track):
        """Where a story stands: Aurel's floor number, Maren's floor index, Tarn's chamber index
        (with "last" standing for the final one)."""
        if track == "echo":
            return self.echo.floor_no, False
        if track == "tick":
            return self.tick.index, self.tick.index == self.tick.floors - 1
        return self.still.index, self.still.index == self.still.chambers - 1

    def scenes_before(self, track):
        """The story to tell before the next level of `track`: the chapter's prologue the first time,
        and any interlude due here. Each is told once a night."""
        mod = CHAPTERS[track]
        panels = []
        if (track, "prologue") not in self.told:
            self.told.add((track, "prologue"))
            panels += mod.PROLOGUE
        key, last = self.chapter_key(track)
        inter = mod.INTERLUDES.get(key) or (mod.INTERLUDES.get("last") if last else None)
        if track == "echo" and key == ECHO_FLOORS[-1] and self.still.state == "done" and \
                self.still_choice != "stay":
            inter = story.LOOM_WITH_STILL                       # they came down the Spindle before him
        if inter and (track, key) not in self.told:
            self.told.add((track, key))
            panels += inter
        return panels

    def aurel_near(self):
        """Aurel has come far enough down that the bottom of the stair is lit (seen from the Loom's hall)."""
        return self.echo.cleared >= len(ECHO_FLOORS) - 2

    def outcome(self):
        """What happened tonight, for the ending (see ending.py)."""
        climbed, strayed = self.still_climb()
        return ending.NightOutcome(
            state=self.state if self.state != "night" else "morning", lamps_lit=self.lamps_lit(),
            lamps_total=self.lamps_total, still_saved=self.still.saved, still_total=self.still.total,
            still_below=self.still_below(), still_done=self.still.state == "done", strayed=strayed,
            still_choice=self.still_choice or "through",
            hoard_choice=self.hoard_choice, released=self.released, bargain_slack=self.bargain_slack(),
            tick_failed=self.tick_failed, day_woven=getattr(self, "day_woven", self.day_minutes()),
            thread_left=self.thread.minutes)

    def ending_panels(self):
        """The end of the night, one scene for each of the three (then the tally, on the epilogue)."""
        return ending.ending_panels(self.outcome())

    # ---------------------------------------------------------------- the night's end
    def check_thread(self):
        if self.state == "night" and self.thread.empty:
            self.state = "endless"
        return self.state

    def thread_tied(self):
        """Aurel's last floor is cleared: the new day replaces the old, woven from what is left."""
        self.day_woven = self.day_minutes()
        self.state = "morning"

    def aurel_woven(self):
        self.state = "woven"

    # ---------------------------------------------------------------- the Guild's drum
    @property
    def drum(self):
        """Minutes of the Guild's hoard still on the drum."""
        return int(self.drum_f)

    def guild_rate(self):
        """Minutes of the drum the Guild sells for every minute of the night: faster the deeper Aurel
        has gone. Nothing, once Maren has reached the drum."""
        if self.hoard_choice == "released":
            return 0.0
        if self.hoard_choice == "bargain":                         # (they still have the drum, and sell it)
            return GUILD_RATE
        return GUILD_RATE * (1 + AUREL_SPUR * self.echo.cleared)

    def _guild_sells(self, minutes):
        """Every minute of the night, the Guild sells a little more of the drum, a lampful at a time:
        burned, and gone for good."""
        self.drum_f = max(0.0, self.drum_f - minutes * self.guild_rate())

    def hoard_at_the_top(self):
        """What Maren will find to decide about in the Drum Room: the drum, and what her watch still holds."""
        return self.drum + self.tick.hoard

    def release_hoard(self, watch=None):
        """Maren opens the brake: the drum and her watch run down the thread to whoever holds the other
        end, and lengthen it for everyone."""
        total = (self.tick.hoard if watch is None else watch) + self.drum
        self.hoard_choice = "released"
        self.released = total
        self.tick.hoard = 0
        self.drum_f = 0.0
        self.thread.give(total)
        return total

    def bargain_slack(self):
        """What the Guildmaster offers to send down the thread: 'what he needs to tie it'."""
        return int(BARGAIN_SHARE * self.perfect_par)

    def take_bargain(self):
        """Maren takes the Guild's bargain: a fixed length sent down the thread, Aurel's unravels paid
        for by the Guild (he cannot be woven in), and she keeps her watch (the morning will take it
        back). The Guild keeps the drum, and the ledger, and goes on selling."""
        self.hoard_choice = "bargain"
        self.kept = self.tick.hoard
        self.tick.hoard = 0
        self.thread.give(self.bargain_slack())
        self.echo.guild_pays = True

    # ---------------------------------------------------------------- the morning
    def day_minutes(self):
        """How much daylight the first morning will have if the thread is tied now. The Loom weaves it
        from everything left of the old day that was not burned (the thread, the drum, Maren's watch),
        so it is that share of a whole summer day, as the old people remember them: dawn to midnight.
        Too much was burned for a day ever to be that long again."""
        survived = self.thread.minutes + self.drum + self.tick.hoard + self.kept
        whole = self.thread.start + self.drum_start + tk.HOARD
        return int(ending.FULL_DAY * min(1.0, survived / whole))

    def day_until(self, minutes=None):
        """'until 2:30 in the afternoon' (dawn is at six)."""
        return ending.day_until(self.day_minutes() if minutes is None else minutes)

    def epilogue(self):
        """(title, lines): the record of the night."""
        return ending.epilogue(self.outcome())

    def perfect(self):
        """Morning, with nothing left undone: the completionist's night."""
        return self.state == "morning" and self.outcome().perfect


def _tick_moves(level, has_watch):
    """Clock minutes of a floor's cheapest clear: its moves and waits (winding back spends the hoard)."""
    plan = tk.solve(level, has_watch=has_watch) or []
    return sum(1 for a in plan if a[0] != "r")
