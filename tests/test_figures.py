import os
import shutil
import tempfile
import unittest

from experiments import figures


def _document():
    return {
        "meta": {"games": ["ataxx"], "configs": ["hard", "main"],
                 "agents": ["mcts", "heuristic"], "label": "t",
                 "games_total": 2,
                 "budgets": {"ataxx": {"hard": 0.1, "main": 0.5}}},
        "score_table": [
            {"game": "ataxx", "config": "hard", "agent": "mcts", "wins": 1,
             "draws": 0, "losses": 1, "games": 2, "score": 0.5,
             "ci_low": 0.1, "ci_high": 0.9},
            {"game": "ataxx", "config": "hard", "agent": "heuristic",
             "wins": 1, "draws": 0, "losses": 1, "games": 2, "score": 0.5,
             "ci_low": 0.1, "ci_high": 0.9},
        ],
        "head_to_head": [
            {"game": "ataxx", "config": "hard", "agent": "mcts",
             "opponent": "heuristic", "wins": 1, "draws": 0, "losses": 1,
             "games": 2, "score": 0.5, "ci_low": 0.1, "ci_high": 0.9},
            {"game": "ataxx", "config": "hard", "agent": "heuristic",
             "opponent": "mcts", "wins": 1, "draws": 0, "losses": 1,
             "games": 2, "score": 0.5, "ci_low": 0.1, "ci_high": 0.9},
        ],
        "budget_response": [
            {"game": "ataxx", "agent": "mcts", "points": [
                {"config": "hard", "budget_s": 0.1, "score": 0.35,
                 "ci_low": 0.27, "ci_high": 0.44, "games": 120},
                {"config": "main", "budget_s": 0.5, "score": 0.39,
                 "ci_low": 0.31, "ci_high": 0.48, "games": 120}]},
        ],
        "simulations_per_root": [
            {"game": "ataxx", "config": "hard", "agent": "mcts", "moves": 10,
             "mean_simulations": 410.6, "median_per_root": 23.5,
             "p5_per_root": 3.9, "pct_below_floor": 20.1, "verdict": "viable"},
            {"game": "ataxx", "config": "main", "agent": "mcts", "moves": 10,
             "mean_simulations": 3142.1, "median_per_root": 90.3,
             "p5_per_root": 36.9, "pct_below_floor": 0.0, "verdict": "ample"},
        ],
    }


class FiguresTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_writes_the_four_required_figures(self):
        written = figures.render_all(_document(), self.dir)
        names = sorted(os.path.basename(p) for p in written)
        self.assertEqual(names, ["fig-budget-response.svg",
                                 "fig-head-to-head.svg",
                                 "fig-score-by-agent.svg",
                                 "fig-sims-per-root.svg"])

    def test_svg_output_is_byte_identical_across_runs(self):
        # matplotlib writes a <dc:date> into SVG metadata and hashes element
        # ids per process. Both must be pinned or the report is never
        # reproducible.
        second = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, second)
        figures.render_all(_document(), self.dir)
        figures.render_all(_document(), second)
        for name in sorted(os.listdir(self.dir)):
            with open(os.path.join(self.dir, name), "rb") as h:
                a = h.read()
            with open(os.path.join(second, name), "rb") as h:
                b = h.read()
            self.assertEqual(a, b, "%s is not reproducible" % name)

    def test_no_date_metadata_is_embedded(self):
        figures.render_all(_document(), self.dir)
        with open(os.path.join(self.dir, "fig-score-by-agent.svg")) as h:
            self.assertNotIn("dc:date", h.read())


if __name__ == "__main__":
    unittest.main()
