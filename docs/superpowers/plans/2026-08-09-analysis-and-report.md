# Analysis Extension and Deterministic Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `analyse.py` with the statistics the project's claims actually rest on, emit them as `analysis.json`, and build a `report.py` that renders a byte-deterministic report with hand-written prose merged in from a sidecar.

**Architecture:** `analyse.py` computes once and writes `results/analysis.json`; `report.py` reads only that JSON plus `docs/report/commentary.md` and renders Markdown + SVG. Computation never happens in the renderer, so every figure traces to one number, and the renderer is testable against a JSON fixture without running a tournament.

**Tech Stack:** Python 3.10 (code targets 3.8 syntax), stdlib `unittest`, matplotlib 3.5.1 + numpy 1.21.5 (analysis path only).

**Design doc:** `docs/superpowers/specs/2026-08-09-analysis-and-report-design.md`

## Global Constraints

- **The measurement path is untouched.** Do not modify `games/`, `agents/`, `evaluation/`, `experiments/runner.py`, `experiments/tournament.py`, `experiments/logger.py`, `experiments/calibrate.py`, `experiments/measure_branching.py`. They stay stdlib-only.
- **matplotlib and numpy may be imported only by `experiments/analyse.py` and `experiments/report.py`.**
- **Code style:** Python 3.8-compatible. Use `# type:` comments, not annotations. No f-strings — use `%` formatting, matching the existing files.
- **Tests:** stdlib `unittest`. Run with `python3 -m unittest discover -s tests`. The suite is at **178 passing** before this plan starts; it must never go red.
- **No `datetime.now()`**, `time.time()`, or any wall-clock read in any output path.
- **Existing public names must not change**: `load`, `binomial_p`, `score_table`, `tag_distribution`, `simulations_per_root`, `_verdict`, `first_move_advantage`, `VIABILITY_FLOOR`.
- **`first_move_advantage` returns the key `excluded_draws`** (not `draws_excluded`). The design doc says otherwise; the code is correct and wins.
- **Commit after every task.** No agent attribution, no `Co-Authored-By` trailers.

## File Structure

| File | Responsibility |
|---|---|
| `experiments/analyse.py` (modify) | All computation. Gains Wilson intervals, head-to-head, budget response, depth, compliance, game length, and `build_analysis()` + `--json`. |
| `experiments/report.py` (create) | Rendering only. Commentary merge, tables, section assembly. |
| `experiments/figures.py` (create) | matplotlib figure generation, isolated so `report.py` stays testable without a plotting backend. |
| `docs/report/commentary.md` (create) | Hand-written prose, keyed by section id. Tracked. |
| `results/raw/run_meta.json` (create) | Reconstructed v1 run metadata. Tracked. |
| `tests/test_analyse.py` (modify) | Statistics tests. |
| `tests/test_report.py` (create) | Commentary merge, section rendering, determinism. |
| `tests/fixtures/analysis_small.json` (create) | Fixed JSON fixture so the renderer is testable without a tournament. |

`figures.py` is separate from `report.py` because matplotlib is slow to import and awkward to test; keeping them apart lets the section-rendering tests run without touching a plotting backend.

---

### Task 1: Wilson score interval

**Files:**
- Modify: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `wilson_interval(wins, draws, losses, z=1.96) -> Dict[str, float]` with keys `score`, `ci_low`, `ci_high`, `games`. Used by Tasks 2, 3, 5.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analyse.py`:

```python
class WilsonIntervalTest(unittest.TestCase):
    def test_draws_count_as_half_a_win(self):
        r = analyse.wilson_interval(0, 10, 0)
        self.assertAlmostEqual(r["score"], 0.5)

    def test_zero_wins_gives_a_zero_lower_bound_and_a_known_upper(self):
        # Wilson for 0/10 at z=1.96 is [0, 0.27753...]. The textbook check.
        r = analyse.wilson_interval(0, 0, 10)
        self.assertAlmostEqual(r["score"], 0.0)
        self.assertAlmostEqual(r["ci_low"], 0.0)
        self.assertAlmostEqual(r["ci_high"], 0.277535, places=5)

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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_analyse.WilsonIntervalTest -v`
Expected: FAIL, `AttributeError: module 'experiments.analyse' has no attribute 'wilson_interval'`

- [ ] **Step 3: Implement**

Add to `experiments/analyse.py`, directly after `binomial_p`:

```python
def wilson_interval(wins, draws, losses, z=1.96):
    # type: (int, int, int, float) -> Dict[str, float]
    """Wilson score interval for the score rate, draws counting as half a win.

    Not the normal approximation. At the rates this study actually produces -
    Ataxx MCTS scored 2-0-38 against the heuristic - the normal approximation
    returns a lower bound of -0.018, which is not a reportable quantity. Wilson
    is closed-form, needs only `math`, and stays inside [0, 1] at the extremes
    where the interesting results live.
    """
    n = wins + draws + losses
    if n <= 0:
        return {"score": 0.0, "ci_low": 0.0, "ci_high": 0.0, "games": 0}
    p = (wins + 0.5 * draws) / float(n)
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return {"score": p,
            "ci_low": max(0.0, (centre - margin) / denominator),
            "ci_high": min(1.0, (centre + margin) / denominator),
            "games": n}
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest tests.test_analyse -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add experiments/analyse.py tests/test_analyse.py
git commit -m "Add Wilson score intervals for the score rate

The normal approximation returns a negative lower bound at the rates this
study produces - Ataxx MCTS scored 2-0-38 against the heuristic, where it
gives -0.018. Wilson is closed-form over math, needs no new dependency,
and stays inside [0, 1] at the extremes where the results live."
```

---

### Task 2: Head-to-head records

**Files:**
- Modify: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes: `wilson_interval` from Task 1.
- Produces: `head_to_head(rows) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]` keyed `(game, config, agent, opponent)`, each value having `wins`, `draws`, `losses`, `games`, `score`, `ci_low`, `ci_high`. Used by Tasks 5, 9.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analyse.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_analyse.HeadToHeadTest -v`
Expected: FAIL, `AttributeError: ... has no attribute 'head_to_head'`

- [ ] **Step 3: Implement**

Add to `experiments/analyse.py`, directly after `score_table`:

```python
def head_to_head(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent, opponent): record and score, pooled over both
    seat orders.

    The score_table figure is against the whole four-agent field, which
    conflates opponents - MCTS's 0.483 on Ataxx-easy averages 1.000 against
    the random agent with 0.000 against Alpha-Beta. Every claim the project
    actually makes is a head-to-head claim, so it needs its own table.
    """
    table = {}
    for row in rows:
        first, second = row["agent_first"], row["agent_second"]
        if first == second:
            continue
        for agent, opponent, seat in ((first, second, "first"),
                                      (second, first, "second")):
            key = (row["game"], row["config"], agent, opponent)
            e = table.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
            if row["winner"] == "draw":
                e["draws"] += 1
            elif row["winner"] == seat:
                e["wins"] += 1
            else:
                e["losses"] += 1
    for e in table.values():
        e.update(wilson_interval(e["wins"], e["draws"], e["losses"]))
    return table
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK, 188 tests or more.

- [ ] **Step 5: Commit**

```bash
git add experiments/analyse.py tests/test_analyse.py
git commit -m "Add head-to-head records pooled over both seat orders

