"""The Long Night: the three stories on one clock."""

import os
import tempfile
import unittest

from helpers import R, cached_floor

import pygame

import echo.campaign as cp
from echo.bot import bot_action, lock_goal
from echo.sim import WAIT
from echo.sisters import tick as tk


def fast_campaign(seed=4, length="measured"):
    """Campaigns generate every level up front; reuse generated floors across tests."""
    cp.generate_floor = cached_floor
    return cp.Campaign(seed, length)


def clear_echo_floor(run):
    f, done = run.floor, set()
    while run.state == "playing":
        idx = next((k for k in range(len(f.lock_order)) if k not in done), None)
        goal, kind = lock_goal(f, done)
        lb, st = run.play.loop_no, {}
        while run.state == "playing" and run.play.loop_no == lb:
            run.act(bot_action(run.sim, goal, kind, st))
        if kind == "plate" and run.play.last_end_pos == goal:
            done.add(idx)
        elif kind == "lever" and st.get("pulled"):
            done.add(idx)


class TheClock(unittest.TestCase):
    def test_spend_give_and_read(self):
        c = cp.Thread(125)
        self.assertEqual(c.hm(), "2:05")
        self.assertFalse(c.spend(5))
        self.assertEqual(c.minutes, 120)
        c.give(10)
        self.assertEqual(c.minutes, 130)
        self.assertTrue(c.spend(500))
        self.assertTrue(c.empty)
        self.assertEqual(c.minutes, 0)


class Budget(unittest.TestCase):
    def test_the_thread_is_cut_to_a_length_measured_against_this_nights_own_levels(self):
        cp.generate_floor = cached_floor
        c = cp.Campaign(4)                                   # built, not yet cut
        self.assertIsNone(c.length)
        par = c.perfect_par                                   # every sconce, every one of the Still
        self.assertGreater(par, sum(c.par.values()))
        lengths = {key: c.minutes_for(key) for key, _, _, _ in cp.LENGTHS}
        for key, _, mult, _ in cp.LENGTHS:
            self.assertEqual(lengths[key], int(mult * par))
        self.assertGreater(lengths["long"], lengths["measured"])
        self.assertGreater(lengths["measured"], lengths["short"])
        c.set_length("short")
        self.assertEqual((c.length, c.thread.minutes), ("short", lengths["short"]))
        self.assertIs(c.echo.thread, c.thread)
        self.assertIs(c.still.thread, c.thread)
        self.assertIs(c.tick.thread, c.thread)

    def test_the_three_stories_and_their_lengths(self):
        c = fast_campaign()
        self.assertEqual((c.total("echo"), c.total("still"), c.total("tick")),
                         (len(cp.ECHO_FLOORS), 3 + cp.STILL_GENERATED, 3 + cp.TICK_GENERATED))
        self.assertEqual(c.echo.floor_no, cp.ECHO_FLOORS[0])


