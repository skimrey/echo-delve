import unittest

from helpers import D, L, R, U, kinds, new_sim, run_actions

from echo.consts import POTION_HEAL
from echo.sim import ANCHOR, WAIT, GhostScript, Mods, move


class Movement(unittest.TestCase):
    def test_move_and_wait(self):
        sim = new_sim(["S...."])
        sim.step(R)
        self.assertEqual(sim.player.pos, (1, 0))
        sim.step(WAIT)
        self.assertEqual(sim.player.pos, (1, 0))
        self.assertEqual(sim.turn, 2)

    def test_walls_and_edges_are_refused_with_a_message_and_cost_no_turn(self):
        sim = new_sim(["S#", "#."])
        for a in (R, D, L, U):
            self.assertIn("wall", sim.validate(a).lower())
        self.assertEqual(sim.turn, 0)
        self.assertEqual(sim.record, [])

    def test_sealed_door_message_names_door_and_plate(self):
        sim = new_sim(["S1.a"])
        msg = sim.validate(R)
        self.assertIn("Door 1", msg)
        self.assertIn("plate 1", msg)

    def test_reaching_the_exit_ends_the_loop(self):
        sim = new_sim(["SE"])
        sim.step(R)
        self.assertEqual(sim.over, "exit")
        with self.assertRaises(RuntimeError):
            sim.step(WAIT)
        self.assertIn("over", sim.validate(WAIT))

    def test_anchor_ends_the_loop_without_a_turn(self):
        sim = new_sim(["S.."])
        sim.step(R)
        sim.step(ANCHOR)
        self.assertEqual(sim.over, "anchor")
        self.assertEqual(sim.record, [R])

    def test_timeout(self):
        sim = new_sim(["S..."], limit=3)
        run_actions(sim, [WAIT, WAIT, WAIT])
        self.assertEqual(sim.over, "timeout")

    def test_limit_bonus_extends_the_timer(self):
        sim = new_sim(["S..."], limit=3, mods=Mods(limit_bonus=2))
        run_actions(sim, [WAIT] * 4)
        self.assertIsNone(sim.over)
        sim.step(WAIT)
        self.assertEqual(sim.over, "timeout")


class Doors(unittest.TestCase):
    def test_plate_opens_and_leaving_closes_it(self):
        sim = new_sim(["#a..S", "#1###"])
        # plate at (1,0), door at (1,1): stand on plate, door opens; step away, closes
        sim.step(L)
        sim.step(L)
        sim.step(L)
        self.assertTrue(sim.plate_held(0))
        self.assertTrue(sim.door_open(0))
        sim.step(R)
        self.assertFalse(sim.door_open(0))

    def test_door_opening_and_closing_emit_events(self):
        sim = new_sim(["#a.S", "#1##"])
        ev = run_actions(sim, [L, L])
        self.assertIn(("door", 0, True), ev)
        ev = sim.step(R)
        self.assertIn(("door", 0, False), ev)

    def test_door_will_not_close_on_someone_standing_in_it(self):
        sim = new_sim(["#S#", "#1#", "#.#", "#a#"])
        self.assertFalse(sim.door_open(0))
        sim.player.x, sim.player.y = sim.floor.doors[0]      # stand in the doorway
        self.assertTrue(sim.door_open(0))

    def test_echo_holds_the_plate_after_you_anchor(self):
        rows = ["S.a#", "###1", "###E"]
        first = new_sim(rows)
        run_actions(first, [R, R, ANCHOR])
        script = GhostScript(list(first.record), "anchor", 1)
        second = new_sim(rows, [script])
        self.assertFalse(second.door_open(0))
        run_actions(second, [WAIT, WAIT])
        self.assertTrue(second.plate_held(0))
        self.assertTrue(second.door_open(0))
        run_actions(second, [WAIT] * 10)               # long after its recording ended
        self.assertTrue(second.door_open(0))

    def test_passing_the_door_with_an_echo(self):
        floor_rows = ["Sa#", "#.#", "#1#", "#E#"]
        first = new_sim(floor_rows)
        run_actions(first, [R, ANCHOR])
        script = GhostScript(list(first.record), "anchor", 1)
        second = new_sim(floor_rows, [script])
        # you walk along the same route first as the echo; then wait for it to reach the plate
        sim = second
        sim.step(WAIT)                      # echo steps onto the plate
        self.assertTrue(sim.door_open(0))
        sim.player.x, sim.player.y = 1, 1   # (1,1) is the corridor above the door
        self.assertIsNone(sim.validate(D))
        ev = run_actions(sim, [D, D])
        self.assertEqual(sim.over, "exit")
        self.assertIn(("exit",), ev)

    def test_enemy_standing_on_a_plate_also_holds_it(self):
        sim = new_sim(["Sa1", "#C#"])
        sim.enemies[0].x, sim.enemies[0].y = sim.floor.plates[0]
        self.assertTrue(sim.door_open(0))


