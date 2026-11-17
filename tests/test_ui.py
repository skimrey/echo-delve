"""Headless UI tests. Every event goes through App.handle exactly like real input.

Covers every button and key on every screen, repeat clicks (no stuck states), cancel/Esc paths,
invalid input (always a visible message), loop transitions, upgrade/end flows and a random-input storm.
"""

import os
import random
import tempfile
import unittest

from helpers import make_floor

import pygame

from echo.app import App
from echo.consts import BASE_SLOTS, MAX_FLOOR, PERKS, UPGRADES
from echo.game_screen import OY, GameScreen
from echo.menus import (EndScreen, ForgeScreen, HelpScreen, PauseScreen, TitleScreen,
                        UpgradeScreen)
from echo.run import FloorPlay
from echo.sim import GhostScript

PLATE_ROWS = ["S.....a#", "######.#", "######1#", "######E#"]
ARENA = ["S.........#", "...........", "...........", "...........", "..........."]


class UITestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App(meta_path=os.path.join(self.tmp.name, "meta.json"), seed=11)

    def tearDown(self):
        self.tmp.cleanup()

    # -- real-event input helpers
    def click(self, pos, button=1):
        self.app.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))

    def hover(self, pos):
        self.app.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))

    def key(self, k):
        self.app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def keys(self, *ks):
        for k in ks:
            self.key(k)

    def btn(self, tag):
        b = self.app.screen.btn(tag)
        self.assertIsNotNone(b, "no button %r on %s" % (tag, type(self.app.screen).__name__))
        return b

    def click_btn(self, tag):
        self.click(self.btn(tag).rect.center)

    def draw_ok(self):
        self.app.draw()
        small = pygame.transform.scale(self.app.surface, (64, 40))
        colours = {tuple(small.get_at((x, y)))[:3] for x in range(64) for y in range(40)}
        self.assertGreater(len(colours), 6, "screen looks blank")

    @property
    def gs(self):
        self.assertIsInstance(self.app.screen, GameScreen)
        return self.app.screen

    @property
    def rn(self):
        return self.app.run

    def tile_click(self, x, y, button=1):
        self.click(self.gs.tile_center((x, y)), button)

    # -- builders
    def game(self, rows, hp=None, **kw):
        self.app.new_run()
        f = make_floor(rows, **kw)
        run = self.app.run
        run.floor = f
        run.play = FloorPlay(f, run.mods(), run.slots + 1)
        run.seen = set()
        if hp is not None:
            run.sim.player.hp = hp
        self.app.replace(GameScreen(self.app))
        return self.gs

    def say_of(self):
        return self.app.screen.msg


class TitleTests(UITestCase):
    def test_buttons_present_and_screen_draws(self):
        self.assertIsInstance(self.app.screen, TitleScreen)
        self.assertEqual([b.tag for b in self.app.screen.buttons], ["new", "forge", "help", "quit"])
        self.draw_ok()

    def test_new_run_by_button_and_by_n_and_enter(self):
        self.click_btn("new")
        self.assertIsInstance(self.app.screen, GameScreen)
        for k in (pygame.K_n, pygame.K_RETURN):
            self.app.to_title()
            self.key(k)
            self.assertIsInstance(self.app.screen, GameScreen, k)
            self.assertEqual(self.rn.state, "playing")

    def test_help_twice_in_a_row_by_button_and_key(self):
        for _ in range(2):
            self.click_btn("help")
            self.assertIsInstance(self.app.screen, HelpScreen)
            self.draw_ok()
            self.click_btn("back")
            self.assertIsInstance(self.app.screen, TitleScreen)
        for closer in (pygame.K_ESCAPE, pygame.K_h, pygame.K_RETURN, pygame.K_SPACE):
            self.key(pygame.K_h)
            self.assertIsInstance(self.app.screen, HelpScreen)
            self.key(closer)
            self.assertIsInstance(self.app.screen, TitleScreen, closer)

    def test_forge_button_and_key(self):
        self.click_btn("forge")
        self.assertIsInstance(self.app.screen, ForgeScreen)
        self.app.to_title()
        self.key(pygame.K_f)
        self.assertIsInstance(self.app.screen, ForgeScreen)

    def test_quit_by_button_escape_and_window_close(self):
        self.click_btn("quit")
        self.assertFalse(self.app.running)
        self.app.running = True
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.running)
        self.app.running = True
        self.app.handle(pygame.event.Event(pygame.QUIT))
        self.assertFalse(self.app.running)

    def test_clicking_nothing_and_unknown_keys_do_nothing(self):
        self.click((3, 3))
        self.key(pygame.K_F9)
        self.hover((480, 270))
        self.assertIsInstance(self.app.screen, TitleScreen)