class OneClock(unittest.TestCase):
    def setUp(self):
        self.c = fast_campaign()

    def test_every_turn_in_every_story_spends_the_last_day(self):
        c = self.c
        start = c.thread.minutes
        c.echo.act(WAIT)
        self.assertEqual(c.thread.minutes, start - 1)
        c.still.spend(3)
        self.assertEqual(c.thread.minutes, start - 4)
        c.tick.on_action(("m", 1, 0))
        c.tick.on_action(("w",))
        self.assertEqual(c.thread.minutes, start - 6)

    def test_winding_the_tower_back_spends_the_hoard_not_the_clock(self):
        c = self.c
        start = c.thread.minutes
        c.tick.on_action(("r",))
        self.assertEqual(c.thread.minutes, start)

    def test_the_opening_order_then_any_order(self):
        c = self.c
        self.assertEqual(c.prologue_next, "echo")
        self.assertEqual([c.available(t) for t in ("echo", "tick", "still")], [True, False, False])
        clear_echo_floor(c.echo)
        c.echo.apply_upgrade(c.echo.options[0])
        self.assertEqual(c.prologue_next, "tick")
        s = c.tick.begin()
        for a in tk.solve(c.tick.level, has_watch=False):
            s.step(a)
        c.tick.settle(s)
        self.assertEqual(c.prologue_next, "still")
        c.still.index = 1
        self.assertIsNone(c.prologue_next)
        self.assertEqual([c.available(t) for t in ("echo", "tick", "still")], [True, True, True])

    def test_aurel_walks_his_own_floors_and_the_loom_is_last(self):
        run = self.c.echo
        seen = []
        while True:
            seen.append(run.floor_no)
            clear_echo_floor(run)
            if run.state == "won":
                break
            run.apply_upgrade(run.options[0])
        self.assertEqual(seen, cp.ECHO_FLOORS)
        self.assertEqual(self.c.echo.floor.index, 10)

    def test_releasing_the_hoard_gives_it_to_everyone(self):
        c = self.c
        c.tick.hoard = 30
        start, drum = c.thread.minutes, c.drum
        self.assertGreater(drum, 0)
        c.release_hoard()                                  # her watch, and what is left on the drum
        self.assertEqual((c.thread.minutes, c.tick.hoard, c.drum, c.hoard_choice),
                         (start + 30 + drum, 0, 0, "released"))

    def test_still_below_counts_everyone_not_yet_up(self):
        c = self.c
        self.assertEqual(c.still_below(), sum(c.still._build(i).population for i in range(c.still.chambers)))
        c.still.state = "done"
        self.assertEqual(c.still_below(), 0)


class TheThread(unittest.TestCase):
    """The thread is the time that is left: what the Guild has not taken."""

    def setUp(self):
        self.c = fast_campaign()

    def test_an_hour_reel_maren_cuts_loose_lengthens_the_thread(self):
        c = self.c
        lv = tk.TickLevel(dict(name="t", hint="", rows=["#######", "#Sr..X#", "#######"], guards=[], doors={}))
        s = tk.Tick(lv, hoard=10)
        start = c.thread.minutes
        ev = s.step(R)
        c.tick.on_step(R, ev, s)
        self.assertEqual(c.thread.minutes, start - 1 + tk.REEL)    # a minute of night, then the reel unspools
        self.assertEqual(s.hoard, 10)                               # into the thread, not her watch

    def test_unravelling_cuts_a_length_of_the_thread(self):
        from echo.run import UNRAVEL_LENGTH
        from echo.sim import ANCHOR
        run = self.c.echo
        run.act(ANCHOR)
        self.assertEqual(run.unravel_cost_short(), "%d minutes of thread" % UNRAVEL_LENGTH)
        before, threads = self.c.thread.minutes, run.threads
        run.unravel(1)
        self.assertEqual(self.c.thread.minutes, before - UNRAVEL_LENGTH)
        self.assertEqual(run.threads, threads)                      # no separate count in the night
        self.c.thread.minutes = UNRAVEL_LENGTH - 1
        run.act(ANCHOR)
        self.assertIn("thread is too short", run.unravel_problem())

    def test_a_full_well_with_too_little_thread_weaves_aurel_in(self):
        from echo.sim import ANCHOR
        run = self.c.echo
        self.c.thread.minutes = 5
        for _ in range(run.slots + 1):
            run.act(ANCHOR)
        self.assertEqual(run.state, "dead")

    def test_clearing_a_floor_does_not_add_threads_in_the_night(self):
        run = self.c.echo
        before = run.threads
        clear_echo_floor(run)
        self.assertEqual(run.threads, before)


