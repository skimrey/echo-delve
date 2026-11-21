import json
import os
import tempfile
import unittest

from helpers import D, L, R, make_floor

from echo.bot import bot_action, lock_goal
from echo.consts import (BASE_ATK, BASE_HP, BASE_SLOTS, BASE_THREADS, MAX_FLOOR, PERKS, SLOT_CAP,
                         THREADS_PER_FLOOR, UPGRADES)
from echo.run import FloorPlay, Meta, Run
from echo.sim import ANCHOR, WAIT, move


def rig(run, rows, **kw):
    """Swap the run's current floor for a hand-drawn one."""
    f = make_floor(rows, **kw)
    run.floor = f
    run.play = FloorPlay(f, run.mods(), run.slots)
    run.seen = set()
    return f


def bot_run(run, pick="hp", max_steps=9000):
    done, steps = set(), 0
    while run.state in ("playing", "upgrade") and steps < max_steps:
        if run.state == "upgrade":
            run.apply_upgrade(pick if pick in run.options else run.options[0])
            done = set()
            continue
        f = run.floor
        idx = next((k for k in range(len(f.lock_order)) if k not in done), None)
        goal, kind = lock_goal(f, done)
        lb, fl = run.play.loop_no, run.floor_no
        st = {}
        while run.state == "playing" and run.play.loop_no == lb and run.floor_no == fl and steps < max_steps:
            run.act(bot_action(run.sim, goal, kind, st))
            steps += 1
        if run.floor_no == fl and kind == "plate" and run.play.last_end in ("anchor", "timeout") \
                and run.play.last_end_pos == goal:
            done.add(idx)
        elif run.floor_no == fl and kind == "lever" and st.get("pulled") and run.play.last_end == "anchor":
            done.add(idx)
    return run


class RunBasics(unittest.TestCase):
    def test_new_run_defaults(self):
        r = Run(seed=1)
        self.assertEqual((r.state, r.floor_no, r.cleared), ("playing", 1, 0))
        self.assertEqual((r.max_hp, r.atk, r.slots), (BASE_HP, BASE_ATK, BASE_SLOTS))
        self.assertEqual(r.play.slots, BASE_SLOTS)
        self.assertEqual(r.threads, BASE_THREADS)
        self.assertTrue(r.floor.verified)

    def test_same_seed_same_dungeon(self):
        a, b = Run(seed=5), Run(seed=5)
        self.assertEqual(a.floor.walls, b.floor.walls)

    def test_perks_apply(self):
        r = Run(seed=1, perks={"hp": 3, "slots": 2, "time": 2, "atk": 1})
        self.assertEqual((r.max_hp, r.atk, r.slots, r.limit_bonus), (BASE_HP + 3, BASE_ATK + 1, BASE_SLOTS + 2, 16))
        self.assertEqual(r.sim.limit, r.floor.limit + 16)
        self.assertEqual(r.sim.player.hp, BASE_HP + 3)

    def test_a_bump_is_refused_and_costs_nothing(self):
        r = Run(seed=1)
        rig(r, ["S#", "##"])
        res = r.act(R)
        self.assertIn("wall", res.message.lower())
        self.assertEqual((r.sim.turn, r.sim.record, res.events, res.ended), (0, [], [], None))

    def test_acting_after_the_run_ended_explains(self):
        r = Run(seed=1)
        r.state = "dead"
        self.assertTrue(r.act(WAIT).message)


