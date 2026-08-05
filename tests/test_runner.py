import csv
import os
import random
import shutil
import tempfile
import unittest

from agents import random_agent
from experiments import runner
from experiments.logger import GameLogger
from games import isolation
from games.base import DRAW, LOSS, WIN

CONFIG = {"name": "test", "time_budget_s": 1.0, "max_nodes": 1000}


class SeedTest(unittest.TestCase):
    def test_seed_is_deterministic(self):
        a = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        b = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertEqual(a, b)

    def test_seed_varies_with_every_input(self):
        base = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertNotEqual(base, runner.game_seed("ataxx", "random", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "mcts", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "hard", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "main", 4))


class PlayGameTest(unittest.TestCase):
    def _play(self, seed=1):
        return runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed,
        )

    def test_produces_a_decisive_result_within_the_ply_bound(self):
        record = self._play()
        self.assertIn(record.winner, ("first", "second"))
        self.assertLessEqual(record.plies, 23)
        self.assertEqual(record.end_reason, "no_moves")

    def test_records_one_move_row_per_ply(self):
        record = self._play()
        self.assertEqual(len(record.moves), record.plies)
        self.assertEqual([m.ply for m in record.moves], list(range(record.plies)))

    def test_agents_alternate_sides(self):
        record = self._play()
        self.assertEqual([m.side for m in record.moves[:4]], [0, 1, 0, 1])

    def test_records_legal_move_count_for_branching_factor_measurement(self):
        record = self._play()
        first = record.moves[0]
        self.assertEqual(first.legal_move_count, 11)

    def test_is_reproducible_from_its_seed(self):
        a = self._play(seed=42)
        b = self._play(seed=42)
        self.assertEqual([m.move for m in a.moves], [m.move for m in b.moves])
        self.assertEqual(a.winner, b.winner)

    def test_different_seeds_give_different_games(self):
        moves = set()
        for seed in range(8):
            moves.add(tuple(m.move for m in self._play(seed=seed).moves))
        self.assertGreater(len(moves), 1)

    def test_ply_cap_ends_the_game_and_is_reported(self):
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("a", "b"),
            CONFIG,
            seed=1,
            ply_cap=4,
        )
        self.assertEqual(record.plies, 4)
        self.assertEqual(record.end_reason, "ply_cap")


class _StubResultGame(object):
    """A game double whose result() is fixed, so _winner()'s mapping from
    "the side to move's outcome" onto "first"/"second" can be exercised for
    every case directly, without needing a real terminal position for each
    one."""

    def __init__(self, outcome):
        self._outcome = outcome

    def result(self, state):
        return self._outcome


class _StubState(object):
    def __init__(self, side_to_move):
        self.side_to_move = side_to_move


class WinnerMappingTest(unittest.TestCase):
    """_winner() decides who won every game in the study. Every other test
    touching .winner is satisfiable by an inverted (first/second-swapped)
    mapping too - see PlayGameTest and LoggerTest, none of which would catch
    the comparison being flipped. These tests call the module-private
    _winner() directly and are deliberately exhaustive, because this mapping
    is too consequential to leave to indirect coverage alone."""

    def test_winner_mapping_is_exhaustively_correct(self):
        cases = [
            (WIN, 0, "first"),
            (WIN, 1, "second"),
            (LOSS, 0, "second"),
            (LOSS, 1, "first"),
            (DRAW, 0, "draw"),
            (DRAW, 1, "draw"),
        ]
        for outcome, side_to_move, expected in cases:
            with self.subTest(outcome=outcome, side_to_move=side_to_move):
                game = _StubResultGame(outcome)
                state = _StubState(side_to_move)
                self.assertEqual(
                    runner._winner(game, state, "no_moves"), expected)

    def test_winner_agrees_with_replaying_the_logged_moves(self):
        for seed in range(6):
            record = runner.play_game(
                isolation,
                (random_agent.choose, random_agent.choose),
                ("random_a", "random_b"),
                CONFIG,
                seed=seed,
            )
            # Independently rebuild the terminal position from the logged
            # move strings alone, exercising the move_to_str/str_to_move
            # round trip end to end, then derive the winner from Isolation's
            # own rule (the side to move at a terminal state has no legal
            # move and has therefore lost) rather than from _winner itself.
            state = isolation.initial_state()
            for move in record.moves:
                state = isolation.apply_move(
                    state, isolation.str_to_move(move.move))
            self.assertTrue(isolation.is_terminal(state))
            expected = "first" if state.side_to_move == 1 else "second"
            self.assertEqual(record.winner, expected)