The field score conflates opponents: MCTS's 0.483 on Ataxx-easy averages
1.000 against random with 0.000 against alpha_beta. Every claim in the
project is a head-to-head claim, and until now each one was computed by
hand outside the codebase."
```

---

### Task 3: Depth, budget compliance, and game length

**Files:**
- Modify: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces three functions used by Task 5:
  - `search_depth(moves) -> Dict[Tuple[str, str, str], Dict[str, Any]]` keyed `(game, config, agent)`, values `median_depth`, `max_depth`, `moves`.
  - `budget_compliance(moves) -> Dict[Tuple[str, str, str], Dict[str, Any]]` keyed `(game, config, agent)`, values `mean_ratio`, `p99_ratio`, `max_ratio`, `moves`.
  - `game_length(rows) -> Dict[Tuple[str, str], Dict[str, Any]]` keyed `(game, config)`, values `mean_plies`, `median_plies`, `games`, `end_reasons`.

The move rows passed to the first two must already carry `game`, `config` and `time_budget_s`, joined from `games.csv`. Task 5 does that join.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analyse.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_analyse.DepthComplianceLengthTest -v`
Expected: FAIL, `AttributeError: ... has no attribute 'search_depth'`

- [ ] **Step 3: Implement**

Add to `experiments/analyse.py`, after `simulations_per_root` and its helpers:

```python
def search_depth(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): depth reached. Alpha-Beta only in practice,
    since only it records a depth - MCTS's tree has no single depth."""
    buckets = {}
    for m in moves:
        raw = m.get("depth", "")
        if raw in (None, ""):
            continue
        key = (m["game"], m["config"], m["agent"])
        buckets.setdefault(key, []).append(int(raw))
    table = {}
    for key, values in buckets.items():
        values.sort()
        table[key] = {"median_depth": _median(values),
                      "max_depth": values[-1],
                      "moves": len(values)}
    return table


def budget_compliance(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): elapsed time as a fraction of the budget.

    This is instrument validation, not a result. A wall-clock budget that the
    agents systematically overrun would make every comparison in the study
    describe the overrun rather than the algorithms.
    """
    buckets = {}
    for m in moves:
        budget = float(m.get("time_budget_s") or 0.0)
        if budget <= 0:
            continue
        key = (m["game"], m["config"], m["agent"])
        buckets.setdefault(key, []).append(float(m["elapsed_s"]) / budget)
    table = {}
    for key, values in buckets.items():
        values.sort()
        table[key] = {"mean_ratio": sum(values) / len(values),
                      "p99_ratio": _percentile(values, 99),
                      "max_ratio": values[-1],
                      "moves": len(values)}
    return table


def game_length(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config): game length in plies and the end-reason split.

    Agent play and random self-play give very different lengths, and the
    original runtime estimate for the tournament was wrong by 2.5x because it
    used the random-play figure.
    """
    buckets = {}
    for row in rows:
        key = (row["game"], row["config"])
        e = buckets.setdefault(key, {"plies": [], "end_reasons": {}})
        e["plies"].append(int(row["plies"]))
        reason = row["end_reason"]
        e["end_reasons"][reason] = e["end_reasons"].get(reason, 0) + 1
    table = {}
    for key, e in buckets.items():
        plies = sorted(e["plies"])
        table[key] = {"mean_plies": sum(plies) / float(len(plies)),
                      "median_plies": _median(plies),
                      "games": len(plies),
                      "end_reasons": e["end_reasons"]}
    return table
```

Note `_median` and `_percentile` already exist from the D9 fix and take a **sorted** list.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add experiments/analyse.py tests/test_analyse.py
git commit -m "Surface search depth, budget compliance and game length

All three are derivable from the CSVs and none was reported. Budget
compliance is instrument validation rather than a result: a wall-clock
budget the agents systematically overran would make every comparison in
the study describe the overrun instead of the algorithms."
```

---

### Task 4: Budget response

**Files:**
- Modify: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes: `score_table` and `wilson_interval`.
- Produces: `budget_response(rows, budgets) -> Dict[Tuple[str, str], List[Dict[str, Any]]]` keyed `(game, agent)`, value a list of points sorted by ascending budget, each `{config, budget_s, score, ci_low, ci_high, games}`. Used by Tasks 5, 8, 9.
- `budgets` is `Dict[str, Dict[str, float]]` — `{game: {config: seconds}}` — produced by Task 5's `budgets_from_games`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_analyse.py`:

```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m unittest tests.test_analyse.BudgetResponseTest -v`
Expected: FAIL, `AttributeError: ... has no attribute 'budget_response'`

- [ ] **Step 3: Implement**

Add to `experiments/analyse.py`, after `head_to_head`:

```python
def budget_response(rows, budgets):
    # type: (List[Dict[str, Any]], Dict[str, Dict[str, float]]) -> Dict[Any, List[Dict[str, Any]]]
    """Per (game, agent): field score as a function of the time budget.

    Field score, not head-to-head, and deliberately: every agent faces the
    same four-agent pool, so the curves are comparable across agents. The
    head-to-head equivalent is derivable from head_to_head() by reading the
    three configs of one (game, agent, opponent) triple, and storing it twice
    would create two numbers that can disagree.
    """
    table = score_table(rows)
    out = {}
    for (game, config, agent), entry in table.items():
        budget = budgets.get(game, {}).get(config)
        if budget is None:
            continue
        point = {"config": config, "budget_s": budget,
                 "games": entry["games"]}
        point.update(wilson_interval(entry["wins"], entry["draws"],
                                     entry["losses"]))
        out.setdefault((game, agent), []).append(point)
    for points in out.values():
        points.sort(key=lambda p: p["budget_s"])
    return out
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add experiments/analyse.py tests/test_analyse.py
git commit -m "Add budget response - field score as a function of the budget

The direct answer to how each paradigm converts time into strength, and
the axis on which the degradation question is asked. Uses field score
because every agent faces the same pool, which makes the curves
comparable across agents."
```

---

### Task 5: Assemble `analysis.json`

**Files:**
- Modify: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Consumes: every function from Tasks 1-4.
- Produces:
  - `budgets_from_games(rows) -> Dict[str, Dict[str, float]]`
  - `join_moves(games_rows, moves_rows) -> List[Dict[str, Any]]` — move rows with `game`, `config`, `time_budget_s` merged in from their game row.
  - `build_analysis(games_rows, moves_rows, label="") -> Dict[str, Any]` — the full document.
  - `--json <path>` CLI flag on `main`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_analyse.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_analyse.BuildAnalysisTest -v`
Expected: FAIL, `AttributeError: ... has no attribute 'build_analysis'`

- [ ] **Step 3: Implement**

Add to `experiments/analyse.py`. Note every list is sorted before it goes in, so the JSON is stable:

```python
def budgets_from_games(rows):
    # type: (List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]
    out = {}
    for row in rows:
        out.setdefault(row["game"], {})[row["config"]] = float(
            row["time_budget_s"])
    return out


