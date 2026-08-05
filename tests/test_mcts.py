import dataclasses
import math
import random
import unittest

from agents import mcts_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import ataxx_eval, isolation_eval, uttt_eval
from games import ataxx, isolation as iso, uttt


def _random_midgame(game, plies, seed):
    """A state reached by up to `plies` random legal moves, stopping early if
    the game ends first."""
    rng = random.Random(seed)
    s = game.initial_state()
    for _ in range(plies):
        if game.is_terminal(s):
            break
        s = game.apply_move(s, rng.choice(game.legal_moves(s)))
    return s


def _ataxx_cell(r, c):
    return r * 7 + c


def _ataxx_mask(*cells):
    m = 0
    for c in cells:
        m |= 1 << c
    return m


class MctsTest(unittest.TestCase):
    def setUp(self):
        self.agent = mcts_agent.make(isolation_eval.evaluate)

    def test_returns_a_legal_move(self):
        s = iso.initial_state()
        ctx = SearchContext(0.2, 100000)
        self.assertIn(self.agent(iso, s, ctx, random.Random(1)),
                      iso.legal_moves(s))

    def test_runs_simulations_and_reports_them_not_nodes(self):
        ctx = SearchContext(0.2, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertGreater(ctx.simulations, 0)
        self.assertEqual(ctx.nodes, 0, "MCTS counts simulations, not nodes")

    def test_a_larger_budget_buys_more_simulations(self):
        small = SearchContext(0.05, 100000)
        large = SearchContext(0.4, 100000)
        self.agent(iso, iso.initial_state(), small, random.Random(1))
        self.agent(iso, iso.initial_state(), large, random.Random(1))
        self.assertGreater(large.simulations, small.simulations)

    def test_is_essentially_never_tagged_normal(self):
        # Anytime by construction: it consumes whatever budget it is given, so
        # the normal tag is an Alpha-Beta phenomenon, not an MCTS one.
        d = decide(self.agent, iso, iso.initial_state(), 0.1, 100000,
                   random.Random(1))
        self.assertEqual(d.tag, MoveTag.TIME_LIMITED)

    def test_node_cap_is_reported(self):
        tiny = mcts_agent.make(isolation_eval.evaluate, max_nodes=4)
        ctx = SearchContext(0.2, 4)
        tiny(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.memory_capped)

    def test_takes_an_immediate_win_when_one_exists(self):
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=0)
        ctx = SearchContext(0.5, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertTrue(iso.is_terminal(iso.apply_move(s, move)))

    def test_beats_the_random_agent_convincingly(self):
        from agents import random_agent
        wins = 0
        games = 20
        for seed in range(games):
            rng = random.Random(seed)
            s = iso.initial_state()
            mcts_side = seed % 2
            agent = mcts_agent.make(isolation_eval.evaluate)
            while not iso.is_terminal(s):
                actor = agent if s.side_to_move == mcts_side else random_agent.choose
                d = decide(actor, iso, s, 0.03, 100000, rng)
                s = iso.apply_move(s, d.move)
            if s.side_to_move != mcts_side:
                wins += 1
        self.assertGreaterEqual(wins, 15,
                                "MCTS won only %d/%d against random" % (wins, games))

    def test_rollout_rewards_stay_inside_the_unit_interval(self):
        rng = random.Random(2)
        for _ in range(200):
            r = mcts_agent._rollout(iso, iso.initial_state(), rng,
                                    isolation_eval.evaluate, 0.25, 8, 40)
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)

    def test_default_exploration_constant_is_root_two(self):
        # UCB1's constant is only meaningful for rewards in [0, 1].
        self.assertAlmostEqual(mcts_agent.DEFAULT_EXPLORATION, math.sqrt(2))

    def test_the_cap_comes_from_construction_not_the_context(self):
        # A small construction-time cap must still govern even when ctx
        # carries a wildly larger max_nodes.
        tiny = mcts_agent.make(isolation_eval.evaluate, max_nodes=4)
        huge_ctx = SearchContext(0.2, 10 ** 9)
        tiny(iso, iso.initial_state(), huge_ctx, random.Random(1))
        self.assertTrue(huge_ctx.memory_capped,
                        "a small max_nodes must cap the tree regardless of "
                        "ctx.max_nodes")

        # A (default, effectively huge) construction-time cap must not be
        # overridden by a tiny ctx.max_nodes - this is the regression this
        # test exists to catch: mcts_agent used to fall back to
        # ctx.max_nodes whenever its own max_nodes was left at the default.
        roomy = mcts_agent.make(isolation_eval.evaluate)
        tiny_ctx = SearchContext(0.05, 1)
        roomy(iso, iso.initial_state(), tiny_ctx, random.Random(1))
        self.assertFalse(tiny_ctx.memory_capped,
                         "ctx.max_nodes=1 must not cap a 200000-node tree")


class CrossGameTest(unittest.TestCase):
    """MCTS on Ataxx and UTTT, not just Isolation - see Finding 2 of the
    branch review: nothing previously verified PASS handling, rollout
    termination under Ataxx's no-progress rule, or basic legality on either
    game."""

    def test_returns_a_legal_move_on_ataxx(self):
        s = _random_midgame(ataxx, 10, seed=5)
        agent = mcts_agent.make(ataxx_eval.evaluate)
        ctx = SearchContext(0.1, 100000)
        move = agent(ataxx, s, ctx, random.Random(1))
        self.assertIn(move, ataxx.legal_moves(s))

    def test_returns_a_legal_move_on_uttt(self):
        s = _random_midgame(uttt, 10, seed=7)
        agent = mcts_agent.make(uttt_eval.evaluate)
        ctx = SearchContext(0.1, 100000)
        move = agent(uttt, s, ctx, random.Random(1))
        self.assertIn(move, uttt.legal_moves(s))

    def test_handles_a_pass_only_position_on_ataxx(self):
        # Same construction as test_ataxx.py's
        # test_a_player_with_no_move_passes_rather_than_losing: P1 has a
        # single piece walled in by P0 pieces at every distance <= 2.
        p1 = _ataxx_mask(_ataxx_cell(0, 0))
        p0_cells = [_ataxx_cell(r, c) for r in range(3) for c in range(3)
                    if (r, c) != (0, 0)]
        s = ataxx.AtaxxState(boards=(_ataxx_mask(*p0_cells), p1),
                             side_to_move=1, plies_since_progress=0)
        self.assertEqual(ataxx.legal_moves(s), [ataxx.PASS])

        agent = mcts_agent.make(ataxx_eval.evaluate)
        ctx = SearchContext(0.1, 100000)
        move = agent(ataxx, s, ctx, random.Random(1))
        self.assertEqual(move, ataxx.PASS)

    def test_rollouts_terminate_on_ataxx(self):
        # A generous budget from a position close to the no-progress limit:
        # the call must return promptly (not hang) and must have actually
        # run simulations.
        s = _random_midgame(ataxx, 10, seed=13)
        s = dataclasses.replace(
            s, plies_since_progress=max(0, ataxx.NO_PROGRESS_LIMIT - 3))
        agent = mcts_agent.make(ataxx_eval.evaluate)
        ctx = SearchContext(0.15, 100000)
        move = agent(ataxx, s, ctx, random.Random(1))
        self.assertIn(move, ataxx.legal_moves(s))
        self.assertGreater(ctx.simulations, 0)


if __name__ == "__main__":
    unittest.main()
