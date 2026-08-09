# V2 Agent Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agents, evaluators and hyperparameters versioned and self-recording, fix the declined-win defect in the v2 heuristic agent, and prepare the V2 run at 25 trials.

**Architecture:** `agents/vN/` and `evaluation/vN/` are self-contained packages declaring their own `VERSION`, caps and rollout parameters. The tournament selects a version, asks it for agents, records the version per game in `games.csv`, and writes `results/raw/run_meta.json` at startup. v1 stays byte-identical and is reached by the existing inline path.

**Tech Stack:** Python 3.10 (3.8 syntax), stdlib `unittest`. Measurement path stays stdlib-only.

**Design doc:** `docs/VERSIONING.md`

## Global Constraints

- **v1 is frozen.** Do not modify `agents/*.py`, `evaluation/*.py`, or anything they import. The only permitted change to `experiments/tournament.py` is additive.
- **Measurement path stays stdlib-only.** No matplotlib/numpy in `agents/`, `evaluation/`, `games/`, `runner.py`, `tournament.py`, `logger.py`.
- **Code style:** Python 3.8-compatible, `# type:` comments, `%` formatting, no f-strings.
- **Tests:** `python3 -m unittest discover -s tests`. **228 passing** at plan start; never let it go red.
- **Commit after every task.** No agent attribution or `Co-Authored-By` trailers.
- Running `python3 -m experiments.tournament` with **no version flag must still reproduce v1 behaviour exactly**, so the default is `v1`.

## File Structure

| File | Responsibility |
|---|---|
| `agents/v2/__init__.py` (create) | v2 roster: `VERSION`, `CAPS`, `MCTS_ROLLOUT`, `build()`, `params()` |
| `agents/v2/{random,heuristic,alpha_beta,mcts}_agent.py` (create) | Clones of v1, with the heuristic fix |
| `evaluation/v2/{__init__,isolation,ataxx,uttt}_eval.py` (create) | Clones of v1 evaluators |
| `agents/v3/`, `evaluation/v3/` (create) | Clones of v2, tagged `v3`, otherwise identical |
| `experiments/tournament.py` (modify) | `--agent-version`, version dispatch, run_meta, version columns |
| `experiments/logger.py` (modify) | Two new `games.csv` columns |
| `experiments/runner.py` (modify) | Carry versions into the game record |
| `experiments/analyse.py` (modify) | Surface versions in `analysis.json` |
| `experiments/report.py` (modify) | Roster table in section 2 |
| `tests/test_versions.py` (create) | Version integrity: tag matches directory, v3 is a faithful clone |

---

### Task 1: The v2 evaluator package

**Files:** Create `evaluation/v2/__init__.py`, `evaluation/v2/{isolation,ataxx,uttt}_eval.py`. Test: `tests/test_versions.py`

**Interfaces:** Produces `evaluation.v2.VERSION == "v2"` and three modules each exposing `evaluate(game, state) -> float`, byte-identical in behaviour to their v1 counterparts.

- [ ] **Step 1: Write the failing test**

Create `tests/test_versions.py`:

```python
import os
import unittest


class EvaluatorVersionTest(unittest.TestCase):
    def test_v2_declares_its_version(self):
        from evaluation import v2
        self.assertEqual(v2.VERSION, "v2")

    def test_v2_evaluators_agree_with_v1_on_the_same_states(self):
        """The v2 evaluators start as exact clones. If they ever diverge it
        must be a deliberate, reviewed change - not a transcription slip."""
        import random
        from evaluation import isolation_eval, ataxx_eval, uttt_eval
        from evaluation.v2 import (isolation_eval as i2, ataxx_eval as a2,
                                   uttt_eval as u2)
        from games import isolation, ataxx, uttt
        for game, old, new in ((isolation, isolation_eval, i2),
                               (ataxx, ataxx_eval, a2),
                               (uttt, uttt_eval, u2)):
            rng = random.Random(7)
            state = game.initial_state()
            for _ in range(30):
                if game.is_terminal(state):
                    break
                self.assertAlmostEqual(old.evaluate(game, state),
                                       new.evaluate(game, state), places=12)
                state = game.apply_move(state, rng.choice(
                    game.legal_moves(state)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify it fails**

Run: `python3 -m unittest tests.test_versions -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'evaluation.v2'`

- [ ] **Step 3: Create the package**

```bash
mkdir -p evaluation/v2
for f in isolation_eval ataxx_eval uttt_eval; do
    cp "evaluation/$f.py" "evaluation/v2/$f.py"
done
cat > evaluation/v2/__init__.py <<'PY'
"""Evaluators for agent version v2.

Currently identical to v1. Cloned rather than shared because an evaluator is
injected into three agents at once, so editing the v1 module in place would
silently change frozen v1 behaviour. See docs/VERSIONING.md.
"""
VERSION = "v2"
PY
```

Then prepend to each of the three copied files, above the existing docstring:

```python
# Agent version v2. Identical to v1 - no change has been made yet.
# Frozen once a tournament has run against it; see docs/VERSIONING.md.
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add evaluation/v2 tests/test_versions.py
git commit -m "Add the v2 evaluator package

