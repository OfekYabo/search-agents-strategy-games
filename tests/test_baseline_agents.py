import random
import unittest

from agents import heuristic_agent, random_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class RandomAgentTest(unittest.TestCase):
    def test_returns_a_legal_move_and_reports_completion(self):
        s = isolation.initial_state()
        ctx = SearchContext(1.0, 100, clock=_Clock())
        move = random_agent.choose(isolation, s, ctx, random.Random(3))
        self.assertIn(move, isolation.legal_moves(s))
        self.assertTrue(ctx.finished)

    def test_is_deterministic_for_a_given_seed(self):
        s = isolation.initial_state()
        a = random_agent.choose(isolation, s, SearchContext(1.0, 100, clock=_Clock()),
                                random.Random(5))
        b = random_agent.choose(isolation, s, SearchContext(1.0, 100, clock=_Clock()),
                                random.Random(5))
        self.assertEqual(a, b)

    def test_is_tagged_normal_through_the_wrapper(self):
        s = isolation.initial_state()
        d = decide(random_agent.choose, isolation, s, 1.0, 100,
                   random.Random(0), clock=_Clock())
        self.assertEqual(d.tag, MoveTag.NORMAL)


class IsolationEvaluatorTest(unittest.TestCase):
    def test_returns_a_value_strictly_inside_the_reward_range(self):
        s = isolation.initial_state()
        v = isolation_eval.evaluate(isolation, s)
        self.assertGreater(v, -1.0)
        self.assertLess(v, 1.0)

    def test_prefers_greater_mobility_for_the_side_to_move(self):
        # Side 0 in the open centre; side 1 boxed into a corner.
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = isolation.IsolationState(blocked=blocked, pawns=(12, 0),
                                     side_to_move=0)
        self.assertGreater(isolation_eval.evaluate(isolation, s), 0.0)


class HeuristicAgentTest(unittest.TestCase):
    def test_picks_the_highest_scoring_move(self):
        target = isolation.legal_moves(isolation.initial_state())[2]

        def evaluate(game, state):
            # `state` here is the CHILD, whose side_to_move is the opponent, so
            # evaluate() scores it from the opponent's perspective and the agent
            # negates it. The move we want chosen must therefore look BAD here.
            return -0.9 if state.pawns[0] == target else 0.9

        agent = heuristic_agent.make(evaluate)
        s = isolation.initial_state()
        ctx = SearchContext(1.0, 100, clock=_Clock())
        self.assertEqual(agent(isolation, s, ctx, random.Random(1)), target)

    def test_reports_completion_when_every_move_was_evaluated(self):
        agent = heuristic_agent.make(lambda game, state: 0.0)
        ctx = SearchContext(1.0, 100, clock=_Clock())
        agent(isolation, isolation.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.finished)

    def test_returns_a_valid_move_when_cut_off_mid_evaluation(self):
        s = isolation.initial_state()

        class Stopped(SearchContext):
            def should_stop(self):
                return True

        ctx = Stopped(1.0, 100, clock=_Clock())
        agent = heuristic_agent.make(lambda game, state: 0.0)
        move = agent(isolation, s, ctx, random.Random(1))
        self.assertIn(move, isolation.legal_moves(s))
        self.assertFalse(ctx.finished)

    def test_breaks_ties_randomly_not_by_move_order(self):
        # All moves score equally; over many seeds more than one must be chosen,
        # otherwise the agent is silently inheriting legal_moves ordering.
        agent = heuristic_agent.make(lambda game, state: 0.5)
        s = isolation.initial_state()
        chosen = set()
        for seed in range(40):
            ctx = SearchContext(1.0, 100, clock=_Clock())
            chosen.add(agent(isolation, s, ctx, random.Random(seed)))
        self.assertGreater(len(chosen), 1)


if __name__ == "__main__":
    unittest.main()
