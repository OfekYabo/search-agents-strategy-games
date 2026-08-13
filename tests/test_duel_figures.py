import os
import shutil
import tempfile
import unittest

from experiments import duel_figures


def _games():
    rows = []
    for config, budget in (("hard", "0.1"), ("main", "0.5"), ("easy", "2.0")):
        for agent in ("mcts", "alpha_beta"):
            for i in range(6):
                rows.append({
                    "game_id": "%s.%s.%s.%d" % (agent, config, "ataxx", i),
                    "game": "ataxx", "config": config, "agent": agent,
                    "time_budget_s": budget,
                    "first_version": "v3" if i % 2 else "v2",
                    "second_version": "v2" if i % 2 else "v3",
                    "winner": "first" if i % 3 else "second"})
    return rows


def _moves(games):
    rows = []
    for g in games:
        for version, work in (("v2", "100"), ("v3", "200")):
            rows.append({"game_id": g["game_id"], "version": version,
                         "nodes": "", "simulations": work,
                         "legal_move_count": "20"})
    return rows


META = {"versions": ["v2", "v3"]}


class FiguresTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_writes_all_three_figures(self):
        games = _games()
        written = duel_figures.render_all(games, _moves(games), META, self.dir)
        self.assertEqual(sorted(os.path.basename(p) for p in written),
                         ["fig-duel-budget.svg", "fig-duel-forest.svg",
                          "fig-duel-work.svg"])

    def test_the_work_figure_is_skipped_without_move_data(self):
        """A run whose moves.csv is missing must still get the score figures
        rather than losing the whole set."""
        written = duel_figures.render_all(_games(), [], META, self.dir)
        self.assertEqual(len(written), 2)

    def test_svg_output_is_byte_identical_across_runs(self):
        # matplotlib stamps a date into SVG metadata and salts element ids per
        # process. Importing experiments.figures pins both; without it these
        # files differ every run while looking identical.
        second = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, second)
        games = _games()
        duel_figures.render_all(games, _moves(games), META, self.dir)
        duel_figures.render_all(games, _moves(games), META, second)
        for name in sorted(os.listdir(self.dir)):
            with open(os.path.join(self.dir, name), "rb") as h:
                a = h.read()
            with open(os.path.join(second, name), "rb") as h:
                b = h.read()
            self.assertEqual(a, b, "%s is not reproducible" % name)

    def test_work_ratios_keep_versions_apart(self):
        games = _games()
        ratios = duel_figures.work_ratios(games, _moves(games))
        self.assertEqual(ratios[("mcts", "ataxx", "hard", "v2")], 100.0)
        self.assertEqual(ratios[("mcts", "ataxx", "hard", "v3")], 200.0)


if __name__ == "__main__":
    unittest.main()
