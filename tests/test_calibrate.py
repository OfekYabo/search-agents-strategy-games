import unittest

from experiments import calibrate
from games import ataxx, isolation, uttt


class BudgetGridTest(unittest.TestCase):
    def test_every_game_has_three_configs_ordered_easy_main_hard(self):
        for name in ("isolation", "ataxx", "uttt"):
            grid = calibrate.BUDGETS[name]
            self.assertEqual(set(grid), {"easy", "main", "hard"})
            self.assertGreater(grid["easy"], grid["main"])
            self.assertGreater(grid["main"], grid["hard"])

    def test_easy_means_more_time_not_less(self):
        # The labels are easy to read backwards; pin the direction.
        self.assertEqual(calibrate.BUDGETS["ataxx"]["easy"], 2.0)
        self.assertEqual(calibrate.BUDGETS["ataxx"]["hard"], 0.1)


class AdherenceTest(unittest.TestCase):
    def test_reports_within_tolerance_for_a_well_behaved_agent(self):
        from agents import random_agent
        from evaluation import isolation_eval
        results = calibrate.check_budget_adherence(
            isolation, isolation_eval, [("random", lambda: random_agent.choose)],
            budgets=(0.05,), samples=3)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].within_tolerance)

    def test_flags_an_agent_that_overruns(self):
        import time

        def hog(game, state, ctx, rng):
            deadline = time.monotonic() + 0.30
            while time.monotonic() < deadline:
                pass
            return game.legal_moves(state)[0]

        from evaluation import isolation_eval
        results = calibrate.check_budget_adherence(
            isolation, isolation_eval, [("hog", lambda: hog)],
            budgets=(0.05,), samples=2)
        self.assertFalse(results[0].within_tolerance,
                         "an agent taking 0.30s on a 0.05s budget must be flagged")


class CapSweepTest(unittest.TestCase):
    def test_a_tiny_cap_produces_memory_limited_moves(self):
        from evaluation import isolation_eval
        results = calibrate.sweep_memory_caps(
            isolation, isolation_eval, budget=0.05, caps=(8, 10 ** 7), agent="alpha_beta")
        tiny = [r for r in results if r.cap == 8][0]
        huge = [r for r in results if r.cap == 10 ** 7][0]
        self.assertGreater(tiny.memory_limited_fraction, 0.0)
        self.assertEqual(huge.memory_limited_fraction, 0.0)


if __name__ == "__main__":
    unittest.main()
