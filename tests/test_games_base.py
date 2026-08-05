import random
import unittest

from games.base import WIN, DRAW, LOSS, ConformanceError, check_conformance


class _ToyGame:
    """Minimal conforming game: count from 0 to 4, mover at 4 loses."""

    NAME = "toy"

    @staticmethod
    def initial_state():
        return (0, 0)  # (count, side_to_move)

    @staticmethod
    def legal_moves(s):
        return [] if s[0] >= 4 else [1, 2]

    @staticmethod
    def apply_move(s, m):
        return (s[0] + m, 1 - s[1])

    @staticmethod
    def is_terminal(s):
        return s[0] >= 4

    @staticmethod
    def result(s):
        return LOSS

    @staticmethod
    def end_reason(s):
        return "exhausted"

    @staticmethod
    def move_to_str(m):
        return str(m)

    @staticmethod
    def str_to_move(text):
        return int(text)


def _side_of(s):
    return s[1]


class ConformanceTest(unittest.TestCase):
    def test_conforming_game_passes(self):
        check_conformance(_ToyGame, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_terminal_disagreeing_with_empty_moves(self):
        class Broken(_ToyGame):
            @staticmethod
            def is_terminal(s):
                return s[0] >= 3  # terminal while moves remain

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_bad_move_string_round_trip(self):
        class Broken(_ToyGame):
            @staticmethod
            def str_to_move(text):
                return 99

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_side_not_alternating(self):
        class Broken(_ToyGame):
            @staticmethod
            def apply_move(s, m):
                return (s[0] + m, s[1])  # side never flips

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_result_outside_scale(self):
        class Broken(_ToyGame):
            @staticmethod
            def result(s):
                return -7.0

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_non_string_end_reason(self):
        class Broken(_ToyGame):
            @staticmethod
            def end_reason(s):
                return 42

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_apply_move_rejecting_a_legal_move(self):
        class Broken(_ToyGame):
            @staticmethod
            def apply_move(s, m):
                raise KeyError("bad move")

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_missing_or_empty_name(self):
        class NoName(object):
            """Delegates to _ToyGame's functions without inheriting its
            class attributes, so NAME is genuinely absent rather than
            merely overridden."""
            initial_state = staticmethod(_ToyGame.initial_state)
            legal_moves = staticmethod(_ToyGame.legal_moves)
            apply_move = staticmethod(_ToyGame.apply_move)
            is_terminal = staticmethod(_ToyGame.is_terminal)
            result = staticmethod(_ToyGame.result)
            end_reason = staticmethod(_ToyGame.end_reason)
            move_to_str = staticmethod(_ToyGame.move_to_str)
            str_to_move = staticmethod(_ToyGame.str_to_move)

        self.assertFalse(hasattr(NoName, "NAME"))
        with self.assertRaises(ConformanceError):
            check_conformance(NoName, random.Random(1), n_games=20, side_of=_side_of)

        class EmptyName(_ToyGame):
            NAME = ""

        with self.assertRaises(ConformanceError):
            check_conformance(EmptyName, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_game_exceeding_ply_bound(self):
        class Endless(_ToyGame):
            @staticmethod
            def legal_moves(s):
                return [0]  # never progresses

            @staticmethod
            def is_terminal(s):
                return False

        with self.assertRaises(ConformanceError):
            check_conformance(Endless, random.Random(1), n_games=1,
                              max_plies=50, side_of=_side_of)


if __name__ == "__main__":
    unittest.main()