Cloned from v1 and currently identical. An evaluator is injected into
three agents at once, so editing the v1 module in place would silently
change frozen v1 behaviour - the hazard the versioning policy exists to
prevent. A test asserts v2 still agrees with v1 numerically, so a future
divergence has to be deliberate rather than a transcription slip."
```

---

### Task 2: The v2 agent package, with the declined-win fix

**Files:** Create `agents/v2/__init__.py` and the four agent modules. Test: `tests/test_versions.py`, `tests/test_agents_v2.py`

**Interfaces:** Produces
- `agents.v2.VERSION == "v2"`, `agents.v2.CAPS`, `agents.v2.MCTS_ROLLOUT`, `agents.v2.AGENTS`
- `agents.v2.build(label, evaluate) -> callable(game, state, ctx, rng)`
- `agents.v2.params(label) -> dict` — the hyperparameters for that agent, for logging.

**The one behavioural change in v2:** the heuristic agent must not decline an immediate win. Measured on v1: 24.0% of available wins declined on Isolation, 14.8% on UTTT, 3.2% on Ataxx. `evaluate` is a static function with no terminal awareness, and the one-ply agent — unlike Alpha-Beta and MCTS, which both check `is_terminal` first — never checks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agents_v2.py`:

```python
import random
import unittest

from agents import base


def _declined_wins(game, ev, agent, seeds):
    """Count positions where an immediate win existed and was not taken."""
    offered = declined = 0
    for seed in seeds:
        rng = random.Random(seed)
        state = game.initial_state()
        turn = 0
        while not game.is_terminal(state):
            moves = game.legal_moves(state)
            if turn % 2 == 0:
                wins = [m for m in moves
                        if game.is_terminal(game.apply_move(state, m))
                        and game.result(game.apply_move(state, m)) != 0]
                ctx = base.SearchContext(0.1, 50000)
                chosen = agent(game, state, ctx, rng)
                if wins:
                    offered += 1
                    if chosen not in wins:
                        declined += 1
            else:
                chosen = rng.choice(moves)
            state = game.apply_move(state, chosen)
            turn += 1
    return offered, declined


class HeuristicTakesWinsTest(unittest.TestCase):
    """v1's one-ply agent scores children with -evaluate(child) and never
    checks whether a child is terminal. A winning child leaves the opponent
    with no moves, so mobility difference scores it ours/32 - while a
    non-winning child that leaves us more room scores (ours-1)/32, which can
    be larger. The agent then declines the win.
    """

    def test_v2_heuristic_never_declines_an_immediate_win(self):
        from agents.v2 import heuristic_agent
        from evaluation.v2 import isolation_eval
        from games import isolation
        agent = heuristic_agent.make(isolation_eval.evaluate)
        offered, declined = _declined_wins(isolation, isolation_eval, agent,
                                           range(60))
        self.assertGreater(offered, 0, "test found no winning positions")
        self.assertEqual(declined, 0)

    def test_the_v1_agent_still_declines_them(self):
        """Guards the fix against being quietly reverted, and documents that
        v1 is left alone deliberately rather than by oversight."""
        from agents import heuristic_agent
        from evaluation import isolation_eval
        from games import isolation
        agent = heuristic_agent.make(isolation_eval.evaluate)
        offered, declined = _declined_wins(isolation, isolation_eval, agent,
                                           range(60))
        self.assertGreater(declined, 0)

    def test_v2_heuristic_takes_wins_on_uttt_too(self):
        from agents.v2 import heuristic_agent
        from evaluation.v2 import uttt_eval
        from games import uttt
        agent = heuristic_agent.make(uttt_eval.evaluate)
        offered, declined = _declined_wins(uttt, uttt_eval, agent, range(40))
        self.assertGreater(offered, 0)
        self.assertEqual(declined, 0)


class RosterTest(unittest.TestCase):
    def test_build_returns_a_callable_for_every_label(self):
        from agents import v2
        from evaluation.v2 import isolation_eval
        for label in v2.AGENTS:
            self.assertTrue(callable(v2.build(label, isolation_eval.evaluate)))

    def test_unknown_label_raises(self):
        from agents import v2
        from evaluation.v2 import isolation_eval
        with self.assertRaises(ValueError):
            v2.build("nope", isolation_eval.evaluate)

    def test_params_expose_the_hyperparameters_for_logging(self):
        from agents import v2
        self.assertEqual(v2.params("mcts")["epsilon"], 1.0)
        self.assertEqual(v2.params("alpha_beta")["max_entries"], 200000)
        self.assertEqual(v2.params("random"), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify they fail**

Run: `python3 -m unittest tests.test_agents_v2 -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'agents.v2'`

- [ ] **Step 3: Clone the four agents**

```bash
mkdir -p agents/v2
for f in random_agent heuristic_agent alpha_beta_agent mcts_agent; do
    cp "agents/$f.py" "agents/v2/$f.py"
done
```

Prepend to each of the four copies, above the existing docstring:

```python
# Agent version v2. See docs/VERSIONING.md - frozen once a tournament has run
# against it. Any fix after that is a new version, not an edit here.
```

Add to `agents/v2/random_agent.py`, `alpha_beta_agent.py`, `mcts_agent.py` only:

```python
# Identical to v1 - no change has been made yet.
```

`agents/v2/heuristic_agent.py` instead gets the fix. Replace the scoring loop body so a
terminal child is recognised:

```python
        for move in moves:
            if ctx.should_stop() and best_moves:
                break
            child = game.apply_move(state, move)
            ctx.note_node()
            # A terminal child has to be scored from the rules, not from the
            # evaluator. `evaluate` is static and has no terminal awareness:
            # a winning child leaves the opponent with no moves, which
            # mobility difference scores as ours/32 - and a non-winning child
            # that leaves us more room scores (ours-1)/32, which can be
            # larger. v1 therefore declined an available immediate win in
            # 24.0% of such positions on Isolation, 14.8% on UTTT and 3.2%
            # on Ataxx. Alpha-Beta and MCTS never had this bug because both
            # check is_terminal before evaluating.
            if game.is_terminal(child):
                # result() is from the perspective of the side to move in the
                # child, i.e. the opponent; negate it exactly as below.
                score = -game.result(child)
            else:
                score = -evaluate(game, child)
            evaluated += 1
