# Plan 3: Calibration, Tournament, Analysis

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the experiment and produce the tables and figures the report is written from.

**Architecture:** Three programs over the existing agents and games. `calibrate.py` verifies budget adherence, then fixes the memory caps and MCTS hyperparameters that measurement has not yet settled. `tournament.py` plays the grid with trials interleaved across matchups and resumes from its own CSV. `analyse.py` reads the CSVs and emits every table and figure, computing nothing that is not derivable from the logs.

**Tech Stack:** Python 3.8.10, standard library only. Tests use `unittest`. Analysis emits Markdown tables; figures are out of scope for this plan.

## Global Constraints

- **Python 3.8.10.** No `match`, no `X | Y` unions, no `dict |`. Use `typing` generics.
- **Standard library only.** No third-party runtime or test dependencies, including for plotting.
- **Every agent is constructed fresh per game.** Alpha-Beta's table and MCTS's tree must never carry across games — a table saturated by a finished game would report a memory cap on an early move of the next.
- **Each agent takes its cap at construction from its own config key**: `max_entries` for Alpha-Beta, `max_nodes` for MCTS. `SearchContext.max_nodes` is informational only.
- **Trials are interleaved across matchups**, never grouped by agent, so timing drift hits every agent equally.
- Commit messages describe the change only — **no mention of Claude, AI, or any agent**.
- Run tests with `python3 -m unittest discover -s tests`.

## Fixed by prior measurement — do not re-derive

**Budget grid** (easy = *more* time, hard = *less*):

| Game | Easy | Main | Hard |
|---|---|---|---|
| Isolation | 0.5 s | 0.1 s | 0.02 s |
| Ataxx | 2.0 s | 0.5 s | 0.1 s |
| UTTT | 2.0 s | 0.5 s | 0.1 s |

**Measured game properties:** Isolation mean 15.9 plies, branching 6.3. UTTT 59.5 plies, 9.1. Ataxx 182.6 plies, 50.9 with a mid-game peak of 76.

**Known and expected outcomes**, so they are not mistaken for bugs:
- Isolation is **saturated** for both agents at every budget — Alpha-Beta solves it at depth 5 in 508 nodes regardless of time. It is a control, not a degradation datapoint.
- MCTS is **starved on Ataxx at every affordable budget** (~0.3–4.9 simulations per root move). Report it; do not engineer around it.
- MCTS is essentially **never tagged `normal`** — it is anytime by construction.

---

### Task 1: Calibration — budget adherence, memory caps, MCTS hyperparameters

**Files:**
- Create: `experiments/calibrate.py`
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Produces `experiments.calibrate` with `BUDGETS` (the grid above as a dict keyed by game name then config name), `check_budget_adherence(game, ev, agents, budgets, tolerance=0.10) -> List[AdherenceResult]`, `sweep_memory_caps(game, ev, budget, caps) -> List[CapResult]`, `sweep_mcts_rollout(game, ev, budget, configs, trials) -> List[RolloutResult]`, and `main()`.
- `AdherenceResult(agent, budget, mean_elapsed, max_elapsed, within_tolerance)`
- `CapResult(agent, cap, memory_limited_fraction, moves)`
- `RolloutResult(epsilon, sample_k, rollout_depth, simulations, per_root, score)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_calibrate.py`:

```python
import unittest

from experiments import calibrate
from games import ataxx, isolation, uttt


class BudgetGridTest(unittest.TestCase):
    def test_every_game_has_three_configs_ordered_easy_main_hard(self):
        for name in ("isolation", "ataxx", "uttt"):
            grid = calibrate.BUDGETS[name]
            self.assertEqual(set(grid), {"easy", "main", "hard"})
            self.assertGreater(grid["easy"], grid["main"])
            self.assertGreater(grid["main"], grid["hard"])

    def test_easy_means_more_time_not_less(self):
        # The labels are easy to read backwards; pin the direction.
        self.assertEqual(calibrate.BUDGETS["ataxx"]["easy"], 2.0)
        self.assertEqual(calibrate.BUDGETS["ataxx"]["hard"], 0.1)


class AdherenceTest(unittest.TestCase):
    def test_reports_within_tolerance_for_a_well_behaved_agent(self):
        from agents import random_agent
        from evaluation import isolation_eval
        results = calibrate.check_budget_adherence(
            isolation, isolation_eval, [("random", lambda: random_agent.choose)],
            budgets=(0.05,), samples=3)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].within_tolerance)

    def test_flags_an_agent_that_overruns(self):
        import time

        def hog(game, state, ctx, rng):
            deadline = time.monotonic() + 0.30
            while time.monotonic() < deadline:
                pass
            return game.legal_moves(state)[0]

        from evaluation import isolation_eval
        results = calibrate.check_budget_adherence(
            isolation, isolation_eval, [("hog", lambda: hog)],
            budgets=(0.05,), samples=2)
        self.assertFalse(results[0].within_tolerance,
                         "an agent taking 0.30s on a 0.05s budget must be flagged")


class CapSweepTest(unittest.TestCase):
    def test_a_tiny_cap_produces_memory_limited_moves(self):
        from evaluation import isolation_eval
        results = calibrate.sweep_memory_caps(
            isolation, isolation_eval, budget=0.05, caps=(8, 10 ** 7), agent="alpha_beta")
        tiny = [r for r in results if r.cap == 8][0]
        huge = [r for r in results if r.cap == 10 ** 7][0]
        self.assertGreater(tiny.memory_limited_fraction, 0.0)
        self.assertEqual(huge.memory_limited_fraction, 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_calibrate -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments.calibrate'`

- [ ] **Step 3: Write minimal implementation**

Create `experiments/calibrate.py`:

```python
"""Calibration: verify budgets are honoured, then fix the caps and rollout
parameters that measurement has not already settled.

Time budgets are NOT swept here. They were set by direct measurement of how much
search each agent obtains at each candidate budget, and are recorded in PLAN.md.
This module confirms them and settles what remains.

Run:  python3 -m experiments.calibrate
"""
import random
import statistics
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

from agents import alpha_beta_agent, heuristic_agent, mcts_agent, random_agent
from agents.base import MoveTag, decide

# easy means MORE time; hard means LESS. Set by measurement, see PLAN.md.
BUDGETS = {
    "isolation": {"easy": 0.5, "main": 0.1, "hard": 0.02},
    "ataxx": {"easy": 2.0, "main": 0.5, "hard": 0.1},
    "uttt": {"easy": 2.0, "main": 0.5, "hard": 0.1},
}

# MCTS is not meaningfully searching below this many simulations per root move;
# any conclusion drawn about it there describes the budget, not the algorithm.
VIABILITY_FLOOR = 10.0


@dataclass(frozen=True)
class AdherenceResult:
    agent: str
    budget: float
    mean_elapsed: float
    max_elapsed: float
    within_tolerance: bool


@dataclass(frozen=True)
class CapResult:
    agent: str
    cap: int
    memory_limited_fraction: float
    moves: int


@dataclass(frozen=True)
class RolloutResult:
    epsilon: float
    sample_k: int
    rollout_depth: int
    simulations: int
    per_root: float
    score: float


def _midgame(game, plies, seed=11):
    rng = random.Random(seed)
    s = game.initial_state()
    for _ in range(plies):
        if game.is_terminal(s):
            break
        s = game.apply_move(s, rng.choice(game.legal_moves(s)))
    return s


def check_budget_adherence(game, ev, agents, budgets, tolerance=0.10, samples=5):
    # type: (Any, Any, List[Tuple[str, Any]], Tuple[float, ...], float, int) -> List[AdherenceResult]
    """Phase 0 gate. An agent that overruns has not been constrained, so every
    later phase and the tournament would be measuring the wrong thing.

    This exists because MCTS once overshot a 0.02s budget by 1283% with no
    visible symptom: the CSV looked normal and every tag was plausible.
    """
    out = []
    for name, factory in agents:
        for budget in budgets:
            elapsed = []
            for i in range(samples):
                state = _midgame(game, plies=6, seed=100 + i)
                if game.is_terminal(state):
                    continue
                d = decide(factory(), game, state, budget, 200000,
                           random.Random(i))
                elapsed.append(d.elapsed_s)
            if not elapsed:
                continue
            mean_e = statistics.mean(elapsed)
            max_e = max(elapsed)
            out.append(AdherenceResult(
                agent=name, budget=budget, mean_elapsed=mean_e,
                max_elapsed=max_e,
                within_tolerance=max_e <= budget * (1.0 + tolerance)))
    return out


def sweep_memory_caps(game, ev, budget, caps, agent="alpha_beta", plies=40):
    # type: (Any, Any, float, Tuple[int, ...], str, int) -> List[CapResult]
    """Choose the cap at which `memory-limited` is a meaningful minority.

    The two agents' caps are NOT interchangeable: a transposition entry is a
    4-tuple while an MCTS node holds a full state, a child mapping and counters.
    They are swept separately and calibrated to comparable byte footprints.
    """
    out = []
    for cap in caps:
        if agent == "alpha_beta":
            make = lambda: alpha_beta_agent.make(ev.evaluate, max_entries=cap)
        else:
            make = lambda: mcts_agent.make(ev.evaluate, max_nodes=cap)
        rng = random.Random(5)
        state = game.initial_state()
        actor = make()
        tags = []
        played = 0
        while not game.is_terminal(state) and played < plies:
            d = decide(actor, game, state, budget, 200000, rng)
            tags.append(d.tag)
            state = game.apply_move(state, d.move)
            played += 1
        limited = sum(1 for t in tags if t == MoveTag.MEMORY_LIMITED)
        out.append(CapResult(agent=agent, cap=cap, moves=len(tags),
                             memory_limited_fraction=(
                                 limited / float(len(tags)) if tags else 0.0)))
    return out


def sweep_mcts_rollout(game, ev, budget, configs, trials=8, plies=20):
    # type: (Any, Any, float, Tuple[Tuple[float, int, int], ...], int, int) -> List[RolloutResult]
    """Select epsilon, sample_k and rollout_depth empirically.

    Only the exploration constant has a principled derivation. These three are
    domain-tuned hyperparameters everywhere in the literature, so they are
    measured against a fixed one-ply opponent rather than asserted.

    The range must include epsilon=1.0 (pure random rollouts) and sample_k=1: a
    prior sweep found the best configuration lay entirely outside a narrower
    range, because guidance costing k*D child evaluations per rollout starves the
    tree on wide games.
    """
    out = []
    probe = _midgame(game, plies)
    roots = max(1, len(game.legal_moves(probe)))
    for eps, k, depth in configs:
        mk = lambda: mcts_agent.make(ev.evaluate, epsilon=eps, sample_k=k,
                                     rollout_depth=depth)
        sims = decide(mk(), game, probe, budget, 200000, random.Random(1)).simulations
        wins = draws = 0
        for t in range(trials):
            rng = random.Random(700 + t)
            mc, hu = mk(), heuristic_agent.make(ev.evaluate)
            side = t % 2
            s = game.initial_state()
            played = 0
            while not game.is_terminal(s) and played < 400:
                actor = mc if s.side_to_move == side else hu
                d = decide(actor, game, s, budget, 200000, rng)
                s = game.apply_move(s, d.move)
                played += 1
            r = game.result(s) if played < 400 else 0.0
            if r == 0.0:
                draws += 1
            else:
                loser = s.side_to_move if r < 0 else 1 - s.side_to_move
                if loser != side:
                    wins += 1
        out.append(RolloutResult(
            epsilon=eps, sample_k=k, rollout_depth=depth, simulations=sims,
            per_root=sims / float(roots),
            score=(wins + 0.5 * draws) / float(trials)))
    return out


ROLLOUT_CANDIDATES = (
    (0.25, 8, 40), (0.25, 2, 40), (0.5, 2, 10),
    (0.8, 2, 10), (1.0, 1, 10), (1.0, 1, 400),
)

CAP_CANDIDATES_AB = (200, 2000, 20000, 200000)
CAP_CANDIDATES_MCTS = (50, 500, 5000, 50000)


def main():
    from evaluation import ataxx_eval, isolation_eval, uttt_eval
    from games import ataxx, isolation, uttt

    games = ((isolation, isolation_eval), (uttt, uttt_eval), (ataxx, ataxx_eval))

    print("=" * 70)
    print("PHASE 0 - budget adherence (GATE)")
    print("=" * 70)
    failures = 0
    for game, ev in games:
        agents = [
            ("random", lambda: random_agent.choose),
            ("heuristic", lambda ev=ev: heuristic_agent.make(ev.evaluate)),
            ("alpha_beta", lambda ev=ev: alpha_beta_agent.make(ev.evaluate)),
            ("mcts", lambda ev=ev: mcts_agent.make(ev.evaluate)),
        ]
        grid = tuple(sorted(BUDGETS[game.NAME].values()))
        for r in check_budget_adherence(game, ev, agents, grid):
            flag = "ok" if r.within_tolerance else "OVERRUN"
            if not r.within_tolerance:
                failures += 1
            print("  %-10s %-11s budget %-6.2f mean %-7.3f max %-7.3f  %s"
                  % (game.NAME, r.agent, r.budget, r.mean_elapsed,
                     r.max_elapsed, flag))
        sys.stdout.flush()
    if failures:
        print("\nPHASE 0 FAILED: %d agent/budget pairs overran. Stopping - every "
              "later phase would measure the wrong thing." % failures)
        return 1
    print("\nPHASE 0 PASSED")

    print("\n" + "=" * 70)
    print("PHASE 2 - memory caps")
    print("=" * 70)
    for game, ev in games:
        budget = BUDGETS[game.NAME]["main"]
        for label, agent, caps in (("alpha_beta", "alpha_beta", CAP_CANDIDATES_AB),
                                   ("mcts", "mcts", CAP_CANDIDATES_MCTS)):
            for r in sweep_memory_caps(game, ev, budget, caps, agent=agent):
                print("  %-10s %-11s cap %-8d memory-limited %5.1f%% of %d moves"
                      % (game.NAME, label, r.cap,
                         100.0 * r.memory_limited_fraction, r.moves))
            sys.stdout.flush()

    print("\n" + "=" * 70)
    print("PHASE 3 - MCTS rollout hyperparameters")
    print("=" * 70)
    for game, ev in games:
        budget = BUDGETS[game.NAME]["main"]
        print("  --- %s at %.2fs ---" % (game.NAME, budget))
        for r in sweep_mcts_rollout(game, ev, budget, ROLLOUT_CANDIDATES):
            note = "" if r.per_root >= VIABILITY_FLOOR else "  (below viability floor)"
            print("    eps%-5.2f k%-3d D%-5d sims %-6d per-root %-7.1f score %.2f%s"
                  % (r.epsilon, r.sample_k, r.rollout_depth, r.simulations,
                     r.per_root, r.score, note))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_calibrate -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Report — do not commit**

---

### Task 2: Tournament runner

**Files:**
- Create: `experiments/tournament.py`
- Modify: `experiments/logger.py` — add `max_entries` to `GAME_COLUMNS` beside `max_nodes`
- Test: `tests/test_tournament.py`

**Interfaces:**
- Produces `experiments.tournament` with `AGENTS` (the four names), `pairings() -> List[Tuple[str, str]]` giving all 12 directed matchups, `build_schedule(games, configs, trials) -> List[Cell]` **interleaved**, `run(schedule, out_dir, workers=1, resume=True)`, and `main(argv)`.
- `Cell(game, config, agent_first, agent_second, trial)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tournament.py`:

```python
import os
import shutil
import tempfile
import unittest