class ForgeTests(UITestCase):
    def setUp(self):
        super().setUp()
        self.app.meta.data["shards"] = 0
        self.app.show_forge()

    def test_cannot_afford_says_why_for_every_perk(self):
        for key in ForgeScreen.ORDER:
            self.click_btn("buy:" + key)
            self.assertIn("costs", self.say_of())
            self.assertEqual(self.app.meta.level(key), 0)

    def test_buy_every_perk_to_the_max_by_click_and_key_then_maxed_message(self):
        self.app.meta.data["shards"] = 500
        self.app.show_forge()
        for i, key in enumerate(ForgeScreen.ORDER):
            mx = PERKS[key][2]
            for n in range(mx):
                if n % 2 == 0:
                    self.click_btn("buy:" + key)
                else:
                    self.key(pygame.K_1 + i)
                self.assertEqual(self.app.meta.level(key), n + 1)
                self.assertIn("Bought", self.say_of())
            self.click_btn("buy:" + key)
            self.assertIn("maxed", self.say_of())
            self.assertEqual(self.btn("buy:" + key).label, "Maxed")
        self.draw_ok()

    def test_shards_are_spent_and_persisted(self):
        self.app.meta.data["shards"] = PERKS["hp"][3]
        self.app.show_forge()
        self.click_btn("buy:hp")
        self.assertEqual(self.app.meta.data["shards"], 0)
        reread = type(self.app.meta)(self.app.meta.path)
        self.assertEqual(reread.level("hp"), 1)

    def test_perk_reaches_the_next_run(self):
        self.app.meta.data["shards"] = 50
        self.app.show_forge()
        self.click_btn("buy:hp")
        self.app.to_title()
        self.key(pygame.K_n)
        self.assertEqual(self.rn.max_hp, 11)

    def test_back_by_button_and_escape(self):
        self.click_btn("back")
        self.assertIsInstance(self.app.screen, TitleScreen)
        self.app.show_forge()
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, TitleScreen)


class MovementInput(UITestCase):
    def setUp(self):
        super().setUp()
        self.game(ARENA)

    def test_every_direction_key(self):
        cases = ((pygame.K_RIGHT, (1, 0)), (pygame.K_d, (1, 0)), (pygame.K_DOWN, (0, 1)), (pygame.K_s, (0, 1)),
                 (pygame.K_LEFT, (-1, 0)), (pygame.K_a, (-1, 0)), (pygame.K_UP, (0, -1)), (pygame.K_w, (0, -1)))
        for k, d in cases:
            self.game(ARENA)
            self.rn.sim.player.x, self.rn.sim.player.y = 5, 2
            self.key(k)
            self.assertEqual(self.rn.sim.player.pos, (5 + d[0], 2 + d[1]), k)
            self.assertEqual(self.rn.sim.turn, 1)

    def test_wait_by_every_route_twice(self):
        for how in ("space", "period", "kp5", "button", "self"):
            for _ in range(2):
                before = self.rn.sim.turn
                if how == "space":
                    self.key(pygame.K_SPACE)
                elif how == "period":
                    self.key(pygame.K_PERIOD)
                elif how == "kp5":
                    self.key(pygame.K_KP5)
                elif how == "button":
                    self.click_btn("wait")
                else:
                    self.tile_click(*self.rn.sim.player.pos)
                self.assertEqual(self.rn.sim.turn, before + 1, how)
        self.assertEqual(self.rn.sim.player.pos, (0, 0))

    def test_click_adjacent_tile_moves(self):
        self.tile_click(1, 0)
        self.assertEqual(self.rn.sim.player.pos, (1, 0))
        self.tile_click(1, 1)
        self.assertEqual(self.rn.sim.player.pos, (1, 1))

    def test_click_far_tile_explains(self):
        self.tile_click(8, 3)
        self.assertEqual(self.rn.sim.turn, 0)
        self.assertIn("next to you", self.say_of())

    def test_bumping_a_wall_costs_nothing_and_says_so(self):
        for k in (pygame.K_UP, pygame.K_LEFT):
            self.key(k)
            self.assertIn("wall", self.say_of().lower())
        self.tile_click(0, 0)            # own tile is a wait, not a bump
        self.assertEqual(self.rn.sim.turn, 1)
        self.rn.sim.turn = 0
        self.tile_click(11, 0)           # wall tile far away
        self.assertIn("next to you", self.say_of())

    def test_clicking_the_hud_and_unknown_keys_do_nothing(self):
        self.click((100, 10))
        self.click((300, 645))
        self.keys(pygame.K_F5, pygame.K_x, pygame.K_q)
        self.assertEqual(self.rn.sim.turn, 0)

    def test_striking_an_enemy_by_key_and_by_click(self):
        self.game(["SC...", "....."])
        self.rn.sim.enemies[0].x = 1
        self.key(pygame.K_RIGHT)
        self.assertEqual(self.rn.sim.enemies[0].hp, 0)
        self.assertIn("You hit", self.say_of())
        self.game(["SC...", "....."])
        self.tile_click(1, 0)
        self.assertEqual(self.rn.sim.enemies[0].hp, 0)
        self.assertEqual(self.rn.sim.record, [("f", 1, 0)])


