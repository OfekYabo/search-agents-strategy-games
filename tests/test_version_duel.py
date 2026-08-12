import os
import shutil
import tempfile
import unittest

from experiments import version_duel


class SeedingTest(unittest.TestCase):
    def test_both_seat_orders_share_a_base_seed(self):
        """The pair must differ only in seating. A seed that depended on which
        version sat first would make the two halves of a trial independent
        samples rather than a matched pair, throwing away the whole point of
        a paired design."""
        a = version_duel.duel_seed("ataxx", "main", "mcts", 7)
        b = version_duel.duel_seed("ataxx", "main", "mcts", 7)
        self.assertEqual(a, b)

    def test_seeds_differ_across_cells_and_trials(self):
        seen = {version_duel.duel_seed(g, c, a, t)
                for g in ("ataxx", "uttt") for c in ("hard", "easy")
                for a in ("mcts", "alpha_beta") for t in range(5)}
        self.assertEqual(len(seen), 2 * 2 * 2 * 5)

    def test_game_id_distinguishes_the_seat_orders(self):
        first = version_duel.duel_game_id("ataxx", "main", "mcts",
                                          ("v2", "v3"), 3)
        second = version_duel.duel_game_id("ataxx", "main", "mcts",
                                           ("v3", "v2"), 3)
        self.assertNotEqual(first, second)
        self.assertIn("v2-v3", first)
        self.assertIn("v3-v2", second)

    def test_random_is_excluded_from_the_roster(self):
        """A duel of the random agent against itself measures nothing about a
        version: it ignores the evaluator, the search and the budget."""
        self.assertNotIn("random", version_duel.AGENTS)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def _run(self, trials=1):
        return version_duel.run(("isolation",), ("hard",), ("heuristic",),
                                ("v2", "v3"), trials, self.dir)

    def test_plays_both_seat_orders(self):
        import csv
        self._run()
        with open(os.path.join(self.dir, "games.csv")) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual({(r["first_version"], r["second_version"])
                          for r in rows}, {("v2", "v3"), ("v3", "v2")})

    def test_every_move_records_which_version_made_it(self):
        import csv
        self._run()
        with open(os.path.join(self.dir, "moves.csv")) as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertEqual({r["version"] for r in rows}, {"v2", "v3"})

    def test_resume_skips_completed_games(self):
        """Nine hours of run must survive a stumble."""
        self.assertEqual(self._run(), 2)
        self.assertEqual(self._run(), 0)

    def test_no_duplicate_move_rows_after_resume(self):
        import csv
        self._run()
        self._run()
        with open(os.path.join(self.dir, "moves.csv")) as handle:
            keys = [(r["game_id"], r["ply"]) for r in csv.DictReader(handle)]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
