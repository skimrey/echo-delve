"""The sister-game prototypes: Stillwater (ripples, the wake, leading the Still) and The Tick
(winding the tower back on the Guild's hoard)."""

import os
import tempfile
import unittest
from collections import deque

from helpers import D, R  # (also forces headless SDL)

import pygame

from echo.sisters import stillwater as sw
from echo.sisters import tick as tk


def chamber(rows, followers=0, pebbles=0, name="test"):
    return sw.parse_chamber(dict(name=name, hint="", rows=rows, followers=followers, pebbles=pebbles))


def walk(sim, tiles):
    for p in tiles:
        if sim.over:
            break
        sim.step(("m", p[0] - sim.player[0], p[1] - sim.player[1]))


def route(c, a, b, water_ok=True, sim=None):
    prev, q = {a: None}, deque([a])
    w, h = c.size
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for dx, dy in sw.DIRS:
            n = (cur[0] + dx, cur[1] + dy)
            if n in prev or n in c.walls or not (0 <= n[0] < w and 0 <= n[1] < h):
                continue
            if sim is not None and sim.gate_closed_at(n) and n != b:
                continue
            if not water_ok and n in c.water and n != b:
                continue
            prev[n] = cur
            q.append(n)
    out, cur = [], b
    while prev.get(cur) is not None:
        out.append(cur)
        cur = prev[cur]
    return out[::-1]


def wait_for_kin(s, limit=30):
    for _ in range(limit):
        if s.over or s.count("following") == 0:
            return
        s.step(("w",))


# ====================================================================== Stillwater

class Ripples(unittest.TestCase):
    POOL = ["#########", "#S~~~~~~#", "#~~~~~~~#", "#~~~~~~~#", "#......E#", "#########"]

    def test_a_ripple_spreads_about_a_tile_a_turn_in_near_circles(self):
        s = sw.Still(chamber(self.POOL))
        s.step(("t",))
        r = s.ripples[0]
        self.assertEqual(r.origin, (2, 1))          # you stand on dry stone: the touch lands beside you
        self.assertEqual(r.arrival((5, 1)), 3)
        self.assertEqual(r.arrival((3, 2)), 2)       # a diagonal step costs ~1.42
        self.assertEqual(r.arrival((4, 3)), 3)       # so the wave grows as a near-circle, not a diamond
        self.assertIsNone(r.arrival((1, 4)))         # dry ledge: no ripple

    def test_standing_still_is_silent_and_wading_is_not(self):
        s = sw.Still(chamber(self.POOL))
        s.step(("w",))
        self.assertEqual(s.ripples, [])
        s.step(R)
        self.assertEqual((s.ripples[0].source, s.ripples[0].reach), ("wade", sw.WADE_REACH))

    def test_walls_and_dry_stone_stop_ripples(self):
        s = sw.Still(chamber(["#########", "#S~~#~~~#", "#~~~#~~~#", "#......E#", "#########"]))
        s.step(("t",))
        self.assertTrue(all(p[0] < 4 for p in s.ripples[0].dist))

    def test_lit_water_stays_visible_for_the_wake_and_is_remembered(self):
        s = sw.Still(chamber(self.POOL))
        s.step(("t",))
        for _ in range(3):
            s.step(("w",))
        self.assertIn((5, 1), s.seen)
        self.assertTrue(s.visible_to_kin((5, 1)))
        for _ in range(sw.WAKE + 1):
            s.step(("w",))
        self.assertFalse(s.visible_to_kin((5, 1)))
        self.assertIn((5, 1), s.seen)                # the map remembers even when the Still cannot see