```

- [ ] **Step 4: Write the roster**

Create `agents/v2/__init__.py`:

```python
"""Agent version v2.

Hyperparameters live here rather than in the harness, because they are
properties of an agent and two versions must be able to declare different
ones. In v1 they lived in experiments/tournament.py, which is what allowed
defect D4 - the tournament silently ran the rollout defaults that calibration
had ranked worst. See docs/VERSIONING.md.
"""
from agents.v2 import (alpha_beta_agent, heuristic_agent, mcts_agent,
                       random_agent)

VERSION = "v2"

AGENTS = ("random", "heuristic", "alpha_beta", "mcts")

# Alpha-Beta entries and MCTS nodes are different sizes, so these are separate
# numbers calibrated to comparable byte footprints - never one shared value.
CAPS = {"max_entries": 200000, "max_nodes": 50000}

# Selected by calibrate.py phase 3, not assumed. epsilon=1.0 with sample_k=1
# means pure random rollouts: no evaluator call inside the playout at all.
MCTS_ROLLOUT = {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10}


def params(label):
    # type: (str) -> dict
    """The hyperparameters this version gives `label`, for run_meta logging."""
    if label == "alpha_beta":
        return {"max_entries": CAPS["max_entries"]}
    if label == "mcts":
        out = {"max_nodes": CAPS["max_nodes"]}
        out.update(MCTS_ROLLOUT)
        return out
    return {}


def build(label, evaluate):
    # type: (str, Any) -> Any
    """A fresh agent per game. Alpha-Beta's table and MCTS's tree must never
    carry across games."""
    if label == "random":
        return random_agent.choose
    if label == "heuristic":
        return heuristic_agent.make(evaluate)
    if label == "alpha_beta":
        return alpha_beta_agent.make(evaluate,
                                     max_entries=CAPS["max_entries"])
    if label == "mcts":
        return mcts_agent.make(evaluate, max_nodes=CAPS["max_nodes"],
                               **MCTS_ROLLOUT)
    raise ValueError("unknown agent %r" % (label,))
```

- [ ] **Step 5: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK. If `test_v2_heuristic_never_declines_an_immediate_win` still fails, the
terminal branch is not being reached — check that `game.result(child)` is negated.

- [ ] **Step 6: Measure the fix on all three games**

```bash
python3 - <<'PY'
import random
from agents.v2 import heuristic_agent
from agents import base
from evaluation.v2 import isolation_eval, uttt_eval, ataxx_eval
from games import isolation, uttt, ataxx
for game, ev, name, n in ((isolation, isolation_eval, "isolation", 60),
                          (uttt, uttt_eval, "uttt", 40),
                          (ataxx, ataxx_eval, "ataxx", 30)):
    agent = heuristic_agent.make(ev.evaluate)
    offered = declined = 0
    for seed in range(n):
        rng = random.Random(seed); state = game.initial_state(); turn = 0
        while not game.is_terminal(state):
            moves = game.legal_moves(state)
            if turn % 2 == 0:
                wins = [m for m in moves
                        if game.is_terminal(game.apply_move(state, m))
                        and game.result(game.apply_move(state, m)) != 0]
                ctx = base.SearchContext(0.1, 50000)
                mv = agent(game, state, ctx, rng)
                if wins:
                    offered += 1
                    declined += (mv not in wins)
            else:
                mv = rng.choice(moves)
            state = game.apply_move(state, mv); turn += 1
    print("%-10s offered %4d declined %4d" % (name, offered, declined))
PY
```
Expected: `declined 0` on all three.

- [ ] **Step 7: Commit**

```bash
git add agents/v2 tests/test_agents_v2.py
git commit -m "Add the v2 agent package and fix the declined-win defect

The one-ply agent scored every child with -evaluate(child) and never
checked whether a child was terminal. evaluate is static and has no
terminal awareness: a winning child leaves the opponent with no moves,
which mobility difference scores as ours/32, while a non-winning child
that leaves us more room scores (ours-1)/32 - which can be larger. The
agent then played the non-winning move.

Measured on v1: an available immediate win was declined in 24.0% of such
positions on Isolation, 14.8% on UTTT and 3.2% on Ataxx. The Isolation
figure closely matches its 25% loss rate to the random agent, which the
v1 report flagged as a weak control without identifying the cause.

Alpha-Beta and MCTS never had this bug - both check is_terminal before
evaluating. Only the one-ply agent skipped it.

A test asserts v1 still declines them, so the fix cannot be quietly
back-ported into the frozen version.

Hyperparameters move into the version package, where they belong."
```

---

### Task 3: The v3 packages

**Files:** Create `agents/v3/`, `evaluation/v3/`. Test: `tests/test_versions.py`

**Interfaces:** `agents.v3.VERSION == "v3"`, same surface as v2.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_versions.py`:

```python
class VersionIntegrityTest(unittest.TestCase):
    def test_every_version_package_tags_itself_with_its_directory(self):
        """A clone with a stale tag inside it produces a run labelled as
        something it is not. Cheap to check, expensive to discover later."""
        import importlib
        for name in ("v2", "v3"):
            for package in ("agents", "evaluation"):
                module = importlib.import_module("%s.%s" % (package, name))
                self.assertEqual(module.VERSION, name,
                                 "%s.%s declares %r" % (package, name,
                                                        module.VERSION))

    def test_v3_starts_as_a_faithful_clone_of_v2(self):
        """v3 is the next version to be improved. Until someone changes it, it
        must behave exactly like v2, or the first comparison will measure a
        transcription error rather than an improvement."""
        import random
        from agents import v2, v3
        from evaluation.v2 import isolation_eval as e2
        from evaluation.v3 import isolation_eval as e3
        from games import isolation
        from agents import base
        self.assertEqual(v2.AGENTS, v3.AGENTS)
        self.assertEqual(v2.CAPS, v3.CAPS)
        self.assertEqual(v2.MCTS_ROLLOUT, v3.MCTS_ROLLOUT)
        for label in ("heuristic",):
            a2 = v2.build(label, e2.evaluate)
            a3 = v3.build(label, e3.evaluate)
            state = isolation.initial_state()
            for _ in range(8):
                if isolation.is_terminal(state):
                    break
                m2 = a2(isolation, state, base.SearchContext(0.1, 50000),
                        random.Random(3))
                m3 = a3(isolation, state, base.SearchContext(0.1, 50000),
                        random.Random(3))
                self.assertEqual(m2, m3)
                state = isolation.apply_move(state, m2)
```

