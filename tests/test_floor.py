import unittest

from helpers import cached_floor

from echo.bot import play_floor
from echo.consts import BASE_SLOTS, ENEMIES, GRID_H, GRID_W, LEVER_MIN_DIST, LOCKS_PER_FLOOR, MAX_FLOOR
from echo.floor import bfs_dist, generate_floor, loops_needed, neighbors
from echo.score import par_plan
from echo.sim import ANCHOR, LoopSim, Mods, move

SEEDS = range(1, 13)


class Structure(unittest.TestCase):
    """Properties of the raw layout (no bot verification)."""

    @classmethod
    def setUpClass(cls):
        cls.floors = [(s, i, cached_floor(s, i, verify=False)) for s in SEEDS for i in range(1, MAX_FLOOR + 1)]

    def each(self):
        for s, i, f in self.floors:
            with self.subTest(seed=s, floor=i):
                yield f

    def locks(self, f):
        return [f.doors[i] if kind == "door" else f.gates[i] for kind, i in f.lock_order]

    def test_locks_follow_the_floor_schedule(self):
        for f in self.each():
            kinds = tuple("plate" if kind == "door" else "lever" for kind, _ in f.lock_order)
            self.assertEqual(kinds, LOCKS_PER_FLOOR[f.index - 1])
            self.assertEqual(len(f.plates), len(f.doors))
            self.assertEqual(len(f.levers), len(f.gates))

    def test_everything_is_in_bounds_on_floor_tiles(self):
        for f in self.each():
            pts = [f.start, f.exit, *f.doors, *f.plates, *f.gates, *f.levers, *f.potions, *f.spikes,
                   *[(x, y) for _, x, y in f.spawns]]
            for x, y in pts:
                self.assertTrue(0 <= x < GRID_W and 0 <= y < GRID_H)
                self.assertFalse(f.walls[y][x], (x, y))

    def test_the_border_is_solid_wall(self):
        for f in self.each():
            for x in range(GRID_W):
                self.assertTrue(f.walls[0][x] and f.walls[GRID_H - 1][x])
            for y in range(GRID_H):
                self.assertTrue(f.walls[y][0] and f.walls[y][GRID_W - 1])

    def test_exit_is_reachable_when_all_doors_are_open(self):
        for f in self.each():
            self.assertIn(f.exit, bfs_dist(f.walls, f.start))

    def test_every_lock_is_a_real_chokepoint(self):
        for f in self.each():
            for d in self.locks(f):
                self.assertNotIn(f.exit, bfs_dist(f.walls, f.start, blocked={d}))

    def test_with_every_lock_shut_the_exit_is_unreachable(self):
        for f in self.each():
            self.assertNotIn(f.exit, bfs_dist(f.walls, f.start, blocked=set(self.locks(f))))

    def test_each_plate_or_lever_is_reachable_before_its_own_lock(self):
        # so an echo can always get there using only the locks before it
        for f in self.each():
            locks = self.locks(f)
            for k, (kind, i) in enumerate(f.lock_order):
                region = bfs_dist(f.walls, f.start, blocked=set(locks[k:]) | set(f.levers))
                if kind == "door":
                    self.assertIn(f.plates[i], region)
                    self.assertGreaterEqual(region[f.plates[i]], 5)
                else:
                    self.assertTrue(any(n in region for n in neighbors(*f.levers[i])))

    def test_levers_are_far_from_their_gates_and_never_cut_the_map(self):
        for f in self.each():
            open_tiles = bfs_dist(f.walls, f.start)
            without = bfs_dist(f.walls, f.start, blocked=set(f.levers))
            self.assertEqual(len(without), len(open_tiles) - len(f.levers))
            for j, lever in enumerate(f.levers):
                walk = bfs_dist(f.walls, f.gates[j], blocked=set(f.levers) - {lever})
                self.assertGreaterEqual(walk[lever], LEVER_MIN_DIST)

    def test_a_lever_is_too_far_to_pull_and_still_reach_the_stairs_in_one_loop(self):
        for f in self.each():
            if not f.levers:
                continue
            plan = par_plan(f)
            self.assertLessEqual(max(plan), f.limit)             # every loop of the par solution fits
            to_exit = bfs_dist(f.walls, f.exit, blocked=set(f.levers))
            for k, (kind, j) in enumerate(f.lock_order):
                if kind == "gate":
                    run_for_it = plan[k] + min(to_exit[n] for n in neighbors(*f.levers[j]) if n in to_exit)
                    self.assertGreater(run_for_it, f.limit)

    def test_plates_never_sit_in_doorways_or_overlap(self):
        for f in self.each():
            spots = [f.start, f.exit, *f.doors, *f.plates, *f.gates, *f.levers]
            self.assertEqual(len(spots), len(set(spots)))

    def test_nothing_spawns_on_a_special_tile_or_near_the_start(self):
        for f in self.each():
            special = {f.start, f.exit, *f.doors, *f.plates, *f.gates, *f.levers, *f.potions, *f.spikes}
            dist = bfs_dist(f.walls, f.start)
            seen = set()
            for kind, x, y in f.spawns:
                self.assertIn(kind, ENEMIES)
                self.assertNotIn((x, y), special)
                self.assertNotIn((x, y), seen)
                seen.add((x, y))
                self.assertGreaterEqual(dist[(x, y)], 3)

    def test_enemy_kinds_unlock_by_floor(self):
        for f in self.each():
            kinds = {k for k, _, _ in f.spawns}
            if f.index < 2:
                self.assertEqual(kinds - {"crawler"}, set())
            if f.index < 4:
                self.assertNotIn("brute", kinds)
            if f.index < MAX_FLOOR:
                self.assertNotIn("warden", kinds)

    def test_the_last_floor_has_a_warden_near_the_stairs(self):
        for s in SEEDS:
            f = cached_floor(s, MAX_FLOOR, verify=False)
            wardens = [(x, y) for k, x, y in f.spawns if k == "warden"]
            self.assertTrue(wardens, s)
            x, y = wardens[0]
            self.assertLessEqual(abs(x - f.exit[0]) + abs(y - f.exit[1]), 3)

    def test_spikes_only_from_floor_two(self):
        for f in self.each():
            if f.index == 1:
                self.assertEqual(f.spikes, {})
            else:
                self.assertTrue(f.spikes)

    def test_limit_leaves_time_for_the_longest_walk(self):
        for f in self.each():
            if f.levers:
                continue                          # lever floors are tuned tighter (see the test above)
            far = max(bfs_dist(f.walls, f.start, blocked=set(f.doors[k:]))[p] for k, p in enumerate(f.plates))
            far = max(far, bfs_dist(f.walls, f.start)[f.exit])
            self.assertGreater(f.limit, far * 1.5)

    def test_same_seed_same_floor_different_seed_differs(self):
        a = generate_floor(7, 3, verify=False)
        b = generate_floor(7, 3, verify=False)
        c = generate_floor(8, 3, verify=False)
        self.assertEqual((a.walls, a.doors, a.plates, a.spawns), (b.walls, b.doors, b.plates, b.spawns))
        self.assertNotEqual(a.walls, c.walls)

    def test_loops_needed(self):
        f = generate_floor(1, 4, verify=False)
        self.assertEqual(loops_needed(f), 3)
        self.assertLessEqual(loops_needed(f), BASE_SLOTS + 1)