def join_moves(games_rows, moves_rows):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Attach game, config and time_budget_s to each move row.

    Move rows carry only a game_id, so anything grouped by game or config -
    and anything measured against the budget - needs this join first. Orphan
    move rows are dropped rather than raising: the crash-safe logger makes
    them impossible in a completed run, but an analysis should not be the
    thing that fails on a half-written file.
    """
    index = {}
    for row in games_rows:
        index[row["game_id"]] = row
    joined = []
    for move in moves_rows:
        game = index.get(move["game_id"])
        if game is None:
            continue
        merged = dict(move)
        merged["game"] = game["game"]
        merged["config"] = game["config"]
        merged["time_budget_s"] = game["time_budget_s"]
        joined.append(merged)
    return joined


def _round(value, places=6):
    # type: (Any, int) -> Any
    """Round floats at write time so platform float repr cannot leak into the
    JSON and break byte-for-byte determinism."""
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, dict):
        return dict((k, _round(v, places)) for k, v in value.items())
    if isinstance(value, list):
        return [_round(v, places) for v in value]
    return value


def build_analysis(games_rows, moves_rows, label=""):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]], str) -> Dict[str, Any]
    """The single source of truth for the report. Everything is computed here,
    once; report.py renders this and never recomputes."""
    joined = join_moves(games_rows, moves_rows)
    budgets = budgets_from_games(games_rows)

    scores = score_table(games_rows)
    h2h = head_to_head(games_rows)
    sims = simulations_per_root(joined)
    depth = search_depth(joined)
    compliance = budget_compliance(joined)
    lengths = game_length(games_rows)
    tags = tag_distribution(moves_rows)
    response = budget_response(games_rows, budgets)

    agents = sorted(set(
        [r["agent_first"] for r in games_rows]
        + [r["agent_second"] for r in games_rows]))

    doc = {
        "meta": {
            "label": label,
            "games_total": len(games_rows),
            "games": sorted(budgets),
            "configs": sorted(set(r["config"] for r in games_rows)),
            "agents": agents,
            "budgets": budgets,
        },
        "score_table": [
            dict(zip(("game", "config", "agent"), key),
                 wins=e["wins"], draws=e["draws"], losses=e["losses"],
                 **wilson_interval(e["wins"], e["draws"], e["losses"]))
            for key, e in sorted(scores.items())],
        "head_to_head": [
            dict(zip(("game", "config", "agent", "opponent"), key), **e)
            for key, e in sorted(h2h.items())],
        "budget_response": [
            {"game": key[0], "agent": key[1], "points": points}
            for key, points in sorted(response.items())],
        "simulations_per_root": [
            dict(zip(("game", "config", "agent"), key),
                 verdict=_verdict(e["median_per_root"]), **e)
            for key, e in sorted(sims.items())],
        "search_depth": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(depth.items())],
        "budget_compliance": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(compliance.items())],
        "game_length": [
            dict(zip(("game", "config"), key), **e)
            for key, e in sorted(lengths.items())],
        "tag_distribution": [
            {"agent": key[0], "tag": key[1], "count": count}
            for key, count in sorted(tags.items())],
        "first_move_advantage": first_move_advantage(games_rows),
    }
    return _round(doc)
```

Then wire the CLI. In `main`, **replace** the `--out` argument (it is declared at
`analyse.py:203` and never used) with `--json`, and write the file after the existing
printing:

```python
    parser.add_argument("--json", default="")
    parser.add_argument("--label", default="")
```

and at the end of `main`, before `return 0`:

```python
    if args.json:
        import json
        document = build_analysis(clean, moves, label=args.label)
        directory = os.path.dirname(args.json)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, "w") as handle:
            json.dump(document, handle, sort_keys=True, indent=2)
            handle.write("\n")
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Verify against the real run and confirm determinism**

```bash
python3 -m experiments.analyse --raw results/raw --json /tmp/a1.json --label v1-tournament > /tmp/t1.md
python3 -m experiments.analyse --raw results/raw --json /tmp/a2.json --label v1-tournament > /tmp/t2.md
cmp /tmp/a1.json /tmp/a2.json && echo "analysis.json is deterministic"
python3 -c "import json; d=json.load(open('/tmp/a1.json')); print('cells', len(d['score_table']), 'h2h', len(d['head_to_head']))"
```
Expected: `analysis.json is deterministic`, `cells 36 h2h 108`.

- [ ] **Step 6: Commit**

```bash
git add experiments/analyse.py tests/test_analyse.py
git commit -m "Emit analysis.json as the single source of truth for the report

Splits computation from presentation. Every figure and table in the
report now traces to one computation, and the renderer becomes testable
against a fixed JSON fixture without running a tournament.

Replaces the --out flag, which was declared and never used - figures were
intended from the start and never built. Figure output belongs to
report.py, and leaving --out here would give two modules a flag of the
same name with different meanings, one of which did nothing.

Floats are rounded at write time so platform float repr cannot leak in
and break byte-for-byte determinism."
```

---

### Task 6: Commentary sidecar parsing and merge

**Files:**
- Create: `experiments/report.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Consumes: nothing.
- Produces, used by Task 9:
  - `SECTION_IDS` — tuple of every valid commentary id, in report order.
  - `parse_commentary(text) -> Dict[str, str]`
  - `validate_commentary(sections, known_ids)` — raises `ValueError` on unknown ids.
  - `commentary_for(sections, section_id) -> str` — body, or the callout.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_report.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_report -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'experiments.report'`

- [ ] **Step 3: Implement**

Create `experiments/report.py`:

```python
"""Renders the report from analysis.json. Computes nothing.

Two kinds of content live here and they are kept strictly apart:

  - Generated: every table and figure, derived from analysis.json. Same input,
    byte-identical output, so the report can be regenerated for any run.
  - Interpretive: hand-written prose in docs/report/commentary.md, merged in
    by section id.