- [ ] **Step 2: Run and verify it fails**

Run: `python3 -m unittest tests.test_versions -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'agents.v3'`

- [ ] **Step 3: Clone v2 to v3**

```bash
cp -r agents/v2 agents/v3
cp -r evaluation/v2 evaluation/v3
rm -rf agents/v3/__pycache__ evaluation/v3/__pycache__
# Retag: the constant, the import paths, and the header comments.
sed -i 's/^VERSION = "v2"$/VERSION = "v3"/' agents/v3/__init__.py evaluation/v3/__init__.py
sed -i 's/^from agents\.v2 import/from agents.v3 import/' agents/v3/__init__.py
sed -i 's/# Agent version v2\./# Agent version v3./' agents/v3/*.py evaluation/v3/*.py
sed -i 's/^"""Agent version v2\.$/"""Agent version v3./' agents/v3/__init__.py
sed -i 's/^"""Evaluators for agent version v2\.$/"""Evaluators for agent version v3./' evaluation/v3/__init__.py
grep -rn "v2" agents/v3/ evaluation/v3/ || echo "no stale v2 references"
```

Then add to the top of `agents/v3/__init__.py` and `evaluation/v3/__init__.py`:

```python
# Currently identical to v2 - no improvement has been made yet. This package
# is where the next round of agent changes goes. See docs/VERSIONING.md.
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add agents/v3 evaluation/v3 tests/test_versions.py
git commit -m "Add the v3 packages as faithful clones of v2

v3 is where the next round of agent changes goes. Until someone makes
one it must behave exactly like v2, or the first v2-versus-v3 comparison
would measure a transcription error rather than an improvement - so a
test asserts the rosters, caps and rollout parameters match and that the
agents choose identical moves from identical states.

A second test asserts each package's VERSION constant matches its
directory name, since a clone carrying a stale tag produces a run
labelled as something it is not."
```

---

### Task 4: Version-aware tournament, run_meta, and version columns

**Files:** Modify `experiments/tournament.py`, `experiments/runner.py`, `experiments/logger.py`. Test: `tests/test_tournament.py`, `tests/test_logger.py`

**Interfaces:**
- `tournament.agent_source(version)` returns the version package, or a v1 shim exposing the same `AGENTS`/`build`/`params`/`VERSION` surface.
- `tournament.write_run_meta(path, version, games, configs, trials, schedule_size)` writes/updates `run_meta.json`.
- `games.csv` gains four columns at the end: `agent_first_version`, `agent_second_version`, `agent_first_params`, `agent_second_params`.

**Why the params go in the CSV and not only in `run_meta.json`.** `run_meta` holds one
roster for the whole run, which is enough for a grid run where every game uses the same
agents. It is **not** enough for the v2-versus-v3 comparison run, where two agents with
*different* hyperparameters play each other in the same game — a single roster cannot say
which epsilon belonged to which side. Per-agent, per-game columns can, and they also
survive the metadata file being lost or overwritten.

`max_nodes` and `max_entries` already exist in `games.csv`, but as one config-level pair
per row rather than per agent, so they cannot express two agents with different caps
either. The new columns supersede them for that purpose; the old two stay where they are
so no existing column position moves.

Params are written as a compact JSON object with sorted keys, e.g.
`{"epsilon": 1.0, "max_nodes": 50000, "rollout_depth": 10, "sample_k": 1}`. Sorted so the
CSV stays byte-deterministic; JSON so the shape does not have to be guessed back.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tournament.py`:

```python
class VersionSelectionTest(unittest.TestCase):
    def test_default_is_v1_so_old_commands_reproduce_v1(self):
        source = tournament.agent_source("v1")
        self.assertEqual(source.VERSION, "v1")
        self.assertEqual(source.AGENTS, tournament.AGENTS)

    def test_v1_shim_builds_the_same_agents_as_the_inline_path(self):
        from evaluation import isolation_eval
        source = tournament.agent_source("v1")
        for label in tournament.AGENTS:
            self.assertTrue(callable(source.build(label, isolation_eval.evaluate)))

    def test_v2_is_selectable_and_reports_its_own_version(self):
        self.assertEqual(tournament.agent_source("v2").VERSION, "v2")

    def test_unknown_version_raises(self):
        with self.assertRaises(ValueError):
            tournament.agent_source("v9")

    def test_v1_shim_exposes_the_harness_constants_as_its_params(self):
        source = tournament.agent_source("v1")
        self.assertEqual(source.params("mcts")["epsilon"], 1.0)


class RunMetaTest(unittest.TestCase):
    def test_writes_the_roster_with_versions_and_params(self):
        import json
        import tempfile
        import os
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "run_meta.json")
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        with open(path) as handle:
            meta = json.load(handle)
        self.assertEqual(meta["agent_version"], "v2")
        self.assertEqual(meta["trials"], 25)
        self.assertEqual(meta["schedule_size"], 300)
        self.assertEqual(meta["source"], "recorded")
        self.assertIn("python", meta)
        self.assertIn("platform", meta)
        self.assertEqual(meta["roster"]["mcts"]["epsilon"], 1.0)

    def test_a_restart_appends_rather_than_clobbering(self):
        import json
        import tempfile
        import os
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "run_meta.json")
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        with open(path) as handle:
            meta = json.load(handle)
        self.assertEqual(len(meta["starts"]), 2)
