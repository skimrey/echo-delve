"""How The Long Night ends: a scene for each of the three, then the record.

The ending depends only on what happened, gathered in a NightOutcome: the Campaign builds one from the
night that was played (Campaign.outcome), and the Story (story_reel.py) builds one from the outcomes
picked on its choice cards, so every ending can be seen without playing a whole night.
"""

from dataclasses import dataclass

DAWN = 6 * 60                          # the first morning begins at six
FULL_DAY = 18 * 60                     # a whole summer day, as the old people remember: dawn to midnight


@dataclass
class NightOutcome:
    state: str = "morning"             # morning | endless (the thread ran out) | woven (Aurel was woven in)
    lamps_lit: int = 75
    lamps_total: int = 75
    still_saved: int = 12              # brought through the break
    still_total: int = 12              # of those Tarn reached
    still_below: int = 0               # still in the caves when the night ended
    still_done: bool = True            # Tarn finished his part
    strayed: int = 0                   # of the saved, lost on the dark stretches of the stair
    still_choice: str = "through"      # at the break Tarn took them "through", or let them "stay"
    hoard_choice: str = "released"     # None (never reached the drum) | released | bargain
    released: int = 300                # minutes let go from the drum and the watch
    bargain_slack: int = 96
    tick_failed: bool = False          # Maren was caught
    day_woven: int = 10 * 60           # minutes of daylight in the first day
    thread_left: int = 20 * 60         # minutes of thread when the night ended

    @property
    def morning(self):
        return self.state == "morning"

    @property
    def stayed(self):
        return self.still_saved if self.still_choice == "stay" else 0

    @property
    def climbed(self):
        return 0 if self.still_choice == "stay" else self.still_saved - self.strayed

    @property
    def perfect(self):
        """Morning, with nothing left undone: the completionist's night."""
        return (self.morning and self.lamps_lit >= self.lamps_total and self.still_done and
                self.still_choice == "through" and self.still_saved == self.still_total and not self.strayed and
                self.hoard_choice == "released")


def duration(minutes):
    """'5 hours and 10 minutes', '40 minutes'."""
    h, m = divmod(int(minutes), 60)
    if not h:
        return "%d minute%s" % (m, "" if m == 1 else "s")
    hours = "%d hour%s" % (h, "" if h == 1 else "s")
    return hours if not m else "%s and %d minute%s" % (hours, m, "" if m == 1 else "s")


def hm(minutes):
    return "%d:%02d" % divmod(minutes, 60)


def day_until(minutes):
    """'until 2:30 in the afternoon' for a day of `minutes` of daylight (dawn is at six)."""
    end = DAWN + minutes
    if end >= 24 * 60:
        return "until midnight, the way the old people remember"
    if minutes < 30:
        return "just long enough to see the sun come up"
    h, mm = divmod(end, 60)
    part = "in the morning" if h < 12 else ("in the afternoon" if h < 17 else "in the evening")
    return "until %d:%02d %s" % (h if h <= 12 else h - 12, mm, part)