The generated report is disposable and must never be hand-edited. Prose lives
in the sidecar precisely so that regenerating is unconditionally safe - if
prose lived in the generated file, regeneration would either destroy it or
need round-trip parsing of a file that is supposed to be write-only.
"""
import re

# Report order. Adding a section here without adding its rendering, or
# renaming one without updating commentary.md, is caught by
# validate_commentary rather than silently dropping prose.
SECTION_IDS = (
    "overview",
    "method",
    "results",
    "budget-response",
    "search-volume",
    "instrument-validation",
    "game-characteristics",
    "limitations",
)

_SECTION_RE = re.compile(r"^<!--\s*section:\s*([a-z0-9-]+)\s*-->\s*$",
                         re.MULTILINE)


def parse_commentary(text):
    # type: (str) -> dict
    """Split the sidecar into {section_id: body}. A body consisting only of
    a TODO marker is treated as empty, so a placeholder reads as a gap rather
    than as prose."""
    sections = {}
    parts = _SECTION_RE.split(text)
    # parts[0] is the preamble before any marker; then (id, body) pairs.
    for index in range(1, len(parts) - 1, 2):
        body = parts[index + 1].strip()
        if body == "<!-- TODO -->":
            body = ""
        sections[parts[index]] = body
    return sections


def validate_commentary(sections, known_ids):
    # type: (dict, tuple) -> None
    unknown = sorted(set(sections) - set(known_ids))
    if unknown:
        raise ValueError(
            "commentary.md has sections matching no report slot: %s. "
            "Rename them or remove them - a renamed report section must not "
            "silently orphan its prose." % ", ".join(unknown))


def commentary_for(sections, section_id):
    # type: (dict, str) -> str
    body = sections.get(section_id, "")
    if not body:
        return "> **[COMMENTARY NEEDED: %s]**" % section_id
    return body
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add experiments/report.py tests/test_report.py
git commit -m "Add commentary sidecar parsing for the report

Prose lives in docs/report/commentary.md keyed by section id, never in the
generated report. That is what makes regeneration unconditionally safe:
prose inside the generated file would either be destroyed on regeneration
or need round-trip parsing of a file that is supposed to be write-only.

An id matching no report slot raises rather than being ignored, so
renaming a section cannot silently orphan its prose."
```

---

### Task 7: Figure module with determinism pinned

**Files:**
- Create: `experiments/figures.py`
- Create: `tests/test_figures.py`

**Interfaces:**
- Consumes: `analysis.json` structure from Task 5.
- Produces `render_all(document, out_dir) -> List[str]` returning the sorted list of written paths, and four private builders. Used by Task 9.

- [ ] **Step 1: Write the failing test**

Create `tests/test_figures.py`:

```python
import json
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m unittest tests.test_figures -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'experiments.figures'`

- [ ] **Step 3: Implement**

Create `experiments/figures.py`. The determinism pinning at the top is load-bearing:

```python
"""SVG figures for the report, rendered from analysis.json.

Kept separate from report.py so the section-rendering tests do not need a
plotting backend, and because matplotlib is slow to import.

