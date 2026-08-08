import unittest

from experiments import analyse


class BinomialTest(unittest.TestCase):
    def test_a_fair_split_is_not_significant(self):
        self.assertGreater(analyse.binomial_p(50, 100), 0.05)

    def test_a_lopsided_split_is_significant(self):
        self.assertLess(analyse.binomial_p(80, 100), 0.05)

    def test_is_symmetric(self):
        self.assertAlmostEqual(analyse.binomial_p(70, 100),
                               analyse.binomial_p(30, 100), places=12)

    def test_handles_the_degenerate_cases(self):
        self.assertEqual(analyse.binomial_p(0, 0), 1.0)
        self.assertLess(analyse.binomial_p(20, 20), 0.001)

    def test_does_not_overflow_at_the_real_grid_size(self):
        # The full grid is over 2000 games. A naive implementation summing
        # binomial coefficients and dividing by 2**n raises OverflowError here.
        p = analyse.binomial_p(1100, 2160)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)


class ScoreTableTest(unittest.TestCase):
    def _rows(self):
        return [
            {"game": "isolation", "config": "main", "agent_first": "a",
             "agent_second": "b", "winner": "first", "end_reason": "no_moves"},
            {"game": "isolation", "config": "main", "agent_first": "b",
             "agent_second": "a", "winner": "second", "end_reason": "no_moves"},
            {"game": "isolation", "config": "main", "agent_first": "a",
             "agent_second": "b", "winner": "draw", "end_reason": "no_moves"},
        ]

    def test_score_counts_a_draw_as_a_half(self):
        table = analyse.score_table(self._rows())
        self.assertAlmostEqual(table[("isolation", "main", "a")]["score"],
                               2.5 / 3.0)

    def test_reports_the_win_draw_loss_split_separately(self):
        entry = analyse.score_table(self._rows())[("isolation", "main", "a")]
        self.assertEqual((entry["wins"], entry["draws"], entry["losses"]),
                         (2, 1, 0))


class FirstMoveTest(unittest.TestCase):
    def test_excludes_draws_and_reports_how_many(self):
        rows = [{"winner": "first"}, {"winner": "second"},
                {"winner": "draw"}, {"winner": "draw"}]
        r = analyse.first_move_advantage(rows)
        self.assertEqual(r["decisive"], 2)
        self.assertEqual(r["excluded_draws"], 2)


class SimulationsPerRootTest(unittest.TestCase):
    def test_simulations_per_root_ignores_rows_without_simulations(self):
        rows = [
            {"game": "isolation", "config": "hard", "agent": "alpha_beta",
             "simulations": "", "legal_move_count": "10"},
            {"game": "isolation", "config": "hard", "agent": "mcts",
             "simulations": "50", "legal_move_count": "10"},
        ]
        table = analyse.simulations_per_root(rows)
        self.assertNotIn(("isolation", "hard", "alpha_beta"), table)
        self.assertIn(("isolation", "hard", "mcts"), table)

    def test_simulations_per_root_divides_by_legal_move_count(self):
        rows = [
            {"game": "isolation", "config": "hard", "agent": "mcts",
             "simulations": "10", "legal_move_count": "5"},
            {"game": "isolation", "config": "hard", "agent": "mcts",
             "simulations": "100", "legal_move_count": "10"},
        ]
        table = analyse.simulations_per_root(rows)
        entry = table[("isolation", "hard", "mcts")]
        # Each row's own ratio: 10/5 = 2 and 100/10 = 10. The median of the
        # two is 6.0. The ratio of the summed columns would be
        # (10+100)/(5+10) = 7.333..., a different number - this guards
        # against dividing the wrong pair of aggregates.
        self.assertAlmostEqual(entry["median_per_root"], 6.0)

    def test_headline_is_not_inflated_by_single_legal_move_positions(self):
        """A position with one legal move contributes a ratio equal to the
        entire simulation count, so a mean over per-row ratios is dragged
        above the ample threshold by endgame positions that involved no
        search decision at all. On the real Ataxx data 10-14% of MCTS
        decisions have exactly one legal move.
        """
        rows = [{"game": "ataxx", "config": "hard", "agent": "mcts",
                 "simulations": "400", "legal_move_count": "20"}
                for _ in range(9)]
        rows.append({"game": "ataxx", "config": "hard", "agent": "mcts",
                     "simulations": "400", "legal_move_count": "1"})
        entry = analyse.simulations_per_root(rows)[("ataxx", "hard", "mcts")]

        # The mean of the ratios is (9*20 + 400)/10 = 58.0, which reads as
        # "ample". Nine of those ten decisions actually saw 20 per root move.
        self.assertAlmostEqual(entry["mean_per_root"], 58.0)
        self.assertEqual(analyse._verdict(entry["mean_per_root"]), "ample")

        self.assertAlmostEqual(entry["median_per_root"], 20.0)
        self.assertEqual(analyse._verdict(entry["median_per_root"]), "viable")

    def test_pct_below_floor_counts_decisions_that_cannot_search(self):
        """The spec's floor is a property of each decision, not of the mean:
        a config whose average is comfortable can still spend a fifth of its
        decisions below the floor."""
        rows = [{"game": "uttt", "config": "hard", "agent": "mcts",
                 "simulations": "5", "legal_move_count": "1"}]
        rows += [{"game": "uttt", "config": "hard", "agent": "mcts",
                  "simulations": "9", "legal_move_count": "1"}]
        rows += [{"game": "uttt", "config": "hard", "agent": "mcts",
                  "simulations": "1000", "legal_move_count": "10"}
                 for _ in range(2)]
        entry = analyse.simulations_per_root(rows)[("uttt", "hard", "mcts")]
        # 5 and 9 are below the floor of 10; 100 and 100 are not.
        self.assertAlmostEqual(entry["pct_below_floor"], 50.0)
        self.assertAlmostEqual(entry["p5_per_root"], 5.0)



