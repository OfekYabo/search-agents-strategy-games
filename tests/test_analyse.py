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


class DepthComplianceLengthTest(unittest.TestCase):
    def test_search_depth_ignores_rows_without_a_depth(self):
        moves = [
            {"game": "ataxx", "config": "hard", "agent": "alpha_beta",
             "depth": "3", "elapsed_s": "0.1", "time_budget_s": "0.1"},
            {"game": "ataxx", "config": "hard", "agent": "mcts",
             "depth": "", "elapsed_s": "0.1", "time_budget_s": "0.1"},
        ]
        t = analyse.search_depth(moves)
        self.assertIn(("ataxx", "hard", "alpha_beta"), t)
        self.assertNotIn(("ataxx", "hard", "mcts"), t)
        self.assertEqual(t[("ataxx", "hard", "alpha_beta")]["max_depth"], 3)

    def test_budget_compliance_is_a_ratio_of_elapsed_to_budget(self):
        moves = [
            {"game": "uttt", "config": "hard", "agent": "mcts", "depth": "",
             "elapsed_s": "0.050", "time_budget_s": "0.100"},
            {"game": "uttt", "config": "hard", "agent": "mcts", "depth": "",
             "elapsed_s": "0.150", "time_budget_s": "0.100"},
        ]
        e = analyse.budget_compliance(moves)[("uttt", "hard", "mcts")]
        self.assertAlmostEqual(e["mean_ratio"], 1.0)
        self.assertAlmostEqual(e["max_ratio"], 1.5)
        self.assertEqual(e["moves"], 2)

    def test_budget_compliance_skips_a_zero_budget(self):
        moves = [{"game": "uttt", "config": "hard", "agent": "mcts",
                  "depth": "", "elapsed_s": "0.1", "time_budget_s": "0"}]
        self.assertEqual(analyse.budget_compliance(moves), {})

    def test_game_length_reports_end_reasons(self):
        rows = [
            {"game": "ataxx", "config": "easy", "plies": "10",
             "end_reason": "eliminated"},
            {"game": "ataxx", "config": "easy", "plies": "20",
             "end_reason": "board_full"},
            {"game": "ataxx", "config": "easy", "plies": "30",
             "end_reason": "eliminated"},
        ]
        e = analyse.game_length(rows)[("ataxx", "easy")]
        self.assertAlmostEqual(e["mean_plies"], 20.0)
        self.assertAlmostEqual(e["median_plies"], 20.0)
        self.assertEqual(e["end_reasons"]["eliminated"], 2)


class BudgetResponseTest(unittest.TestCase):
    def test_points_are_sorted_by_ascending_budget(self):
        rows = [
            {"game": "ataxx", "config": "hard", "agent_first": "a",
             "agent_second": "b", "winner": "first"},
            {"game": "ataxx", "config": "easy", "agent_first": "a",
             "agent_second": "b", "winner": "second"},
            {"game": "ataxx", "config": "main", "agent_first": "a",
             "agent_second": "b", "winner": "first"},
        ]
        budgets = {"ataxx": {"hard": 0.1, "main": 0.5, "easy": 2.0}}
        points = analyse.budget_response(rows, budgets)[("ataxx", "a")]
        self.assertEqual([p["config"] for p in points],
                         ["hard", "main", "easy"])
        self.assertEqual([p["budget_s"] for p in points], [0.1, 0.5, 2.0])

    def test_each_point_carries_a_confidence_interval(self):
        rows = [{"game": "uttt", "config": "main", "agent_first": "a",
                 "agent_second": "b", "winner": "first"}]
        points = analyse.budget_response(rows, {"uttt": {"main": 0.5}})
        point = points[("uttt", "a")][0]
        self.assertAlmostEqual(point["score"], 1.0)
        self.assertLessEqual(point["ci_low"], 1.0)
        self.assertEqual(point["games"], 1)


class BuildAnalysisTest(unittest.TestCase):
    def _data(self):
        games = [
            {"game_id": "g1", "game": "ataxx", "config": "hard",
             "time_budget_s": "0.1", "max_nodes": "50000",
             "max_entries": "200000", "agent_first": "mcts",
             "agent_second": "heuristic", "winner": "second", "plies": "12",
             "end_reason": "eliminated", "seed": "1", "workers": "1"},
        ]
        moves = [
            {"game_id": "g1", "ply": "0", "agent": "mcts", "side": "first",
             "tag": "time-limited", "elapsed_s": "0.1", "nodes": "",
             "simulations": "200", "depth": "", "move": "x",
             "legal_move_count": "20"},
        ]
        return games, moves

    def test_document_has_every_documented_top_level_key(self):
        games, moves = self._data()
        doc = analyse.build_analysis(games, moves, label="test")
        for key in ("meta", "score_table", "head_to_head", "budget_response",
                    "simulations_per_root", "search_depth",
                    "budget_compliance", "game_length", "tag_distribution",
                    "first_move_advantage"):
            self.assertIn(key, doc)

    def test_meta_records_the_label_and_the_grid_shape(self):
        games, moves = self._data()
        meta = analyse.build_analysis(games, moves, label="v1")["meta"]
        self.assertEqual(meta["label"], "v1")
        self.assertEqual(meta["games_total"], 1)
        self.assertEqual(meta["games"], ["ataxx"])
        self.assertEqual(meta["budgets"], {"ataxx": {"hard": 0.1}})

    def test_join_moves_attaches_game_and_budget(self):
        games, moves = self._data()
        joined = analyse.join_moves(games, moves)
        self.assertEqual(joined[0]["game"], "ataxx")
        self.assertEqual(joined[0]["config"], "hard")
        self.assertEqual(joined[0]["time_budget_s"], "0.1")

    def test_join_moves_drops_orphans_rather_than_crashing(self):
        games, moves = self._data()
        moves.append(dict(moves[0], game_id="missing"))
        self.assertEqual(len(analyse.join_moves(games, moves)), 1)

    def test_document_is_json_serialisable_and_sorted(self):
        import json
        games, moves = self._data()
        doc = analyse.build_analysis(games, moves, label="x")
        text = json.dumps(doc, sort_keys=True, indent=2)
        self.assertEqual(json.loads(text)["meta"]["label"], "x")


if __name__ == "__main__":
    unittest.main()