DETERMINISM: matplotlib is not reproducible by default. It stamps a <dc:date>
into SVG metadata and salts element ids per process, so two runs over identical
data produce different bytes. Both are pinned below. Without that, the report's
whole "same input, same output" property is false and nobody notices, because
the figures still look right.
"""
import os

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "search-agents-strategy-games"

import matplotlib.pyplot as plt   # noqa: E402  (must follow use/rcParams)

_SAVE = {"format": "svg", "metadata": {"Date": None}, "bbox_inches": "tight"}
_AGENT_ORDER = ("alpha_beta", "mcts", "heuristic", "random")


def _agents(document):
    known = [a for a in _AGENT_ORDER if a in document["meta"]["agents"]]
    rest = [a for a in document["meta"]["agents"] if a not in _AGENT_ORDER]
    return known + sorted(rest)


def _configs_by_budget(document, game):
    budgets = document["meta"]["budgets"].get(game, {})
    return sorted(budgets, key=lambda c: budgets[c])


def _save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return path


def _score_by_agent(document, out_dir):
    games = document["meta"]["games"]
    agents = _agents(document)
    index = {}
    for row in document["score_table"]:
        index[(row["game"], row["config"], row["agent"])] = row
    fig, axes = plt.subplots(1, len(games), figsize=(5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        configs = _configs_by_budget(document, game)
        width = 0.8 / max(len(configs), 1)
        for offset, config in enumerate(configs):
            xs, ys, lo, hi = [], [], [], []
            for position, agent in enumerate(agents):
                row = index.get((game, config, agent))
                if row is None:
                    continue
                xs.append(position + offset * width)
                ys.append(row["score"])
                lo.append(row["score"] - row["ci_low"])
                hi.append(row["ci_high"] - row["score"])
            ax.bar(xs, ys, width=width, yerr=[lo, hi], capsize=2,
                   label="%.2fs" % document["meta"]["budgets"][game][config])
        ax.set_xticks([p + 0.4 - width / 2 for p in range(len(agents))])
        ax.set_xticklabels(agents, rotation=20, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_title(game)
        ax.set_ylabel("score rate" if column == 0 else "")
        ax.legend(fontsize="small", title="budget")
    fig.suptitle("Score by agent, with Wilson 95% intervals")
    return _save(fig, out_dir, "fig-score-by-agent.svg")


def _budget_response(document, out_dir):
    games = document["meta"]["games"]
    series = {}
    for row in document["budget_response"]:
        series.setdefault(row["game"], {})[row["agent"]] = row["points"]
    fig, axes = plt.subplots(1, len(games), figsize=(5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        for agent in _agents(document):
            points = series.get(game, {}).get(agent)
            if not points:
                continue
            xs = [p["budget_s"] for p in points]
            ys = [p["score"] for p in points]
            ax.plot(xs, ys, marker="o", label=agent)
            ax.fill_between(xs, [p["ci_low"] for p in points],
                            [p["ci_high"] for p in points], alpha=0.15)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("budget (s, log)")
        ax.set_ylabel("score rate" if column == 0 else "")
        ax.set_title(game)
        ax.legend(fontsize="small")
    fig.suptitle("Budget response: does more time buy strength?")
    return _save(fig, out_dir, "fig-budget-response.svg")


def _head_to_head(document, out_dir):
    games = document["meta"]["games"]
    agents = _agents(document)
    pooled = {}
    for row in document["head_to_head"]:
        key = (row["game"], row["agent"], row["opponent"])
        acc = pooled.setdefault(key, [0, 0, 0])
        acc[0] += row["wins"]
        acc[1] += row["draws"]
        acc[2] += row["losses"]
    fig, axes = plt.subplots(1, len(games), figsize=(4.5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        grid = []
        for me in agents:
            line = []
            for opponent in agents:
                acc = pooled.get((game, me, opponent))
                if me == opponent or acc is None:
                    line.append(float("nan"))
                else:
                    total = acc[0] + acc[1] + acc[2]
                    line.append((acc[0] + 0.5 * acc[1]) / total)
            grid.append(line)
        ax.imshow(grid, vmin=0.0, vmax=1.0, cmap="RdYlGn")
        ax.set_xticks(range(len(agents)))
        ax.set_xticklabels(agents, rotation=45, ha="right", fontsize="small")
        ax.set_yticks(range(len(agents)))
        ax.set_yticklabels(agents, fontsize="small")
        for r, line in enumerate(grid):
            for c, value in enumerate(line):
                if value == value:   # not NaN
                    ax.text(c, r, "%.3f" % value, ha="center", va="center",
                            fontsize="small")
        ax.set_title(game)
    fig.suptitle("Head-to-head score (row agent vs column opponent), "
                 "pooled over budgets")
    return _save(fig, out_dir, "fig-head-to-head.svg")


def _sims_per_root(document, out_dir):
    budgets = document["meta"]["budgets"]
    series = {}
    for row in document["simulations_per_root"]:
        budget = budgets.get(row["game"], {}).get(row["config"])
        if budget is None:
            continue
        series.setdefault(row["game"], []).append(
            (budget, row["median_per_root"]))
    fig, ax = plt.subplots(figsize=(6, 4))
    for game in document["meta"]["games"]:
        points = sorted(series.get(game, []))
        if not points:
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points],
                marker="o", label=game)
    ax.axhline(10.0, linestyle="--", linewidth=1, color="grey")
    ax.text(ax.get_xlim()[0], 11.0, "viability floor", fontsize="small",
            color="grey")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("budget (s, log)")
    ax.set_ylabel("median simulations per root move (log)")
    ax.set_title("MCTS search volume against the viability floor")
    ax.legend(fontsize="small")
    return _save(fig, out_dir, "fig-sims-per-root.svg")


def render_all(document, out_dir):
    # type: (dict, str) -> list
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    written = [
        _score_by_agent(document, out_dir),
        _budget_response(document, out_dir),
        _head_to_head(document, out_dir),
        _sims_per_root(document, out_dir),
    ]
    return sorted(written)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest tests.test_figures -v`
Expected: PASS. If `test_svg_output_is_byte_identical_across_runs` fails, the hashsalt or the `Date` metadata is not being applied — fix that rather than relaxing the test.

- [ ] **Step 5: Commit**

```bash
git add experiments/figures.py tests/test_figures.py
git commit -m "Add SVG figures with matplotlib determinism pinned

matplotlib is not reproducible by default: it stamps a dc:date into SVG
metadata and salts element ids per process, so two runs over identical
data produce different bytes. Both are pinned, and a test asserts byte
equality across two renders.

Without the pinning the report's same-input-same-output property would be
quietly false, and nobody would notice because the figures still look
correct - the same class of defect as D9."
```

---

### Task 8: Derived views — non-transitivity and every-agent-vs-random

**Files:**
- Modify: `experiments/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: the `head_to_head` list from `analysis.json`.
- Produces, used by Task 9:
  - `pool_head_to_head(document) -> Dict[Tuple[str, str, str], Dict[str, Any]]` keyed `(game, agent, opponent)`, pooled across configs by summing W/D/L then recomputing the score.
  - `vs_random(document) -> List[Dict[str, Any]]` sorted rows of every agent's pooled record against `random`.

These are derived at render time rather than stored, so there is only ever one head-to-head number in the JSON.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_report.py`:

```python
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
        # Averaging the two scores would give 0.5 as well here, so use an
        # asymmetric case: pooled is 40-0-40 = 0.5 either way. Check the
        # record is summed, which is what distinguishes the two methods.
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_report.DerivedViewsTest -v`
Expected: FAIL, `AttributeError: module 'experiments.report' has no attribute 'pool_head_to_head'`

- [ ] **Step 3: Implement**

Add to `experiments/report.py`:

```python
def pool_head_to_head(document):
    # type: (dict) -> dict
    """Pool head-to-head records across configs, keyed (game, agent, opponent).

    Sums wins/draws/losses and recomputes the score. NOT the mean of the three
    config scores: those are different numbers whenever the cells differ in
    size or in variance, and the summed record is the one with a defensible
    confidence interval.
    """
    pooled = {}
    for row in document["head_to_head"]:
        key = (row["game"], row["agent"], row["opponent"])
        acc = pooled.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
        acc["wins"] += row["wins"]
        acc["draws"] += row["draws"]
        acc["losses"] += row["losses"]
    for entry in pooled.values():
        total = entry["wins"] + entry["draws"] + entry["losses"]
        entry["games"] = total
        entry["score"] = ((entry["wins"] + 0.5 * entry["draws"]) / total
                          if total else 0.0)
    return pooled


def vs_random(document):
    # type: (dict) -> list
    """Every agent's pooled record against the random agent.

    A one-ply evaluator should crush a random opponent. On Isolation the
    heuristic scores only 0.750 against it, against 0.963 on UTTT - and
    Isolation is the designated control game, so a weak control belongs in
    instrument validation where it cannot hide behind an average.
    """
    pooled = pool_head_to_head(document)
    rows = []
    for (game, agent, opponent), entry in sorted(pooled.items()):
        if opponent != "random" or agent == "random":
            continue
        row = {"game": game, "agent": agent}
        row.update(entry)
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add experiments/report.py tests/test_report.py
git commit -m "Add pooled head-to-head and the vs-random control check

Pooling sums the record and recomputes rather than averaging the three
config scores, which are different numbers whenever the cells differ in
size or variance.

The vs-random view exists because a one-ply evaluator should crush a
random opponent, and on Isolation the heuristic manages only 0.750
against 0.963 on UTTT. Isolation is the designated control game, so that
belongs in instrument validation rather than averaged into a field score."
```

---

### Task 9: Render the report

**Files:**
- Modify: `experiments/report.py`
- Create: `docs/report/commentary.md`
- Create: `tests/fixtures/analysis_small.json`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: everything from Tasks 5-8.
- Produces: `render(document, sections, figure_names) -> str`, and `main(argv=None)` with flags `--analysis`, `--commentary`, `--out`, `--figures`, `--label`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_report.py`:

```python
import json
import os
import shutil
import tempfile


class RenderTest(unittest.TestCase):
    def _document(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures",
                            "analysis_small.json")
        with open(path) as handle:
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
```

- [ ] **Step 2: Create the fixture**

Generate it from the real run so the fixture is realistic, then trim it by hand to two games:

```bash
mkdir -p tests/fixtures
python3 -m experiments.analyse --raw results/raw --json tests/fixtures/analysis_small.json --label fixture > /dev/null
python3 - <<'PY'
import json
path = "tests/fixtures/analysis_small.json"
d = json.load(open(path))
keep = {"ataxx", "isolation"}
d["meta"]["games"] = sorted(keep)
d["meta"]["budgets"] = {k: v for k, v in d["meta"]["budgets"].items() if k in keep}
for key in ("score_table", "head_to_head", "budget_response",
            "simulations_per_root", "search_depth", "budget_compliance",
            "game_length"):
    d[key] = [r for r in d[key] if r["game"] in keep]
json.dump(d, open(path, "w"), sort_keys=True, indent=2)
PY
```

- [ ] **Step 3: Run the tests and verify they fail**

Run: `python3 -m unittest tests.test_report.RenderTest -v`
Expected: FAIL, `AttributeError: module 'experiments.report' has no attribute 'render'`

- [ ] **Step 4: Implement the renderer**

Add to `experiments/report.py`. Every section follows the same shape: a heading, generated
tables, an optional figure, then the commentary slot.

```python
def _table(headers, rows):
    # type: (list, list) -> str
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def _pct(value):
    return "%.1f%%" % value


def _score(row):
    return "%.3f [%.3f-%.3f]" % (row["score"], row["ci_low"], row["ci_high"])


def render(document, sections, figure_names):
    # type: (dict, dict, list) -> str
    meta = document["meta"]
    agents = meta["agents"]
    games = meta["games"]
    figures_present = set(figure_names)
    pooled = pool_head_to_head(document)

    def figure(name, caption):
        if name not in figures_present:
            return ""
        return "\n![%s](figures/%s)\n" % (caption, name)

    def slot(section_id):
        return "\n" + commentary_for(sections, section_id) + "\n"

    parts = []
    parts.append("# Tournament report: %s\n" % (meta["label"] or "unlabelled"))

    # 1. Overview
    parts.append("## 1. Overview\n")
    parts.append(_table(
        ["property", "value"],
        [["games played", meta["games_total"]],
         ["games", ", ".join(games)],
         ["configs", ", ".join(meta["configs"])],
         ["agents", ", ".join(agents)],
         ["error moves", document["tag_distribution"] and sum(
             r["count"] for r in document["tag_distribution"]
             if r["tag"] in ("error", "illegal_move", "agent_error")) or 0]]))
    parts.append(slot("overview"))

    # 2. Method for this run
    parts.append("## 2. Method for this run\n")
    parts.append(_table(
        ["game", "config", "budget (s)"],
        [[game, config, meta["budgets"][game][config]]
         for game in games
         for config in sorted(meta["budgets"][game],
                              key=lambda c: meta["budgets"][game][c])]))
    parts.append(slot("method"))

    # 3. Results
    parts.append("## 3. Results\n")
    for game in games:
        parts.append("\n**%s** - head-to-head, pooled over budgets "
                     "(row agent vs column opponent)\n" % game)
        rows = []
        for me in agents:
            line = [me]
            for opponent in agents:
                entry = pooled.get((game, me, opponent))
                line.append("-" if entry is None else "%.3f" % entry["score"])
            rows.append(line)
        parts.append(_table([""] + agents, rows))
    parts.append(figure("fig-head-to-head.svg", "Head-to-head"))
    parts.append(figure("fig-score-by-agent.svg", "Score by agent"))
    parts.append("\n**Non-transitivity check** - "
                 "every agent's pooled score against every other\n")
    parts.append(_table(
        ["game", "agent", "opponent", "score", "W-D-L"],
        [[g, a, o, "%.3f" % e["score"],
          "%d-%d-%d" % (e["wins"], e["draws"], e["losses"])]
         for (g, a, o), e in sorted(pooled.items())]))
    parts.append("\n→ Full per-config breakdown: [E1](#e1-full-head-to-head). "
                 "Full score table: [E2](#e2-full-score-table).\n")
    parts.append(slot("results"))

    # 4. Budget response
    parts.append("## 4. Budget response\n")
    for row in document["budget_response"]:
        parts.append("\n**%s / %s**\n" % (row["game"], row["agent"]))
        parts.append(_table(
            ["budget (s)", "config", "score", "games"],
            [[p["budget_s"], p["config"], _score(p), p["games"]]
             for p in row["points"]]))
    parts.append(figure("fig-budget-response.svg", "Budget response"))
    parts.append(slot("budget-response"))

    # 5. Search volume and viability
    parts.append("## 5. Search volume and viability\n")
    parts.append(_table(
        ["game", "config", "agent", "mean sims", "median /root", "p5 /root",
         "% below floor", "verdict"],
        [[r["game"], r["config"], r["agent"], "%.1f" % r["mean_simulations"],
          "%.1f" % r["median_per_root"], "%.1f" % r["p5_per_root"],
          _pct(r["pct_below_floor"]), r["verdict"]]
         for r in document["simulations_per_root"]]))
    parts.append("\n**Alpha-Beta depth reached**\n")
    parts.append(_table(
        ["game", "config", "agent", "median depth", "max depth"],
        [[r["game"], r["config"], r["agent"], r["median_depth"],
          r["max_depth"]] for r in document["search_depth"]]))
    parts.append(figure("fig-sims-per-root.svg", "Simulations per root move"))
    parts.append(slot("search-volume"))

    # 6. Instrument validation
    parts.append("## 6. Instrument validation\n")
    parts.append("\n**Budget compliance** (elapsed / budget)\n")
    parts.append(_table(
        ["game", "config", "agent", "mean", "p99", "max", "moves"],
        [[r["game"], r["config"], r["agent"], _pct(100 * r["mean_ratio"]),
          _pct(100 * r["p99_ratio"]), _pct(100 * r["max_ratio"]), r["moves"]]
         for r in document["budget_compliance"]]))
    parts.append("\n**Every agent against the random agent** - a one-ply "
                 "evaluator should dominate here; a weak control game shows "
                 "up as a low score\n")
    parts.append(_table(
        ["game", "agent", "score", "W-D-L"],
        [[r["game"], r["agent"], "%.3f" % r["score"],
          "%d-%d-%d" % (r["wins"], r["draws"], r["losses"])]
         for r in vs_random(document)]))
    fma = document["first_move_advantage"]
    parts.append("\n**First-move advantage** (decisive games only): "
                 "first %d, second %d, decisive %d, draws excluded %d, "
                 "p = %.4f\n" % (fma["first"], fma["second"], fma["decisive"],
                                 fma["excluded_draws"], fma["p"]))
    parts.append("\n→ Move-tag distribution: [E3](#e3-move-tag-distribution).\n")
    parts.append(slot("instrument-validation"))

    # 7. Game characteristics
    parts.append("## 7. Game characteristics\n")
    parts.append(_table(
        ["game", "config", "mean plies", "median plies", "games"],
        [[r["game"], r["config"], "%.1f" % r["mean_plies"],
          r["median_plies"], r["games"]] for r in document["game_length"]]))
    parts.append("\n→ End-reason breakdown: [E4](#e4-end-reasons).\n")
    parts.append(slot("game-characteristics"))

    # 8. Limitations
    parts.append("## 8. Limitations\n")
    parts.append("\nScores are Wilson 95% intervals. With %d games in the "
                 "smallest head-to-head cell, differences below roughly 0.15 "
                 "are not resolvable. A wall-clock budget makes the run one "
                 "sample rather than a replayable artifact.\n"
                 % min((e["games"] for e in pooled.values()), default=0))
    parts.append(slot("limitations"))

    # Extras
    parts.append("\n---\n\n## Extras\n")
    parts.append("\n### E1. Full head-to-head\n")
    parts.append(_table(
        ["game", "config", "agent", "opponent", "score", "W-D-L", "games"],
        [[r["game"], r["config"], r["agent"], r["opponent"], _score(r),
          "%d-%d-%d" % (r["wins"], r["draws"], r["losses"]), r["games"]]
         for r in document["head_to_head"]]))
    parts.append("\n### E2. Full score table\n")
    parts.append(_table(
        ["game", "config", "agent", "W", "D", "L", "score"],
        [[r["game"], r["config"], r["agent"], r["wins"], r["draws"],
          r["losses"], _score(r)] for r in document["score_table"]]))
    parts.append("\n### E3. Move-tag distribution\n")
    parts.append(_table(
        ["agent", "tag", "count"],
        [[r["agent"], r["tag"], r["count"]]
         for r in document["tag_distribution"]]))
    parts.append("\n### E4. End reasons\n")
    parts.append(_table(
        ["game", "config", "reason", "count"],
        [[r["game"], r["config"], reason, count]
         for r in document["game_length"]
         for reason, count in sorted(r["end_reasons"].items())]))
    parts.append("\n### E5. Provenance\n")
    parts.append("\nRegenerate this report with:\n\n"
                 "```bash\n"
                 "python3 -m experiments.analyse --raw results/raw \\\n"
                 "        --json results/analysis.json --label %s\n"
                 "python3 -m experiments.report --analysis "
                 "results/analysis.json\n"
                 "```\n" % (meta["label"] or "unlabelled"))

    return "\n".join(parts) + "\n"
```

Then add the CLI at the end of `experiments/report.py`:

```python
def main(argv=None):
    # type: (Any) -> int
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default="results/analysis.json")
    parser.add_argument("--commentary", default="docs/report/commentary.md")
    parser.add_argument("--out", default="results/report.md")
    parser.add_argument("--figures", default="results/figures")
    args = parser.parse_args(argv)

    with open(args.analysis) as handle:
        document = json.load(handle)

    sections = {}
    if os.path.exists(args.commentary):
        with open(args.commentary) as handle:
            sections = parse_commentary(handle.read())
    validate_commentary(sections, SECTION_IDS)

    from experiments import figures
    written = figures.render_all(document, args.figures)
    names = [os.path.basename(p) for p in written]

    text = render(document, sections, names)
    directory = os.path.dirname(args.out)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.out, "w") as handle:
        handle.write(text)

    missing = [i for i in SECTION_IDS if not sections.get(i)]
    if missing:
        sys.stderr.write("warning: %d commentary section(s) unfilled: %s\n"
                         % (len(missing), ", ".join(missing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Add `import sys` to the imports at the top of `report.py`.

- [ ] **Step 5: Create the commentary skeleton**

Create `docs/report/commentary.md`:

```markdown
# Report commentary

Hand-written interpretation, merged into the generated report by section id.
This file is the ONLY place prose belongs - `results/report.md` is generated and
any edit to it is lost on the next run.

Replace each `<!-- TODO -->` with prose. A section left as TODO renders as a
visible `[COMMENTARY NEEDED: id]` callout in the report, so gaps are obvious.

<!-- section: overview -->
<!-- TODO -->

<!-- section: method -->
<!-- TODO -->

<!-- section: results -->
<!-- TODO -->

<!-- section: budget-response -->
<!-- TODO -->

<!-- section: search-volume -->
<!-- TODO -->

<!-- section: instrument-validation -->
<!-- TODO -->

<!-- section: game-characteristics -->
<!-- TODO -->

<!-- section: limitations -->
<!-- TODO -->
```

- [ ] **Step 6: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add experiments/report.py docs/report/commentary.md tests/test_report.py tests/fixtures/analysis_small.json
git commit -m "Render the report from analysis.json with commentary merged in

The body stays direct and every deeper table moves to linked extras at the
end, so a reader gets results first and depth on request.

Unfilled commentary warns and renders a visible callout rather than
failing: the skeleton has to be generatable before any prose exists, so
failing on empty slots would block the first run."
```

---

### Task 10: End-to-end determinism against the real run

**Files:**
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: everything.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_report.py`:

```python
class EndToEndDeterminismTest(unittest.TestCase):
    def test_two_full_renders_are_byte_identical(self):
        from experiments import report as report_module
        document = RenderTest()._document()
        first = tempfile.mkdtemp()
        second = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, first)
        self.addCleanup(shutil.rmtree, second)
        for target in (first, second):
            report_module.main([
                "--analysis", os.path.join(
                    os.path.dirname(__file__), "fixtures",
                    "analysis_small.json"),
                "--commentary", "/nonexistent-commentary.md",
                "--out", os.path.join(target, "report.md"),
                "--figures", os.path.join(target, "figures")])
        names = sorted(os.listdir(os.path.join(first, "figures")))
        self.assertEqual(names, sorted(os.listdir(
            os.path.join(second, "figures"))))
        for relative in ["report.md"] + [
                os.path.join("figures", n) for n in names]:
            with open(os.path.join(first, relative), "rb") as h:
                a = h.read()
            with open(os.path.join(second, relative), "rb") as h:
                b = h.read()
            self.assertEqual(a, b, "%s is not reproducible" % relative)
```

- [ ] **Step 2: Run it and verify it passes**

Run: `python3 -m unittest tests.test_report.EndToEndDeterminismTest -v`
Expected: PASS. If it fails, the cause is in `figures.py` determinism pinning or a
non-sorted iteration in `render` — fix the cause, never the assertion.

- [ ] **Step 3: Commit**

```bash
git add tests/test_report.py
git commit -m "Assert the whole report pipeline is byte-reproducible

Covers the markdown and every SVG together. The figure-level test can pass
while a non-sorted iteration in the renderer still makes the markdown
unstable, so the guarantee needs asserting end to end."
```

---

### Task 11: `run_meta.json` for v1, and the method section

**Files:**
- Create: `results/raw/run_meta.json`
- Modify: `experiments/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_run_meta(path) -> dict` returning `{}` when the file is absent.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_report.py`:

```python
class RunMetaTest(unittest.TestCase):
    def test_absent_file_is_not_an_error(self):
        self.assertEqual(report.load_run_meta("/nonexistent.json"), {})

    def test_method_section_says_so_when_metadata_is_missing(self):
        document = RenderTest()._document()
        text = report.render(document, {}, [], run_meta={})
        self.assertIn("not recorded by this run", text)

    def test_reconstructed_metadata_is_labelled_as_such(self):
        document = RenderTest()._document()
        meta = {"source": "reconstructed", "python": "3.10.12",
                "mcts_rollout": {"epsilon": 1.0, "sample_k": 1,
                                 "rollout_depth": 10}}
        text = report.render(document, {}, [], run_meta=meta)
        self.assertIn("reconstructed", text)
        self.assertIn("3.10.12", text)
```

- [ ] **Step 2: Run and verify they fail**

Run: `python3 -m unittest tests.test_report.RunMetaTest -v`
Expected: FAIL, `AttributeError: ... has no attribute 'load_run_meta'`

- [ ] **Step 3: Implement**

Add to `experiments/report.py`:

```python
def load_run_meta(path):
    # type: (str) -> dict
    """Run metadata the CSVs cannot supply - rollout parameters, interpreter,
    host. Absent is a valid state and renders as "not recorded", never as an
    invented value."""
    import json
    import os
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        return json.load(handle)
```

Change `render`'s signature to `render(document, sections, figure_names, run_meta=None)`
and replace the section 2 body with:

```python
    # 2. Method for this run
    run_meta = run_meta or {}
    parts.append("## 2. Method for this run\n")
    parts.append(_table(
        ["game", "config", "budget (s)"],
        [[game, config, meta["budgets"][game][config]]
         for game in games
         for config in sorted(meta["budgets"][game],
                              key=lambda c: meta["budgets"][game][c])]))
    if run_meta:
        if run_meta.get("source") == "reconstructed":
            parts.append("\n> These values are **reconstructed**, not "
                         "recorded by the run itself. The tournament does "
                         "not yet write its own metadata.\n")
        parts.append(_table(
            ["property", "value"],
            [[key, run_meta[key]] for key in sorted(run_meta)
             if key != "source"]))
    else:
        parts.append("\n> Run metadata was **not recorded by this run**. "
                     "The MCTS rollout parameters, interpreter version and "
                     "host are not present in the CSVs; see "
                     "`experiments/tournament.py` at the run's tag.\n")
    parts.append(slot("method"))
```

Wire it in `main`:

```python
    run_meta = load_run_meta(os.path.join(
        os.path.dirname(args.analysis) or ".", "run_meta.json"))
    text = render(document, sections, names, run_meta=run_meta)
```

- [ ] **Step 4: Create the v1 metadata file**

Create `results/raw/run_meta.json`:

```json
{
  "source": "reconstructed",
  "tag": "v1-tournament",
  "python": "3.10.12",
  "platform": "Ubuntu 22.04, Multipass guest, 4 vCPU / 4 GB",
  "wall_clock": "7h56m",
  "restarts": 0,
  "mcts_rollout": {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10},
  "caps": {"max_nodes": 50000, "max_entries": 200000},
  "note": "Reconstructed after the fact. The tournament does not write run metadata; see the V2 improvement list."
}
```

- [ ] **Step 5: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add experiments/report.py results/raw/run_meta.json tests/test_report.py
git commit -m "Record run metadata the CSVs cannot supply

The MCTS rollout parameters live only in tournament.py, so the report
cannot prove from data which configuration produced a result. That is
precisely the parameter whose absence caused D4 and drove the F3 rewrite.

For v1 the file is reconstructed and says so, so a reader can tell
reconstruction from measurement. Absent metadata renders as 'not recorded'
and never as an invented value."
```

---

### Task 12: Generate the v1 report

**Files:**
- Create: `results/report.md`, `results/figures/*.svg`, `results/analysis.json`
- Modify: `.gitignore`

- [ ] **Step 1: Generate**

```bash
python3 -m experiments.analyse --raw results/raw \
        --json results/analysis.json --label v1-tournament > results/tables.md
python3 -m experiments.report --analysis results/analysis.json
```
Expected: a warning listing 8 unfilled commentary sections. That is correct at this stage.

- [ ] **Step 2: Verify determinism on the real data**

```bash
cp results/report.md /tmp/report-a.md
python3 -m experiments.report --analysis results/analysis.json
cmp /tmp/report-a.md results/report.md && echo "v1 report is reproducible"
```
Expected: `v1 report is reproducible`.

- [ ] **Step 3: Sanity-check the content**

```bash
grep -c "COMMENTARY NEEDED" results/report.md      # expect 8
grep -n "0.050\|0.175\|0.450" results/report.md | head
ls results/figures/
```
Expected: 8 callouts, the Ataxx MCTS-vs-heuristic scores present, four SVGs.

- [ ] **Step 4: Track the outputs**

Add to `.gitignore` nothing new — `results/analysis.json`, `results/report.md` and
`results/figures/` are all **tracked deliberately**, so a reader sees the results without
running anything. Confirm they are not excluded:

```bash
git check-ignore -v results/report.md results/analysis.json results/figures || echo "all tracked"
```

- [ ] **Step 5: Commit**

```bash
git add results/analysis.json results/report.md results/figures results/tables.md
git commit -m "Generate the v1 report

Eight commentary sections are deliberately unfilled and render as visible
callouts; prose is the next pass, written against a structure that now
exists and can be reviewed on its own."
```

---

### Task 13: Documentation consistency

**Files:**
- Modify: `README.md`, `docs/RUNBOOK.md`, `docs/spec/technical-spec.md`, `RESUME.md`

- [ ] **Step 1: Record the dependency split in README.md**

Add a short section after the Games table:

```markdown
## Dependencies

Running the tournament needs **nothing installed** - Python 3.8+ and the standard
library. That property is deliberate: the measurement uses wall-clock budgets, so a
lean environment is part of the instrument.

Reproducing the **figures** needs `matplotlib` and `numpy` (`requirements-analysis.txt`).
They are used only by `experiments/analyse.py`, `experiments/report.py` and
`experiments/figures.py`, never by the measurement path.
```

- [ ] **Step 2: Create `requirements-analysis.txt`**

```
matplotlib>=3.5
numpy>=1.21
```

- [ ] **Step 3: Correct the superseded framing in the spec**

In `docs/spec/technical-spec.md`, after the paragraph at lines 512-516 beginning
"**Ataxx scores 0.00 against the one-ply agent**", add:

```markdown
> **CORRECTED by the v1 run (2026-08-08).** These pilot figures were measured with the
> guided rollout defaults, before calibration selected pure random rollouts. With the
> calibrated parameters, Ataxx MCTS gets a median of 23.5 / 90.3 / 347.6 simulations per
> root move at 0.1 / 0.5 / 2.0 s and no decision in the 2160-game run fell below 1 per
> root move. MCTS is **beaten, not starved**: it scores 0.050 / 0.175 / 0.450 head to head
> against the one-ply heuristic. See `docs/FINDINGS.md` F3.
```

- [ ] **Step 4: Point RESUME.md at the report**

In `RESUME.md` section 6, after the analyse command, add:

```markdown
Then generate the report:

```bash
python3 -m experiments.analyse --raw results/raw --json results/analysis.json --label <tag>
python3 -m experiments.report --analysis results/analysis.json
```

Prose goes in `docs/report/commentary.md`, never in `results/report.md`, which is
regenerated from scratch every time.
```

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add README.md requirements-analysis.txt docs/spec/technical-spec.md RESUME.md
git commit -m "Document the dependency split and correct the spec's starvation framing

The stdlib-only promise now states which half of the codebase it covers,
so 'running the tournament needs nothing installed' stays true while the
figures have a stated requirements file.

The spec still carried the pilot's 'under three samples per root move'
reading for Ataxx, which the v1 run contradicts. It is annotated rather
than rewritten - the spec is a record of what was specified, and the
correction belongs beside it."
```

---

## Self-Review

**Spec coverage.** Wilson intervals (T1), head-to-head (T2), depth/compliance/length (T3),
budget response (T4), `analysis.json` and the removal of the dead `--out` (T5), commentary
sidecar (T6), figures with determinism pinned (T7), the two derived tables added on review
(T8), the merged Results section and linked extras (T9), determinism end to end (T10),
`run_meta.json` and the method section (T11), v1 generation (T12), documentation split and
the spec correction (T13). Every spec section maps to a task.

**Type consistency.** `wilson_interval` returns `score`/`ci_low`/`ci_high`/`games` and is
consumed under those names in T2, T4, T5. `head_to_head` is keyed
`(game, config, agent, opponent)` in T2 and read under that shape in T5 and T8.
`first_move_advantage` is read as `excluded_draws` in T9, matching the existing code rather
than the design doc. `_median` and `_percentile` take pre-sorted lists in T3, matching their
existing contract.

**Known deviation from the design doc.** The design doc lists a `game_length` key without
`config`; this plan keys it `(game, config)` because the budget changes game length and a
single per-game figure would hide that.
