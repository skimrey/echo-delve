"""The Story (the whole Long Night, front to back), and dev mode: keys that finish or fail any level,
the hub's shortcuts, and the endings picker."""

import os
import tempfile
import unittest

from helpers import cached_floor

import pygame

import echo.campaign as cp
from echo import ending, story_reel
from echo.sisters import stillwater as sw


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cp.generate_floor = cached_floor

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, game="night", dev=False):
        from echo.app import App
        self.app = App(meta_path=os.path.join(self.tmp.name, "m.json"), seed=4, game=game, dev=dev)
        return self.app

    def key(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def name(self):
        return type(self.app.screen).__name__


class TheStory(Base):
    def skip_chapter(self):
        """Go to the last panel of the current chapter, finish its line, and go on."""
        scr = self.app.screen
        ci = scr.chapter
        scr.goto(max(i for i, p in enumerate(scr.panels) if p[3] == ci))
        scr.t = 99
        self.app.draw()
        scr.advance()

    def to_the_choice(self, label):
        scr = self.app.screen
        while scr.chapters[scr.chapter][0] != label:
            self.skip_chapter()
        self.skip_chapter()
        self.assertEqual(self.name(), "ChoiceCard")               # played, not told
        self.assertIs(self.app.screen.parent, scr)                # (the animated scene goes on behind it)
        self.app.draw()

    def test_the_whole_story_with_both_choices(self):
        app = self.make()
        self.key(pygame.K_s)                                      # "The Story" on the Long Night's title
        scr = app.screen
        self.assertEqual(self.name(), "StoryScreen")
        self.assertEqual([c[0] for c in scr.chapters[:4]], ["The world", "Aurel", "Maren", "Tarn"])
        self.to_the_choice("The break")
        self.key(pygame.K_2)                                      # Tarn lets them stay
        self.assertEqual((app.screen, scr.chapters[scr.chapter][0]), (scr, "They stay"))
        self.to_the_choice("The Drum Room")
        self.key(pygame.K_2)                                      # Maren takes the bargain
        self.assertEqual(scr.chapters[scr.chapter][0], "The bargain")
        self.skip_chapter()
        self.skip_chapter()                                       # (the Loom's door)
        self.assertEqual(scr.chapters[scr.chapter][0], "The end")
        keys = [p[0] for p in scr.panels if p[3] == scr.chapter]
        self.assertEqual(keys[:2], ["loom_tied", "black_water"])  # they stayed: the water went black around them
        self.assertIn("coach", keys)
        self.assertNotIn("reunion", keys)
        self.skip_chapter()
        self.assertEqual(self.name(), "EpilogueScreen")
        app.draw()
        self.assertIn("bargain", " ".join(app.screen.lines))
        self.key(pygame.K_RETURN)
        self.assertEqual(self.name(), "NightTitle")

    def test_back_and_the_chapters_along_the_bottom(self):
        app = self.make()
        app.night_story()
        scr = app.screen
        self.skip_chapter()
        self.skip_chapter()
        self.assertEqual((scr.chapter, scr.reached), (2, 2))
        app.draw()
        self.assertEqual([ci for ci, _ in scr.chapter_rects], [0, 1, 2])   # revealed one at a time
        first = scr.chapter_start(2)
        self.assertEqual(scr.i, first)
        self.key(pygame.K_LEFT)                                   # back, across the chapter's edge
        self.assertEqual((scr.i, scr.chapter), (first - 1, 1))
        self.click(dict(scr.chapter_rects)[0].center)             # and straight back to the start
        self.assertEqual(scr.i, 0)
        self.key(pygame.K_3)                                      # (or by number)
        self.assertEqual(scr.chapter, 2)
        app.draw()

    def test_going_back_past_a_choice_asks_it_again(self):
        app = self.make()
        app.night_story()
        scr = app.screen
        self.to_the_choice("The break")
        self.key(pygame.K_1)
        self.assertEqual(scr.chapters[scr.chapter][0], "Through")
        self.assertEqual(scr.chapters[scr.chapter][2][0][0], "loom_arrival")   # (landing in a heap)
        scr.goto(scr.chapter_start([c[0] for c in scr.chapters].index("The break")))
        self.to_the_choice("The break")
        self.key(pygame.K_2)
        labels = [c[0] for c in scr.chapters]
        self.assertIn("They stay", labels)
        self.assertNotIn("Through", labels)

    def test_dev_mode_asks_how_the_rest_of_the_night_went(self):
        app = self.make(dev=True)
        app.night_story()
        scr = app.screen
        self.to_the_choice("The break")
        self.key(pygame.K_1)
        self.to_the_choice("The Drum Room")
        self.key(pygame.K_1)
        self.skip_chapter()
        self.skip_chapter()
        self.assertEqual(self.name(), "OutcomeScreen")
        app.draw()
        self.key(pygame.K_x)                                      # the worst morning
        self.key(pygame.K_RETURN)
        self.assertIs(app.screen, scr)
        keys = [(p[0], p[1]) for p in scr.panels if p[3] == scr.chapter]
        self.assertEqual(keys, ending.ending_panels(story_reel.outcome_for(story_reel.WORST)))

    def click(self, pos):
        self.app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))