from experiments import tournament


class PairingTest(unittest.TestCase):
    def test_twelve_directed_matchups_from_four_agents(self):
        p = tournament.pairings()
        self.assertEqual(len(p), 12)
        self.assertEqual(len(set(p)), 12)

    def test_each_pairing_appears_in_both_seat_orders(self):
        p = set(tournament.pairings())
        for a, b in p:
            self.assertIn((b, a), p, "%s vs %s missing its reverse" % (a, b))

    def test_no_agent_plays_itself(self):
        for a, b in tournament.pairings():
            self.assertNotEqual(a, b)


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.schedule = tournament.build_schedule(
            games=("isolation",), configs=("main",), trials=3)

    def test_covers_every_matchup_and_trial(self):
        self.assertEqual(len(self.schedule), 12 * 3)

    def test_trials_are_interleaved_not_grouped_by_matchup(self):
        # Consecutive cells must not repeat the same matchup, so that timing
        # drift is spread across agents rather than accumulating against one.
        matchups = [(c.agent_first, c.agent_second) for c in self.schedule]
        repeats = sum(1 for i in range(1, len(matchups))
                      if matchups[i] == matchups[i - 1])
        self.assertEqual(repeats, 0, "schedule is grouped, not interleaved")

    def test_all_trials_of_a_matchup_are_present_exactly_once(self):
        seen = {}
        for c in self.schedule:
            key = (c.agent_first, c.agent_second, c.trial)
            self.assertNotIn(key, seen)
            seen[key] = True
        self.assertEqual(len(seen), 36)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_runs_a_tiny_grid_and_writes_both_csvs(self):
        schedule = [c for c in tournament.build_schedule(
            games=("isolation",), configs=("hard",), trials=1)
            if "alpha_beta" not in (c.agent_first, c.agent_second)
            and "mcts" not in (c.agent_first, c.agent_second)]
        tournament.run(schedule, self.dir, resume=False)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "games.csv")))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "moves.csv")))

    def test_resume_skips_already_completed_games(self):
        schedule = [c for c in tournament.build_schedule(
            games=("isolation",), configs=("hard",), trials=1)
            if c.agent_first == "random" and c.agent_second == "heuristic"]
        tournament.run(schedule, self.dir, resume=False)
        import csv
        with open(os.path.join(self.dir, "games.csv")) as h:
            first = len(list(csv.DictReader(h)))
        tournament.run(schedule, self.dir, resume=True)
        with open(os.path.join(self.dir, "games.csv")) as h:
            second = len(list(csv.DictReader(h)))
        self.assertEqual(first, second, "resume re-ran completed games")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_tournament -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments.tournament'`