class TheStill(unittest.TestCase):
    ROWS = ["############", "#S.........#", "#..........#", "#........E.#", "############"]

    def test_they_follow_you_through_your_wake_and_climb_out_at_the_way_up(self):
        c = chamber(self.ROWS, followers=2)
        s = sw.Still(c)
        walk(s, route(c, c.start, c.exit))
        wait_for_kin(s)
        self.assertEqual(s.count("saved"), 2)
        s.step(("x",))
        self.assertEqual(s.over, "out")

    def test_left_in_the_dark_they_stop_and_climbing_out_leaves_them(self):
        c = chamber(self.ROWS, followers=1)
        s = sw.Still(c)
        walk(s, route(c, c.start, c.exit))
        s.kin[0].pos = (1, 1)
        for _ in range(sw.WAKE + 3):                 # your trail past them fades
            s.step(("w",))
        self.assertFalse(s.visible_to_kin((1, 1)))
        before = s.kin[0].pos
        s.step(("w",))
        self.assertEqual(s.kin[0].pos, before)
        self.assertIn("only go on from the way on", sw.Still(c).validate(("x",)))     # not from the start
        s.step(("x",))
        self.assertEqual((s.count("lost"), s.over), (1, "out"))

    def test_a_stranded_one_joins_when_you_reach_them(self):
        c = chamber(["##########", "#S......s#", "#.......E#", "##########"])
        s = sw.Still(c)
        self.assertEqual(s.count("stranded"), 1)
        walk(s, [(x, 1) for x in range(2, 8)])
        self.assertEqual(s.count("following"), 1)

    def test_the_still_never_crowd_onto_one_tile(self):
        c = chamber(["##############", "#S..........E#", "#............#", "##############"], followers=3)
        s = sw.Still(c)
        for x in range(2, 9):
            s.step(("m", 1, 0))
            following = [k.pos for k in s.kin if k.state == "following"]
            self.assertEqual(len(following), len(set(following)))
        self.assertEqual(s.count("following"), 3)                    # (and all three kept up)

    def test_a_line_holds_together_hand_on_shoulder(self):
        # a single-file corridor on dry stone: only the tiles you walked light up, and only for a few
        # turns; the one at the back can only follow the shoulder in front of them
        c = chamber(["#################", "#S.............E#", "#################"], followers=3)
        s = sw.Still(c)
        for _ in range(12):
            s.step(("m", 1, 0))
        for _ in range(10):
            s.step(("w",))
        xs = sorted(k.pos[0] for k in s.kin if k.state == "following")
        self.assertEqual(len(xs), 3)
        self.assertEqual(xs, list(range(xs[0], xs[0] + 3)))        # a line, each touching the next
        self.assertEqual(xs[-1], s.player[0] - 1)

    def test_an_eel_takes_a_follower_who_wades_near_it(self):
        c = chamber(["##########", "#S.~~~~e~#", "#..~~~~~~#", "#........#", "#.......E#", "##########"],
                    followers=1)
        s = sw.Still(c)
        walk(s, [(2, 1), (3, 1), (4, 1), (5, 1)])
        for _ in range(12):
            if s.over or s.count("lost"):
                break
            s.step(("w",))
        self.assertTrue(s.count("lost") == 1 or s.over == "caught")


class FloatGates(unittest.TestCase):
    ROWS = ["###########", "#S~~~~~~~a#", "#.#########", "#.A.....E##", "###########"]

    def test_a_ripple_on_the_float_lifts_the_gate_for_a_while(self):
        s = sw.Still(chamber(self.ROWS))
        s.step(("t",))                                 # from the water at (2,1) to the float at (9,1): 7 turns
        for _ in range(6):
            s.step(("w",))
            self.assertFalse(s.gate_open(0))
        ev = s.step(("w",))
        self.assertIn(("gate", 0, True), ev)
        for _ in range(sw.GATE_OPEN - 1):
            s.step(("w",))
            self.assertTrue(s.gate_open(0))
        s.step(("w",))
        self.assertFalse(s.gate_open(0))

    def test_a_shut_gate_refuses_you_with_a_hint(self):
        s = sw.Still(chamber(self.ROWS))
        walk(s, [(1, 2), (1, 3)])
        self.assertIn("Float-gate A is down", s.validate(R))