class NoShortcut(unittest.TestCase):
    def test_walking_straight_to_the_exit_without_echoes_never_works(self):
        for s in range(1, 9):
            for i in range(1, MAX_FLOOR + 1):
                f = cached_floor(s, i, verify=False)
                sim = LoopSim(f, [], Mods())
                from echo.floor import bfs_path
                path = bfs_path(f.walls, f.start, f.exit)
                for a, b in zip(path, path[1:]):
                    if sim.over or sim.validate(move(b[0] - a[0], b[1] - a[1])):
                        break
                    sim.step(move(b[0] - a[0], b[1] - a[1]))
                self.assertNotEqual(sim.over, "exit", (s, i))


class Verified(unittest.TestCase):
    def test_every_verified_floor_is_cleared_by_the_bot_with_the_baseline_kit(self):
        for s in range(1, 9):
            for i in range(1, MAX_FLOOR + 1):
                f = cached_floor(s, i)
                with self.subTest(seed=s, floor=i):
                    self.assertTrue(f.verified)
                    fp = play_floor(f)
                    self.assertEqual(fp.status, "cleared")
                    self.assertLessEqual(fp.loop_no, BASE_SLOTS + 1)

    def test_the_bot_needs_an_echo_per_lock(self):
        # the loop that clears a floor is at least len(locks)+1: echoes really are required
        for s in range(1, 6):
            for i in range(1, MAX_FLOOR + 1):
                f = cached_floor(s, i)
                fp = play_floor(f)
                self.assertGreaterEqual(fp.loop_no, len(f.lock_order) + 1, (s, i))

    def test_verification_matches_replaying_the_stored_scripts(self):
        # replay the winning run's echoes and the final actions by hand to be sure the sim is deterministic
        f = generate_floor(3, 4)
        fp1, fp2 = play_floor(f), play_floor(f)
        self.assertEqual([s.actions for s in fp1.scripts], [s.actions for s in fp2.scripts])
        self.assertEqual(fp1.sim.record, fp2.sim.record)

    def test_anchoring_everything_never_wins(self):
        f = generate_floor(2, 3)
        from echo.run import FloorPlay
        fp = FloorPlay(f, Mods(), BASE_SLOTS)
        while fp.status == "playing":
            fp.act(ANCHOR)
        self.assertEqual(fp.status, "full")
        self.assertEqual(fp.loop_no, BASE_SLOTS + 1)
        self.assertEqual(len(fp.scripts), BASE_SLOTS + 1)


if __name__ == "__main__":
    unittest.main()