def ending_panels(o):
    """The end of the night, one scene for each of the three (then the tally, on the epilogue)."""
    out = []
    saved, below, climbed, strayed = o.still_saved, o.still_below, o.climbed, o.strayed
    if o.morning:
        longest = " It is the longest day anyone in Hollowmere can remember." if o.day_woven >= 10 * 60 else ""
        out.append(("loom_tied", "The thread is tied. The Loom shudders, then sings, and weaves a morning from "
                                 "everything that is left of the old day: a day that lasts %s.%s Far above, the "
                                 "bells of Hollowmere ring for the first morning in three hundred and twelve "
                                 "days." % (day_until(o.day_woven), longest)))
        if o.stayed:
            out.append(("black_water", "Tarn let his people stay in the last of the light. When the thread was tied, the "
                                       "water went black around them, and the dark came back as if it had never left. "
                                       "Far above them, a stair they will never see is burning with lamps."))
        if below:
            out.append(("black_water", "Below, the water went black. %d of the Still were still in the dark when "
                                       "the new day came.%s" % (below, " Tarn had brought %d through the break "
                                                                       "before it did." % saved if saved else "")))
        if climbed and o.lamps_lit >= o.lamps_total:
            out.append(("stair_lit", "Every sconce on the stair is burning, for the first time since the dark came "
                                     "up. The Still climb it behind Aurel, one landing at a time, and not one of "
                                     "them loses the way."))
        if climbed:
            text = ("They come up the stair behind Aurel, by the lamps he lit, and out into the first sunrise any "
                    "of them has ever seen: %d of the Still. They shade their eyes, and none of them looks away."
                    % climbed)
            if strayed:
                text += " %d lost their way on the dark stretches of the stair." % strayed
            out.append(("sunrise" if climbed >= 6 else "sunrise_few", text))
    elif o.state == "endless":
        out.append(("town", "The thread ran out before it could be tied. There is no day left to replace the old "
                            "one, and Hollowmere will stay in the dark."))
    else:
        out.append(("wardens", "Aurel's thread ran out on the stair. The Deep wove him in, a Warden beside his "
                               "mother, and the loose end drifted back up to the first landing."))
    if not o.morning:
        if o.stayed:
            out.append(("pool_glow", "Tarn let his people stay. With no new day to take it back, the light never left "
                                     "their water. It is the last light of the last day, and it is theirs."))
        elif o.still_done:
            out.append(("loom_waiting", "The Still waited in the Loom's hall, in the dark, for someone to come down "
                                        "the stair. Nobody came."))
        else:
            out.append(("dim", "In the caves, the Still went on stirring the water, in a light that grew dimmer and "
                               "dimmer, but never quite went out."))
    if o.hoard_choice == "released" and o.morning:
        out.append(("drum_open", "Far above, Maren had let the hoard run down the thread to him, every hour of "
                                 "it. She knew he had tied it when the drum shuddered and began to turn the "
                                 "other way, and the watch in her hand, for the first time, ran forwards."))
        out.append(("reunion", "She is waiting at the mouth of the Deep, with nothing in her hands. Neither of "
                               "them says anything. He holds out their mother's lantern, and this time, she "
                               "takes it."))
        out.append(("tick_door", "By noon, the Guild's ledgers are nailed to the door of the Tick: every hour "
                                 "kept back, for generations, in a careful hand. For longer than anyone could "
                                 "remember, the Guild had been selling the town a cure for a cold it was making. "
                                 "Nobody in Hollowmere pays for an hour again. The brake on the drum is left "
                                 "open, and in time it rusts that way."))
    elif o.hoard_choice == "released":
        out.append(("roofs_empty", "Maren let the hoard go down the thread. She sat on the roof of the Tick with "
                                   "nothing in her hands, and watched the sky stay dark."))
    elif o.hoard_choice == "bargain":
        out.append(("coach", "Maren took the Guild's bargain. A Guild coach carried her to the edge of Hollowmere "
                             "before dawn, the watch ticking warm against her pulse."))
        if o.morning:
            out.append(("road", "The sun came up behind her. The watch went grey in her hand, and cold: the Loom had "
                                "taken back every hour of it. There is only ever one day. The Guild had not mentioned "
                                "that."))
    elif o.tick_failed:
        out.append(("tick_stair", "Maren was caught on the stairs of the Tick, the watch still in her hand."))
    else:
        out.append(("tick_stair", "Maren never reached the Drum Room. The hoard stayed wound where the Guild had "
                                  "put it%s." % (", until the morning took it back" if o.morning else "")))
    if o.morning and o.hoard_choice != "released":                      # nobody told the town
        if o.hoard_choice == "bargain":
            text = ("The Guild kept its word about Aurel: he came home. By nightfall the ledger is ash, the brake on "
                    "the drum is shut, and the Guild has begun, very quietly, to keep a little of every day back. "
                    "Nobody in Hollowmere knows why the days are so short. Nobody ever has.")
        else:
            text = ("By nightfall, the brake on the drum is closed again, and the Guild has begun, very quietly, "
                    "to keep a little of every day back. Nobody in Hollowmere knows why the days are so short. "
                    "Nobody ever has.")
        out.append(("ledgers", text))
    return out


def epilogue(o):
    """(title, lines): the record of the night, one line for each of the three (the ending scenes have
    told it; this is what it came to)."""
    lines = []
    if o.morning:
        title = "Morning"
        lines.append("Aurel tied the thread, with %d of the stair's %d sconces lit. The first day lasted from "
                     "dawn %s." % (o.lamps_lit, o.lamps_total, day_until(o.day_woven)))
    elif o.state == "endless":
        title = "No morning"
        lines.append("The thread ran out before Aurel could tie it. Hollowmere will stay in the dark.")
    else:
        title = "Woven in"
        lines.append("Aurel's thread ran out on the stair, and the Deep wove him in.")
    tarn = "Tarn brought %d of the Still through the break" % o.still_saved
    if o.stayed:
        tarn = "Tarn brought %d of the Still to the break, and let them stay in the light; %s" % (
            o.stayed, "the morning took it from them." if o.morning else "it never left them.")
    elif o.still_below:
        tarn += "; %d were still in the dark when the water went black." % o.still_below
    elif o.still_saved < o.still_total:
        tarn += " (%d were lost on the way)." % (o.still_total - o.still_saved)
    else:
        tarn += ", every one of them."
    lines.append(tarn)
    if o.morning and o.climbed:
        if o.strayed:
            lines.append("%d climbed out into their first sunrise; %d lost their way on the dark stretches of "
                         "the stair." % (o.climbed, o.strayed))
        else:
            lines.append("All %d of them climbed out into their first sunrise." % o.climbed)
    if o.hoard_choice == "released":
        lines.append("Maren let %s of the Guild's hoard go, back into the thread%s." %
                     (duration(o.released), ", and nailed its ledgers to the door of the Tick" if o.morning else ""))
    elif o.hoard_choice == "bargain":
        lines.append("Maren took the Guild's bargain and its %s of slack, and gave them the ledger." %
                     duration(o.bargain_slack) + (" The morning took her watch back anyway." if o.morning else ""))
    elif o.tick_failed:
        lines.append("Maren was caught on the stairs of the Tick, the watch in her hand.")
    else:
        lines.append("Maren never reached the Drum Room.")
    if o.morning and o.hoard_choice != "released":
        lines.append("By nightfall, the Guild had closed the brake again.")
    if o.perfect:
        lines.append("A perfect night: every sconce lit, every one of the Still home, every hour let go, "
                     "Maren waiting at the top of the stair, and the Guild's ledgers on the door of the Tick.")
    lines.append("Thread left when the night ended: %s." % hm(o.thread_left))
    return title, lines