class TheWaterDims(unittest.TestCase):
    """As the night (the thread) runs down, the water dims: ripples and the wake shrink."""

    def test_the_light_follows_the_night(self):
        self.assertEqual(sw.light_for(100, 100), 1.0)
        self.assertEqual(sw.light_for(0, 100), sw.MIN_LIGHT)
        self.assertEqual(sw.light_for(500, 100), 1.0)                  # a lengthened thread is no brighter
        run = sw.StillRun(seed=1)
        bright = run.light()
        run.spend(sw.NIGHT // 2)
        self.assertLess(run.light(), bright)

    def test_dim_water_makes_shorter_ripples_and_a_shorter_wake(self):
        c = sw.parse_chamber(dict(name="t", rows=Ripples.POOL))
        bright, dim = sw.Still(c, 1.0), sw.Still(c, sw.MIN_LIGHT)
        bright.step(("t",))
        dim.step(("t",))
        self.assertLess(dim.ripples[0].reach, bright.ripples[0].reach)
        self.assertLess(dim.wake, bright.wake)

    def test_generated_chambers_stay_possible_at_the_dimmest_light(self):
        for seed in (1, 2, 3):
            for index in range(len(sw.CHAMBERS), len(sw.CHAMBERS) + sw.GENERATED):
                c = sw.generate_chamber(seed, index)
                done = sw.walkthrough(c, light=sw.MIN_LIGHT)
                self.assertEqual((done.over, done.count("saved")), ("out", c.population), (seed, index))

    def test_the_listeners_at_the_dimmest_light_take_both_pebbles(self):
        c = sw.parse_chamber(sw.CHAMBERS[2])
        s = sw.Still(c, sw.MIN_LIGHT)
        walk(s, route(c, c.start, (12, 2), water_ok=False))
        s.step(("f", 1, 0))                                          # one pebble no longer reaches both eels
        walk(s, route(c, (12, 2), (12, 5), water_ok=False))
        s.step(("f", 1, 0))
        walk(s, route(c, (12, 5), (12, 9), water_ok=False))
        for _ in range(4):
            s.step(("w",))
        walk(s, [(x, 9) for x in range(13, 29)])
        wait_for_kin(s)
        s.step(("x",))
        self.assertEqual((s.over, s.count("saved")), ("out", c.population))


class HandwrittenChambers(unittest.TestCase):
    def test_each_tutorial_chamber_can_bring_everyone_up(self):
        c = sw.parse_chamber(sw.CHAMBERS[0])
        s = sw.Still(c)
        walk(s, route(c, c.start, (20, 1)))
        walk(s, route(c, s.player, c.exit))
        wait_for_kin(s)
        s.step(("x",))
        self.assertEqual((s.over, s.count("saved")), ("out", c.population))
        c = sw.parse_chamber(sw.CHAMBERS[1])
        s = sw.Still(c)
        walk(s, route(c, c.start, (18, 1), water_ok=False))
        s.step(("t",))
        walk(s, route(c, (18, 1), (27, 6), water_ok=False))
        while not s.gate_open(0) and s.turn < 200:
            s.step(("w",))
        walk(s, route(c, s.player, c.exit, sim=s))
        wait_for_kin(s)
        s.step(("x",))
        self.assertEqual((s.over, s.count("saved")), ("out", c.population))
        c = sw.parse_chamber(sw.CHAMBERS[2])
        s = sw.Still(c)
        walk(s, route(c, c.start, (12, 2), water_ok=False))
        s.step(("f", 1, 0))
        walk(s, route(c, (12, 2), (12, 9), water_ok=False))
        walk(s, [(x, 9) for x in range(13, 29)])
        wait_for_kin(s)
        s.step(("x",))
        self.assertEqual((s.over, s.count("saved")), ("out", c.population))

    def test_the_listeners_punish_wading_straight_in(self):
        c = sw.parse_chamber(sw.CHAMBERS[2])
        s = sw.Still(c)
        walk(s, route(c, c.start, (12, 9), water_ok=False))
        walk(s, [(x, 9) for x in range(13, 29)])
        self.assertEqual(s.over, "caught")

    def test_the_walkthrough_guide_clears_the_tutorials_without_eels(self):
        for spec in sw.CHAMBERS[:2]:
            c = sw.parse_chamber(spec)
            done = sw.walkthrough(c)
            self.assertEqual((done.over, done.count("saved")), ("out", c.population), spec["name"])


class GeneratedChambers(unittest.TestCase):
    def test_every_generated_chamber_can_bring_everyone_up_and_differs_by_seed(self):
        shapes = set()
        for seed in range(1, 9):
            for index in range(len(sw.CHAMBERS), len(sw.CHAMBERS) + sw.GENERATED):
                c = sw.generate_chamber(seed, index)
                with self.subTest(seed=seed, index=index):
                    done = sw.walkthrough(c)
                    self.assertEqual((done.over, done.count("saved")), ("out", c.population))
                    for light in (sw.MIN_LIGHT, 1.0):                # the eels leave a safe way past
                        done = sw.walkthrough(c, light=light, eels=True)
                        self.assertEqual((done.over, done.count("saved")), ("out", c.population))
                    self.assertNotIn(c.start, c.water)
                    self.assertNotIn(c.exit, c.water)
                    self.assertEqual(len(c.gates), len(c.basins))
                    self.assertTrue(c.gates)
                shapes.add(frozenset(c.walls))
        self.assertGreater(len(shapes), 30)
        a, b = sw.generate_chamber(3, 4), sw.generate_chamber(3, 4)
        self.assertEqual((a.walls, a.water, a.eels), (b.walls, b.water, b.eels))

    def test_deeper_chambers_have_more_eels(self):
        counts = [len(sw.generate_chamber(seed, len(sw.CHAMBERS) + 4).eels) for seed in range(1, 6)]
        self.assertGreaterEqual(sum(counts), 5)                     # up to 3 each, where they are fair
        self.assertTrue(all(len(sw.generate_chamber(seed, len(sw.CHAMBERS)).eels) <= 1 for seed in range(1, 6)))


class StillRunClock(unittest.TestCase):
    def test_the_night_runs_down_and_dawn_ends_the_run(self):
        run = sw.StillRun(seed=4)
        self.assertEqual(run.chambers, len(sw.CHAMBERS) + sw.GENERATED)
        self.assertFalse(run.spend(10))
        self.assertEqual(run.night, sw.NIGHT - 10)
        self.assertTrue(run.spend(sw.NIGHT))
        self.assertEqual(run.state, "dawn")

    def test_finishing_a_chamber_counts_who_was_saved_and_moves_on(self):
        run = sw.StillRun(seed=4)
        c = run.chamber
        s = sw.Still(c)
        walk(s, route(c, c.start, c.exit))
        wait_for_kin(s)
        s.step(("x",))
        run.finish(s)
        self.assertEqual((run.index, run.saved, run.total), (1, s.count("saved"), c.population))
        self.assertEqual(run.chamber.name, sw.CHAMBERS[1]["name"])


# ====================================================================== The Tick

def tlevel(rows, guards=(), doors=None, bell=None):
    return tk.TickLevel(dict(name="t", hint="", rows=rows, guards=list(guards), doors=doors or {}, bell=bell))


class Clockwork(unittest.TestCase):
    def test_rounds_loop_and_face_where_they_walk(self):
        g = tk.Guard(tk._expand([(1, 1), (4, 1)]))
        self.assertEqual([g.at(t) for t in range(7)], [(1, 1), (2, 1), (3, 1), (4, 1), (3, 1), (2, 1), (1, 1)])
        self.assertEqual(g.facing(0), (1, 0))
        self.assertEqual(g.facing(3), (-1, 0))

    def test_doors_open_once_or_on_a_cycle(self):
        lv = tlevel(["######", "#S12X#", "######"], doors={"1": ("once", 3, 2), "2": ("every", 10, 2, 7)})
        self.assertEqual([t for t in range(30) if lv.door_open((2, 1), t)], [3, 4])
        self.assertEqual([t for t in range(30) if lv.door_open((3, 1), t)], [3, 4, 13, 14, 23, 24])
        self.assertEqual(lv.door_label((2, 1)), "open once, ticks 3-4")
        s = tk.Tick(lv)
        self.assertIn("opens on tick 3", s.validate(R))
        s.t = 10
        self.assertIn("will not open again", s.validate(R))

    def test_sight_is_a_widening_cone_blocked_by_walls(self):
        lv = tlevel(["##########", "#S.......#", "#........#", "#...#....#", "#.......X#", "##########"],
                    guards=[([(1, 3), (2, 3)], 0)])
        s = tk.Tick(lv)
        seen = s.sight(lv.guards[0], 0)
        self.assertIn((2, 3), seen)
        self.assertIn((3, 2), seen)
        self.assertNotIn((5, 3), seen)
        self.assertNotIn((1, 2), seen)


class TheRegulator(unittest.TestCase):
    CORRIDOR = ["#########", "#S......#", "#######1#", "#X......#", "#########"]

    def test_you_stay_put_while_the_tower_goes_back_and_each_tick_costs_a_minute(self):
        lv = tlevel(self.CORRIDOR, doors={"1": ("once", 2, 2)})
        s = tk.Tick(lv, hoard=10)
        for _ in range(6):
            s.step(R)
        for _ in range(3):
            s.step(("r",))
        self.assertEqual((s.player, s.t, s.hoard, s.spent), ((7, 1), 3, 7, 3))
        s.step(D)
        self.assertEqual(s.player, (7, 2))

    def test_the_watch_has_limits(self):
        lv = tlevel(self.CORRIDOR, doors={"1": ("once", 2, 2)})
        s = tk.Tick(lv, hoard=1)
        self.assertIn("tick 0", s.validate(("r",)))
        s.step(R)
        s.step(("r",))
        s.step(R)
        self.assertIn("hoard is empty", s.validate(("r",)))
        self.assertIn("Regulator", tk.Tick(lv, has_watch=False).validate(("r",)))

    def test_a_watch_lying_on_the_floor_can_be_taken(self):
        lv = tlevel(["#######", "#SW..X#", "#######"])
        s = tk.Tick(lv)
        self.assertFalse(s.has_watch)
        s.step(R)
        self.assertTrue(s.has_watch)
        self.assertIn(("watch",), s.events)

    def test_hour_reels_refill_the_hoard(self):
        lv = tlevel(["#######", "#Sr..X#", "#######"])
        s = tk.Tick(lv, hoard=5)
        s.step(R)
        self.assertEqual(s.hoard, 5 + tk.REEL)
        self.assertFalse(s.reels)


class BeingSeen(unittest.TestCase):
    ROWS = ["##########", "#S.......#", "#.......X#", "##########"]

    def test_the_key_snaps_you_back_for_a_price(self):
        lv = tlevel(self.ROWS, guards=[([(8, 1), (5, 1)], 0)])          # a warden walking toward you
        s = tk.Tick(lv, hoard=20)
        walk_moves = [R, R, R, R]
        for a in walk_moves:
            s.step(a)
            if s.events and s.events[-1][0] == "snapback":
                break
        self.assertEqual(s.events[-1][:1], ("snapback",))
        self.assertEqual(s.hoard, 20 - tk.SNAP_COST)
        self.assertIsNone(s.seen_at(s.player, s.t))
        self.assertIsNone(s.over)

    def test_without_the_minutes_you_are_caught(self):
        lv = tlevel(self.ROWS, guards=[([(8, 1), (5, 1)], 0)])
        s = tk.Tick(lv, hoard=tk.SNAP_COST - 1)
        for a in [R, R, R, R]:
            if s.over:
                break
            s.step(a)
        self.assertEqual(s.over, "caught")

    def test_you_can_be_seen_while_winding_back(self):
        lv = tlevel(["##########", "#S.......#", "#.......X#", "##########"], guards=[([(1, 1), (6, 1)], 0)])
        s = tk.Tick(lv, hoard=0)
        spot = (7, 1)
        self.assertIsNone(s.seen_at(spot, 8))
        self.assertIsNotNone(s.seen_at(spot, 4))
        s.player, s.t, s.hoard = spot, 8, 4          # it faces the way it is about to walk: watched on tick 4
        for _ in range(4):
            if s.over:
                break
            s.step(("r",))
        self.assertEqual(s.over, "caught")

    def test_walking_through_a_warden_is_caught(self):
        lv = tlevel(["#######", "#S...X#", "#######"])
        lv.guards = [tk.Guard([(3, 1), (2, 1), (3, 1), (4, 1)], 0)]
        s = tk.Tick(lv, hoard=0)
        s.step(R)
        self.assertEqual(s.over, "caught")

    def test_the_quarter_bell(self):
        lv = tlevel(["#######", "#S...X#", "#######"], bell=3)
        s = tk.Tick(lv, hoard=0)
        s.step(("w",))
        s.step(("w",))
        s.step(("w",))
        self.assertEqual((s.over, s.caught_by), ("caught", -1))


class TickFloors(unittest.TestCase):
    def test_the_handwritten_floors_solve_and_the_later_ones_need_the_key(self):
        for i, spec in enumerate(tk.FLOORS):
            lv = tk.TickLevel(spec)
            plan = tk.solve(lv, has_watch=i > 0)
            with self.subTest(floor=spec["name"]):
                self.assertIsNotNone(plan)
                s = tk.Tick(lv, hoard=100, has_watch=i > 0)
                for a in plan:
                    s.step(a)
                self.assertEqual(s.over, "out")
                self.assertEqual(s.spent, tk.solve_cost(lv, has_watch=i > 0))
                if i > 0:
                    self.assertIsNone(tk.solve(lv, has_watch=False))

    def test_generated_floors_need_the_key_cost_a_fair_price_and_differ_by_seed(self):
        shapes = set()
        for seed in range(1, 6):
            for index in range(len(tk.FLOORS), len(tk.FLOORS) + tk.GENERATED):
                lv = tk.generate_floor(seed, index)
                with self.subTest(seed=seed, index=index):
                    self.assertIsNone(tk.solve_cost(lv, has_watch=False))
                    self.assertTrue(4 <= lv.min_cost <= 14)
                    self.assertGreater(lv.bell, len(tk.solve(lv)))
                shapes.add(frozenset(lv.walls))
        self.assertGreater(len(shapes), 15)

    def test_the_run_settles_the_hoard_and_runs_out(self):
        run = tk.TickRun(seed=3)
        self.assertEqual((run.floors, run.hoard, run.level.name), (len(tk.FLOORS) + tk.GENERATED, tk.HOARD,
                                                                   tk.FLOORS[0]["name"]))
        s = run.begin()
        for a in tk.solve(run.level, has_watch=False):
            s.step(a)
        self.assertTrue(run.settle(s))
        self.assertEqual((run.index, run.has_watch), (1, True))
        self.assertEqual(run.level.name, tk.FLOORS[1]["name"])     # (built in the background)
        s = run.begin()
        s.hoard = run.level.min_cost - 1
        s.over = "caught"
        self.assertFalse(run.settle(s))
        self.assertEqual(run.state, "spent")


# ====================================================================== screens

class SisterScreens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def app(self, game, seen=False):
        from echo.app import App
        a = App(meta_path=os.path.join(self.tmp.name, "m.json"), game=game)
        a.meta.data["seen_intro_" + game] = seen
        return a

    def key(self, app, k):
        app.handle(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))

    def test_the_story_plays_the_first_time_only(self):
        from echo.cinematics import IntroScreen
        from echo.sisters.still_screen import StillScreen
        from echo.sisters.tick_screen import TickScreen
        for game, cls in (("stillwater", StillScreen), ("tick", TickScreen)):
            app = self.app(game)
            self.key(app, pygame.K_n)
            self.assertIsInstance(app.screen, IntroScreen, game)
            for i in range(len(app.screen.panels)):
                app.screen.i, app.screen.t = i, 3.0
                app.draw()
            self.key(app, pygame.K_ESCAPE)
            self.assertIsInstance(app.screen, cls)
            self.assertTrue(app.meta.data["seen_intro_" + game])
            app.to_title()
            self.key(app, pygame.K_n)
            self.assertIsInstance(app.screen, cls)

    def test_stillwater_card_play_climb_out_and_retry(self):
        from echo.sisters.common import Card, ProtoTitle, RulesCard
        app = self.app("stillwater", seen=True)
        self.assertEqual(pygame.display.get_caption()[0], "Stillwater (prototype)")
        self.key(app, pygame.K_n)
        scr = app.screen
        self.assertTrue(scr.intro)
        app.draw()
        self.key(app, pygame.K_SPACE)
        self.assertFalse(scr.intro)
        self.assertEqual(scr.sim.turn, 0)              # dismissing the card is not a turn
        self.key(app, pygame.K_h)
        self.assertIsInstance(app.screen, RulesCard)
        app.draw()
        self.key(app, pygame.K_ESCAPE)
        c = scr.level
        keys = {(0, -1): pygame.K_UP, (1, 0): pygame.K_RIGHT, (0, 1): pygame.K_DOWN, (-1, 0): pygame.K_LEFT}
        for p in route(c, c.start, c.exit):
            self.key(app, keys[(p[0] - scr.sim.player[0], p[1] - scr.sim.player[1])])
            app.tick(0.05)
        app.draw()
        self.assertIn("The way on", scr.msg)
        for _ in range(6):
            self.key(app, pygame.K_SPACE)
        self.key(app, pygame.K_RETURN)
        if scr.sim.over != "out":                      # someone still down there: confirm
            self.assertIn("without them", scr.msg)
            self.key(app, pygame.K_RETURN)
        self.assertIsInstance(app.screen, Card)
        app.draw()
        self.key(app, pygame.K_RETURN)
        scr2 = app.screen
        self.assertEqual(scr2.run.index, 1)
        self.key(app, pygame.K_SPACE)
        self.key(app, pygame.K_RIGHT)
        self.key(app, pygame.K_r)
        self.assertEqual((app.screen.sim.turn, app.screen.run.index), (0, 1))
        self.key(app, pygame.K_ESCAPE)                 # the card
        self.assertIsInstance(app.screen, ProtoTitle)

    def test_stillwater_step_back_after_an_eel(self):
        from echo.sisters.still_screen import BACK_STEPS, StillScreen
        app = self.app("stillwater", seen=True)
        c = chamber(["##########", "#S~~~~~~e#", "#........#", "#.......E#", "##########"])
        run = sw.StillRun(seed=1)
        app.replace(StillScreen(app, run, c))
        scr = app.screen
        self.key(app, pygame.K_SPACE)                              # the card
        self.key(app, pygame.K_b)
        self.assertIn("Nothing to step back", scr.msg)
        for _ in range(8):                                         # wade straight at the eel
            if scr.sim.over:
                break
            self.key(app, pygame.K_RIGHT)
        self.assertEqual(scr.sim.over, "caught")
        self.assertIn("B: the Still pull you back", scr.msg)
        turn, night = scr.sim.turn, run.night
        self.key(app, pygame.K_b)
        self.assertIsNone(scr.sim.over)
        self.assertEqual(scr.sim.turn, turn - BACK_STEPS)
        self.assertEqual(run.night, night)                         # the night does not give them back
        self.assertIn("pull you back", scr.msg)
        self.key(app, pygame.K_DOWN)                               # and on, by the dry ledge
        self.assertEqual(scr.sim.player[1], 2)

    def test_the_tick_preview_wind_and_the_choice_at_the_top(self):
        from echo.sisters.common import Card, ChoiceCard, ProtoTitle
        from echo.sisters.tick_screen import TickScreen
        app = self.app("tick", seen=True)
        self.assertEqual(pygame.display.get_caption()[0], "The Tick (prototype)")
        run = tk.TickRun(seed=2)
        run.index, run.has_watch = 1, True
        run._level = run._build(1)
        app.replace(TickScreen(app, run))
        scr = app.screen
        self.key(app, pygame.K_SPACE)
        for _ in range(27):
            self.key(app, pygame.K_RIGHT)
        self.key(app, pygame.K_DOWN)
        self.assertIn("will not open again", scr.msg)
        for _ in range(12):
            self.key(app, pygame.K_LEFTBRACKET)
        self.assertEqual(scr.preview, 15)
        self.assertIn("Enter winds there for 12 minutes", scr.msg)
        app.draw()
        self.key(app, pygame.K_RETURN)
        self.assertEqual((scr.sim.t, scr.sim.hoard), (15, tk.HOARD - 12))
        self.key(app, pygame.K_DOWN)
        self.assertEqual(scr.sim.player, (28, 2))
        for _ in range(5):
            app.tick(0.1)                              # holding Q only repeats while the key is really down
        self.assertEqual(scr.sim.t, 16)
        self.key(app, pygame.K_DOWN)
        for _ in range(27):
            self.key(app, pygame.K_LEFT)
        self.assertIsInstance(app.screen, Card)         # floor climbed
        app.draw()
        self.key(app, pygame.K_RETURN)
        from echo.cinematics import IntroScreen
        self.assertIsInstance(app.screen, IntroScreen)  # Maren's interlude, the first time round
        self.assertEqual(app.screen.title, "Maren")
        app.draw()
        self.key(app, pygame.K_ESCAPE)
        scr = app.screen
        self.assertEqual((scr.run.index, scr.level.name), (2, tk.FLOORS[2]["name"]))
        self.assertIn("tick:2", app.meta.data["seen_scenes"])
        scr.run.index = scr.run.floors - 1              # pretend this is the top of the tower
        scr.sim.over = "out"
        scr._floor_done()
        self.assertIsInstance(app.screen, ChoiceCard)
        app.draw()
        self.key(app, pygame.K_1)
        self.assertIsInstance(app.screen, Card)
        self.assertIn("down the thread", app.screen.body)
        self.key(app, pygame.K_RETURN)
        self.assertIsInstance(app.screen, ProtoTitle)

    def test_the_tick_floor_one_caught_and_retry(self):
        from echo.sisters.tick_screen import TickScreen
        app = self.app("tick", seen=True)
        self.key(app, pygame.K_n)
        scr = app.screen
        self.assertIsInstance(scr, TickScreen)
        self.key(app, pygame.K_SPACE)
        self.assertTrue(scr.sim.has_watch)               # stolen before the first floor (the prologue)
        scr.sim.player = (9, 4)                          # stand in the warden's way
        while not scr.sim.over:
            scr.act(("w",))
        self.assertIn("lantern", scr.msg)
        app.draw()
        self.key(app, pygame.K_RETURN)
        self.assertEqual(app.screen.sim.t, 0)


if __name__ == "__main__":
    unittest.main()