class AnchorInput(UITestCase):
    def setUp(self):
        super().setUp()
        self.game(PLATE_ROWS)

    def test_anchor_needs_two_presses_by_key(self):
        self.key(pygame.K_e)
        self.assertTrue(self.gs.confirm)
        self.assertEqual(self.rn.play.loop_no, 1)
        self.assertIn("again", self.say_of())
        self.key(pygame.K_e)
        self.assertEqual(self.rn.play.loop_no, 2)
        self.assertFalse(self.gs.confirm)
        self.assertIn("anchored", self.say_of())

    def test_anchor_by_button_twice_in_a_row_across_loops(self):
        for n in (2, 3):
            self.click_btn("anchor")
            self.assertTrue(self.gs.confirm)
            self.click_btn("anchor")
            self.assertEqual(self.rn.play.loop_no, n)
        self.assertEqual(len(self.rn.play.scripts), 2)

    def test_escape_cancels_without_opening_the_menu(self):
        self.key(pygame.K_e)
        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.gs.confirm)
        self.assertIn("cancelled", self.say_of())
        self.assertIsInstance(self.app.screen, GameScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, PauseScreen)

    def test_any_other_key_cancels_and_still_acts(self):
        self.key(pygame.K_e)
        self.key(pygame.K_RIGHT)
        self.assertFalse(self.gs.confirm)
        self.assertEqual(self.rn.sim.player.pos, (1, 0))
        self.assertEqual(self.rn.play.loop_no, 1)

    def test_right_click_and_other_buttons_cancel(self):
        self.key(pygame.K_e)
        self.click((300, 300), button=3)
        self.assertFalse(self.gs.confirm)
        self.key(pygame.K_e)
        self.click_btn("paths")
        self.assertFalse(self.gs.confirm)
        self.key(pygame.K_e)
        self.click_btn("wait")
        self.assertFalse(self.gs.confirm)
        self.assertEqual(self.rn.sim.turn, 1)
        self.assertEqual(self.rn.play.loop_no, 1)

    def test_last_loop_warns(self):
        self.rn.play.loop_no = self.rn.play.loops_max
        self.key(pygame.K_e)
        self.assertIn("LAST LOOP", self.say_of())
        self.key(pygame.K_ESCAPE)