class Loops(unittest.TestCase):
    ROWS = ["S.....a#", "######.#", "######1#", "######E#"]

    def setUp(self):
        self.r = Run(seed=1)
        rig(self.r, self.ROWS, limit=50)

    def test_anchor_starts_the_next_loop_with_an_echo(self):
        r = self.r
        for a in (R, R):
            r.act(a)
        res = r.act(ANCHOR)
        self.assertEqual(res.ended, "anchor")
        self.assertEqual(r.play.loop_no, 2)
        self.assertEqual(len(r.play.scripts), 1)
        self.assertEqual(r.sim.turn, 0)
        self.assertEqual(r.sim.player.pos, r.floor.start)
        self.assertEqual(len(r.sim.ghosts), 1)
        self.assertEqual(r.state, "playing")

    def test_timeout_auto_anchors(self):
        r = self.r
        r.sim.limit = 2
        r.act(R)
        res = r.act(R)
        self.assertEqual(res.ended, "timeout")
        self.assertEqual(r.play.scripts[0].ending, "anchor")
        self.assertEqual(r.play.loop_no, 2)
        # the echo ends exactly where you stood
        for _ in range(3):
            r.act(WAIT)
        self.assertEqual(r.sim.ghosts[0].pos, (2, 0))

    def test_dying_leaves_an_echo_that_fades(self):
        r = Run(seed=1)
        rig(r, ["SC..", "...."])
        r.sim.player.hp = 1
        r.sim.enemies[0].awake = True
        res = r.act(WAIT)
        self.assertEqual(res.ended, "dead")
        self.assertEqual(r.play.scripts[0].ending, "dead")
        self.assertEqual(r.state, "playing")
        self.assertEqual(r.play.loop_no, 2)

    def test_a_full_well_asks_for_an_unravel_instead_of_ending_the_run(self):
        r = self.r
        for i in range(BASE_SLOTS + 1):
            self.assertEqual(r.state, "playing")
            r.act(ANCHOR)
        self.assertEqual(r.state, "unravel")
        self.assertEqual(r.play.status, "full")
        self.assertEqual(len(r.play.scripts), BASE_SLOTS + 1)
        self.assertEqual(r.play.last_label, BASE_SLOTS + 1)
        self.assertIn("unravel", r.act(WAIT).message.lower())

    def test_running_out_of_loops_with_no_threads_ends_the_run(self):
        r = self.r
        r.threads = 0
        for i in range(BASE_SLOTS + 1):
            self.assertEqual(r.state, "playing")
            r.act(ANCHOR)
        self.assertEqual(r.state, "dead")
        self.assertIn("no threads left", r.reason)
        self.assertEqual(r.play.status, "full")

    def test_dying_on_the_last_loop_has_its_own_reason(self):
        r = Run(seed=1)
        rig(r, ["SC..", "...."])
        r.threads = 0
        for _ in range(BASE_SLOTS):
            r.act(ANCHOR)
        self.assertTrue(r.play.last_loop)
        r.sim.player.hp = 1
        r.sim.enemies[0].awake = True
        r.act(WAIT)
        self.assertEqual(r.state, "dead")
        self.assertIn("fell", r.reason)

    def test_the_full_two_loop_solution(self):
        r = self.r
        for a in [R] * 6 + [ANCHOR]:                 # loop 1: stand on the plate, anchor
            r.act(a)
        # loop 2: walk in step with the echo; it is on the plate when you reach the door
        for a in [R] * 6 + [D, D, D]:
            res = r.act(a)
            self.assertEqual(res.message, "")
        self.assertEqual(r.state, "upgrade")
        self.assertEqual(r.cleared, 1)

    def test_door_stays_sealed_without_the_echo(self):
        r = self.r
        for a in [R] * 3 + [ANCHOR]:                 # the echo stands in the wrong place
            r.act(a)
        for a in [R] * 6 + [D]:
            r.act(a)
        res = r.act(D)
        self.assertIn("Door 1", res.message)
        self.assertEqual(r.sim.player.pos, (6, 1))
        self.assertEqual(r.state, "playing")


