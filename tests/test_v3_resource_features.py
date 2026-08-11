import csv
import os
import random
import shutil
import tempfile
import unittest
from dataclasses import dataclass

from agents import v3
from agents.base import SearchContext
from evaluation.v3 import ataxx_eval
from experiments import runner, tournament
from experiments.logger import MOVE_COLUMNS
from games import isolation


class _TickClock(object):
    def __init__(self, step=1e-5):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now


@dataclass(frozen=True)
class _TinyState:
    depth: int
    side_to_move: int
    path: int


class _TinyGame:
    NAME = "tiny"

    @staticmethod
    def initial_state():
        return _TinyState(0, 0, 0)

    @staticmethod
    def legal_moves(state):
        return [] if state.depth >= 4 else [0, 1]

    @staticmethod
    def apply_move(state, move):
        return _TinyState(state.depth + 1, 1 - state.side_to_move,
                          state.path * 3 + move + 1)

    @staticmethod
    def result(state):
        return 0.0


def _zero_eval(game, state):
    return 0.0


class V3EvaluatorTest(unittest.TestCase):
    def test_ataxx_uses_the_screened_47_53_weights(self):
        self.assertAlmostEqual(ataxx_eval._MATERIAL_WEIGHT, 0.47)
        self.assertAlmostEqual(ataxx_eval._EXPOSURE_WEIGHT, 0.53)


class V3MctsReuseTest(unittest.TestCase):
    def test_subtree_is_reused_between_consecutive_decisions(self):
        agent = v3.build("mcts", _zero_eval)
        game = _TinyGame
        state = game.initial_state()

        first_ctx = SearchContext(0.02, v3.CAPS["max_nodes"],
                                  clock=_TickClock())
        our_move = agent(game, state, first_ctx, random.Random(7))
        after_ours = game.apply_move(state, our_move)
        # Pick one opponent reply. On this tiny tree the first search expands
        # the complete relevant layer, so the reply is already in the retained
        # subtree and the second decision must start warm.
        current = game.apply_move(after_ours, game.legal_moves(after_ours)[0])

        second_ctx = SearchContext(0.01, v3.CAPS["max_nodes"],
                                   clock=_TickClock())
        agent(game, current, second_ctx, random.Random(11))
        self.assertGreater(second_ctx.mcts_reused_nodes, 0)
        self.assertGreaterEqual(second_ctx.mcts_tree_nodes,
                                second_ctx.mcts_reused_nodes)


class V3AlphaBetaInstrumentationTest(unittest.TestCase):
    def test_tt_occupancy_and_hit_counters_are_exposed(self):
        from evaluation.v3 import isolation_eval
        agent = v3.build("alpha_beta", isolation_eval.evaluate)
        ctx = SearchContext(0.03, v3.CAPS["max_nodes"], clock=_TickClock())
        agent(isolation, isolation.initial_state(), ctx, random.Random(2))
        self.assertTrue(ctx._tracks_tt)
        self.assertGreater(ctx.tt_size, 0)
        self.assertGreaterEqual(ctx.tt_lookups, ctx.tt_hits)


class SeparateRngTest(unittest.TestCase):
    def _run(self, draws_by_first):
        seen = []

        def first(game, state, ctx, rng):
            for _ in range(draws_by_first):
                rng.random()
            ctx.completed()
            return game.legal_moves(state)[0]

        def second(game, state, ctx, rng):
            if not seen:
                seen.append(rng.random())
            ctx.completed()
            return game.legal_moves(state)[0]

        runner.play_game(
            isolation, (first, second), ("a", "b"),
            {"name": "rng", "time_budget_s": 1.0,
             "max_nodes": 50000, "max_entries": 200000},
            seed=123, ply_cap=2, separate_rng_streams=True)
        return seen[0]

    def test_one_side_consuming_more_randomness_does_not_shift_the_other(self):
        self.assertEqual(self._run(1), self._run(1000))


class SequentialTournamentTest(unittest.TestCase):
    def test_parallel_workers_are_rejected(self):
        directory = tempfile.mkdtemp()
        try:
            with self.assertRaises(ValueError):
                tournament.run([], directory, workers=2, version="v3")
        finally:
            shutil.rmtree(directory)


class InstrumentationColumnsTest(unittest.TestCase):
    def test_new_move_columns_are_appended(self):
        self.assertEqual(MOVE_COLUMNS[:11], [
            "game_id", "ply", "agent", "side", "tag", "elapsed_s",
            "nodes", "simulations", "depth", "move", "legal_move_count"])
        for column in ("tt_lookups", "tt_hits", "tt_size",
                       "mcts_tree_nodes", "mcts_reused_nodes"):
            self.assertIn(column, MOVE_COLUMNS)



class V3AnalysisExtrasTest(unittest.TestCase):
    def test_branching_and_throughput_are_derived_from_existing_move_rows(self):
        from experiments import analyse
        moves = [
            {"game": "ataxx", "config": "hard", "agent": "alpha_beta",
             "legal_move_count": "10", "elapsed_s": "0.1",
             "nodes": "100", "simulations": ""},
            {"game": "ataxx", "config": "hard", "agent": "alpha_beta",
             "legal_move_count": "30", "elapsed_s": "0.2",
             "nodes": "300", "simulations": ""},
            {"game": "ataxx", "config": "hard", "agent": "mcts",
             "legal_move_count": "20", "elapsed_s": "0.1",
             "nodes": "", "simulations": "50"},
        ]
        bf = analyse.branching_factor(moves)[("ataxx", "hard")]
        self.assertAlmostEqual(bf["mean"], 20.0)
        self.assertAlmostEqual(bf["median"], 20.0)
        tp = analyse.search_throughput(moves)
        self.assertAlmostEqual(
            tp[("ataxx", "hard", "alpha_beta")]["nodes_per_second"],
            400.0 / 0.3)
        self.assertAlmostEqual(
            tp[("ataxx", "hard", "mcts")]["simulations_per_second"],
            500.0)

    def test_main_game_rows_have_an_experiment_label(self):
        from agents import random_agent
        record = runner.play_game(
            isolation, (random_agent.choose, random_agent.choose),
            ("random", "random"),
            {"name": "hard", "time_budget_s": 0.001,
             "max_nodes": 50000, "max_entries": 200000},
            seed=4, ply_cap=2)
        self.assertEqual(record.experiment, "main_tournament")


if __name__ == "__main__":
    unittest.main()
