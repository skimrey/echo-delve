import json
import os
import tempfile
import unittest

from helpers import D, L, R, make_floor

from echo.bot import bot_action
from echo.consts import BASE_ATK, BASE_HP, BASE_SLOTS, MAX_FLOOR, PERKS, SLOT_CAP, UPGRADES
from echo.run import FloorPlay, Meta, Run
from echo.sim import ANCHOR, WAIT, move


def rig(run, rows, **kw):
    """Swap the run's current floor for a hand-drawn one."""
    f = make_floor(rows, **kw)
    run.floor = f
    run.play = FloorPlay(f, run.mods(), run.slots + 1)
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
        remaining = [k for k in range(len(f.plates)) if k not in done]
        target = remaining[0] if remaining else None
        goal = f.plates[target] if target is not None else f.exit
        lb, fl = run.play.loop_no, run.floor_no
        st = {}
        while run.state == "playing" and run.play.loop_no == lb and run.floor_no == fl and steps < max_steps:
            run.act(bot_action(run.sim, goal, target is not None, st))
            steps += 1
        if (target is not None and run.floor_no == fl and run.play.last_end in ("anchor", "timeout")
                and run.play.last_end_pos == goal):
            done.add(target)
    return run


class RunBasics(unittest.TestCase):
    def test_new_run_defaults(self):
        r = Run(seed=1)
        self.assertEqual((r.state, r.floor_no, r.cleared), ("playing", 1, 0))
        self.assertEqual((r.max_hp, r.atk, r.slots), (BASE_HP, BASE_ATK, BASE_SLOTS))
        self.assertEqual(r.play.loops_max, BASE_SLOTS + 1)
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

    def test_running_out_of_loops_ends_the_run(self):
        r = self.r
        for i in range(BASE_SLOTS + 1):
            self.assertEqual(r.state, "playing")
            r.act(ANCHOR)
        self.assertEqual(r.state, "dead")
        self.assertIn("no echoes left", r.reason)
        self.assertEqual(r.play.status, "failed")

    def test_dying_on_the_last_loop_has_its_own_reason(self):
        r = Run(seed=1)
        rig(r, ["SC..", "...."])
        r.play.loop_no = r.play.loops_max
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
            self.assertEqual(r.play.loops_max, r.slots + 1)

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
        self.assertEqual(r.shards_earned(), MAX_FLOOR + 3)


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