class Upgrades(unittest.TestCase):
    def cleared_run(self):
        r = Run(seed=1)
        rig(r, ["SE"])
        r.act(R)
        self.assertEqual(r.state, "upgrade")
        return r

    def test_three_distinct_valid_options(self):
        for seed in range(1, 15):
            r = Run(seed=seed)
            rig(r, ["SE"])
            r.act(R)
            self.assertEqual(len(r.options), 3)
            self.assertEqual(len(set(r.options)), 3)
            for k in r.options:
                self.assertIn(k, UPGRADES)

    def test_every_upgrade_does_its_job_and_advances_the_floor(self):
        for key in UPGRADES:
            r = self.cleared_run()
            r.options = [key, "hp", "atk"] if key not in ("hp", "atk") else [key, "sight", "time"]
            before = (r.max_hp, r.atk, r.slots, r.limit_bonus, r.sight, r.ghost_hp)
            r.apply_upgrade(key)
            after = (r.max_hp, r.atk, r.slots, r.limit_bonus, r.sight, r.ghost_hp)
            self.assertNotEqual(before, after, key)
            self.assertEqual((r.floor_no, r.state), (2, "playing"))
            self.assertEqual(r.floor.index, 2)
            self.assertEqual(r.sim.player.max_hp, r.max_hp)
            self.assertEqual(r.play.slots, r.slots)

    def test_specific_effects(self):
        for key, field, delta in (("hp", "max_hp", 2), ("atk", "atk", 1), ("slot", "slots", 1),
                                  ("time", "limit_bonus", 12), ("sight", "sight", 2), ("guard", "ghost_hp", 2)):
            r = self.cleared_run()
            r.options = [key, "hp" if key != "hp" else "atk", "sight" if key != "sight" else "time"]
            old = getattr(r, field)
            r.apply_upgrade(key)
            self.assertEqual(getattr(r, field), old + delta, key)

    def test_unoffered_or_out_of_phase_upgrades_are_rejected(self):
        r = self.cleared_run()
        bad = [k for k in UPGRADES if k not in r.options][0]
        with self.assertRaises(ValueError):
            r.apply_upgrade(bad)
        with self.assertRaises(ValueError):
            Run(seed=1).apply_upgrade("hp")

    def test_slot_upgrade_not_offered_at_the_cap(self):
        for seed in range(1, 30):
            r = Run(seed=seed, perks={"slots": 2})
            r.slots = SLOT_CAP
            rig(r, ["SE"])
            r.act(R)
            self.assertNotIn("slot", r.options)

    def test_winning_the_last_floor(self):
        r = Run(seed=1)
        r.floor_no = MAX_FLOOR
        r.cleared = MAX_FLOOR - 1
        rig(r, ["SE"])
        r.act(R)
        self.assertEqual(r.state, "won")
        self.assertEqual(r.cleared, MAX_FLOOR)
        self.assertEqual(r.last_result.grade, "S+")          # a par clear also earns bonus shards
        self.assertEqual(r.shards_earned(), MAX_FLOOR + 3 + 2)


