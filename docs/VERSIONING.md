# Agent versioning policy

Read this before changing any agent. It exists because this project's deliverable is
**measurements**, and a measurement is worthless if you cannot say what produced it.

---

## The rule

> **Once a tournament has been run with a version, that version is frozen. A fix is a
> new version, never an edit to the old one.**

The freeze point is **the run, not the creation**. A version under construction can be
changed freely. The moment a tournament writes results against it, it becomes a
historical record and stops being editable.

Editing a version that has already produced results silently invalidates every table,
figure and claim derived from them, and leaves no trace that it happened. That is the
same class of failure as the eight defects in `docs/FINDINGS.md`: a plausible,
well-formed result that is quietly wrong.

---

## What a version covers

A version is **everything that can change the numbers without changing the question**:

| Versioned | Why |
|---|---|
| `agents/vN/` | The search implementations themselves |
| `evaluation/vN/` | Evaluators are shared by three agents via injection; editing one in place would silently alter frozen v1 behaviour |
| **Hyperparameters** — caps, rollout parameters | See below. These used to live in the harness, which made them un-versionable |

**Deliberately NOT versioned:**

- `games/` — the rules define the *question*, not the answer. If a rule changes, it is
  not a new agent version, it is a different experiment and every previous result is
  void rather than comparable.
- `experiments/` — the harness measures; it does not play. A harness change affects how
  results are recorded, not what the agents do.

### Hyperparameters belong to the version, not the harness

In v1, `MCTS_ROLLOUT` and `CAPS` lived as constants in `experiments/tournament.py`. That
is the wrong home: they are **properties of an agent**, and leaving them in the harness
means two versions cannot declare different ones. It is also what made defect D4
possible - the tournament silently ran defaults the calibration had ranked worst.

From v2 onward each version package declares its own:

```python
# agents/v2/__init__.py
VERSION = "v2"
CAPS = {"max_entries": 200000, "max_nodes": 50000}
MCTS_ROLLOUT = {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10}
```

The harness asks the version package for its agents and records what it was given.

## Layout

```
agents/          alpha_beta_agent.py, mcts_agent.py, ...   <- v1. FROZEN. Do not touch.
agents/v2/       __init__.py + the four agents             <- the V2 run
agents/v3/       __init__.py + the four agents             <- the V3 run
evaluation/      isolation_eval.py, ...                    <- v1. FROZEN.
evaluation/v2/   isolation_eval.py, ...
evaluation/v3/   isolation_eval.py, ...
```

Each versioned module declares its own version:

```python
VERSION = "v2"
```

**v1 carries no `VERSION` constant and is not being changed.** It produced
`results/report.md` under the tag `v1-tournament`, and that report is published work.
Anything reading an agent treats a missing `VERSION` as `"v1"`.

The directory name and the `VERSION` constant must agree. A test enforces this, because
a clone with a stale tag inside it is exactly the kind of mistake that produces a run
labelled as something it is not.

---

## Why the code is duplicated rather than shared

Cloning an agent triples its code, and in ordinary software that would be wrong. Here it
is the point.

- **v1 must stay byte-identical** to what produced the published report.
- **v3 belongs to whoever is improving it** and must be changeable without any risk of
  disturbing v2.
- A shared base class would mean a change made for v3 silently altering v2's behaviour -
  which is precisely the thing this policy exists to prevent.

**The cost, stated plainly:** a genuine bug affecting more than one live version has to
be fixed in each of them separately, and each fix produces a **new version**. There is no
way to patch several versions at once, by design. Accept the duplication or accept
unattributable results; there is no third option.

---

## When you find a bug

| Situation | What to do |
|---|---|
| The version has **not** been run yet | Edit it in place. Nothing depends on it. |
| The version **has** been run | Create the next version with the fix. Leave the old one alone. |
| The bug affects several live versions | One new version per affected version. Say so in the commit message. |

Never edit a version to "just fix a typo" after it has been run. If it changed the
bytes, it can change the numbers.

---

## What gets recorded

Every run writes `results/raw/run_meta.json` at startup, containing the agent roster with
each agent's version and parameters, the caps, the budgets, the interpreter version, the
platform, and the git commit. `games.csv` additionally carries
`agent_first_version` / `agent_second_version` per game, so version attribution survives
even if the metadata file is lost.

This exists because the V1 run could **not** say from its own data which MCTS rollout
parameters produced it - they lived only as a constant in `tournament.py`. That gap caused
defect D4 and forced the rewrite of finding F3. Section 2 of the v1 report is
reconstructed for exactly this reason, and it says so.

---

## Which versions a run may mix

- **A grid run uses one version throughout.** The V2 run is entirely v2 agents.
- **A comparison run may mix two**, and should use distinct agent labels - `mcts_v2`
  against `mcts_v3` - rather than the same label at two versions. The analysis keys by
  agent label, so distinct labels need no special handling anywhere downstream.

Comparisons are between the **two newest versions** (v2 against v3). v1 is not a
comparison target; it is the historical baseline whose report is already written.

---

## V3 status

`docs/v3-candidates.md` now records both the screening work and the changes selected
for V3: Ataxx evaluator reweighting, per-side RNG streams, bounded-memory
instrumentation, MCTS subtree reuse, and duplicate `legal_moves()` removal in hot
search paths. Isolation and UTTT evaluators remain unchanged after screening did not
show a search-level improvement worth adopting.

## Deciding whether a change is worth a version

Version numbers are cheap; runs are not. The V2 grid costs about **10 hours**. Before
creating a version, be able to answer: what measurement will differ, and will the run be
able to resolve it? With 25 trials in both seat orders, a head-to-head cell contains
50 games and still has fairly wide uncertainty. A small expected effect should be
screened with a targeted head-to-head rather than justified by the full grid alone.