class LoopFlow(UITestCase):
    def test_two_loop_solution_end_to_end_then_upgrade_then_next_floor(self):
        self.game(PLATE_ROWS, limit=50)
        self.keys(*[pygame.K_RIGHT] * 6)
        self.assertTrue(self.rn.sim.plate_held(0))
        self.keys(pygame.K_e, pygame.K_e)
        self.assertEqual(self.rn.play.loop_no, 2)
        self.assertIn("Loop 2/%d begins" % (BASE_SLOTS + 1), self.say_of())
        self.draw_ok()
        self.keys(*[pygame.K_RIGHT] * 6)                 # walk in step with the echo
        self.assertTrue(self.rn.sim.door_open(0))
        self.keys(pygame.K_DOWN, pygame.K_DOWN, pygame.K_DOWN)
        self.assertEqual(self.rn.state, "upgrade")
        self.assertIsInstance(self.app.screen, UpgradeScreen)
        self.draw_ok()
        self.key(pygame.K_1)
        self.assertIsInstance(self.app.screen, GameScreen)
        self.assertEqual(self.rn.floor_no, 2)
        self.draw_ok()

    def test_sealed_door_message_is_visible(self):
        self.game(PLATE_ROWS)
        self.keys(*[pygame.K_RIGHT] * 6, pygame.K_DOWN)
        self.key(pygame.K_DOWN)
        self.assertIn("Door 1 is sealed", self.say_of())
        self.assertEqual(self.rn.sim.turn, 7)

    def test_timeout_message_and_auto_echo(self):
        gs = self.game(PLATE_ROWS)
        self.rn.sim.limit = 2
        self.keys(pygame.K_RIGHT, pygame.K_RIGHT)
        self.assertIn("collapsed", self.say_of())
        self.assertEqual(self.rn.play.loop_no, 2)
        self.assertEqual(len(self.rn.play.scripts), 1)

    def test_death_message_and_dead_echo(self):
        self.game(["SC..", "...."], hp=1)
        self.rn.sim.enemies[0].awake = True
        self.key(pygame.K_SPACE)
        self.assertIn("You fell", self.say_of())
        self.assertEqual(self.rn.play.scripts[0].ending, "dead")
        self.assertEqual(self.rn.play.loop_no, 2)
        self.assertIsInstance(self.app.screen, GameScreen)

    def test_running_out_of_loops_shows_the_end_screen_once(self):
        self.game(PLATE_ROWS)
        for _ in range(BASE_SLOTS + 1):
            self.assertIsInstance(self.app.screen, GameScreen)
            self.keys(pygame.K_e, pygame.K_e)
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.app.end_run()
        self.assertEqual(self.app.meta.data["runs"], 1)
        self.draw_ok()

    def test_winning_the_last_floor(self):
        self.app.new_run()
        self.rn.floor_no = MAX_FLOOR
        self.rn.cleared = MAX_FLOOR - 1
        f = make_floor(["SE"])
        self.rn.floor = f
        self.rn.play = FloorPlay(f, self.rn.mods(), self.rn.slots + 1)
        self.app.replace(GameScreen(self.app))
        self.key(pygame.K_RIGHT)
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.rn.state, "won")
        self.assertEqual((self.app.meta.data["wins"], self.app.meta.data["shards"]), (1, MAX_FLOOR + 3))
        self.draw_ok()


class UpgradeAndEnd(UITestCase):
    def to_upgrade(self):
        self.game(["SE"])
        self.key(pygame.K_RIGHT)
        self.assertIsInstance(self.app.screen, UpgradeScreen)

    def test_each_card_by_key_and_by_click(self):
        for i in range(3):
            for how in ("key", "click"):
                self.to_upgrade()
                taken = self.rn.options[i]
                before = (self.rn.max_hp, self.rn.atk, self.rn.slots, self.rn.limit_bonus,
                          self.rn.sight, self.rn.ghost_hp)
                if how == "key":
                    self.key(pygame.K_1 + i)
                else:
                    self.click_btn("up%d" % i)
                after = (self.rn.max_hp, self.rn.atk, self.rn.slots, self.rn.limit_bonus,
                         self.rn.sight, self.rn.ghost_hp)
                self.assertNotEqual(before, after, taken)
                self.assertIsInstance(self.app.screen, GameScreen)
                self.assertEqual(self.rn.floor_no, 2)
                self.assertEqual(self.rn.picked, [taken])

    def test_upgrade_screen_ignores_junk_and_does_not_double_apply(self):
        self.to_upgrade()
        self.keys(pygame.K_4, pygame.K_x, pygame.K_ESCAPE)
        self.click((5, 5))
        self.assertIsInstance(self.app.screen, UpgradeScreen)
        self.hover(self.btn("up1").rect.center)
        self.draw_ok()
        self.key(pygame.K_2)
        self.assertEqual(len(self.rn.picked), 1)
        self.key(pygame.K_2)             # now on the game screen: just a no-op key
        self.assertEqual(len(self.rn.picked), 1)

    def test_end_screen_buttons_and_keys(self):
        for tag, key, cls in (("new", pygame.K_n, GameScreen), ("new", pygame.K_RETURN, GameScreen),
                              ("forge", pygame.K_f, ForgeScreen), ("title", pygame.K_ESCAPE, TitleScreen)):
            for how in ("click", "key"):
                self.app.new_run()
                self.app.abandon_run()
                self.assertIsInstance(self.app.screen, EndScreen)
                self.draw_ok()
                if how == "click":
                    self.click_btn(tag)
                else:
                    self.key(key)
                self.assertIsInstance(self.app.screen, cls, (tag, how))


