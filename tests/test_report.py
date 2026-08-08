import unittest

from experiments import report


class CommentaryTest(unittest.TestCase):
    TEXT = "\n".join([
        "Preamble that belongs to no section.",
        "",
        "<!-- section: overview -->",
        "This run answers the width question.",
        "",
        "<!-- section: results -->",
        "<!-- TODO -->",
        "",
    ])

    def test_parses_a_filled_section(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(sections["overview"],
                         "This run answers the width question.")

    def test_a_todo_only_section_counts_as_empty(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(sections["results"], "")

    def test_a_filled_section_renders_its_prose(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(report.commentary_for(sections, "overview"),
                         "This run answers the width question.")

    def test_an_empty_section_renders_a_visible_callout(self):
        sections = report.parse_commentary(self.TEXT)
        rendered = report.commentary_for(sections, "results")
        self.assertIn("COMMENTARY NEEDED", rendered)
        self.assertIn("results", rendered)

    def test_a_missing_section_renders_a_visible_callout(self):
        rendered = report.commentary_for({}, "limitations")
        self.assertIn("COMMENTARY NEEDED", rendered)

    def test_an_unknown_section_id_is_an_error(self):
        # A renamed report section must not silently orphan its prose.
        with self.assertRaises(ValueError):
            report.validate_commentary({"no-such-slot": "text"},
                                       report.SECTION_IDS)

    def test_every_known_id_validates(self):
        sections = dict((i, "x") for i in report.SECTION_IDS)
        report.validate_commentary(sections, report.SECTION_IDS)


class DerivedViewsTest(unittest.TestCase):
    def _document(self):
        return {"meta": {"games": ["ataxx"], "agents": ["mcts", "random"]},
                "head_to_head": [
                    {"game": "ataxx", "config": "hard", "agent": "mcts",
                     "opponent": "random", "wins": 30, "draws": 0,
                     "losses": 10, "games": 40, "score": 0.75},
                    {"game": "ataxx", "config": "easy", "agent": "mcts",
                     "opponent": "random", "wins": 10, "draws": 0,
                     "losses": 30, "games": 40, "score": 0.25}]}

    def test_pooling_sums_the_record_then_recomputes(self):
        pooled = report.pool_head_to_head(self._document())
        entry = pooled[("ataxx", "mcts", "random")]
        self.assertEqual((entry["wins"], entry["losses"]), (40, 40))
        self.assertAlmostEqual(entry["score"], 0.5)

    def test_pooling_is_not_the_mean_of_the_config_scores(self):
        document = self._document()
        document["head_to_head"][1]["wins"] = 0
        document["head_to_head"][1]["losses"] = 4
        document["head_to_head"][1]["games"] = 4
        document["head_to_head"][1]["score"] = 0.0
        entry = report.pool_head_to_head(document)[("ataxx", "mcts", "random")]
        # Summed: 30 wins of 44 games = 0.6818. Mean of scores: 0.375.
        self.assertAlmostEqual(entry["score"], 30.0 / 44.0, places=4)

    def test_vs_random_lists_every_agent_except_random(self):
        rows = report.vs_random(self._document())
        self.assertEqual([r["agent"] for r in rows], ["mcts"])
        self.assertEqual(rows[0]["game"], "ataxx")


if __name__ == "__main__":
    unittest.main()