```

Append to `tests/test_logger.py`:

```python
class VersionColumnTest(unittest.TestCase):
    def test_games_csv_carries_the_agent_versions_and_params(self):
        from experiments import logger as logger_module
        for column in ("agent_first_version", "agent_second_version",
                       "agent_first_params", "agent_second_params"):
            self.assertIn(column, logger_module.GAME_COLUMNS)

    def test_the_new_columns_are_appended_not_inserted(self):
        """Existing column positions must not move, or every tool that reads
        these CSVs by position breaks on old files."""
        from experiments import logger as logger_module
        self.assertEqual(logger_module.GAME_COLUMNS[:13], [
            "game_id", "game", "config", "time_budget_s", "max_nodes",
            "max_entries", "agent_first", "agent_second", "winner", "plies",
            "end_reason", "seed", "workers"])
```

- [ ] **Step 2: Run and verify they fail**

Run: `python3 -m unittest tests.test_tournament tests.test_logger -v`
Expected: FAIL, `AttributeError: ... has no attribute 'agent_source'`

- [ ] **Step 3: Add the v1 shim and version dispatch**

In `experiments/tournament.py`, after `_make_agent`:

```python
class _V1Source(object):
    """Exposes v1's inline agent construction under the same interface the
    versioned packages provide, so the tournament has one code path.

    v1 has no package of its own and must not grow one: it is frozen, and its
    hyperparameters live here in the harness, which is exactly the mistake the
    versioned packages exist to correct. This shim reads them rather than
    moving them.
    """

    VERSION = "v1"
    AGENTS = AGENTS

    @staticmethod
    def build(label, evaluate):
        return _make_agent(label, _Evaluator(evaluate))

    @staticmethod
    def params(label):
        if label == "alpha_beta":
            return {"max_entries": CAPS["max_entries"]}
        if label == "mcts":
            out = {"max_nodes": CAPS["max_nodes"]}
            out.update(MCTS_ROLLOUT)
            return out
        return {}


class _Evaluator(object):
    """_make_agent takes a module with an `evaluate` attribute; the versioned
    interface passes the function itself. Adapts one to the other."""

    def __init__(self, evaluate):
        self.evaluate = evaluate


def agent_source(version):
    # type: (str) -> Any
    if version == "v1":
        return _V1Source
    if version == "v2":
        from agents import v2
        return v2
    if version == "v3":
        from agents import v3
        return v3
    raise ValueError("unknown agent version %r" % (version,))


def evaluator_source(version, game):
    # type: (str, str) -> Any
    if version == "v1":
        return _evaluator(game)
    module = __import__("evaluation.%s" % version, fromlist=["x"])
    return getattr(module, "%s_eval" % game)
```

- [ ] **Step 4: Add run_meta writing**

Add to `experiments/tournament.py`:

```python
def write_run_meta(path, version, games, configs, trials, schedule_size):
    # type: (str, str, tuple, tuple, int, int) -> None
    """Record what this run is, at startup.

    The v1 run could not say from its own data which rollout parameters
    produced it - they lived only as a constant here. That gap caused defect
    D4 and forced the rewrite of finding F3.

    A restart appends to `starts` rather than clobbering, so a resumed run
    keeps the history of every attempt instead of only the last one.
    """
    import json
    import platform
    import subprocess
    import sys

    source = agent_source(version)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        commit = "unknown"

    start = {"python": sys.version.split()[0],
             "platform": platform.platform(),
             "commit": commit}

    existing = {}
    if os.path.exists(path):
        try:
            with open(path) as handle:
                existing = json.load(handle)
        except ValueError:
            existing = {}

    meta = {
        "source": "recorded",
        "agent_version": version,
        "games": list(games),
        "configs": list(configs),
        "trials": trials,
        "schedule_size": schedule_size,
        "budgets": dict((g, dict(BUDGETS[g])) for g in games),
        "roster": dict((label, source.params(label))
                       for label in source.AGENTS),
        "python": start["python"],
        "platform": start["platform"],
        "commit": commit,
        "starts": existing.get("starts", []) + [start],
    }
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(meta, handle, sort_keys=True, indent=2)
        handle.write("\n")
```

- [ ] **Step 5: Wire the version through run() and the CLI**

In `run()`, change the signature to `run(schedule, out_dir, workers=1, resume=True, version="v1")`, and inside the loop replace the agent construction:

```python
        source = agent_source(version)
        ev = evaluator_source(version, cell.game)
        evaluate = ev.evaluate
        agents = (source.build(cell.agent_first, evaluate),
                  source.build(cell.agent_second, evaluate))
```

and pass the versions into `runner.play_game(..., agent_versions=(version, version))`.

In `main()`, add:

```python
    parser.add_argument("--agent-version", dest="agent_version", default="v1")
```

and before `run(...)`:

```python
    write_run_meta(os.path.join(args.out, "run_meta.json"), args.agent_version,
                   games, configs, args.trials, len(schedule))
```

- [ ] **Step 6: Add the CSV columns**

In `experiments/logger.py`, append these four to `GAME_COLUMNS` **at the end**, so
existing column positions do not move:

```python
    "agent_first_version", "agent_second_version",
    "agent_first_params", "agent_second_params",
