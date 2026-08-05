import random
import unittest

from agents import alpha_beta_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation as iso


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class AlphaBetaTest(unittest.TestCase):
    def setUp(self):
        self.agent = alpha_beta_agent.make(isolation_eval.evaluate)

    def test_returns_a_legal_move(self):
        s = iso.initial_state()
        ctx = SearchContext(0.5, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertIn(move, iso.legal_moves(s))

    def test_records_the_depth_it_reached(self):
        ctx = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertIsNotNone(ctx.depth_reached)
        self.assertGreaterEqual(ctx.depth_reached, 1)

    def test_expands_nodes_and_reports_them(self):
        ctx = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertGreater(ctx.nodes, 0)
        self.assertEqual(ctx.simulations, 0, "alpha-beta runs no simulations")

    def test_deeper_budget_reaches_deeper(self):
        shallow = SearchContext(0.02, 100000)
        deep = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), shallow, random.Random(1))
        self.agent(iso, iso.initial_state(), deep, random.Random(1))
        self.assertGreaterEqual(deep.depth_reached, shallow.depth_reached)

    def test_takes_an_immediate_win_when_one_exists(self):
        # P0 at (2,2); P1 at (0,0) with its only escapes blocked, so any P0 move
        # that does not free P1 wins immediately. Verify AB reports a proven win.
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=0)
        self.assertEqual(iso.legal_moves(
            iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=1)), [])
        ctx = SearchContext(1.0, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        after = iso.apply_move(s, move)
        self.assertTrue(iso.is_terminal(after), "should end the game at once")

    def test_beats_the_heuristic_agent_more_often_than_not(self):
        # The whole point of search: same evaluator, deeper look. If Alpha-Beta
        # does not beat the one-ply agent, either the search or the sign is wrong.
        from agents import heuristic_agent
        heur = heuristic_agent.make(isolation_eval.evaluate)
        wins = 0
        games = 20
        for seed in range(games):
            rng = random.Random(seed)
            s = iso.initial_state()
            ab_side = seed % 2
            ab = alpha_beta_agent.make(isolation_eval.evaluate)
            while not iso.is_terminal(s):
                actor = ab if s.side_to_move == ab_side else heur
                d = decide(actor, iso, s, 0.05, 100000, rng)
                s = iso.apply_move(s, d.move)
            if s.side_to_move != ab_side:
                wins += 1
        self.assertGreaterEqual(wins, 14,
                           "alpha-beta won %d/%d against one-ply" % (wins, games))

    def test_the_returned_move_matches_a_search_limited_to_the_reported_depth(self):
        s = iso.initial_state()
        for budget in (0.01, 0.05, 0.2):
            d = decide(self.agent, iso, s, budget, 10 ** 9, random.Random(1))
            self.assertIsNotNone(d.depth)
            reference = alpha_beta_agent.make(isolation_eval.evaluate,
                                             max_depth=d.depth)
            ctx = SearchContext(60.0, 10 ** 9)
            expected = reference(iso, s, ctx, random.Random(1))
            self.assertEqual(ctx.depth_reached, d.depth)
            self.assertEqual(
                d.move, expected,
                "budget %s reported depth %s but returned a move that a clean "
                "depth-%s search does not produce - a partial iteration leaked"
                % (budget, d.depth, d.depth))

    def test_the_table_persists_across_decisions(self):
        # A generous budget and a fixed max_depth make this depth-controlled
        # rather than time-controlled: the only thing that can change the node
        # count between the two searches of the same position is whatever the
        # table already knows.
        depth = 6
        s0 = iso.initial_state()
        agent = alpha_beta_agent.make(isolation_eval.evaluate, max_depth=depth)

        ctx0 = SearchContext(60.0, 10 ** 9)
        move0 = agent(iso, s0, ctx0, random.Random(1))
        s1 = iso.apply_move(s0, move0)

        ctx1 = SearchContext(60.0, 10 ** 9)
        agent(iso, s1, ctx1, random.Random(1))

        fresh = alpha_beta_agent.make(isolation_eval.evaluate, max_depth=depth)
        ctx_fresh = SearchContext(60.0, 10 ** 9)
        fresh(iso, s1, ctx_fresh, random.Random(1))

        self.assertLess(
            ctx1.nodes, ctx_fresh.nodes,
            "a second decision from the same agent should need fewer nodes "
            "than a fresh agent on the same position, because its table "
            "already holds work from the previous decision (%d vs %d nodes)"
            % (ctx1.nodes, ctx_fresh.nodes))

    def test_a_saturated_table_keeps_reporting_the_cap(self):
        tiny = alpha_beta_agent.make(isolation_eval.evaluate, max_entries=64)
        s = iso.initial_state()
        capped_once = False
        for _ in range(5):
            ctx = SearchContext(0.5, 100000)
            move = tiny(iso, s, ctx, random.Random(1))
            if ctx.memory_capped:
                capped_once = True
            elif capped_once:
                self.fail("memory cap stopped being reported on a later "
                          "decision, but a full table is never evicted from")
            s = iso.apply_move(s, move)
        self.assertTrue(capped_once,
                        "a 64-entry table must saturate within a few decisions")

    def test_discards_an_incomplete_iteration(self):
        # A clock that expires partway through the first deepening still yields a
        # legal move, and the move is not tagged normal.
        clock = FakeClock()

        class Tight(SearchContext):
            def should_stop(self):
                clock.advance(0.005)
                return SearchContext.should_stop(self)

        ctx = Tight(0.01, 100000, check_every=1, clock=clock)
        s = iso.initial_state()
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertIn(move, iso.legal_moves(s))

    def test_memory_cap_is_reported(self):
        tiny = alpha_beta_agent.make(isolation_eval.evaluate, max_entries=8)
        ctx = SearchContext(0.3, 100000)
        tiny(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.memory_capped,
                        "an 8-entry table must fill and report the cap")

    def test_tagged_time_limited_under_a_very_tight_budget(self):
        s = iso.initial_state()
        d = decide(self.agent, iso, s, 0.0005, 100000, random.Random(1))
        self.assertIn(d.tag, (MoveTag.TIME_LIMITED, MoveTag.MEMORY_LIMITED))
        self.assertIn(d.move, iso.legal_moves(s))


if __name__ == "__main__":
    unittest.main()