class Endings(unittest.TestCase):
    def test_morning_with_the_still_below_and_the_hoard_kept(self):
        c = fast_campaign()
        c.take_bargain()
        c.thread_tied()
        title, lines = c.epilogue()
        text = " ".join(lines)
        self.assertEqual(title, "Morning")
        self.assertIn("water went black", text)
        self.assertIn("took her watch back anyway", text)           # there is only ever one day

    def test_morning_with_everyone_out_and_the_hoard_released(self):
        c = fast_campaign()
        c.still.state, c.still.saved, c.still.total = "done", 12, 12
        drum = c.drum
        c.release_hoard(20)
        c.thread_tied()
        text = " ".join(c.epilogue()[1])
        self.assertIn("first sunrise", text)
        from echo import ending
        self.assertIn("let %s of the Guild's hoard go" % ending.duration(20 + drum), text)

    def test_the_still_climb_home_by_aurels_lamps(self):
        c = fast_campaign()
        self.assertGreater(c.lamps_total, 20)
        self.assertEqual(c.stair_lit(), len(c.echo.lit) / c.lamps_total)
        c.still.state, c.still.saved, c.still.total = "done", 20, 20
        c.echo.lit = set()
        climbed, strayed = c.still_climb()
        self.assertEqual((climbed, strayed), (20 - int(20 * cp.DARK_LOSS), int(20 * cp.DARK_LOSS)))
        c.thread_tied()
        text = " ".join(c.epilogue()[1])
        self.assertIn("lost their way on the dark stretches", text)
        c.echo.lit = set(c.echo.torches)                  # floor 1 fully lit: a bit more of the stair
        self.assertGreater(c.still_climb()[0], climbed)

    def test_a_fully_lit_stair_brings_everyone_home(self):
        c = fast_campaign()
        c.still.state, c.still.saved, c.still.total = "done", 9, 12
        c.lamps_lit = lambda: c.lamps_total
        self.assertEqual(c.still_climb(), (9, 0))
        c.thread_tied()
        text = " ".join(c.epilogue()[1])
        self.assertIn("All 9 of them", text)
        self.assertIn("3 were lost on the way", text)

    def test_the_last_day_running_out_and_aurel_woven_in(self):
        c = fast_campaign()
        c.thread.spend(10 ** 6)
        self.assertEqual(c.check_thread(), "endless")
        self.assertEqual(c.epilogue()[0], "No morning")
        c = fast_campaign()
        c.aurel_woven()
        self.assertIn("wove him in", " ".join(c.epilogue()[1]))


