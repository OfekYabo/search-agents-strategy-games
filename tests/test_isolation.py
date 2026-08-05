import random
import unittest

from games import isolation
from games.base import LOSS, check_conformance


def cell(r, c):
    return r * 5 + c


class IsolationRulesTest(unittest.TestCase):
    def test_initial_position(self):
        s = isolation.initial_state()
        self.assertEqual(s.blocked, 0)
        self.assertEqual(s.pawns, (cell(0, 2), cell(4, 2)))
        self.assertEqual(s.side_to_move, 0)

    def test_ply_one_branching_factor_is_eleven(self):
        # From (0,2) on an empty board: E 2, W 2, S 3, SE 2, SW 2.
        # The southward ray yields THREE, not four: it stops before (4,2),
        # which is the opponent's starting cell. Gamebook section 5.3.
        s = isolation.initial_state()
        self.assertEqual(len(isolation.legal_moves(s)), 11)

    def test_maximum_branching_factor_from_centre_is_sixteen(self):
        # 16 requires the opponent to stand on one of the eight cells no ray
        # from the centre passes through; (0,1) is one of them.
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(2, 2), cell(0, 1)),
                                     side_to_move=0)
        self.assertEqual(len(isolation.legal_moves(s)), 16)

    def test_opponent_pawn_truncates_a_ray_from_the_centre(self):
        # Same centre position but the opponent on the southward ray: 15, not 16.
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(2, 2), cell(4, 2)),
                                     side_to_move=0)
        self.assertEqual(len(isolation.legal_moves(s)), 15)

    def test_ray_stops_before_a_blocked_cell(self):
        s = isolation.IsolationState(blocked=1 << cell(2, 2),
                                     pawns=(cell(0, 2), cell(4, 4)),
                                     side_to_move=0)
        moves = isolation.legal_moves(s)
        self.assertIn(cell(1, 2), moves)      # reachable, before the block
        self.assertNotIn(cell(2, 2), moves)   # the blocked cell itself
        self.assertNotIn(cell(3, 2), moves)   # beyond it - no jumping

    def test_ray_stops_before_the_opponent_pawn(self):
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(0, 2), cell(2, 2)),
                                     side_to_move=0)
        moves = isolation.legal_moves(s)
        self.assertIn(cell(1, 2), moves)
        self.assertNotIn(cell(2, 2), moves)
        self.assertNotIn(cell(3, 2), moves)

    def test_vacated_cell_becomes_blocked(self):
        s = isolation.initial_state()
        start = s.pawns[0]
        s2 = isolation.apply_move(s, cell(1, 2))
        self.assertTrue(s2.blocked & (1 << start))
        self.assertEqual(s2.pawns[0], cell(1, 2))
        self.assertEqual(s2.side_to_move, 1)

    def test_starting_cells_are_not_exempt_from_blocking(self):
        # Gamebook 4.2: no exempt cells anywhere, including the start cells.
        s = isolation.initial_state()
        s2 = isolation.apply_move(s, cell(1, 2))
        self.assertTrue(s2.blocked & (1 << cell(0, 2)))

    def test_player_with_no_move_loses(self):
        # Pawn at corner (0,0) with both neighbours on its rays blocked.
        blocked = (1 << cell(0, 1)) | (1 << cell(1, 0)) | (1 << cell(1, 1))
        s = isolation.IsolationState(blocked=blocked,
                                     pawns=(cell(0, 0), cell(4, 4)),
                                     side_to_move=0)
        self.assertEqual(isolation.legal_moves(s), [])
        self.assertTrue(isolation.is_terminal(s))
        self.assertEqual(isolation.result(s), LOSS)

    def test_move_string_round_trips(self):
        for index in range(25):
            self.assertEqual(
                isolation.str_to_move(isolation.move_to_str(index)), index)


class IsolationInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(isolation, random.Random(7), n_games=300, max_plies=30)

    def test_exactly_one_cell_blocks_per_ply_and_no_game_exceeds_23(self):
        rng = random.Random(11)
        for _ in range(200):
            s = isolation.initial_state()
            plies = 0
            while not isolation.is_terminal(s):
                expected_blocked = plies
                self.assertEqual(bin(s.blocked).count("1"), expected_blocked)
                s = isolation.apply_move(s, rng.choice(isolation.legal_moves(s)))
                plies += 1
            self.assertLessEqual(plies, 23)

    def test_no_game_ever_draws(self):
        rng = random.Random(13)
        for _ in range(200):
            s = isolation.initial_state()
            while not isolation.is_terminal(s):
                s = isolation.apply_move(s, rng.choice(isolation.legal_moves(s)))
            self.assertEqual(isolation.result(s), LOSS)


if __name__ == "__main__":
    unittest.main()