class Combat(unittest.TestCase):
    def test_walking_into_an_enemy_strikes_and_is_recorded_as_a_strike(self):
        sim = new_sim(["SC..."], mods=Mods(atk=2))
        sim.enemies[0].x = 1
        ev = sim.step(R)
        self.assertEqual(sim.player.pos, (0, 0))
        self.assertEqual(sim.record, [("f", 1, 0)])
        self.assertIn("attack", kinds(ev))
        self.assertEqual(sim.enemies[0].hp, 0)
        self.assertIn("died", kinds(ev))

    def test_dead_enemies_are_removed_and_can_be_walked_through(self):
        sim = new_sim(["S.C.."], mods=Mods(atk=5))
        sim.enemies[0].x = 1
        sim.step(R)
        self.assertIsNone(sim.enemy_at(1, 0))
        sim.step(R)
        self.assertEqual(sim.player.pos, (1, 0))

    def test_player_death(self):
        sim = new_sim(["SC"], mods=Mods(max_hp=1))
        sim.enemies[0].awake = True
        ev = sim.step(WAIT)
        self.assertEqual(sim.over, "dead")
        self.assertIn("dead", kinds(ev))

    def test_damage_wakes_a_sleeper(self):
        sim = new_sim(["S....C"], mods=Mods(atk=1))
        sim.enemies[0].x = 1
        self.assertFalse(sim.enemies[0].awake)
        sim.step(R)
        self.assertTrue(sim.enemies[0].awake)

    def test_potion_heals_up_to_max(self):
        sim = new_sim(["Sp.."], mods=Mods(max_hp=10))
        sim.player.hp = 5
        ev = sim.step(R)
        self.assertEqual(sim.player.hp, 5 + POTION_HEAL)
        self.assertNotIn(sim.player.pos, sim.potions)
        sim2 = new_sim(["Sp.."], mods=Mods(max_hp=10))
        sim2.player.hp = 9
        sim2.step(R)
        self.assertEqual(sim2.player.hp, 10)


class Spikes(unittest.TestCase):
    def test_active_phase_hurts_inactive_phase_does_not(self):
        # phase 0 is up on turns 0-1, down on 2-3
        sim = new_sim(["S^..."], mods=Mods(max_hp=10))
        sim.step(R)                       # turn 0: spike is up
        self.assertEqual(sim.player.hp, 9)
        sim.step(WAIT)                    # turn 1: still up
        self.assertEqual(sim.player.hp, 8)
        sim.step(WAIT)                    # turn 2: down
        self.assertEqual(sim.player.hp, 8)
        sim.step(WAIT)
        self.assertEqual(sim.player.hp, 8)
        sim.step(WAIT)                    # turn 4: up again
        self.assertEqual(sim.player.hp, 7)

    def test_phase_one_is_the_opposite(self):
        sim = new_sim(["Sv..."], mods=Mods(max_hp=10))
        sim.step(R)
        self.assertEqual(sim.player.hp, 10)
        sim.step(WAIT)
        sim.step(WAIT)                    # turn 2: phase 1 is up
        self.assertEqual(sim.player.hp, 9)

    def test_spikes_can_kill(self):
        sim = new_sim(["S^"], mods=Mods(max_hp=1))
        sim.step(R)
        self.assertEqual(sim.over, "dead")