```

In `experiments/runner.py`, accept `agent_versions=("v1", "v1")` and
`agent_params=({}, {})` in `play_game`, and place all four on the game record. Serialise
the params where they are written, so the record carries plain data:

```python
import json
...
        agent_first_params=json.dumps(agent_params[0], sort_keys=True),
        agent_second_params=json.dumps(agent_params[1], sort_keys=True),
```

Sorted keys keep the CSV byte-deterministic across runs.

In `tournament.py`'s loop, pass what the version actually gave each agent:

```python
        agents = (source.build(cell.agent_first, evaluate),
                  source.build(cell.agent_second, evaluate))
        record = runner.play_game(
            game, agents, (cell.agent_first, cell.agent_second), config, seed,
            ply_cap=300, trial=cell.trial, workers=workers,
            agent_versions=(version, version),
            agent_params=(source.params(cell.agent_first),
                          source.params(cell.agent_second)))
```

- [ ] **Step 7: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 8: Verify v1 behaviour is unchanged and v2 works end to end**

```bash
rm -rf /tmp/v1check /tmp/v2check
python3 -m experiments.tournament --games isolation --configs hard --trials 1 --out /tmp/v1check
python3 -m experiments.tournament --games isolation --configs hard --trials 1 \
        --agent-version v2 --out /tmp/v2check
head -1 /tmp/v1check/games.csv | tr ',' '\n' | tail -2
python3 -c "
import csv
for d in ('/tmp/v1check','/tmp/v2check'):
    r = list(csv.DictReader(open(d + '/games.csv')))
    print(d, 'games', len(r), 'version', r[0]['agent_first_version'])"
python3 -c "import json; m=json.load(open('/tmp/v2check/run_meta.json')); print('meta version', m['agent_version'], '| roster mcts', m['roster']['mcts'])"
```
Expected: the two new columns present, `v1` and `v2` recorded respectively, and run_meta
showing the v2 roster.

- [ ] **Step 9: Commit**

```bash
git add experiments tests
git commit -m "Make the tournament version-aware and self-recording

Selects an agent version, records it per game, and writes run_meta.json
at startup with the roster, hyperparameters, budgets, interpreter,
platform and git commit.

The v1 run could not say from its own data which rollout parameters
produced it, because they lived only as a constant in this file. That gap
caused defect D4 and forced the rewrite of finding F3. It is closed.

v1 is reached through a shim exposing the same interface as the versioned
packages, so there is one code path. The shim reads the harness constants
rather than moving them: v1 is frozen, and its hyperparameters living in
the harness is precisely the mistake the versioned packages correct.

The default version is v1, so an existing command line reproduces v1
behaviour exactly. The two new games.csv columns are appended at the end
so no existing column position moves."
```

---

### Task 5: Surface versions in the analysis and report

**Files:** Modify `experiments/analyse.py`, `experiments/report.py`. Test: `tests/test_analyse.py`, `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_analyse.py`:

```python
class AgentVersionMetaTest(unittest.TestCase):
    def test_meta_records_the_agent_versions_present(self):
        games = [{"game_id": "g1", "game": "ataxx", "config": "hard",
                  "time_budget_s": "0.1", "agent_first": "mcts",
                  "agent_second": "heuristic", "winner": "second",
                  "plies": "12", "end_reason": "eliminated",
                  "agent_first_version": "v2", "agent_second_version": "v2"}]
        meta = analyse.build_analysis(games, [], label="x")["meta"]
        self.assertEqual(meta["agent_versions"], ["v2"])

    def test_missing_version_columns_default_to_v1(self):
        games = [{"game_id": "g1", "game": "ataxx", "config": "hard",
                  "time_budget_s": "0.1", "agent_first": "mcts",
                  "agent_second": "heuristic", "winner": "second",
                  "plies": "12", "end_reason": "eliminated"}]
        meta = analyse.build_analysis(games, [], label="x")["meta"]
        self.assertEqual(meta["agent_versions"], ["v1"])

    def test_roster_is_read_from_the_csv_not_guessed(self):
        """The hyperparameters must come from the data. run_meta holds one
        roster for a whole run and cannot describe a comparison run where two
        agents carry different parameters in the same game."""
        games = [{"game_id": "g1", "game": "ataxx", "config": "hard",
                  "time_budget_s": "0.1", "agent_first": "mcts",
                  "agent_second": "heuristic", "winner": "second",
                  "plies": "12", "end_reason": "eliminated",
                  "agent_first_version": "v2", "agent_second_version": "v2",
                  "agent_first_params": '{"epsilon": 1.0, "sample_k": 1}',
                  "agent_second_params": "{}"}]
        meta = analyse.build_analysis(games, [], label="x")["meta"]
        self.assertEqual(meta["roster"]["mcts@v2"], {"epsilon": 1.0,
                                                     "sample_k": 1})
        self.assertEqual(meta["roster"]["heuristic@v2"], {})

    def test_two_versions_of_one_agent_keep_separate_parameters(self):
        """The case run_meta cannot express: same label, two versions, two
        parameter sets, in the same run."""
        base = {"game": "ataxx", "config": "hard", "time_budget_s": "0.1",
                "winner": "first", "plies": "9", "end_reason": "eliminated"}
        games = [dict(base, game_id="g1", agent_first="mcts",
                      agent_second="mcts",
                      agent_first_version="v2", agent_second_version="v3",
                      agent_first_params='{"epsilon": 1.0}',
                      agent_second_params='{"epsilon": 0.8}')]
        meta = analyse.build_analysis(games, [], label="x")["meta"]
        self.assertEqual(meta["roster"]["mcts@v2"], {"epsilon": 1.0})
        self.assertEqual(meta["roster"]["mcts@v3"], {"epsilon": 0.8})

    def test_conflicting_parameters_for_one_agent_version_are_flagged(self):
        """If the same agent at the same version shows two parameter sets in
        one run, something is wrong and it must not be silently averaged
        away."""
        base = {"game": "ataxx", "config": "hard", "time_budget_s": "0.1",
                "winner": "first", "plies": "9", "end_reason": "eliminated",
                "agent_second": "random", "agent_second_version": "v2",
                "agent_second_params": "{}"}
        games = [dict(base, game_id="g1", agent_first="mcts",
                      agent_first_version="v2",
                      agent_first_params='{"epsilon": 1.0}'),
                 dict(base, game_id="g2", agent_first="mcts",
                      agent_first_version="v2",
                      agent_first_params='{"epsilon": 0.5}')]
        meta = analyse.build_analysis(games, [], label="x")["meta"]
        self.assertIn("mcts@v2", meta["roster_conflicts"])