class Chapters(unittest.TestCase):
    """Each of the three has a prologue when their part begins, and interludes along the way."""

    def test_prologues_once_then_interludes_where_they_fall(self):
        from echo import story
        from echo.sisters import stillwater as sw
        c = fast_campaign()
        self.assertEqual(c.scenes_before("echo"), story.PROLOGUE)
        self.assertEqual(c.scenes_before("echo"), [])                 # told once a night
        self.assertEqual(c.scenes_before("tick"), tk.PROLOGUE)
        self.assertEqual(c.scenes_before("still"), sw.PROLOGUE)
        c.tick.index = 2
        self.assertEqual(c.scenes_before("tick"), tk.INTERLUDES[2])
        c.tick.index = c.tick.floors - 1                              # the Drum Room
        self.assertEqual(c.scenes_before("tick"), tk.INTERLUDES["last"])
        c.still.index = 3
        self.assertEqual(c.scenes_before("still"), sw.INTERLUDES[3])
        c.echo.floor_no = 5
        self.assertEqual(c.scenes_before("echo"), story.INTERLUDES[5])
        self.assertEqual(c.scenes_before("echo"), [])

    def test_maren_has_the_watch_from_the_start(self):
        c = fast_campaign()
        self.assertTrue(c.tick.begin().has_watch)                     # (stolen in her prologue)

    def test_aurels_sconces_brighten_the_water(self):
        c = fast_campaign()
        c.echo.lit = set()
        dark = c.still.light()
        c.lamps_lit = lambda: c.lamps_total
        self.assertAlmostEqual(c.still.light(), min(1.0, dark + cp.LAMPLIGHT))
        c.thread.minutes = c.thread.start // 3                        # a late, dim hour
        c.lamps_lit = lambda: 0
        late = c.still.light()
        c.lamps_lit = lambda: c.lamps_total
        self.assertAlmostEqual(c.still.light(), late + cp.LAMPLIGHT)

    def test_the_ending_has_a_scene_for_each_of_them(self):
        c = fast_campaign()
        c.still.state, c.still.saved, c.still.total = "done", 12, 12
        c.lamps_lit = lambda: c.lamps_total
        c.release_hoard(30)
        c.thread_tied()
        keys = [k for k, _ in c.ending_panels()]
        self.assertEqual(keys, ["loom_tied", "stair_lit", "sunrise", "drum_open", "reunion", "tick_door"])
        c = fast_campaign()                                           # the Still left below, the hoard kept
        c.take_bargain()
        c.thread_tied()
        keys = [k for k, _ in c.ending_panels()]
        self.assertEqual(keys, ["loom_tied", "black_water", "coach", "road", "ledgers"])   # (and it starts again)
        c = fast_campaign()
        c.thread.spend(10 ** 6)
        c.check_thread()
        keys = [k for k, _ in c.ending_panels()]
        self.assertEqual(keys, ["town", "dim", "tick_stair"])          # (no morning: the water keeps its light)

    def test_a_perfect_night_has_its_own_scene_and_line(self):
        c = fast_campaign()
        c.still.state, c.still.saved, c.still.total = "done", 12, 12
        c.lamps_lit = lambda: c.lamps_total
        c.release_hoard(30)
        c.thread_tied()
        self.assertTrue(c.perfect())
        self.assertEqual([k for k, _ in c.ending_panels()],
                         ["loom_tied", "stair_lit", "sunrise", "drum_open", "reunion", "tick_door"])
        self.assertIn("A perfect night", " ".join(c.epilogue()[1]))
        c.lamps_lit = lambda: c.lamps_total - 1                      # one sconce short
        self.assertFalse(c.perfect())
        self.assertNotIn("stair_lit", [k for k, _ in c.ending_panels()])

    def test_every_scene_the_story_asks_for_can_be_drawn(self):
        from echo import story
        from echo.cinematics import draw_scene
        from echo.sisters import stillwater as sw
        lists = [cp.INTRO, story.INTRO, story.PROLOGUE, tk.INTRO, tk.PROLOGUE, sw.INTRO, sw.PROLOGUE]
        lists += [v for m in (story, tk, sw) for v in m.INTERLUDES.values()]
        keys = {k for panels in lists for k, _ in panels}
        keys |= {"loom_tied", "black_water", "sunrise", "sunrise_few", "town", "wardens", "ascent", "roofs_dawn",
                 "roofs_empty", "roofs_dust", "roofs_night", "tick_stair", "stair_lit", "drum_open", "road",
                 "drum_master",
                 "reunion", "tick_door", "ledgers"}
        surf = pygame.Surface((960, 440))
        for k in sorted(keys):
            with self.subTest(scene=k):
                self.assertTrue(draw_scene(surf, k, 2.5, (0, 0, 960, 440)))


