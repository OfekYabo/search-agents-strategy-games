import random
import unittest

from games import uttt
from games.base import DRAW, LOSS, WIN, check_conformance


def mv(board, cell):
    return board * 9 + cell


class UtttRulesTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(uttt.NAME, "uttt")

    def test_initial_state_allows_all_81_cells(self):
        s = uttt.initial_state()
        self.assertEqual(s.send, -1)
        self.assertEqual(s.side_to_move, 0)
        self.assertEqual(len(uttt.legal_moves(s)), 81)

    def test_send_rule_restricts_to_the_cell_index_just_played(self):
        s = uttt.initial_state()
        s = uttt.apply_move(s, mv(4, 7))       # cell 7 sends opponent to board 7
        self.assertEqual(s.send, 7)
        moves = uttt.legal_moves(s)
        self.assertEqual(len(moves), 9)
        self.assertTrue(all(m // 9 == 7 for m in moves))

    def test_a_won_local_board_is_closed_and_frees_the_opponent(self):
        # P0 takes cells 0,1,2 of board 0. Interleave P1 moves so the send
        # constraint keeps landing P0 back on board 0.
        s = uttt.initial_state()
        for m in (mv(0, 0), mv(0, 3), mv(0, 1), mv(0, 4), mv(0, 2)):
            s = uttt.apply_move(s, m)
        self.assertEqual(s.status[0], 1)               # board 0 won by player 0
        # P1 was sent to board 2 (cell index of the last move). Play there,
        # choosing cell 0 so the reply would be sent to the closed board 0.
        s = uttt.apply_move(s, mv(2, 0))
        self.assertEqual(s.send, 0)
        moves = uttt.legal_moves(s)
        self.assertTrue(all(m // 9 != 0 for m in moves),
                        "closed board must offer no moves")
        self.assertGreater(len(moves), 9,
                           "being sent to a closed board must free the mover")

    def test_a_full_local_board_with_no_winner_is_drawn_and_counts_for_neither(self):
        s = uttt.initial_state()
        # Fill board 0 in an order that produces no three-in-a-row:
        # P0 -> 0,1,5,6,7 ; P1 -> 2,3,4,8  (checked by hand: no line for either)
        order = [0, 2, 1, 3, 5, 4, 6, 8, 7]
        state = s
        for i, cell in enumerate(order):
            # force every move into board 0 by rebuilding the send constraint
            state = uttt.UtttState(marks=state.marks, status=state.status,
                                   send=0, side_to_move=state.side_to_move,
                                   winnable=state.winnable,
                                   global_winner=state.global_winner)
            state = uttt.apply_move(state, mv(0, cell))
        self.assertEqual(state.status[0], 3, "full, no winner -> drawn")
        # A drawn board forms part of no global line for either player.
        for player in (0, 1):
            for line_index, line in enumerate(uttt.LINES):
                if 0 in line:
                    self.assertFalse((state.winnable[player] >> line_index) & 1)

    def test_winning_three_boards_in_a_row_wins_the_game(self):
        # Hand-built terminal position: P0 owns boards 0, 1, 2.
        s = uttt.UtttState(marks=(0, 0), status=(1, 1, 1, 0, 0, 0, 0, 0, 0),
                           send=-1, side_to_move=1,
                           winnable=(0, 0), global_winner=1)
        self.assertTrue(uttt.is_terminal(s))
        self.assertEqual(uttt.result(s), LOSS)      # side to move (P1) lost
        self.assertEqual(uttt.end_reason(s), "line")

    def test_result_is_a_win_from_the_winner_s_own_perspective(self):
        s = uttt.UtttState(marks=(0, 0), status=(1, 1, 1, 0, 0, 0, 0, 0, 0),
                           send=-1, side_to_move=0,
                           winnable=(0, 0), global_winner=1)
        self.assertEqual(uttt.result(s), WIN)

    def test_early_draw_when_no_global_line_remains_winnable(self):
        # Every board decided such that no line is winnable by either player,
        # but empty cells would still exist under a naive rule.
        status = (1, 2, 1,
                  2, 1, 2,
                  2, 2, 3)
        s = uttt.initial_state()
        s = uttt.UtttState(marks=s.marks, status=status, send=-1,
                           side_to_move=0,
                           winnable=uttt.winnable_masks(status),
                           global_winner=uttt.global_winner_of(status))
        self.assertEqual(s.global_winner, 0, "no line is owned outright")
        self.assertEqual(s.winnable, (0, 0))
        self.assertTrue(uttt.is_terminal(s))
        self.assertEqual(uttt.result(s), DRAW)
        self.assertEqual(uttt.end_reason(s), "early_draw")

    def test_winnable_masks_agree_with_recomputation_on_every_transition(self):
        # A cached derived field whose incremental update drifts would corrupt
        # terminal detection silently, so check it against a from-scratch value.
        rng = random.Random(5)
        for _ in range(60):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                self.assertEqual(s.winnable, uttt.winnable_masks(s.status))
                self.assertEqual(s.global_winner,
                                 uttt.global_winner_of(s.status))
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))

    def test_move_string_round_trips(self):
        for m in range(81):
            self.assertEqual(uttt.str_to_move(uttt.move_to_str(m)), m)


class UtttInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(uttt, random.Random(11), n_games=200, max_plies=100)

    def test_no_game_exceeds_81_plies_and_cells_never_vacate(self):
        rng = random.Random(13)
        for _ in range(100):
            s = uttt.initial_state()
            plies = 0
            occupied = 0
            while not uttt.is_terminal(s):
                total = bin(s.marks[0] | s.marks[1]).count("1")
                self.assertEqual(total, occupied)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))
                occupied += 1
                plies += 1
            self.assertLessEqual(plies, 81)

    def test_players_never_occupy_the_same_cell(self):
        rng = random.Random(17)
        for _ in range(100):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                self.assertEqual(s.marks[0] & s.marks[1], 0)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))

    def test_no_move_is_ever_offered_in_a_decided_board(self):
        rng = random.Random(19)
        for _ in range(100):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                for m in uttt.legal_moves(s):
                    self.assertEqual(s.status[m // 9], 0)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))


if __name__ == "__main__":
    unittest.main()