```

Append to `tests/test_report.py`:

```python
class RosterSectionTest(unittest.TestCase):
    def test_method_section_shows_the_roster_when_recorded(self):
        with open(_fixture_path()) as handle:
            document = json.load(handle)
        meta = {"source": "recorded", "agent_version": "v2",
                "roster": {"mcts": {"epsilon": 1.0, "sample_k": 1},
                           "random": {}}}
        text = report.render(document, {}, [], run_meta=meta)
        self.assertIn("agent version", text.lower())
        self.assertIn("epsilon=1.0", text)
```

- [ ] **Step 2: Run and verify they fail**

Run: `python3 -m unittest tests.test_analyse.AgentVersionMetaTest tests.test_report.RosterSectionTest -v`
Expected: FAIL on `KeyError: 'agent_versions'`.

- [ ] **Step 3: Implement**

Add to `analyse.py`:

```python
def roster_from_games(rows):
    # type: (List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]
    """Agent hyperparameters, read from the CSV rather than from a metadata
    file or a document.

    Keyed `label@version`, because the whole point is the case a single
    run-level roster cannot express: the same agent label at two versions,
    with different parameters, inside one run. That is exactly what a
    version-comparison run looks like.

    Returns the roster and a sorted list of keys that showed conflicting
    parameters. A conflict means the run is not what it claims to be, so it is
    surfaced rather than resolved by picking one.
    """
    import json
    roster = {}
    conflicts = set()
    for row in rows:
        for side in ("first", "second"):
            label = row.get("agent_%s" % side)
            if not label:
                continue
            version = row.get("agent_%s_version" % side) or "v1"
            raw = row.get("agent_%s_params" % side)
            if raw in (None, ""):
                continue
            try:
                params = json.loads(raw)
            except ValueError:
                continue
            key = "%s@%s" % (label, version)
            if key in roster and roster[key] != params:
                conflicts.add(key)
            roster[key] = params
    return roster, sorted(conflicts)
```

and in `build_analysis`, before assembling `doc`:

```python
    roster, roster_conflicts = roster_from_games(games_rows)
```

then add to `meta`:

```python
            "agent_versions": sorted(set(
                [r.get("agent_first_version") or "v1" for r in games_rows]
                + [r.get("agent_second_version") or "v1"
                   for r in games_rows])),
            "roster": roster,
            "roster_conflicts": roster_conflicts,
```

In `report.py`'s section 2, render the roster from **`analysis.json`** — that is the copy
derived from the CSVs — rather than from `run_meta`, which is a claim about the run rather
than a record of it:

```python
    roster = meta.get("roster") or {}
    if roster:
        parts.append("\n**Agent roster and hyperparameters**, read from "
                     "`games.csv` rather than from metadata, so it describes "
                     "what actually ran\n")
        parts.append(_table(
            ["agent", "version", "hyperparameters"],
            [[key.split("@")[0], key.split("@")[1],
              _plain(roster[key]) if roster[key] else "-"]
             for key in sorted(roster)]))
    for key in meta.get("roster_conflicts") or []:
        parts.append("\n> **WARNING: %s ran with more than one set of "
                     "hyperparameters in this run.** The run is not what it "
                     "claims to be; do not compare these results until it is "
                     "explained.\n" % key)
```

Exclude the run-level bookkeeping from the generic `run_meta` property table by extending
the skip list from `if key != "source"` to
`if key not in ("source", "roster", "starts")`.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m unittest discover -s tests`
Expected: OK.

- [ ] **Step 5: Confirm the v1 report is unchanged**

```bash
python3 -m experiments.analyse --raw results/raw --json /tmp/a3.json --label v1-tournament > /dev/null
python3 -m experiments.report --analysis /tmp/a3.json --out /tmp/r3.md --figures /tmp/f3 2>/dev/null
diff <(sed 's/figures\///' /tmp/r3.md) <(sed 's/figures\///' results/report.md) && echo "v1 report unchanged"
```
Expected: `v1 report unchanged` — the v1 CSVs have no version columns, so they default to
v1 and nothing else moves.

- [ ] **Step 6: Commit**

```bash
git add experiments tests
git commit -m "Surface agent versions and the roster in the analysis and report

Runs without the version columns default to v1, so the v1 analysis and
its published report regenerate byte-identically.

Section 2 gains the roster and its hyperparameters when the run recorded
them, which is what makes a v2-versus-v3 comparison checkable from the
report rather than from memory."
```

---

### Task 6: Prepare the V2 run

**Files:** Modify `/etc/systemd/system/tournament.service` (system), `RESUME.md`, `docs/RUNBOOK.md`

- [ ] **Step 1: Confirm nothing is running**

Run: `systemctl is-active tournament`
Expected: `inactive`. If active, stop before continuing.

- [ ] **Step 2: Update the unit for V2**

