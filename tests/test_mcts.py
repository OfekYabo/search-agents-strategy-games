import math
import random
import unittest

from agents import mcts_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation as iso


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


if __name__ == "__main__":
    unittest.main()