class Echoes(unittest.TestCase):
    def record(self, rows, actions, ending="anchor", **kw):
        sim = new_sim(rows, **kw)
        run_actions(sim, actions)
        if sim.over is None and ending == "anchor":
            sim.step(ANCHOR)
        return GhostScript(list(sim.record), ending, 1)

    def test_echo_replays_your_moves_from_the_start_and_then_stands_still(self):
        rows = ["S....."]
        s = self.record(rows, [R, R, R])
        sim = new_sim(rows, [s])
        g = sim.ghosts[0]
        self.assertEqual(g.pos, (0, 0))
        run_actions(sim, [WAIT])
        self.assertEqual(g.pos, (1, 0))
        run_actions(sim, [WAIT, WAIT])
        self.assertEqual(g.pos, (3, 0))
        run_actions(sim, [WAIT] * 5)
        self.assertEqual(g.pos, (3, 0))
        self.assertTrue(g.alive)

    def test_a_dead_echo_fades_when_the_recording_ends(self):
        rows = ["S....."]
        s = GhostScript([R, R], "dead", 1)
        sim = new_sim(rows, [s])
        ev = run_actions(sim, [WAIT, WAIT])
        self.assertFalse(sim.ghosts[0].alive)
        self.assertIn("faded", kinds(ev))

    def test_you_and_your_echo_share_tiles(self):
        rows = ["S...."]
        s = GhostScript([R], "anchor", 1)
        sim = new_sim(rows, [s])
        sim.step(R)
        self.assertEqual(sim.player.pos, sim.ghosts[0].pos)

    def test_echo_never_wanders_when_a_foe_is_already_dead(self):
        rows = ["SC..."]
        # recorded loop: strike the crawler twice (it has more HP than one hit)
        sim = new_sim(rows, mods=Mods(atk=1))
        sim.enemies[0].x = 1
        sim.enemies[0].hp = sim.enemies[0].max_hp = 2
        run_actions(sim, [R, R])
        self.assertEqual(sim.record, [("f", 1, 0), ("f", 1, 0)])
        script = GhostScript(list(sim.record), "anchor", 1)
        # replay with the crawler killed by you on the first beat: the echo's swings hit air
        second = new_sim(rows, [script], mods=Mods(atk=5))
        second.enemies[0].x = 1
        ev = second.step(R)               # you strike (killing it); echo swings at the corpse tile
        self.assertEqual(second.ghosts[0].pos, (0, 0))
        ev = second.step(WAIT)
        self.assertEqual(second.ghosts[0].pos, (0, 0))
        self.assertIn("swing", kinds(ev))

    def test_an_echo_bumping_a_wall_is_blocked_not_moved(self):
        rows = ["S.#"]
        s = GhostScript([R, R, R], "anchor", 1)
        sim = new_sim(rows, [s])
        ev = run_actions(sim, [WAIT, WAIT, WAIT])
        self.assertEqual(sim.ghosts[0].pos, (1, 0))
        self.assertIn(("blocked", "G1"), ev)

    def test_an_echo_moving_toward_an_enemy_is_blocked_not_swapped_in(self):
        s = GhostScript([R, R], "anchor", 1)
        sim = new_sim(["S.C.."], [s])
        sim.enemies[0].x = 1
        ev = sim.step(WAIT)
        self.assertEqual(sim.ghosts[0].pos, (0, 0))
        self.assertIn(("blocked", "G1"), ev)

    def test_an_echo_at_a_sealed_door_waits_and_continues_its_script_afterwards(self):
        rows = ["S1.a"]
        s = GhostScript([R, R], "anchor", 1)
        sim = new_sim(rows, [s])
        ev = sim.step(WAIT)
        self.assertEqual(sim.ghosts[0].pos, (0, 0))
        self.assertIn(("blocked", "G1"), ev)

    def test_echo_fights_enemies_and_can_die(self):
        rows = ["S.C"]
        s = GhostScript([WAIT, WAIT, WAIT, WAIT], "anchor", 1)
        sim = new_sim(rows, [s], mods=Mods(max_hp=2))
        sim.player.x, sim.player.y = 0, 0
        sim.enemies[0].awake = True
        sim.enemies[0].x = 1
        # the player stands elsewhere; echo and player share tile (0,0): the crawler attacks the player first
        run_actions(sim, [WAIT])
        self.assertEqual(sim.player.hp, 1)
        self.assertEqual(sim.ghosts[0].hp, 2)

    def test_echo_hp_matches_yours_plus_the_guard_bonus(self):
        sim = new_sim(["S.."], [GhostScript([], "anchor", 1)], mods=Mods(max_hp=12, ghost_hp=2))
        self.assertEqual(sim.ghosts[0].hp, 14)

    def test_echo_picks_up_potions_but_not_twice(self):
        rows = ["Sp..."]
        s = GhostScript([R], "anchor", 1)
        sim = new_sim(rows, [s], mods=Mods(max_hp=10))
        sim.ghosts[0].hp = 5
        sim.step(WAIT)
        self.assertEqual(sim.ghosts[0].hp, 8)
        self.assertEqual(len(sim.potions), 0)