class PauseAndHelp(UITestCase):
    def setUp(self):
        super().setUp()
        self.game(ARENA)

    def test_pause_resume_twice_in_a_row(self):
        for _ in range(2):
            self.key(pygame.K_ESCAPE)
            self.assertIsInstance(self.app.screen, PauseScreen)
            self.draw_ok()
            self.key(pygame.K_ESCAPE)
            self.assertIsInstance(self.app.screen, GameScreen)
        self.click_btn("menu")
        self.click_btn("resume")
        self.assertIsInstance(self.app.screen, GameScreen)

    def test_help_from_game_and_from_pause_returns_where_it_came_from(self):
        self.key(pygame.K_h)
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, GameScreen)
        self.click_btn("help")
        self.click_btn("back")
        self.assertIsInstance(self.app.screen, GameScreen)
        self.key(pygame.K_ESCAPE)
        self.key(pygame.K_h)
        self.assertIsInstance(self.app.screen, HelpScreen)
        self.key(pygame.K_ESCAPE)
        self.assertIsInstance(self.app.screen, PauseScreen)
        self.click_btn("help")
        self.click_btn("back")
        self.assertIsInstance(self.app.screen, PauseScreen)

    def test_game_state_survives_pause_and_help(self):
        self.key(pygame.K_RIGHT)
        self.key(pygame.K_ESCAPE)
        self.key(pygame.K_h)
        self.key(pygame.K_ESCAPE)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.rn.sim.player.pos, (1, 0))
        self.assertEqual(self.rn.sim.turn, 1)

    def test_abandon_needs_two_steps_and_escape_cancels(self):
        self.key(pygame.K_ESCAPE)
        self.click_btn("abandon")
        self.assertIsInstance(self.app.screen, PauseScreen)
        self.assertIn("again", self.say_of())
        self.key(pygame.K_ESCAPE)
        self.assertIn("cancelled", self.say_of())
        self.assertIsInstance(self.app.screen, PauseScreen)
        self.assertEqual(self.btn("abandon").label, "Abandon Run  (A)")
        self.key(pygame.K_a)
        self.key(pygame.K_a)
        self.assertIsInstance(self.app.screen, EndScreen)
        self.assertEqual(self.rn.state, "dead")
        self.assertIn("abandoned", self.rn.reason)
        self.assertEqual(self.app.meta.data["runs"], 1)

    def test_abandon_by_clicking_twice(self):
        self.click_btn("menu")
        self.click_btn("abandon")
        self.click_btn("abandon")
        self.assertIsInstance(self.app.screen, EndScreen)