class Unravel(unittest.TestCase):
    ROWS = Loops.ROWS

    def setUp(self):
        self.r = Run(seed=1)
        rig(self.r, self.ROWS, limit=50)

    def fill(self, plans):
        for plan in plans:
            for a in plan + [ANCHOR]:
                self.r.act(a)

    def test_recorded_echoes_remember_their_loop_and_end(self):
        self.fill([[R, R], [R]])
        a, b = self.r.play.scripts
        self.assertEqual((a.label, a.loop, a.end_pos), (1, 1, (2, 0)))
        self.assertEqual((b.label, b.loop, b.end_pos), (2, 2, (1, 0)))

    def test_unravel_frees_the_slot_and_the_next_loop_rewrites_it(self):
        r = self.r
        self.fill([[R], [R, R], [R, R, R]])
        r.act(R)
        r.unravel(2)
        self.assertEqual(r.threads, BASE_THREADS - 1)
        self.assertEqual([s.label for s in r.play.scripts], [1, 3])
        self.assertEqual((r.sim.turn, r.sim.record, r.sim.player.pos), (0, [], r.floor.start))
        self.assertEqual(sorted(g.key for g in r.sim.ghosts), ["G1", "G3"])
        self.assertEqual(r.play.loop_no, 5)                  # the interrupted loop still counts
        self.assertEqual(r.play.free_label(), 2)
        r.act(R)
        r.act(ANCHOR)
        self.assertEqual([s.label for s in r.play.scripts], [1, 2, 3])
        self.assertEqual(r.play.script(2).actions, [R])
        self.assertEqual(r.play.script(2).loop, 5)
        self.assertEqual([g.key for g in r.sim.ghosts], ["G1", "G2", "G3"])

    def test_a_full_well_can_discard_the_loop_just_played(self):
        r = self.r
        self.fill([[R]] * BASE_SLOTS + [[R, R]])
        self.assertEqual(r.state, "unravel")
        kept = [list(s.actions) for s in r.play.scripts[:-1]]
        r.unravel(r.play.last_label)
        self.assertEqual(r.state, "playing")
        self.assertEqual(r.play.status, "playing")
        self.assertEqual([s.actions for s in r.play.scripts], kept)
        self.assertTrue(r.play.last_loop)

    def test_a_ruined_floor_is_recoverable(self):
        # every slot holds a useless echo; unravel one and record the plate-holder in its place
        r = self.r
        self.fill([[R, R]] * (BASE_SLOTS + 1))
        self.assertEqual(r.state, "unravel")
        r.unravel(3)
        for a in [R] * 6 + [ANCHOR]:
            r.act(a)
        self.assertEqual(r.state, "unravel")                # that loop ended short of the stairs too
        r.unravel(1)
        for a in [R] * 6 + [D, D, D]:
            res = r.act(a)
            self.assertEqual(res.message, "")
        self.assertEqual(r.state, "upgrade")
        self.assertEqual(r.threads, BASE_THREADS - 2 + THREADS_PER_FLOOR)

    def test_running_out_of_threads_after_unravelling_ends_the_run(self):
        r = self.r
        r.threads = 1
        self.fill([[R]] * (BASE_SLOTS + 1))
        r.unravel(1)
        r.act(ANCHOR)
        self.assertEqual((r.state, r.threads), ("dead", 0))
        self.assertIn("no threads left", r.reason)

    def test_what_cannot_be_unravelled(self):
        r = self.r
        self.assertIn("No echoes", r.unravel_problem())
        with self.assertRaises(ValueError):
            r.unravel(1)
        self.fill([[R]])
        with self.assertRaises(ValueError):
            r.unravel(7)                                    # no such echo: nothing is spent
        self.assertEqual((r.threads, len(r.play.scripts)), (BASE_THREADS, 1))
        r.threads = 0
        self.assertIn("No threads", r.unravel_problem())
        with self.assertRaises(ValueError):
            r.unravel(1)
        r.threads = 1
        r.state = "upgrade"
        self.assertTrue(r.unravel_problem())
        with self.assertRaises(ValueError):
            r.unravel(1)

    def test_a_cleared_floor_cannot_be_unravelled(self):
        fp = FloorPlay(make_floor(["SE"]), Run(seed=1).mods(), 2)
        fp.act(R)
        self.assertEqual(fp.status, "cleared")
        with self.assertRaises(ValueError):
            fp.unravel(1)

    def test_threads_are_earned_per_floor_and_carry_over(self):
        r = Run(seed=1)
        r.threads = 1
        rig(r, ["SE"])
        r.act(R)
        self.assertEqual(r.threads, 1 + THREADS_PER_FLOOR)
        r.apply_upgrade(r.options[0])
        self.assertEqual(r.threads, 1 + THREADS_PER_FLOOR)

    def test_unravelling_changes_what_later_echoes_meet(self):
        # echo 1 kills the crawler; once it is unravelled the crawler survives to meet echo 2
        r = Run(seed=1)
        rig(r, ["S.C....", "......."], limit=30)
        r.sim.enemies[0].awake = True
        for a in [move(1, 0), move(1, 0), ANCHOR]:
            r.act(a)
        r.sim.enemies[0].awake = True
        for _ in range(2):
            r.act(WAIT)
        self.assertFalse(r.sim.enemies[0].alive)
        r.unravel(1)
        self.assertTrue(r.sim.enemies[0].alive)
        self.assertEqual(r.sim.ghosts, [])


class MetaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "deep", "meta.json")

    def tearDown(self):
        self.tmp.cleanup()

    def finished_run(self, cleared=2, won=False):
        r = Run(seed=1)
        r.cleared = cleared
        r.state = "won" if won else "dead"
        return r

    def test_record_and_reload(self):
        m = Meta(self.path)
        m.record(self.finished_run(3))
        m.record(self.finished_run(6, won=True))
        m2 = Meta(self.path)
        self.assertEqual((m2.data["runs"], m2.data["wins"], m2.data["best_floor"], m2.data["shards"]),
                         (2, 1, 6, 3 + 6 + 3))

    def test_corrupt_or_wrong_typed_files_are_tolerated(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(Meta(self.path).data["runs"], 0)
        with open(self.path, "w") as f:
            json.dump({"runs": "many", "shards": 5, "perks": []}, f)
        m = Meta(self.path)
        self.assertEqual((m.data["runs"], m.data["shards"], m.data["perks"]), (0, 5, {}))

    def test_no_path_means_no_files(self):
        m = Meta(None)
        m.record(self.finished_run())
        self.assertEqual(m.data["runs"], 1)

    def test_buying_perks(self):
        m = Meta(self.path)
        m.data["shards"] = 100
        for key, (_, _, mx, base) in PERKS.items():
            cost_before = m.cost(key)
            self.assertEqual(cost_before, base)
            self.assertTrue(m.buy(key))
            self.assertEqual(m.level(key), 1)
            for _ in range(mx - 1):
                self.assertTrue(m.buy(key))
            self.assertFalse(m.can_buy(key))
            self.assertFalse(m.buy(key))
            self.assertEqual(m.level(key), mx)
        self.assertEqual(Meta(self.path).data["perks"], {k: v[2] for k, v in PERKS.items()})

    def test_cannot_buy_without_shards(self):
        m = Meta(self.path)
        self.assertFalse(m.buy("hp"))
        m.data["shards"] = PERKS["hp"][3] - 1
        self.assertFalse(m.buy("hp"))
        m.data["shards"] += 1
        self.assertTrue(m.buy("hp"))
        self.assertEqual(m.data["shards"], 0)
        self.assertGreater(m.cost("hp"), PERKS["hp"][3])


class FullRuns(unittest.TestCase):
    def test_the_bot_wins_whole_runs_through_the_real_run_api(self):
        for seed in (1, 2, 3):
            r = bot_run(Run(seed=seed))
            with self.subTest(seed=seed):
                self.assertEqual(r.state, "won", r.reason)
                self.assertEqual(r.cleared, MAX_FLOOR)
                self.assertEqual(len(r.picked), MAX_FLOOR - 1)


if __name__ == "__main__":
    unittest.main()


class Lamps(unittest.TestCase):
    """The sconces of the stair: walk close to light them; they stay lit, show what is near them,
    and are worth points."""

    def rigged(self, torches, rows=("###########", "#S.......E#", "#.........#", "###########")):
        r = Run(seed=1)
        f = rig(r, list(rows))
        f._torch_cache = (f, list(torches))
        r.lit = set()
        return r

    def test_a_sconce_lights_when_you_walk_within_reach(self):
        r = self.rigged([(5, 0)])                 # above the corridor, 4 steps along
        r.light_lamps()
        self.assertEqual(r.lit, set())            # too far from the start
        r.act(R)
        self.assertEqual(r.lit, set())            # (2, 1) is still more than two steps away
        r.act(R)
        self.assertEqual(r.lit, {(5, 0)})         # (3, 1): close enough, nothing in between

    def test_a_wall_in_between_keeps_it_cold(self):
        rows = ("###########", "#S..#....E#", "#...#.....#", "###########")
        r = self.rigged([(5, 0)], rows)
        self.assertEqual(r.light_lamps((3, 1)), [])   # close, but the wall at (4, 1) is in the way
        self.assertEqual(r.light_lamps((6, 1)), [(5, 0)])

    def test_lit_sconces_stay_lit_across_loops_and_show_their_surroundings(self):
        r = self.rigged([(5, 0)])
        for a in [R, R, R]:
            r.act(a)
        r.act(ANCHOR)
        self.assertEqual(r.play.loop_no, 2)
        self.assertIn((5, 0), r.lit)
        glow = r.lamp_glow()
        self.assertIn((5, 1), glow)
        self.assertIn((7, 2), glow)
        self.assertNotIn((1, 1), glow)

    def test_lamps_are_counted_and_scored_when_the_floor_is_cleared(self):
        from echo.score import LAMP_BONUS, SCORE_MAX
        r = self.rigged([(3, 0), (5, 6)])         # one on the way, one out of reach in the rock
        for _ in range(8):
            r.act(R)
        res = r.last_result
        self.assertEqual((res.lamps, res.lamps_total), (1, 2))
        self.assertEqual(res.lamp_points, LAMP_BONUS // 2)
        self.assertEqual(res.score, SCORE_MAX + LAMP_BONUS // 2)

    def test_a_new_floor_starts_dark(self):
        r = Run(seed=2)
        self.assertTrue(r.torches)
        r.lit = set(r.torches)
        r.start_floor()
        self.assertLess(len(r.lit), len(r.torches))