class TheOrderDecidesTheThread(unittest.TestCase):
    """Whose part you play when decides how much thread is left, and what is left becomes the morning."""

    def test_the_guild_sells_the_drum_all_night_faster_as_aurel_goes_deeper(self):
        c = fast_campaign()
        start = c.drum
        self.assertEqual(start, int(cp.DRUM_SHARE * c.perfect_par))
        c.thread.spend(100)
        self.assertEqual(c.drum, int(start - 100 * cp.GUILD_RATE))
        c.echo.cleared = 4
        before = c.drum_f
        c.thread.spend(100)
        self.assertAlmostEqual(before - c.drum_f, 100 * cp.GUILD_RATE * (1 + 4 * cp.AUREL_SPUR))
        c.release_hoard()                                         # once Maren has let it go, the selling stops
        c.thread.spend(100)
        self.assertEqual((c.drum, c.guild_rate()), (0, 0.0))

    def test_maren_early_finds_more_to_let_go(self):
        early, late = fast_campaign(), fast_campaign()
        late.echo.cleared = 5
        late.thread.spend(800)
        early.thread.spend(800 - 300)                             # (the same night, but Maren came 300 minutes sooner)
        self.assertGreater(early.hoard_at_the_top(), late.hoard_at_the_top() + 200)

    def test_every_turn_in_dim_water_costs_more(self):
        from echo.sisters import stillwater as sw
        c = fast_campaign()
        start = c.thread.minutes
        c.still.spend(10, light=1.0)
        self.assertEqual(c.thread.minutes, start - 10)
        c.still.spend(10, light=0.5)                              # (dimmer than MIN_LIGHT counts as MIN_LIGHT)
        self.assertEqual(c.thread.minutes, start - 10 - int(10 / sw.MIN_LIGHT))

    def test_the_guilds_bargain_is_real_but_the_drum_stays_shut(self):
        c = fast_campaign()
        c.tick.hoard = 25
        start, drum = c.thread.minutes, c.drum
        c.take_bargain()
        self.assertEqual(c.thread.minutes, start + c.bargain_slack())   # what he sends down the thread
        self.assertEqual((c.kept, c.drum, c.hoard_choice), (25, drum, "bargain"))
        self.assertEqual(c.guild_rate(), cp.GUILD_RATE)               # they still have the drum, and sell it
        run = c.echo                                                  # and they pay for Aurel's unravels
        self.assertTrue(run.can_afford_unravel())
        from echo.sim import GhostScript
        run.play.scripts.append(GhostScript([], "anchor", 1, 1, run.floor.start, ()))
        before = c.thread.minutes
        run.unravel(1)
        self.assertEqual(c.thread.minutes, before)
        c.thread_tied()
        keys = [k for k, _ in c.ending_panels()]
        self.assertIn("road", keys)
        self.assertNotIn("reunion", keys)
        self.assertIn("kept its word about Aurel", c.ending_panels()[-1][1])

    def test_late_to_the_drum_the_bargain_can_be_worth_more(self):
        c = fast_campaign()
        c.echo.cleared = 5
        c.thread.spend(1000)                                          # the Guild has sold almost all of it
        self.assertLess(c.hoard_at_the_top() - c.tick.hoard, c.bargain_slack())

    def test_what_is_left_becomes_the_morning(self):
        c = fast_campaign()
        from echo import ending
        whole = c.thread.start + c.drum_start + tk.HOARD
        self.assertEqual(c.day_minutes(), int(ending.FULL_DAY * (c.thread.minutes + c.drum + tk.HOARD) / whole))
        self.assertNotIn("midnight", c.day_until())               # (too much was burned, ever since)
        self.assertEqual(c.day_until(10 * 60 + 30), "until 4:30 in the afternoon")
        self.assertEqual(c.day_until(45), "until 6:45 in the morning")
        before = c.day_minutes()
        c.release_hoard()
        self.assertEqual(c.day_minutes(), before)                 # (it is in the thread now: nothing lost)
        c.thread.spend(c.thread.minutes // 2)
        self.assertLess(c.day_minutes(), before)                  # every minute of the night, a little less day
        c.thread.spend(c.thread.minutes - 1)
        c.thread_tied()
        self.assertLess(c.day_woven, 5)
        self.assertIn("just long enough to see the sun come up", c.ending_panels()[0][1])


class NightScreens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cp.generate_floor = cached_floor
        from echo.app import App
        self.app = App(meta_path=os.path.join(self.tmp.name, "m.json"), seed=4, game="night")

    def tearDown(self):
        self.tmp.cleanup()

    def key(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def name(self):
        return type(self.app.screen).__name__

    def chapter(self, who):
        """A story's chapter is told before its level: check whose, then skip it."""
        self.assertEqual(self.name(), "IntroScreen")
        self.assertEqual(self.app.screen.title, who)
        self.app.draw()
        self.key(pygame.K_ESCAPE)

    def dismiss_order_card(self):
        self.assertEqual(self.name(), "Card")
        self.assertEqual(self.app.screen.title, cp.ORDER_TITLE)
        self.app.draw()
        self.key(pygame.K_RETURN)
        self.assertEqual(self.name(), "NightScreen")

    def begin(self):
        self.key(pygame.K_n)
        self.assertEqual(self.name(), "LoadingScreen")       # the night is built first...
        self.app.draw()
        self.app.screen.finish_now()
        self.assertEqual(self.name(), "LengthScreen")        # ...then you choose how much thread is left
        self.app.draw()
        self.key(pygame.K_2)

    def test_the_length_cards_show_their_text(self):
        # regression: the cards were drawn over by plain buttons, leaving empty boxes
        self.key(pygame.K_n)
        self.app.screen.finish_now()
        self.app.draw()
        for key, _, _, _ in cp.LENGTHS:
            r = self.app.screen.btn("len:" + key).rect
            gold = sum(1 for x in range(r.x, r.right, 2) for y in range(r.y + 70, r.y + 95, 2)
                       if (lambda c: c.r > 200 and c.g > 160 and c.b < 140)(self.app.surface.get_at((x, y))))
            self.assertGreater(gold, 5, key)           # the length (h:mm) is drawn in gold

    def test_title_length_story_then_the_night(self):
        self.assertEqual(pygame.display.get_caption()[0], "The Long Night")
        self.app.draw()
        self.begin()
        self.assertEqual(self.name(), "IntroScreen")            # the first time, the story comes first
        for i in range(len(cp.INTRO)):
            self.app.screen.i, self.app.screen.t = i, 3.0
            self.app.draw()
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.name(), "NightScreen")
        self.assertIn("Aurel", self.app.screen.msg)
        self.app.draw()
        self.key(pygame.K_1)                                      # Maren is not first
        self.assertEqual((self.name(), self.app.screen.msg), ("NightScreen", "Not yet."))

    def test_playing_aurel_leaving_and_coming_back(self):
        self.app.meta.data["seen_intro_night"] = True
        self.begin()
        self.assertEqual(self.name(), "NightScreen")
        self.key(pygame.K_2)
        self.chapter("Aurel")                                     # his prologue, before his first floor
        self.assertEqual(self.name(), "GameScreen")
        start = self.app.campaign.thread.minutes
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_SPACE)
        self.assertLess(self.app.campaign.thread.minutes, start)
        self.app.draw()
        turn = self.app.run.sim.turn
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.app.screen.btn("abandon").label, "Back to the Night  (A)")
        self.key(pygame.K_a)
        self.assertEqual(self.name(), "NightScreen")
        self.key(pygame.K_2)                                      # (told once: straight back in)
        self.assertEqual((self.name(), self.app.run.sim.turn), ("GameScreen", turn))   # where he left off

    def test_the_sister_stories_leave_to_the_night(self):
        self.app.meta.data["seen_intro_night"] = True
        self.begin()
        c = self.app.campaign
        c.echo.cleared = 1                                        # past the opening (pretend)
        c.tick.index = 1
        c.still.index = 1
        c.still.chamber = c.still._build(1)
        c.tick._level = c.tick._build(1)
        c.tick.has_watch = True
        self.app.to_night()
        self.dismiss_order_card()                                 # the opening is over: the order matters
        for k, who, name in ((pygame.K_1, "Maren", "TickScreen"), (pygame.K_3, "Tarn", "StillScreen")):
            self.key(k)
            self.chapter(who)
            self.assertEqual(self.name(), name)
            self.key(pygame.K_SPACE)                              # the floor card
            self.key(pygame.K_SPACE)                              # a wait: spends the clock
            self.app.draw()
            self.key(pygame.K_ESCAPE)
            self.assertEqual(self.name(), "NightScreen")

    def test_the_loom_warns_then_the_night_ends(self):
        self.app.meta.data["seen_intro_night"] = True
        self.begin()
        c = self.app.campaign
        c.echo.cleared = 1
        c.tick.index = c.still.index = 1
        c.still.chamber = c.still._build(1)
        c.echo.floor_no = cp.ECHO_FLOORS[-1]
        c.echo.start_floor()
        self.app.to_night()
        self.dismiss_order_card()
        self.key(pygame.K_2)
        self.assertIn("This is the Loom", self.app.screen.msg)
        self.assertEqual(self.name(), "NightScreen")
        self.key(pygame.K_2)
        self.assertEqual([k for k, _ in self.app.screen.panels][-2:], ["loom_door", "loom_door"])  # his mother
        self.chapter("Aurel")
        self.assertEqual(self.name(), "GameScreen")
        c.thread_tied()
        self.app.to_night()
        self.assertEqual(self.name(), "IntroScreen")              # the ending: one scene for each of them
        self.assertEqual(self.app.screen.panels, c.ending_panels())
        for i in range(len(self.app.screen.panels)):
            self.app.screen.i, self.app.screen.t = i, 4.0
            self.app.draw()
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.name(), "EpilogueScreen")
        self.app.to_night()                                       # (told once)
        self.assertEqual(self.name(), "EpilogueScreen")
        self.app.tick(1.0)
        self.app.draw()
        self.key(pygame.K_RETURN)
        self.assertEqual(self.name(), "NightTitle")

    def test_running_out_of_time_mid_level(self):
        self.app.meta.data["seen_intro_night"] = True
        self.begin()
        c = self.app.campaign
        self.key(pygame.K_2)
        self.chapter("Aurel")
        c.thread.minutes = 1
        self.key(pygame.K_SPACE)
        self.chapter(None)                                        # the ending (nobody's chapter)
        self.assertEqual(self.name(), "EpilogueScreen")
        self.assertEqual(c.state, "endless")


