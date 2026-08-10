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


class RunMetaTest(unittest.TestCase):
    def _document(self):
        with open(_fixture_path()) as handle:
            return json.load(handle)

    def test_absent_file_is_not_an_error(self):
        self.assertEqual(report.load_run_meta("/nonexistent.json"), {})

    def test_method_section_says_so_when_metadata_is_missing(self):
        text = report.render(self._document(), {}, [], run_meta={})
        self.assertIn("not recorded by this run", text)

    def test_reconstructed_metadata_is_labelled_as_such(self):
        meta = {"source": "reconstructed", "python": "3.10.12",
                "mcts_rollout": {"epsilon": 1.0, "sample_k": 1,
                                 "rollout_depth": 10}}
        text = report.render(self._document(), {}, [], run_meta=meta)
        self.assertIn("reconstructed", text)
        self.assertIn("3.10.12", text)

    def test_the_v1_metadata_file_records_the_rollout_parameters(self):
        # The one parameter the CSVs cannot supply, and the one whose absence
        # caused D4 and drove the F3 rewrite.
        path = os.path.join(os.path.dirname(__file__), os.pardir,
                            "results", "raw", "run_meta.json")
        meta = report.load_run_meta(path)
        self.assertEqual(meta["source"], "reconstructed")
        self.assertEqual(meta["mcts_rollout"],
                         {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10})


class NoMirroredRowsTest(unittest.TestCase):
    def _document(self):
        with open(_fixture_path()) as handle:
            return json.load(handle)

    def test_flat_tables_list_each_pairing_once(self):
        """A record and its mirror carry the same information: complementary
        score, reversed W-D-L. They belong in a matrix, where reading a row
        scans one agent against the field, but in a flat table they are pure
        duplication."""
        text = report.render(self._document(), {}, [])
        extras = text.split("### E1. Full head-to-head")[1]
        extras = extras.split("### E2.")[0]
        pairs = set()
        for line in extras.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 7 or cells[0] in ("game", "---"):
                continue
            key = (cells[0], cells[1], tuple(sorted((cells[2], cells[3]))))
            self.assertNotIn(key, pairs, "mirrored row for %s" % (key,))
            pairs.add(key)
        self.assertTrue(pairs)

    def test_the_matrix_still_shows_both_directions(self):
        # The matrix is the primary view and a half-empty one is harder to
        # read, so deduplication must not reach it.
        text = report.render(self._document(), {}, [])
        results = text.split("## 3. Results")[1].split("## 4.")[0]
        self.assertIn("| alpha_beta | - |", results)
        self.assertIn("| random |", results)


class MainWiringTest(unittest.TestCase):
    """render() taking run_meta as an argument was tested; main() finding the
    file was not, and it looked in the analysis directory rather than beside
    the CSVs, so the real report said "not recorded" while the file existed."""

    def _run(self, target, run_meta_path):
        report.main(["--analysis", _fixture_path(),
                     "--commentary", "/nonexistent-commentary.md",
                     "--out", os.path.join(target, "report.md"),
                     "--figures", os.path.join(target, "figures"),
                     "--run-meta", run_meta_path])
        with open(os.path.join(target, "report.md")) as handle:
            return handle.read()

    def test_main_loads_run_meta_from_the_raw_directory(self):
        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        path = os.path.join(os.path.dirname(__file__), os.pardir,
                            "results", "raw", "run_meta.json")
        text = self._run(target, path)
        self.assertIn("reconstructed", text)
        self.assertNotIn("not recorded by this run", text)

    def test_main_falls_back_to_not_recorded_when_absent(self):
        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        text = self._run(target, "/nonexistent-run-meta.json")
        self.assertIn("not recorded by this run", text)


class DepthFormattingTest(unittest.TestCase):
    def test_median_depth_is_formatted_consistently(self):
        with open(_fixture_path()) as handle:
            document = json.load(handle)
        text = report.render(document, {}, [])
        section = text.split("Alpha-Beta depth reached")[1].split("##")[0]
        for line in section.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 5 or cells[0] in ("game", "---"):
                continue
            self.assertRegex(cells[3], r"^\d+\.\d$",
                             "median depth %r is not formatted" % cells[3])

class RosterSectionTest(unittest.TestCase):
    def _document(self, **meta_extra):
        with open(_fixture_path()) as handle:
            document = json.load(handle)
        document["meta"].update(meta_extra)
        return document

    def test_roster_comes_from_the_analysis_not_from_run_meta(self):
        """run_meta is a claim about the run; the analysis roster is derived
        from games.csv and describes what actually ran."""
        document = self._document(
            roster={"mcts@v2": {"epsilon": 1.0}, "random@v2": {}},
            roster_conflicts=[])
        text = report.render(document, {}, [], run_meta={"source": "recorded"})
        self.assertIn("epsilon=1.0", text)
        self.assertIn("v2", text)

    def test_conflicting_parameters_produce_a_visible_warning(self):
        document = self._document(roster={"mcts@v2": {"epsilon": 1.0}},
                                  roster_conflicts=["mcts@v2"])
        text = report.render(document, {}, [])
        self.assertIn("WARNING", text)
        self.assertIn("mcts@v2", text)

    def test_absent_roster_renders_nothing_extra(self):
        document = self._document(roster={}, roster_conflicts=[])
        text = report.render(document, {}, [])
        self.assertNotIn("WARNING", text)

class SearchTimeSectionTest(unittest.TestCase):
    def _document(self, **meta_extra):
        with open(_fixture_path()) as handle:
            document = json.load(handle)
        document["meta"].update(meta_extra)
        return document

    def test_overview_reports_run_time_derived_from_the_data(self):
        text = report.render(self._document(), {}, [])
        self.assertIn("search time", text.lower())

    def test_wall_clock_is_shown_beside_it_when_recorded(self):
        text = report.render(self._document(), {}, [],
                             run_meta={"source": "recorded",
                                       "wall_clock_seconds": 35325})
        self.assertIn("9.81", text)

    def test_a_large_gap_between_wall_clock_and_search_is_flagged(self):
        """A wall clock much longer than the search time means the run stalled
        or was paused. Silently reporting only one of them would hide it."""
        document = self._document(total_search_seconds=3600.0)
        text = report.render(document, {}, [],
                             run_meta={"source": "recorded",
                                       "wall_clock_seconds": 7200})
        self.assertIn("STALL", text.upper())


if __name__ == "__main__":
    unittest.main()
