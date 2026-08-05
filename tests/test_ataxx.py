import random
import unittest

from games import ataxx
from games.base import DRAW, LOSS, WIN, check_conformance


def cell(r, c):
    return r * 7 + c


def mask(*cells):
    m = 0
    for c in cells:
        m |= 1 << c
    return m


class AtaxxRulesTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ataxx.NAME, "ataxx")

    def test_initial_position(self):
        s = ataxx.initial_state()
        self.assertEqual(s.boards[0], mask(cell(0, 0), cell(6, 6)))
        self.assertEqual(s.boards[1], mask(cell(0, 6), cell(6, 0)))
        self.assertEqual(s.side_to_move, 0)
        self.assertEqual(s.plies_since_progress, 0)

    def test_jump_ring_has_all_sixteen_cells_including_knight_shapes(self):
        # A lone piece at the centre with an otherwise empty board: 8 clone
        # destinations and 16 jump destinations. Missing the knight-shaped
        # cells - the classic bug - would give 8 jumps instead of 16.
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3)), mask(cell(0, 0))),
                             side_to_move=0, plies_since_progress=0)
        moves = ataxx.legal_moves(s)
        clones = [m for m in moves if m[0] == -1]
        jumps = [m for m in moves if m[0] >= 0]
        self.assertEqual(len(clones), 8)
        self.assertEqual(len(jumps), 16)
        # (1,2)-shaped destination must be present
        self.assertIn((cell(3, 3), cell(1, 2)), jumps)
        # straight two-step must also be present
        self.assertIn((cell(3, 3), cell(1, 3)), jumps)

    def test_clones_are_deduplicated_by_destination(self):
        # Two adjacent friendly pieces both able to clone into the same cell.
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3), cell(3, 5)), mask(cell(0, 0))),
                             side_to_move=0, plies_since_progress=0)
        clone_dests = [m[1] for m in ataxx.legal_moves(s) if m[0] == -1]
        self.assertEqual(len(clone_dests), len(set(clone_dests)))
        self.assertIn(cell(3, 4), clone_dests)

    def test_clone_keeps_the_source_and_adds_a_piece(self):
        s = ataxx.initial_state()
        before = bin(s.boards[0]).count("1")
        s2 = ataxx.apply_move(s, (-1, cell(0, 1)))
        self.assertEqual(bin(s2.boards[0]).count("1"), before + 1)
        self.assertTrue(s2.boards[0] & (1 << cell(0, 0)))

    def test_jump_vacates_the_source_and_keeps_the_count(self):
        s = ataxx.initial_state()
        before = bin(s.boards[0]).count("1")
        s2 = ataxx.apply_move(s, (cell(0, 0), cell(0, 2)))
        self.assertEqual(bin(s2.boards[0]).count("1"), before)
        self.assertFalse(s2.boards[0] & (1 << cell(0, 0)))
        self.assertTrue(s2.boards[0] & (1 << cell(0, 2)))

    def test_conversion_flips_all_eight_neighbours_and_is_not_chained(self):
        # P1 ring around (3,3); a P1 piece two cells further out must NOT flip.
        ring = [cell(2, 2), cell(2, 3), cell(2, 4), cell(3, 2),
                cell(3, 4), cell(4, 2), cell(4, 3), cell(4, 4)]
        outer = cell(1, 1)
        s = ataxx.AtaxxState(boards=(mask(cell(6, 6)), mask(*(ring + [outer]))),
                             side_to_move=0, plies_since_progress=0)
        s2 = ataxx.apply_move(s, (-1, cell(3, 3)))   # arrives adjacent to the ring
        for c in ring:
            self.assertTrue(s2.boards[0] & (1 << c), "ring cell must convert")
        self.assertTrue(s2.boards[1] & (1 << outer),
                        "conversion must not chain to the outer piece")

    def test_occupied_count_never_decreases(self):
        rng = random.Random(3)
        for _ in range(40):
            s = ataxx.initial_state()
            occupied = 4
            while not ataxx.is_terminal(s):
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))
                now = bin(s.boards[0] | s.boards[1]).count("1")
                self.assertGreaterEqual(now, occupied)
                occupied = now

    def test_a_player_with_no_move_passes_rather_than_losing(self):
        # P1 has a single piece walled in by P0 pieces at every distance <= 2.
        p1 = mask(cell(0, 0))
        p0_cells = [cell(r, c) for r in range(3) for c in range(3)
                    if (r, c) != (0, 0)]
        s = ataxx.AtaxxState(boards=(mask(*p0_cells), p1),
                             side_to_move=1, plies_since_progress=0)
        moves = ataxx.legal_moves(s)
        self.assertEqual(moves, [ataxx.PASS])
        self.assertFalse(ataxx.is_terminal(s))
        s2 = ataxx.apply_move(s, ataxx.PASS)
        self.assertEqual(s2.side_to_move, 0)
        self.assertEqual(s2.plies_since_progress, 1,
                         "a pass is not progress")

    def test_zero_pieces_loses(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0)), 0),
                             side_to_move=1, plies_since_progress=0)
        self.assertTrue(ataxx.is_terminal(s))
        self.assertEqual(ataxx.result(s), LOSS)
        self.assertEqual(ataxx.end_reason(s), "eliminated")

    def test_no_progress_limit_ends_the_game(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)),
                                     mask(cell(6, 6), cell(6, 5))),
                             side_to_move=0,
                             plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertTrue(ataxx.is_terminal(s))
        self.assertEqual(ataxx.end_reason(s), "no_progress")
        self.assertEqual(ataxx.result(s), DRAW)   # counts are level

    def test_progress_counter_resets_on_a_clone_and_on_a_conversion(self):
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3)), mask(cell(6, 6))),
                             side_to_move=0, plies_since_progress=7)
        self.assertEqual(ataxx.apply_move(s, (-1, cell(3, 4))).plies_since_progress, 0)
        # A jump with no conversion is not progress.
        s2 = ataxx.apply_move(s, (cell(3, 3), cell(3, 5)))
        self.assertEqual(s2.plies_since_progress, 8)

    def test_scoring_is_by_piece_count(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)), mask(cell(6, 6))),
                             side_to_move=1,
                             plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertEqual(ataxx.result(s), LOSS)    # side to move has fewer
        s2 = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)), mask(cell(6, 6))),
                              side_to_move=0,
                              plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertEqual(ataxx.result(s2), WIN)

    def test_move_string_round_trips_for_clones_jumps_and_pass(self):
        self.assertEqual(ataxx.str_to_move(ataxx.move_to_str(ataxx.PASS)),
                         ataxx.PASS)
        for m in ((-1, cell(1, 1)), (cell(0, 0), cell(2, 2)),
                  (cell(6, 6), cell(4, 5))):
            self.assertEqual(ataxx.str_to_move(ataxx.move_to_str(m)), m)


class AtaxxInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(ataxx, random.Random(23), n_games=60, max_plies=400)

    def test_players_never_occupy_the_same_cell(self):
        rng = random.Random(29)
        for _ in range(40):
            s = ataxx.initial_state()
            while not ataxx.is_terminal(s):
                self.assertEqual(s.boards[0] & s.boards[1], 0)
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))

    def test_a_double_pass_never_occurs(self):
        # docs/games/ataxx.md 4.4.1 proves this cannot happen: whenever an empty
        # cell exists at least one player can move. A failure here is a bug.
        rng = random.Random(31)
        for _ in range(40):
            s = ataxx.initial_state()
            previous_was_pass = False
            while not ataxx.is_terminal(s):
                moves = ataxx.legal_moves(s)
                is_pass = moves == [ataxx.PASS]
                self.assertFalse(is_pass and previous_was_pass,
                                 "double pass is provably impossible")
                previous_was_pass = is_pass
                s = ataxx.apply_move(s, rng.choice(moves))

    def test_a_full_board_is_never_a_draw(self):
        # 49 cells is odd, so a full board cannot be level on pieces.
        rng = random.Random(37)
        for _ in range(40):
            s = ataxx.initial_state()
            while not ataxx.is_terminal(s):
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))
            if bin(s.boards[0] | s.boards[1]).count("1") == 49:
                self.assertNotEqual(ataxx.result(s), DRAW)


if __name__ == "__main__":
    unittest.main()