class Endings(Base):
    def test_every_combination_of_outcomes_has_an_ending(self):
        import itertools
        from echo.cinematics import draw_scene
        surf = pygame.Surface((960, 440))
        seen = set()
        for sel in itertools.product(*[range(len(opts)) for _, opts in story_reel.ROWS]):
            o = story_reel.outcome_for(list(sel))
            panels = ending.ending_panels(o)
            title, lines = ending.epilogue(o)
            self.assertTrue(panels and lines)
            seen.update(k for k, _ in panels)
        for k in seen:
            self.assertTrue(draw_scene(surf, k, 1.0, (0, 0, 960, 440)), k)
        self.assertTrue(story_reel.outcome_for(story_reel.PERFECT).perfect)
        self.assertFalse(story_reel.outcome_for(story_reel.WORST).perfect)

    def test_the_picker_on_the_dev_title(self):
        app = self.make(dev=True)
        self.assertIsNotNone(app.screen.btn("endings"))
        self.key(pygame.K_e)
        self.assertEqual(self.name(), "OutcomeScreen")
        self.key(pygame.K_DOWN)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_RIGHT)                                     # the Still: some lost on the way
        self.key(pygame.K_RETURN)
        self.assertIn("lost on the way", " ".join(p[1] for p in app.screen.panels) +
                      " ".join(ending.epilogue(story_reel.outcome_for([0, 0, 1, 0, 0]))[1]))
        app2 = self.make(dev=False)
        self.assertIsNone(app2.screen.btn("endings"))                 # (not without --dev)


class DevKeys(Base):
    def test_echo_delve_finish_perfect_and_fail(self):
        app = self.make(game="echo", dev=True)
        app.meta.data["seen_intro"] = True
        app.new_run()
        self.key(pygame.K_F10)                                       # perfectly: every sconce, at its par
        self.assertEqual(self.name(), "VictoryScreen")
        res = app.run.last_result
        self.assertEqual((res.lamps, res.spent, res.grade), (res.lamps_total, res.par, "S+"))
        app.draw()
        app.run.apply_upgrade(app.run.options[0])
        from echo.game_screen import GameScreen
        app.replace(GameScreen(app))
        self.key(pygame.K_F9)                                        # a clean clear, at par
        self.assertEqual(app.run.last_result.spent, app.run.last_result.par)
        app.run.apply_upgrade(app.run.options[0])
        app.replace(GameScreen(app))
        self.key(pygame.K_F11)                                       # and a failure ends the run
        self.assertEqual((app.run.state, self.name()), ("dead", "EndScreen"))

    def test_stillwater_and_the_tick(self):
        app = self.make(game="stillwater", dev=True)
        app.meta.data["seen_intro_stillwater"] = True
        self.key(pygame.K_n)
        self.key(pygame.K_SPACE)                                     # the chamber's card
        self.key(pygame.K_F10)
        self.assertEqual(self.name(), "Card")
        self.assertEqual(app.screen.parent.run.saved, sw.parse_chamber(sw.CHAMBERS[0]).population)
        app = self.make(game="tick", dev=True)
        app.meta.data["seen_intro_tick"] = True
        self.key(pygame.K_n)
        self.key(pygame.K_SPACE)
        self.key(pygame.K_F11)
        self.assertEqual(app.screen.sim.over, "caught")
        self.key(pygame.K_r)
        self.key(pygame.K_SPACE)
        self.key(pygame.K_F9)
        self.assertEqual((self.name(), app.screen.parent.run.index), ("Card", 1))

    def test_the_hub_skips_ahead_and_moves_the_thread(self):
        app = self.make(dev=True)
        c = cp.Campaign(4, "measured")
        app.campaign = c
        app.meta.data["seen_intro_night"] = True
        app.to_night()
        start = c.thread.minutes
        self.key(pygame.K_F5)
        self.assertEqual(c.thread.minutes, start + 60)
        self.key(pygame.K_F6)
        self.assertEqual(c.thread.minutes, start)
        self.key(pygame.K_F12)
        self.assertTrue(c.aurel_on_last_floor)
        self.assertEqual((c.tick.index, c.still.index), (c.tick.floors - 1, c.still.chambers - 1))
        self.assertEqual(self.name(), "NightScreen")
        app.draw()

    def test_no_dev_keys_without_dev_mode(self):
        app = self.make(game="echo")
        app.meta.data["seen_intro"] = True
        app.new_run()
        self.key(pygame.K_F9)
        self.assertEqual((self.name(), app.run.state), ("GameScreen", "playing"))


if __name__ == "__main__":
    unittest.main()


class DevStorm(Base):
    def test_random_keys_with_the_dev_keys_never_crash(self):
        import random
        from test_campaign import Storm
        keys = Storm.KEYS + [pygame.K_F1, pygame.K_F5, pygame.K_F6, pygame.K_F9, pygame.K_F10, pygame.K_F11,
                             pygame.K_F12, pygame.K_e, pygame.K_n, pygame.K_p]
        app = self.make(dev=True)
        app.meta.data["seen_intro_night"] = True
        c = cp.Campaign(4, "measured")
        app.cut_thread(c, "measured")
        rng = random.Random(3)
        for i in range(1200):
            name = self.name()
            if name == "LoadingScreen":
                app.screen.finish_now()
                continue
            if name == "NightTitle" and app.campaign.state == "night" and rng.random() < 0.7:
                app.to_night()
                continue
            self.key(rng.choice(keys))
            app.tick(0.05)
            if i % 40 == 0:
                app.draw()
        self.assertGreaterEqual(app.campaign.thread.minutes, 0)
