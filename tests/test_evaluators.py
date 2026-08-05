import random
import unittest

from evaluation import ataxx_eval, isolation_eval, uttt_eval
from games import ataxx, isolation, uttt

_CASES = ((ataxx, ataxx_eval), (uttt, uttt_eval), (isolation, isolation_eval))


class EvaluatorRangeTest(unittest.TestCase):
    def test_all_evaluators_stay_strictly_inside_the_reward_range(self):
        # Terminal rewards are exactly +-1, so an evaluation reaching that
        # magnitude would let a heuristic estimate outrank a real win.
        for game, module in _CASES:
            rng = random.Random(7)
            for _ in range(40):
                s = game.initial_state()
                while not game.is_terminal(s):
                    v = module.evaluate(game, s)
                    self.assertGreater(v, -1.0, game.NAME)
                    self.assertLess(v, 1.0, game.NAME)
                    s = game.apply_move(s, rng.choice(game.legal_moves(s)))

    def test_all_evaluators_are_antisymmetric(self):
        # The same position seen from the other side must invert. A fixed-player
        # evaluation would silently flip sign on alternate plies.
        for game, module in _CASES:
            rng = random.Random(9)
            for _ in range(20):
                s = game.initial_state()
                for _ in range(6):
                    if game.is_terminal(s):
                        break
                    flipped = _flip_side(s)
                    self.assertAlmostEqual(
                        module.evaluate(game, s),
                        -module.evaluate(game, flipped), places=9,
                        msg="%s evaluation is not antisymmetric" % game.NAME)
                    s = game.apply_move(s, rng.choice(game.legal_moves(s)))


def _flip_side(s):
    import dataclasses
    return dataclasses.replace(s, side_to_move=1 - s.side_to_move)


class AtaxxEvaluatorTest(unittest.TestCase):
    def test_prefers_having_more_pieces(self):
        few = ataxx.AtaxxState(boards=(1 << 0, (1 << 48) | (1 << 47) | (1 << 41)),
                               side_to_move=0, plies_since_progress=0)
        self.assertLess(ataxx_eval.evaluate(ataxx, few), 0.0)

    def test_prefers_less_exposed_pieces_at_equal_material(self):
        # Same count for both sides; one side's pieces sit in a corner cluster
        # (fewer empty neighbours), the other's in the open centre.
        corner = ataxx.AtaxxState(
            boards=((1 << 0) | (1 << 1) | (1 << 7),
                    (1 << 24) | (1 << 25) | (1 << 31)),
            side_to_move=0, plies_since_progress=0)
        self.assertGreater(ataxx_eval.evaluate(ataxx, corner), 0.0)


class UtttEvaluatorTest(unittest.TestCase):
    def test_prefers_owning_more_local_boards(self):
        status = (1, 1, 0, 0, 0, 0, 0, 0, 0)
        s = uttt.UtttState(marks=(0, 0), status=status, send=-1, side_to_move=0,
                           winnable=uttt.winnable_masks(status),
                           global_winner=uttt.global_winner_of(status))
        self.assertGreater(uttt_eval.evaluate(uttt, s), 0.0)

    def test_prefers_the_centre_board_over_an_edge_board(self):
        centre = (0, 0, 0, 0, 1, 0, 0, 0, 0)
        edge = (0, 1, 0, 0, 0, 0, 0, 0, 0)

        def value(status):
            s = uttt.UtttState(marks=(0, 0), status=status, send=-1,
                               side_to_move=0,
                               winnable=uttt.winnable_masks(status),
                               global_winner=uttt.global_winner_of(status))
            return uttt_eval.evaluate(uttt, s)

        self.assertGreater(value(centre), value(edge))


if __name__ == "__main__":
    unittest.main()