if __name__ == "__main__":
    unittest.main()


class Storm(unittest.TestCase):
    """Random keys across the whole night (hub, all three stories, their cards and menus): nothing
    may crash, and the night's bookkeeping stays sane."""

    KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
            pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_SPACE, pygame.K_t, pygame.K_f, pygame.K_b,
            pygame.K_r, pygame.K_e, pygame.K_u, pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_h, pygame.K_TAB,
            pygame.K_BACKSPACE, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_x, pygame.K_c]

    def test_random_keys_through_the_night(self):
        import random
        from echo.app import App
        cp.generate_floor = cached_floor
        with tempfile.TemporaryDirectory() as tmp:
            app = App(meta_path=os.path.join(tmp, "m.json"), seed=4, game="night")
            app.meta.data["seen_intro_night"] = True
            c = cp.Campaign(4, "long")
            app.cut_thread(c, "long")
            c.echo.cleared = 1                                    # past the opening (pretend)
            c.tick.index, c.tick.has_watch = 1, True
            c.tick._level = c.tick._build(1)
            c.still.index = 1
            c.still.chamber = c.still._build(1)
            app.to_night()
            rng = random.Random(12)
            seen = set()
            for i in range(2500):
                name = type(app.screen).__name__
                seen.add(name)
                if name in ("NightTitle", "TitleScreen"):
                    if c.state != "night":
                        break
                    app.to_night()
                    continue
                k = rng.choice(self.KEYS)
                app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))
                app.tick(0.05)
                if i % 25 == 0:
                    app.draw()
                self.assertGreaterEqual(c.thread.minutes, 0)
                self.assertLessEqual(c.lamps_lit(), c.lamps_total)
            self.assertTrue({"NightScreen", "GameScreen", "StillScreen", "TickScreen"} <= seen, seen)
