import random
import unittest

from agents.base import Decision, MoveTag, SearchContext, decide


class FakeClock:
    """Manually advanced clock, so timing tests are deterministic."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _StubGame:
    @staticmethod
    def legal_moves(s):
        return [10, 20, 30]


class SearchContextTest(unittest.TestCase):
    def test_does_not_stop_before_budget_expires(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=1, clock=clock)
        clock.advance(0.5)
        self.assertFalse(ctx.should_stop())

    def test_stops_once_budget_expires(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=1, clock=clock)
        clock.advance(1.5)
        self.assertTrue(ctx.should_stop())

    def test_polls_clock_only_every_check_every_calls(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=4, clock=clock)
        clock.advance(99.0)
        # First three calls fall between polls and must not observe the clock.
        self.assertFalse(ctx.should_stop())
        self.assertFalse(ctx.should_stop())
        self.assertFalse(ctx.should_stop())
        self.assertTrue(ctx.should_stop())

    def test_counts_nodes(self):
        ctx = SearchContext(1.0, max_nodes=100, clock=FakeClock())
        for _ in range(7):
            ctx.note_node()
        self.assertEqual(ctx.nodes, 7)

    def test_records_memory_cap_and_completion_flags(self):
        ctx = SearchContext(1.0, max_nodes=100, clock=FakeClock())
        self.assertFalse(ctx.memory_capped)
        self.assertFalse(ctx.finished)
        ctx.hit_memory_cap()
        ctx.completed()
        self.assertTrue(ctx.memory_capped)
        self.assertTrue(ctx.finished)


class DecideTest(unittest.TestCase):
    def test_tags_normal_when_agent_reports_completion(self):
        def agent(game, state, ctx, rng):
            ctx.completed()
            return 20

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.NORMAL)
        self.assertEqual(d.move, 20)

    def test_tags_time_limited_when_agent_does_not_complete(self):
        def agent(game, state, ctx, rng):
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.TIME_LIMITED)

    def test_memory_outranks_time_when_both_apply(self):
        def agent(game, state, ctx, rng):
            ctx.hit_memory_cap()
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.MEMORY_LIMITED)

    def test_completion_outranks_memory(self):
        def agent(game, state, ctx, rng):
            ctx.hit_memory_cap()
            ctx.completed()
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.NORMAL)

    def test_exception_is_tagged_error_and_falls_back_to_a_legal_move(self):
        def agent(game, state, ctx, rng):
            raise ValueError("boom")

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.ERROR)
        self.assertIn(d.move, [10, 20, 30])
        self.assertIn("boom", d.error)

    def test_records_elapsed_time_and_node_count(self):
        clock = FakeClock()

        def agent(game, state, ctx, rng):
            ctx.note_node()
            ctx.note_node()
            clock.advance(0.25)
            ctx.completed()
            return 30

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=clock)
        self.assertEqual(d.nodes, 2)
        self.assertAlmostEqual(d.elapsed_s, 0.25)

    def test_decision_is_immutable(self):
        d = Decision(move=1, tag=MoveTag.NORMAL, elapsed_s=0.0, nodes=0,
                     simulations=None, depth=None, error=None)
        with self.assertRaises(Exception):
            d.move = 2


if __name__ == "__main__":
    unittest.main()