class _FlakyLegalMovesGame(object):
    """Wraps a real game module and forwards everything except
    legal_moves(), which works once and then raises.

    play_game() calls legal_moves() once per ply to record
    legal_move_count, and decide()'s error fallback calls it again to pick a
    replacement move. Failing on the second call makes both the agent and
    the fallback fail, which is exactly the case play_game must survive
    without ever calling apply_move(None).
    """

    def __init__(self, game):
        self._game = game
        self._calls = 0

    def legal_moves(self, state):
        self._calls += 1
        if self._calls > 1:
            raise RuntimeError("legal_moves exhausted")
        return self._game.legal_moves(state)

    def __getattr__(self, name):
        return getattr(self._game, name)


def _raising_agent(game, state, ctx, rng):
    raise RuntimeError("agent blew up")


def _illegal_move_agent(game, state, ctx, rng):
    """Returns a deliberately illegal move, standing in for a real
    Alpha-Beta/MCTS bug (stale transposition-table hit, off-by-one in
    best-move bookkeeping) that returns a wrong-but-plausible move without
    raising."""
    legal = game.legal_moves(state)
    return next(c for c in range(25) if c not in legal)


class ErrorHandlingTest(unittest.TestCase):
    def test_agent_returning_no_move_ends_the_game_as_an_error(self):
        wrapped = _FlakyLegalMovesGame(isolation)
        record = runner.play_game(
            wrapped,
            (_raising_agent, random_agent.choose),
            ("bad", "random_b"),
            CONFIG,
            seed=1,
        )
        self.assertEqual(record.end_reason, "agent_error")
        self.assertEqual(record.winner, "draw")
        self.assertEqual(record.moves[-1].tag, "error")
        self.assertEqual(record.moves[-1].move, "--")

    def test_illegal_move_ends_the_game_and_is_recorded(self):
        record = runner.play_game(
            isolation,
            (_illegal_move_agent, random_agent.choose),
            ("bad", "random_b"),
            CONFIG,
            seed=1,
        )
        self.assertEqual(record.end_reason, "illegal_move")
        self.assertEqual(record.winner, "draw")
        self.assertEqual(record.moves[-1].tag, "error")


class LoggerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.games_path = os.path.join(self.dir, "games.csv")
        self.moves_path = os.path.join(self.dir, "moves.csv")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def _write_one(self):
        logger = GameLogger(self.games_path, self.moves_path)
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed=1,
        )
        logger.write(record)
        logger.close()
        return record

    def test_writes_one_game_row_and_one_row_per_move(self):
        record = self._write_one()
        with open(self.games_path) as handle:
            games = list(csv.DictReader(handle))
        with open(self.moves_path) as handle:
            moves = list(csv.DictReader(handle))
        self.assertEqual(len(games), 1)
        self.assertEqual(len(moves), record.plies)
        self.assertEqual(games[0]["game"], "isolation")
        self.assertEqual(int(games[0]["plies"]), record.plies)

    def test_node_and_simulation_counts_are_separate_columns(self):
        self._write_one()
        with open(self.moves_path) as handle:
            header = next(csv.reader(handle))
        self.assertIn("nodes", header)
        self.assertIn("simulations", header)

    def test_completed_ids_supports_resume(self):
        record = self._write_one()
        logger = GameLogger(self.games_path, self.moves_path)
        self.assertIn(record.game_id, logger.completed_ids())
        logger.close()


if __name__ == "__main__":
    unittest.main()
