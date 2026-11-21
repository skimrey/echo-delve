"""Par, grades and floor scores, plus the decorative torch placement and the story text."""

import unittest

from helpers import D, L, R, U, cached_floor, make_floor

from echo import story
from echo.bot import play_floor
from echo.consts import MAX_FLOOR
from echo.floor import generate_floor, place_torches
from echo.run import FloorPlay, Meta, Run
from echo.score import GRADES, SCORE_MAX, floor_score, grade_for, par_plan, par_routes, par_turns
from echo.sim import ANCHOR, WAIT, Mods

PLATE = ["S.....a#", "######.#", "######1#", "######E#"]


def rig(run, rows, **kw):
    f = make_floor(rows, **kw)
    run.floor = f
    run.play = FloorPlay(f, run.mods(), run.slots)
    return f


class Par(unittest.TestCase):
    def test_no_doors_is_just_the_walk(self):
        self.assertEqual(par_plan(make_floor(["S...E"])), [4])

    def test_one_door_plate_walk_plus_final_walk(self):
        # loop 1: 6 steps to the plate; loop 2: 9 steps to the stairs (the echo is there in time)
        self.assertEqual(par_plan(make_floor(PLATE)), [6, 9])
        self.assertEqual(par_turns(make_floor(PLATE)), 15)

    def test_the_final_loop_waits_for_a_slow_echo(self):
        # the plate is 9 steps away but the door only 2: the last loop must wait at the door
        rows = ["S.1E", "#.##", "#.##", "#.##", "#.##", "#.##", "#.##", "#.##", "#a##"]
        plan = par_plan(make_floor(rows))
        self.assertEqual(plan[0], 9)
        self.assertEqual(plan[1], 9 + 1 + 1)     # wait until move 9, step into the door, then onto the stairs

    def test_a_plate_behind_an_earlier_door_waits_for_that_echo(self):
        rows = ["Sa1..b2E"]
        # loop 1: plate a in 1; loop 2: through door 1 (open from move 1) to plate b: 5;
        # final: door 2 opens on move 5, so 7 moves total
        self.assertEqual(par_plan(make_floor(rows)), [1, 5, 7])

    def test_unreachable_is_none(self):
        f = make_floor(["S#E"])
        self.assertIsNone(par_plan(f))
        self.assertIsNone(par_turns(f))
        self.assertEqual(floor_score(10, None), 0)

    def test_the_intended_solution_played_perfectly_scores_exactly_par(self):
        r = Run(seed=1)
        rig(r, PLATE, limit=50)
        for a in [R] * 6 + [ANCHOR] + [R] * 6 + [D, D, D]:
            r.act(a)
        res = r.last_result
        self.assertEqual((res.spent, res.par, res.score, res.grade), (15, 15, SCORE_MAX, "S+"))

    def test_par_is_achievable_in_the_real_simulation(self):
        # replay the par plan keystroke by keystroke on enemy-free copies of generated floors:
        # it must clear the floor in exactly par turns (so the timing model matches the sim)
        import copy
        for s in (1, 2, 3, 4):
            for i in range(1, MAX_FLOOR + 1):
                f = copy.copy(cached_floor(s, i))
                f.spawns = []
                routes = par_routes(f)
                fp = FloorPlay(f, Mods(max_hp=99), len(f.lock_order))
                for k, actions in enumerate(routes):
                    for a in actions:
                        self.assertIsNone(fp.sim.validate(a), (s, i, k))
                        fp.act(a)
                    if k < len(routes) - 1:
                        fp.act(ANCHOR)
                with self.subTest(seed=s, floor=i):
                    self.assertEqual(fp.status, "cleared")
                    self.assertEqual(fp.turns_spent, par_turns(f))

    def test_the_bot_never_beats_par_on_generated_floors(self):
        # the bot plays the intended solution (plus fights), so par is a lower bound for it
        for s in (1, 2, 3):
            for i in range(1, MAX_FLOOR + 1):
                f = cached_floor(s, i)
                fp = play_floor(f)
                with self.subTest(seed=s, floor=i):
                    self.assertEqual(fp.status, "cleared")
                    self.assertGreaterEqual(fp.turns_spent, par_turns(f))


class TurnsSpent(unittest.TestCase):
    def test_every_turn_in_every_loop_counts_but_bumps_and_anchors_do_not(self):
        r = Run(seed=1)
        rig(r, PLATE, limit=50)
        r.act(U)                                  # a bump: refused, free
        for a in [R, R, WAIT, ANCHOR]:
            r.act(a)
        self.assertEqual(r.play.turns_spent, 3)
        r.act(R)
        r.unravel(1)                              # the unravelled loop's turns stay spent
        self.assertEqual(r.play.turns_spent, 4)
        r.act(L)                                  # walking into a wall is refused
        self.assertEqual(r.play.turns_spent, 4)

    def test_timeouts_count_every_turn(self):
        r = Run(seed=1)
        rig(r, PLATE, limit=5)
        for _ in range(5):
            r.act(WAIT)
        self.assertEqual((r.play.loop_no, r.play.turns_spent), (2, 5))


