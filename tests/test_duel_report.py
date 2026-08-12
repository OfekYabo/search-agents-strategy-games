import unittest

from experiments import duel_report


def _games(new_wins_first, new_wins_second, losses=0):
    """new_wins_first: v3 seated first and won. new_wins_second: v3 seated
    second and won. Pooling both is what makes the cell a matched pair."""
    rows = []
    base = {"game": "ataxx", "config": "main", "agent": "mcts", "trial": "0",
            "game_id": "g"}
    for _ in range(new_wins_first):
        rows.append(dict(base, first_version="v3", second_version="v2",
                         winner="first"))
    for _ in range(new_wins_second):
        rows.append(dict(base, first_version="v2", second_version="v3",
                         winner="second"))
    for _ in range(losses):
        rows.append(dict(base, first_version="v3", second_version="v2",
                         winner="second"))
    return rows


class ScoringTest(unittest.TestCase):
    def test_score_is_from_the_new_version_point_of_view(self):
        entry = duel_report.score_for(_games(3, 3, losses=2), "v3")[()]
        self.assertEqual((entry["wins"], entry["losses"]), (6, 2))
        self.assertAlmostEqual(entry["score"], 0.75)

    def test_seat_orders_are_pooled_not_double_counted(self):
        entry = duel_report.score_for(_games(5, 5), "v3")[()]
        self.assertEqual(entry["games"], 10)
        self.assertAlmostEqual(entry["score"], 1.0)

    def test_a_win_for_the_old_version_counts_against_the_new_one(self):
        rows = [{"game": "ataxx", "config": "main", "agent": "mcts",
                 "first_version": "v2", "second_version": "v3",
                 "winner": "first"}]
        entry = duel_report.score_for(rows, "v3")[()]
        self.assertEqual((entry["wins"], entry["losses"]), (0, 1))

    def test_grouping_splits_by_the_requested_keys(self):
        rows = _games(2, 0) + [dict(g, agent="heuristic")
                               for g in _games(0, 0, losses=2)]
        table = duel_report.score_for(rows, "v3", ("agent",))
        self.assertEqual(table[("mcts",)]["wins"], 2)
        self.assertEqual(table[("heuristic",)]["losses"], 2)


class VerdictTest(unittest.TestCase):
    def test_a_wide_interval_is_not_resolved(self):
        entry = duel_report.score_for(_games(3, 3, losses=2), "v3")[()]
        self.assertEqual(duel_report._verdict(entry), "not resolved")

    def test_a_clear_win_reads_as_stronger(self):
        entry = duel_report.score_for(_games(60, 60, losses=20), "v3")[()]
        self.assertEqual(duel_report._verdict(entry), "**stronger**")

    def test_a_clear_loss_reads_as_weaker(self):
        entry = duel_report.score_for(_games(10, 10, losses=100), "v3")[()]
        self.assertEqual(duel_report._verdict(entry), "**WEAKER**")


class RenderTest(unittest.TestCase):
    META = {"versions": ["v2", "v3"], "rng_streams": "per_side",
            "rng_note": "Both seats use independent streams."}

    def test_unfilled_slots_render_callouts(self):
        text = duel_report.render(_games(5, 5), [], self.META)
        for section_id in duel_report.SECTION_IDS:
            self.assertIn("COMMENTARY NEEDED: %s" % section_id, text)

    def test_the_rng_note_reaches_the_method_section(self):
        text = duel_report.render(_games(5, 5), [], self.META)
        self.assertIn("Both seats use independent streams.", text)

    def test_empty_run_does_not_crash(self):
        self.assertIn("No games found",
                      duel_report.render([], [], self.META))

    def test_search_volume_is_reported_per_version(self):
        games = _games(1, 0)
        games[0]["game_id"] = "g1"
        moves = [{"game_id": "g1", "version": "v3", "nodes": "",
                  "simulations": "400", "legal_move_count": "20"},
                 {"game_id": "g1", "version": "v2", "nodes": "",
                  "simulations": "200", "legal_move_count": "20"}]
        text = duel_report.render(games, moves, self.META)
        self.assertIn("Search volume", text)
        self.assertIn("20.0", text)     # v3: 400/20 sims per root
        self.assertIn("10.0", text)     # v2: 200/20


if __name__ == "__main__":
    unittest.main()
