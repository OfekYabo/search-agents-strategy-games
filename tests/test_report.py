import json
import os
import shutil
import tempfile
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


def _fixture_path():
    return os.path.join(os.path.dirname(__file__), "fixtures",
                        "analysis_small.json")


class RenderTest(unittest.TestCase):
    def _document(self):
        with open(_fixture_path()) as handle:
            return json.load(handle)

    def test_every_section_id_appears_in_the_output(self):
        text = report.render(self._document(), {}, [])
        for section_id in report.SECTION_IDS:
            self.assertIn("COMMENTARY NEEDED: %s" % section_id, text)

    def test_filled_prose_replaces_the_callout(self):
        text = report.render(self._document(), {"overview": "Because."}, [])
        self.assertIn("Because.", text)
        self.assertNotIn("COMMENTARY NEEDED: overview", text)

    def test_extras_are_present_and_linked(self):
        text = report.render(self._document(), {}, [])
        self.assertIn("## Extras", text)
        self.assertIn("#e1-full-head-to-head", text)

    def test_output_contains_no_wall_clock_timestamp(self):
        import datetime
        text = report.render(self._document(), {}, [])
        self.assertNotIn(str(datetime.date.today().year) + "-", text)

    def test_rendering_twice_is_byte_identical(self):
        document = self._document()
        self.assertEqual(report.render(document, {}, []),
                         report.render(document, {}, []))

    def test_missing_top_level_key_fails_loudly(self):
        document = self._document()
        del document["score_table"]
        with self.assertRaises(KeyError):
            report.render(document, {}, [])


class EndToEndDeterminismTest(unittest.TestCase):
    def test_two_full_renders_are_byte_identical(self):
        first = tempfile.mkdtemp()
        second = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, first)
        self.addCleanup(shutil.rmtree, second)
        for target in (first, second):
            report.main([
                "--analysis", _fixture_path(),
                "--commentary", "/nonexistent-commentary.md",
                "--out", os.path.join(target, "report.md"),
                "--figures", os.path.join(target, "figures")])
        names = sorted(os.listdir(os.path.join(first, "figures")))
        self.assertEqual(names,
                         sorted(os.listdir(os.path.join(second, "figures"))))
        for relative in ["report.md"] + [
                os.path.join("figures", n) for n in names]:
            with open(os.path.join(first, relative), "rb") as h:
                a = h.read()
            with open(os.path.join(second, relative), "rb") as h:
                b = h.read()
            self.assertEqual(a, b, "%s is not reproducible" % relative)


if __name__ == "__main__":
    unittest.main()