class Grades(unittest.TestCase):
    def test_grade_bands(self):
        self.assertEqual(grade_for(100, 100), "S+")
        self.assertEqual(grade_for(90, 100), "S+")         # under par
        self.assertEqual(grade_for(110, 100), "S")
        self.assertEqual(grade_for(140, 100), "A")
        self.assertEqual(grade_for(180, 100), "B")
        self.assertEqual(grade_for(240, 100), "C")
        self.assertEqual(grade_for(400, 100), "D")
        self.assertEqual([g for _, g in GRADES], ["S+", "S", "A", "B", "C", "D"])

    def test_scores_scale_with_efficiency_and_reward_beating_par(self):
        self.assertEqual(floor_score(100, 100), 1000)
        self.assertEqual(floor_score(200, 100), 500)
        self.assertEqual(floor_score(98, 100), 1100)
        self.assertLess(floor_score(101, 100), 1000)

    def test_results_accumulate_and_great_grades_pay_shards(self):
        r = Run(seed=1)
        rig(r, ["S..E"])
        for _ in range(3):
            r.act(R)
        self.assertEqual(r.state, "upgrade")
        self.assertEqual((r.last_result.grade, r.last_result.bonus), ("S+", 2))
        self.assertEqual(r.total_score, 1000)
        self.assertEqual(r.shards_earned(), 1 + 2)
        r.apply_upgrade(r.options[0])
        rig(r, ["S..E"])
        for a in [WAIT] * 4 + [R] * 3:            # 7 turns against par 3: grade C, no bonus
            r.act(a)
        self.assertEqual((r.last_result.grade, r.last_result.bonus), ("C", 0))
        self.assertEqual(r.total_score, 1000 + round(1000 * 3 / 7))
        self.assertEqual(len(r.scores), 2)

    def test_best_score_is_remembered(self):
        m = Meta(None)
        r = Run(seed=1)
        rig(r, ["S..E"])
        for _ in range(3):
            r.act(R)
        r.state = "dead"
        m.record(r)
        self.assertEqual(m.data["best_score"], 1000)
        m.record(Run(seed=2))
        self.assertEqual(m.data["best_score"], 1000)


class Torches(unittest.TestCase):
    def test_sconces_hang_on_wall_faces_above_open_floor(self):
        for s in (1, 2, 3):
            for i in range(1, MAX_FLOOR + 1):
                f = cached_floor(s, i)
                torches = place_torches(f)
                self.assertGreater(len(torches), 2)
                for x, y in torches:
                    self.assertTrue(f.walls[y][x], (s, i, x, y))
                    self.assertFalse(f.walls[y + 1][x])
                self.assertEqual(torches, place_torches(f))

    def test_torches_do_not_change_the_dungeon(self):
        a = generate_floor(4, 3)
        place_torches(a)
        b = generate_floor(4, 3)
        self.assertEqual((a.walls, a.spawns, a.plates), (b.walls, b.spawns, b.plates))


class Story(unittest.TestCase):
    def test_every_floor_has_a_name_and_lines(self):
        for n in range(1, MAX_FLOOR + 1):
            self.assertTrue(story.floor_name(n) and story.floor_arrival(n) and story.floor_cleared(n))
        self.assertEqual(len(story.FLOORS), MAX_FLOOR)
        self.assertGreaterEqual(len(story.INTRO), 3)
        self.assertTrue(all(k in story.ENEMY_LORE for k in ("crawler", "archer", "brute", "warden")))


if __name__ == "__main__":
    unittest.main()


class LeverPar(unittest.TestCase):
    def test_a_lever_loop_walks_beside_the_lever_and_pulls(self):
        f = make_floor(["S..g.E", "...L.."])
        routes = par_routes(f)
        # the lever at (3,1) can only be pulled from (2,1) or (4,1): 3 moves then the pull (4 actions).
        # The last loop reaches the gate after 2 moves, waits until action 4, then 3 more moves: 7
        self.assertEqual(par_plan(f), [4, 7])
        self.assertEqual(routes[0][-1], R)

    def test_the_final_loop_waits_at_the_gate_for_a_far_lever(self):
        rows = ["S.gE", ".###", ".###", ".###", ".###", "L###"]
        # lever loop: 4 moves down beside the lever (0,5)? (0,4) then pull down: 5 actions
        self.assertEqual(par_plan(make_floor(rows)), [5, 5 + 1 + 1])

    def test_lever_par_replays_exactly_in_the_sim(self):
        f = make_floor(["S..g.E", "...L.."])
        fp = FloorPlay(f, Mods(), 3)
        routes = par_routes(f)
        for a in routes[0] + [ANCHOR] + routes[1]:
            fp.act(a)
        self.assertEqual((fp.status, fp.turns_spent), ("cleared", par_turns(f)))