class PathsHoverEffects(UITestCase):
    def setUp(self):
        super().setUp()
        self.game(PLATE_ROWS)

    def test_paths_toggle_by_button_and_tab_twice(self):
        self.assertTrue(self.gs.show_paths)
        for how in ("button", "tab", "button", "tab"):
            before = self.gs.show_paths
            if how == "button":
                self.click_btn("paths")
            else:
                self.key(pygame.K_TAB)
            self.assertNotEqual(self.gs.show_paths, before)
            self.assertIn("Echo paths", self.say_of())
            self.draw_ok()

    def test_paths_are_drawn_for_a_live_echo_and_follow_its_script(self):
        script = GhostScript([("m", 1, 0)] * 3 + [("w",)], "anchor", 1)
        self.rn.play.scripts.append(script)
        from echo.sim import LoopSim
        self.rn.play.sim = LoopSim(self.rn.floor, [script], self.rn.mods())
        paths = self.gs.ghost_paths(self.rn.sim)
        self.assertEqual(paths[0][1], [(0, 0), (1, 0), (2, 0), (3, 0)])
        self.draw_ok()
        self.key(pygame.K_SPACE)
        paths = self.gs.ghost_paths(self.rn.sim)
        self.assertEqual(paths[0][1], [(1, 0), (2, 0), (3, 0)])

    def test_tooltips_describe_what_you_see(self):
        self.game(["SC.1a..", "......."])
        sim = self.rn.sim
        self.rn.seen |= {(x, y) for x in range(7) for y in range(2)}
        self.gs.visible = set(self.rn.seen)
        self.assertIn("Crawler", self.gs.describe_tile((1, 0)))
        self.assertIn("asleep", self.gs.describe_tile((1, 0)))
        self.assertIn("You:", self.gs.describe_tile((0, 0)))
        self.assertIn("Door 1", self.gs.describe_tile((3, 0)))
        self.assertIn("Plate 1", self.gs.describe_tile((4, 0)))
        self.assertEqual(self.gs.describe_tile((50, 50)), "")
        self.hover(self.gs.tile_center((1, 0)))
        self.assertEqual(self.gs.hover_tile, (1, 0))
        self.draw_ok()
        self.hover((400, 5))
        self.assertIsNone(self.gs.hover_tile)

    def test_right_click_reports_or_says_nothing(self):
        self.game(["SC...", "....."])
        self.rn.seen |= {(x, y) for x in range(5) for y in range(2)}
        self.tile_click(1, 0, button=3)
        self.assertIn("Crawler", self.say_of())
        self.click((900, 500), button=3)
        self.assertEqual(self.say_of(), "Nothing to see there.")

    def test_floating_effects_appear_and_expire(self):
        self.game(["SC...", "....."])
        self.rn.sim.enemies[0].x = 1
        self.key(pygame.K_RIGHT)
        self.assertTrue(self.gs.effects)
        self.draw_ok()
        self.assertTrue(self.app.screen.update(0.2))
        self.assertTrue(self.app.screen.update(2.0))
        self.assertFalse(self.gs.effects)
        self.assertFalse(self.app.screen.update(0.1))

    def test_draw_with_many_echoes_and_enemies_and_every_feature(self):
        self.game(["S..p.^..vC.A.B.W", "....1....a......", "..E............."])
        for i in range(7):
            s = GhostScript([("m", 1, 0)] * (i + 1), "anchor" if i % 2 else "dead", i + 1)
            self.rn.play.scripts.append(s)
        from echo.sim import LoopSim
        self.rn.play.sim = LoopSim(self.rn.floor, self.rn.play.scripts, self.rn.mods())
        self.rn.seen |= {(x, y) for x in range(16) for y in range(3)}
        self.gs.reveal()
        for _ in range(4):
            self.draw_ok()
            self.key(pygame.K_SPACE)
        self.draw_ok()


class Storm(UITestCase):
    KEYS = [pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_e, pygame.K_TAB, pygame.K_h,
            pygame.K_n, pygame.K_f, pygame.K_a, pygame.K_w, pygame.K_s, pygame.K_d, pygame.K_UP,
            pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
            pygame.K_PERIOD, pygame.K_F1]

    def test_random_input_never_raises_and_keeps_invariants(self):
        screens_seen = set()
        for seed in (1, 2, 3, 4):
            rng = random.Random(seed)
            self.app = App(meta_path=os.path.join(self.tmp.name, "m%d.json" % seed), seed=seed)
            self.app.meta.data["shards"] = 40
            self.app.new_run()
            for step in range(900):
                roll = rng.random()
                if roll < 0.4:
                    self.click((rng.randrange(0, 960), rng.randrange(0, 660)), rng.choice((1, 1, 1, 3)))
                elif roll < 0.8:
                    self.key(rng.choice(self.KEYS))
                elif roll < 0.9:
                    self.hover((rng.randrange(0, 960), rng.randrange(0, 660)))
                else:
                    self.app.tick(rng.choice((0.05, 0.4)))
                self.app.running = True
                screens_seen.add(type(self.app.screen).__name__)
                self.assertTrue(self.app.stack)
                if step % 30 == 0:
                    self.app.draw()
                if isinstance(self.app.screen, TitleScreen):
                    self.app.new_run()
                run = self.app.run
                if run and run.state == "playing":
                    p = run.sim.player
                    self.assertTrue(0 <= p.x < 40 and 0 <= p.y < 24)
                    self.assertLessEqual(run.play.loop_no, run.play.loops_max)
                    self.assertLessEqual(run.sim.turn, run.sim.limit)
            self.app.draw()
        for needed in ("GameScreen", "PauseScreen", "HelpScreen", "EndScreen"):
            self.assertIn(needed, screens_seen)


if __name__ == "__main__":
    unittest.main()