class WilsonIntervalTest(unittest.TestCase):
    def test_draws_count_as_half_a_win(self):
        r = analyse.wilson_interval(0, 10, 0)
        self.assertAlmostEqual(r["score"], 0.5)

    def test_zero_wins_gives_a_zero_lower_bound_and_a_known_upper(self):
        # Wilson for 0/10 at z=1.96 is [0, 0.27753...]. The textbook check.
        r = analyse.wilson_interval(0, 0, 10)
        self.assertAlmostEqual(r["score"], 0.0)
        self.assertAlmostEqual(r["ci_low"], 0.0)
        self.assertAlmostEqual(r["ci_high"], 0.2775402, places=6)

    def test_never_returns_a_negative_lower_bound(self):
        # The real Ataxx-hard head-to-head: 2 wins, 0 draws, 38 losses. The
        # normal approximation gives -0.018 here, which cannot be reported.
        r = analyse.wilson_interval(2, 0, 38)
        self.assertAlmostEqual(r["score"], 0.05)
        self.assertGreater(r["ci_low"], 0.0)
        self.assertAlmostEqual(r["ci_low"], 0.013822, places=5)
        self.assertAlmostEqual(r["ci_high"], 0.165040, places=5)

    def test_never_returns_an_upper_bound_above_one(self):
        r = analyse.wilson_interval(40, 0, 0)
        self.assertAlmostEqual(r["score"], 1.0)
        self.assertLessEqual(r["ci_high"], 1.0)

    def test_no_games_is_not_a_crash(self):
        r = analyse.wilson_interval(0, 0, 0)
        self.assertEqual(r["games"], 0)
        self.assertEqual(r["score"], 0.0)


class HeadToHeadTest(unittest.TestCase):
    def _rows(self):
        # Same pairing in both seat orders. "a" wins once from each seat,
        # and there is one draw.
        return [
            {"game": "ataxx", "config": "hard", "agent_first": "a",
             "agent_second": "b", "winner": "first"},
            {"game": "ataxx", "config": "hard", "agent_first": "b",
             "agent_second": "a", "winner": "second"},
            {"game": "ataxx", "config": "hard", "agent_first": "a",
             "agent_second": "b", "winner": "draw"},
        ]

    def test_pools_both_seat_orders(self):
        t = analyse.head_to_head(self._rows())
        entry = t[("ataxx", "hard", "a", "b")]
        self.assertEqual((entry["wins"], entry["draws"], entry["losses"]),
                         (2, 1, 0))

    def test_is_symmetric_between_the_two_agents(self):
        t = analyse.head_to_head(self._rows())
        entry = t[("ataxx", "hard", "b", "a")]
        self.assertEqual((entry["wins"], entry["draws"], entry["losses"]),
                         (0, 1, 2))

    def test_scores_are_complementary(self):
        t = analyse.head_to_head(self._rows())
        ab = t[("ataxx", "hard", "a", "b")]["score"]
        ba = t[("ataxx", "hard", "b", "a")]["score"]
        self.assertAlmostEqual(ab + ba, 1.0)

    def test_carries_a_confidence_interval(self):
        entry = analyse.head_to_head(self._rows())[("ataxx", "hard", "a", "b")]
        self.assertIn("ci_low", entry)
        self.assertLessEqual(entry["ci_low"], entry["score"])
        self.assertGreaterEqual(entry["ci_high"], entry["score"])

    def test_does_not_pair_an_agent_with_itself(self):
        rows = [{"game": "uttt", "config": "main", "agent_first": "a",
                 "agent_second": "a", "winner": "first"}]
        self.assertNotIn(("uttt", "main", "a", "a"), analyse.head_to_head(rows))


if __name__ == "__main__":
    unittest.main()