class StoryCanon(unittest.TestCase):
    def test_the_intro_answers_the_big_questions(self):
        text = " ".join(t for _, t in story.INTRO)
        self.assertIn("Do not be afraid of them", text)            # the figures beside you...
        self.assertIn("your own footsteps", text)                  # ...are your echoes
        self.assertIn("went down before you", text)                # who the Wardens are
        self.assertIn("first landing", text)                       # how the thread reaches its next holder
        self.assertIn("mother to daughter", text)                  # the lantern was never his...
        self.assertIn("Maren put it into your hands", text)        # ...his sister ran (The Tick)
        self.assertEqual(story.HERO, "Aurel Vell")

    def test_the_ending_and_floor_lines_point_at_the_sister_stories(self):
        lines = " ".join(a + b for _, a, b in story.FLOORS) + " ".join(story.ENDING_WON)
        self.assertIn("keeper's window", lines)                    # the Still, seen through it (Stillwater)
        self.assertIn("slid down the Spindle", lines)              # ...and met at the Loom
        self.assertIn("Tick", lines)                               # Maren (The Tick)
        self.assertIn("%d", story.REWIND_LINE)


class Prefetch(unittest.TestCase):
    def test_the_background_floor_is_the_same_floor(self):
        r = Run(seed=21)
        r.prefetch_next_floor()
        ahead = r._take_floor(2)
        direct = generate_floor(21, 2)
        self.assertEqual((ahead.walls, ahead.lock_order, ahead.spawns), (direct.walls, direct.lock_order, direct.spawns))

    def test_clearing_a_floor_starts_the_prefetch_and_the_upgrade_uses_it(self):
        r = Run(seed=21)
        rig(r, ["SE"])
        r.act(R)
        self.assertEqual(r._prefetch[0], 2)
        r.apply_upgrade(r.options[0])
        self.assertIsNone(r._prefetch)
        self.assertEqual((r.floor.index, r.floor.walls), (2, generate_floor(21, 2).walls))


class LeverEchoes(unittest.TestCase):
    def test_an_echo_remembers_when_it_pulled(self):
        r = Run(seed=1)
        rig(r, ["S..g.E", "...L.."])
        for a in (D, R, R, R, ANCHOR):
            r.act(a)
        self.assertEqual(r.play.scripts[0].pulls, ((3, 0),))
        for a in (R, R, WAIT, WAIT, R, R, R):                  # in step behind the echo's pull
            r.act(a)
        self.assertEqual(r.state, "upgrade")


class LampPar(unittest.TestCase):
    """Par follows the sconces you light: the fastest clear, rising by what each further sconce
    costs, up to the clear that lights every one of them."""

    def play_plan(self, s, i):
        import copy
        from echo.consts import LAMP_REACH
        from echo.score import LampPlan, lamp_info
        f = copy.copy(cached_floor(s, i))
        f.spawns = []                                     # (par is a clean-room target: enemies aside)
        plan = LampPlan(f, place_torches(f), LAMP_REACH)
        r = Run(seed=s, floors=[i], prebuilt={i: f}, perks={"hp": 90})
        for k, actions in enumerate(plan.routes):
            for a in actions:
                self.assertEqual(r.act(a).message, "", (s, i, k))
            if k < len(plan.routes) - 1:
                r.act(ANCHOR)
        return r, plan, lamp_info(f)

    def test_every_sconce_at_par_is_achievable_and_scores_best(self):
        for s, i in ((1, 1), (1, 7), (2, 3), (3, 3), (3, 7), (2, 10)):
            with self.subTest(seed=s, floor=i):
                r, plan, info = self.play_plan(s, i)
                res = r.last_result
                self.assertEqual(r.state, "won")
                self.assertEqual(len(info.sconces), len(place_torches(cached_floor(s, i))))   # all reachable
                self.assertEqual((res.lamps, res.lamps_total), (len(info.sconces), len(info.sconces)))
                self.assertEqual(res.spent, info.par_all)
                self.assertEqual((res.par, res.grade), (info.par_all, "S+"))
                self.assertGreater(res.par, res.par_fast)                      # lighting them takes turns...
                self.assertGreaterEqual(res.score, SCORE_MAX + 200)            # ...but it is the best score

    def test_par_rises_with_each_sconce_from_the_fastest_clear(self):
        from echo.score import lamp_info
        for s, i in ((1, 3), (2, 5), (3, 10)):
            f = cached_floor(s, i)
            info = lamp_info(f)
            pars = [info.par_for(n) for n in range(len(info.sconces) + 1)]
            self.assertEqual(pars[0], par_turns(f))
            self.assertEqual(pars[info.fast_lamps], par_turns(f))            # what the fastest clear passes anyway
            self.assertEqual(pars, sorted(pars))
            self.assertEqual(pars[-1], info.par_all)
            self.assertLess(info.par_all, 2 * par_turns(f))