- [ ] **Step 3: Write minimal implementation**

First make three edits to existing files:

1. `experiments/logger.py` — add `"max_entries"` to `GAME_COLUMNS` immediately after `"max_nodes"`, and write `record.max_entries` in `write()`.
2. `experiments/runner.py` — add `max_entries: int = 0` to `GameRecord` (after `max_nodes`, before the fields that already have defaults), and populate it in `play_game` from `config.get("max_entries", 0)`.
3. `experiments/runner.py` — **rename `_game_id` to `game_id` (public)** and keep `play_game` using it. The tournament must call the same function rather than re-deriving the format; two copies of an id format silently desync and would break `--resume` without any error.

Then create `experiments/tournament.py`:

```python
"""Full round-robin tournament over the grid.

Trials are interleaved across matchups rather than grouped, so that thermal
drift or background load on the host affects every agent equally rather than
accumulating against whichever ran last. This is a correctness requirement of
the methodology, not an optimisation.

Run:  python3 -m experiments.tournament --games all --configs all --trials 20
"""
import argparse
import itertools
import os
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

from agents import alpha_beta_agent, heuristic_agent, mcts_agent, random_agent
from experiments import runner
from experiments.calibrate import BUDGETS
from experiments.logger import GameLogger

AGENTS = ("random", "heuristic", "alpha_beta", "mcts")

# Alpha-Beta entries and MCTS nodes are different sizes, so these are separate
# numbers calibrated to comparable byte footprints - never one shared value.
CAPS = {"max_entries": 200000, "max_nodes": 50000}


@dataclass(frozen=True)
class Cell:
    game: str
    config: str
    agent_first: str
    agent_second: str
    trial: int


def pairings():
    # type: () -> List[Tuple[str, str]]
    """All 12 directed matchups: every unordered pair in both seat orders."""
    out = []
    for a, b in itertools.combinations(AGENTS, 2):
        out.append((a, b))
        out.append((b, a))
    return out


def build_schedule(games, configs, trials):
    # type: (Tuple[str, ...], Tuple[str, ...], int) -> List[Cell]
    """Interleaved: trial 0 of every matchup, then trial 1, and so on. No two
    consecutive cells share a matchup."""
    schedule = []
    for trial in range(trials):
        for game in games:
            for config in configs:
                for first, second in pairings():
                    schedule.append(Cell(game, config, first, second, trial))
    return schedule


def _game_module(name):
    from games import ataxx, isolation, uttt
    return {"isolation": isolation, "ataxx": ataxx, "uttt": uttt}[name]


def _evaluator(name):
    from evaluation import ataxx_eval, isolation_eval, uttt_eval
    return {"isolation": isolation_eval, "ataxx": ataxx_eval,
            "uttt": uttt_eval}[name]


def _make_agent(name, ev):
    """A fresh agent per game. Alpha-Beta's table and MCTS's tree must never
    carry across games - a table saturated by a finished game would report a
    memory cap on an early move of the next one."""
    if name == "random":
        return random_agent.choose
    if name == "heuristic":
        return heuristic_agent.make(ev.evaluate)
    if name == "alpha_beta":
        return alpha_beta_agent.make(ev.evaluate,
                                     max_entries=CAPS["max_entries"])
    if name == "mcts":
        return mcts_agent.make(ev.evaluate, max_nodes=CAPS["max_nodes"])
    raise ValueError("unknown agent %r" % (name,))


def run(schedule, out_dir, workers=1, resume=True):
    # type: (List[Cell], str, int, bool) -> int
    games_path = os.path.join(out_dir, "games.csv")
    moves_path = os.path.join(out_dir, "moves.csv")
    logger = GameLogger(games_path, moves_path)
    done = logger.completed_ids() if resume else set()

    played = 0
    for index, cell in enumerate(schedule):
        game = _game_module(cell.game)
        ev = _evaluator(cell.game)
        budget = BUDGETS[cell.game][cell.config]
        config = {"name": cell.config, "time_budget_s": budget,
                  "max_nodes": CAPS["max_nodes"],
                  "max_entries": CAPS["max_entries"]}
        seed = runner.game_seed(cell.game, cell.agent_first, cell.agent_second,
                                cell.config, cell.trial)
        # Same function the runner uses - never re-derive the format here, or
        # --resume silently stops matching and re-runs completed games.
        record_id = runner.game_id(cell.game, cell.agent_first,
                                   cell.agent_second, cell.config, cell.trial)
        if record_id in done:
            continue
        agents = (_make_agent(cell.agent_first, ev),
                  _make_agent(cell.agent_second, ev))
        record = runner.play_game(
            game, agents, (cell.agent_first, cell.agent_second), config, seed,
            ply_cap=300, trial=cell.trial, workers=workers)
        logger.write(record)
        played += 1
        if played % 20 == 0:
            print("  %d/%d games" % (index + 1, len(schedule)))
            sys.stdout.flush()
    logger.close()
    return played


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="all")
    parser.add_argument("--configs", default="all")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--out", default="results/raw")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)

    games = (("isolation", "uttt", "ataxx") if args.games == "all"
             else tuple(args.games.split(",")))
    configs = (("easy", "main", "hard") if args.configs == "all"
               else tuple(args.configs.split(",")))
    schedule = build_schedule(games, configs, args.trials)
    print("scheduled %d games across %d matchups" % (len(schedule), 12))
    played = run(schedule, args.out, workers=args.workers,
                 resume=not args.no_resume)
    print("played %d games (rest already present)" % played)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_tournament -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Report — do not commit**

---

### Task 3: Analysis

**Files:**
- Create: `experiments/analyse.py`
- Test: `tests/test_analyse.py`

**Interfaces:**
- Produces `experiments.analyse` with `load(games_csv, moves_csv)`, `score_table(rows)`, `tag_distribution(moves)`, `first_move_advantage(rows)`, `binomial_p(wins, n)`, and `main(argv)` printing Markdown tables to stdout.

> **Figures are deliberately out of scope here.** Producing SVG by hand with no plotting library is a task of its own, and the tables are what the report's claims rest on. Redirect stdout to a file and paste; add figures afterwards if time allows.

**Statistics, per the spec:** report **score rate** `(W + 0.5D)/N` *and* the W/D/L split separately, never "win rate" alone. Run the first-move binomial test on **decisive games only**, reporting how many draws were excluded — a test on 20 decisive games out of 100 is far weaker than the percentage suggests. Exclude `error`-tagged moves and their games from all statistics, reporting both counts separately.

- [ ] **Step 1: Write the failing test**

Create `tests/test_analyse.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_analyse -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `experiments/analyse.py`:

```python
"""Tables and figures, computed only from the CSVs.

Reporting rules from the spec, all load-bearing:
  - Report score rate (W + 0.5D)/N AND the win/draw/loss split. Never "win rate"
    alone: a draw-heavy result is itself a finding and score rate hides it.
  - Run the first-move binomial test on DECISIVE games only, since a 50/50 null
    is undefined when draws exist, and report how many draws were excluded.
  - Exclude error-tagged moves and their games from all statistics, and report
    the counts separately. A nonzero error count is a bug report, not a datum.
  - Report simulations per root move beside every MCTS result. Below about 10,
    MCTS is not meaningfully searching and any conclusion describes the budget.
"""
import argparse
import csv
import math
import os
import sys
from typing import Any, Dict, List


def load(games_csv, moves_csv):
    with open(games_csv, newline="") as h:
        games = list(csv.DictReader(h))
    with open(moves_csv, newline="") as h:
        moves = list(csv.DictReader(h))
    return games, moves


def binomial_p(wins, n):
    # type: (int, int) -> float
    """Two-sided exact binomial test against p=0.5. Stdlib only.

    Computed in log space via lgamma. The naive form - summing binomial
    coefficients and dividing by 2**n - overflows: the full grid is over two
    thousand games, and float(2 ** 2000) raises OverflowError.
    """
    if n <= 0:
        return 1.0
    observed = abs(wins - n / 2.0)
    log_half_n = -n * math.log(2.0)
    total = 0.0
    for k in range(n + 1):
        if abs(k - n / 2.0) >= observed:
            log_coeff = (math.lgamma(n + 1) - math.lgamma(k + 1)
                         - math.lgamma(n - k + 1))
            total += math.exp(log_coeff + log_half_n)
    return min(1.0, total)


def score_table(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): wins, draws, losses and score rate.

    Each row contributes to both seats, so an agent's record is pooled across
    the seat it happened to occupy.
    """
    table = {}
    for row in rows:
        for seat, agent in (("first", row["agent_first"]),
                            ("second", row["agent_second"])):
            key = (row["game"], row["config"], agent)
            e = table.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
            if row["winner"] == "draw":
                e["draws"] += 1
            elif row["winner"] == seat:
                e["wins"] += 1
            else:
                e["losses"] += 1
    for e in table.values():
        n = e["wins"] + e["draws"] + e["losses"]
        e["games"] = n
        e["score"] = (e["wins"] + 0.5 * e["draws"]) / float(n) if n else 0.0
    return table


def tag_distribution(moves):
    out = {}
    for m in moves:
        key = (m["agent"], m["tag"])
        out[key] = out.get(key, 0) + 1
    return out


def first_move_advantage(rows):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    first = sum(1 for r in rows if r["winner"] == "first")
    second = sum(1 for r in rows if r["winner"] == "second")
    draws = sum(1 for r in rows if r["winner"] == "draw")
    decisive = first + second
    return {"first": first, "second": second, "decisive": decisive,
            "excluded_draws": draws,
            "p": binomial_p(first, decisive) if decisive else 1.0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="results/raw")
    parser.add_argument("--out", default="results/figures")
    args = parser.parse_args(argv)

    games, moves = load(os.path.join(args.raw, "games.csv"),
                        os.path.join(args.raw, "moves.csv"))

    errors = [m for m in moves if m["tag"] == "error"]
    bad_games = set(m["game_id"] for m in errors)
    clean = [g for g in games if g["game_id"] not in bad_games]
    print("games %d (excluded %d containing %d error moves)"
          % (len(clean), len(games) - len(clean), len(errors)))
    if errors:
        print("  NOTE: a nonzero error count is a bug report, not a data point.")

    table = score_table(clean)
    print("\n## Score rate by agent")
    print("\n| game | config | agent | W | D | L | score |")
    print("|---|---|---|---|---|---|---|")
    for key in sorted(table):
        e = table[key]
        print("| %s | %s | %s | %d | %d | %d | %.3f |"
              % (key[0], key[1], key[2], e["wins"], e["draws"], e["losses"],
                 e["score"]))

    print("\n## First-move advantage (decisive games only)")
    fm = first_move_advantage(clean)
    print("first %d, second %d, decisive %d, draws excluded %d, p = %.4f"
          % (fm["first"], fm["second"], fm["decisive"],
             fm["excluded_draws"], fm["p"]))

    print("\n## Move-tag distribution")
    clean_moves = [m for m in moves if m["game_id"] not in bad_games]
    tags = tag_distribution(clean_moves)
    for key in sorted(tags):
        print("  %-12s %-16s %d" % (key[0], key[1], tags[key]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_analyse -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Report — do not commit**

---

### Task 4: Run the calibration pilot

Not a coding task. Run it, read it, decide.

- [ ] **Step 1: Run** `python3 -m experiments.calibrate 2>&1 | tee results/calibration.txt`
- [ ] **Step 2: Check phase 0 passed.** If any agent overran its budget, **stop** — every later number would be measuring the wrong thing.
- [ ] **Step 3: Choose the memory caps** from phase 2: the value where `memory-limited` is a meaningful minority at the main budget, not near 0% or near 100%. Set `CAPS` in `experiments/tournament.py` accordingly, keeping the two agents' values separate.
- [ ] **Step 4: Choose the rollout parameters** from phase 3, pooled across games, and set them as the MCTS defaults. Record per-game sensitivity — if the pooled choice leaves MCTS starved on a game, that must be reported as a limitation rather than buried.
- [ ] **Step 5: Commit** the calibration output and the chosen constants.

---

### Task 5: Run the tournament

- [ ] **Step 1: Smoke-run** one config, one game, two trials: `python3 -m experiments.tournament --games isolation --configs hard --trials 2`. Confirm both CSVs appear and look sane.
- [ ] **Step 2: Estimate** total runtime from the smoke run before committing to the full grid.
- [ ] **Step 3: Run the full grid** in the background: `python3 -m experiments.tournament --games all --configs all --trials 20 --out results/raw`. Expect roughly 10-21 hours; it resumes if interrupted.
- [ ] **Step 4: Run the analysis**, `python3 -m experiments.analyse --raw results/raw | tee results/tables.md`, and commit the CSVs and tables.

---

## What Plan 3 delivers

The experiment, its data, and the tables and figures the report is written from. After this, what remains is writing the report itself — for which PLAN.md's metrics section is the outline, and the findings recorded across `docs/spec/technical-spec.md` and the three gamebooks are the material.