class Enemies(unittest.TestCase):
    def test_sleeping_until_someone_is_close(self):
        sim = new_sim(["S............C"])
        sim.step(WAIT)
        self.assertFalse(sim.enemies[0].awake)
        sim.player.x = 8
        sim.step(WAIT)
        self.assertTrue(sim.enemies[0].awake)

    def test_waking_uses_the_enemy_turn(self):
        sim = new_sim(["S.....C"])
        e = sim.enemies[0]
        before = e.pos
        sim.step(WAIT)
        self.assertTrue(e.awake)
        self.assertEqual(e.pos, before)

    def test_crawler_chases_one_step_per_turn_and_hits(self):
        sim = new_sim(["S....C"], mods=Mods(max_hp=10))
        e = sim.enemies[0]
        e.awake = True
        sim.step(WAIT)
        self.assertEqual(e.pos, (4, 0))
        run_actions(sim, [WAIT] * 3)
        self.assertEqual(e.pos, (1, 0))
        sim.step(WAIT)
        self.assertEqual(sim.player.hp, 9)
        self.assertEqual(e.pos, (1, 0))

    def test_enemy_goes_for_the_nearest_target_including_echoes(self):
        rows = ["S.........C"]
        s = GhostScript([R] * 9, "anchor", 1)
        sim = new_sim(rows, [s])
        sim.enemies[0].awake = True
        run_actions(sim, [WAIT] * 8)
        self.assertLess(sim.ghosts[0].hp, sim.ghosts[0].max_hp)

    def test_enemy_cannot_pass_a_sealed_door(self):
        sim = new_sim(["S.1.C", "###a#"])
        e = sim.enemies[0]
        e.awake = True
        run_actions(sim, [WAIT] * 4)
        self.assertGreater(e.pos[0], 2)           # never gets past the sealed door at x=2
        self.assertEqual(sim.player.hp, sim.player.max_hp)

    def test_enemies_do_not_stack(self):
        sim = new_sim(["S.....CC"])
        for e in sim.enemies:
            e.awake = True
        run_actions(sim, [WAIT] * 3)
        self.assertNotEqual(sim.enemies[0].pos, sim.enemies[1].pos)

    def test_brute_acts_every_other_turn(self):
        sim = new_sim(["S...B"], mods=Mods(max_hp=20))
        b = sim.enemies[0]
        b.awake = True
        positions = []
        for _ in range(4):
            sim.step(WAIT)
            positions.append(b.pos[0])
        self.assertEqual(positions, [3, 3, 2, 2])

    def test_brute_hits_for_two(self):
        sim = new_sim(["SB"], mods=Mods(max_hp=10))
        sim.enemies[0].awake = True
        sim.step(WAIT)
        self.assertEqual(sim.player.hp, 8)

    def test_archer_shoots_along_a_clear_line_with_a_cooldown(self):
        sim = new_sim(["S...A"], mods=Mods(max_hp=10))
        a = sim.enemies[0]
        a.awake = True
        ev = sim.step(WAIT)
        self.assertIn("shot", kinds(ev))
        self.assertEqual(sim.player.hp, 9)
        ev = sim.step(WAIT)
        self.assertNotIn("shot", kinds(ev))
        ev = sim.step(WAIT)
        self.assertIn("shot", kinds(ev))
        self.assertEqual(a.pos, (4, 0))

    def test_archer_cannot_shoot_through_walls_or_off_axis(self):
        sim = new_sim(["S#..A"], mods=Mods(max_hp=10))
        sim.enemies[0].awake = True
        ev = sim.step(WAIT)
        self.assertNotIn("shot", kinds(ev))
        sim2 = new_sim(["S....", ".....", "....A"], mods=Mods(max_hp=10))
        sim2.enemies[0].awake = True
        ev = sim2.step(WAIT)
        self.assertNotIn("shot", kinds(ev))

    def test_archer_range_is_limited(self):
        sim = new_sim(["S.......A"], mods=Mods(max_hp=10))
        sim.enemies[0].awake = True
        ev = sim.step(WAIT)
        self.assertNotIn("shot", kinds(ev))

    def test_warden_is_tough(self):
        sim = new_sim(["SW"], mods=Mods(atk=2))
        sim.step(R)
        self.assertEqual(sim.enemies[0].hp, 7)


class Determinism(unittest.TestCase):
    def test_same_inputs_same_events(self):
        rows = ["S.....C..A", "..........", "....B....."]
        acts = [R, R, D, WAIT, R, R, U, WAIT, R, R]

        def go():
            sim = new_sim(rows)
            return run_actions(sim, acts), sim.player.pos, sim.player.hp

        self.assertEqual(go(), go())


if __name__ == "__main__":
    unittest.main()