```bash
sudo sed -i \
  's|^ExecStart=.*|ExecStart=/usr/bin/python3 -m experiments.tournament --games all --configs all --trials 25 --agent-version v2 --out results/v2|' \
  /etc/systemd/system/tournament.service
sudo sed -i 's|^Description=.*|Description=Search-agents tournament v2 (full grid, 2700 games)|' \
  /etc/systemd/system/tournament.service
sudo systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/tournament.service 2>&1 | grep -v snapd || echo "unit clean"
grep -E "ExecStart|Description" /etc/systemd/system/tournament.service
```

`results/v2` is a **new output directory** — the V1 CSVs stay untouched at `results/raw`.

- [ ] **Step 3: Point status.sh at the V2 run**

In `status.sh`, change `RAW=$DIR/results/raw` to `RAW=$DIR/results/v2` and `TOTAL=2160`
to `TOTAL=2700`.

- [ ] **Step 4: Smoke test the exact V2 configuration**

```bash
rm -rf /tmp/v2smoke
time python3 -m experiments.tournament --games all --configs hard --trials 2 \
     --agent-version v2 --out /tmp/v2smoke
python3 - <<'PY'
import csv, collections
G = {r["game_id"]: r for r in csv.DictReader(open("/tmp/v2smoke/games.csv"))}
M = [(r["game_id"], r["ply"]) for r in csv.DictReader(open("/tmp/v2smoke/moves.csv"))]
t = collections.Counter(r["tag"] for r in csv.DictReader(open("/tmp/v2smoke/moves.csv")))
print("games", len(G), "expect 72")
print("dupes", len(M) - len(set(M)), "expect 0")
print("illegal", t.get("illegal_move", 0), "agent_error", t.get("agent_error", 0))
print("versions", set(r["agent_first_version"] for r in G.values()))
PY
```
Expected: 72 games, 0 dupes, 0 errors, versions `{'v2'}`.

- [ ] **Step 5: Update RESUME.md for V2**

Change the grid line to `3 x 12 x 3 x 25 = 2700 games`, the expected duration to
**~9.9 h**, the output path to `results/v2`, and the `ExecStart` block to match the
installed unit. Add: *"V1 lives at `results/raw` and is not touched by this run."*

- [ ] **Step 6: Commit**

```bash
git add status.sh RESUME.md docs/RUNBOOK.md
git commit -m "Prepare the V2 run: 25 trials, v2 agents, separate output directory

Output goes to results/v2 so the v1 CSVs and the published v1 report stay
untouched and comparable.

25 trials rather than 20 narrows a head-to-head interval from about
+/-0.15 to +/-0.13 for roughly two extra hours - measured from v1, where
search time was 7.94 h against 7.93 h wall clock, so the run scales
linearly and the estimate is ~9.9 h."
```

---

## Self-Review

**Spec coverage.** Evaluator versioning (T1), agent versioning + the declined-win fix +
hyperparameters moving into the version package (T2), v3 clones (T3), version-aware
tournament + run_meta + CSV columns (T4), analysis and report surfacing (T5), V2 run
preparation (T6). `docs/VERSIONING.md` names games and `experiments/` as deliberately
unversioned, and no task versions them.

**Type consistency.** `build(label, evaluate)` and `params(label)` have the same
signatures in `agents/v2`, `agents/v3` and `_V1Source`. `agent_source` returns something
exposing `VERSION`, `AGENTS`, `build`, `params` in all four cases. `write_run_meta`
writes `source: "recorded"`, matching the `"reconstructed"` value the v1 file uses and
the report's existing branch on it.

**Risk noted.** T4 step 3 assumes `_make_agent` takes a module-like object with an
`evaluate` attribute; `_Evaluator` adapts the function-based interface to it. If
`_make_agent`'s signature differs, adapt the shim rather than changing `_make_agent` —
v1's construction path must not move.

## Requirements audit

Every request made about V2, and where it is covered.

| Requirement | Task | Note |
|---|---|---|
| Version tag on each agent, v2 and v3 | T2, T3 | v1 deliberately untagged; missing tag reads as v1 |
| Tag recorded correctly in the report | T5 | From `games.csv`, not from docs |
| Clone each agent to v2 and v3 files | T2, T3 | With "identical to v1, not yet changed" comments |
| Evaluators versioned too | T1 | Injected into three agents; editing in place would alter v1 |
| **Hyperparameters logged to the CSV** | **T4 step 6** | **Per agent, per game, as sorted JSON** |
| Analysis reads params from data, not docs | T5 | `roster_from_games`, keyed `label@version` |
| 25 trials | T6 | 2700 games, ~9.9 h |
| Same trials for every game | T6 | Uniform; the non-uniform option was declined |
| Isolation-hard stays at 0.02 s | — | No change made |
| Isolation heuristic considered | T2 | Became a defect fix, not a tuning change |
| Tournament records its own configuration | T4 | `run_meta.json`, written at startup |
| v1 stays frozen and reproducible | T4 step 8, T5 step 5 | Default version is v1; v1 report must regenerate byte-identically |

### Deferred deliberately, recorded so they are not lost

1. **The version-comparison run** (`mcts_v2` against `mcts_v3`). `--agent-version` is
   single-valued, so the harness **cannot yet run two versions against each other**. This
   is fine — v3 does not differ from v2 yet, so there is nothing to compare — but it is
   work that must happen before that comparison. The CSV params columns added here are
   what will make the result analysable when it does.
2. **The Ataxx crossover run** (MCTS vs heuristic at 2/5/10 s, ~3.7 h) to find where MCTS
   overtakes the one-ply agent. To be run after the final agent version, before the
   report is finished.
3. **Recording the evaluator version separately from the agent version.** The tournament
   ties them — `agent_source(v)` and `evaluator_source(v, game)` take the same string — so
   one field describes both. If they are ever allowed to differ, the CSV needs a second
   column.
