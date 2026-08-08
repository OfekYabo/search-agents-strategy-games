# Design: analysis extension and deterministic report generator

**Date:** 2026-08-09 · **Status:** approved, pending implementation plan
**Context:** the v1 tournament (2160 games, tag `v1-tournament`) is complete and its raw
CSVs are committed. `analyse.py` emits four basic tables and no figures.

---

## Goals

1. Extend the analysis so the numbers the project's claims actually rest on exist in code
   rather than in shell history — confidence intervals, head-to-head results, budget response.
2. Produce a **report** with two clearly separated kinds of content:
   - **Deterministic**: every table and figure computed from raw CSVs. Same input, byte-identical output. Works on any run, v1 or future.
   - **Interpretive**: hand-written prose in named slots, filled by a human or an agent
     *after* generation, which regeneration must never destroy.
3. Serve two audiences: us, understanding the run; and the school submission, which will
   take parts of this verbatim.

## Non-goals

- No changes to the measurement path. `games/`, `agents/`, `evaluation/`, `runner.py`,
  `tournament.py`, `logger.py` are untouched. The v1 CSVs are frozen evidence.
- No re-running of the tournament.
- No statistical machinery beyond what a claim in this project actually needs. No scipy.

---

## Dependency policy — an explicit split

The project has been stdlib-only, and the earlier framing treated that as global. It is
not: the constraint protects the **measurement**, where wall-clock budgets mean any
background CPU corrupts results and the harness must run from a bare checkout. It buys
nothing in **post-hoc analysis**, which reads frozen CSVs and cannot affect a measurement.

| Path | Modules | Dependencies |
|---|---|---|
| **Measurement** | `games/`, `agents/`, `evaluation/`, `experiments/{runner,tournament,logger,calibrate,measure_branching}.py` | **stdlib only — unchanged promise** |
| **Analysis / report** | `experiments/{analyse,report}.py` | matplotlib, numpy (`requirements-analysis.txt`) |

Installed on the tournament VM via apt: matplotlib 3.5.1, numpy 1.21.5. Verified to add
**no systemd services and no timers** (48 enabled units before and after), so a future run
is unaffected. The existing operational rule is unchanged and sufficient: *do not run
analysis while a tournament is running.*

README and RUNBOOK must state the split plainly, so "running the tournament needs nothing
installed" stays true and "reproducing the figures needs these two" is not a surprise.

> A secondary reason to prefer matplotlib over hand-rolled SVG: defect D9 was a
> reporting-layer bug that produced well-formed, plausible, wrong output and passed its own
> test. Adding 200-300 lines of bespoke axis-scaling code to that same layer is the wrong
> direction. Use the library that is already battle-tested.

---

## Architecture

Computation and presentation are split, because today `analyse.py` computes and prints in
one pass, which makes the numbers impossible to reuse and the rendering impossible to test.

```
results/raw/{games,moves}.csv
        |
        v
  analyse.py          computes everything, once
        |
        +--> results/analysis.json     <-- single source of truth
        +--> stdout (markdown summary, unchanged behaviour for quick CLI use)
        |
        v
  report.py           renders only; never recomputes
        |
        +--> results/figures/*.svg
        +--> results/report.md     <-- generated, committed, never hand-edited
                ^
                |
        docs/report/commentary.md  <-- hand-written, tracked, merged by ID
```

**Why the JSON matters:** every figure and table in the report traces to one computation,
and `report.py` is testable against a fixed JSON fixture without running a tournament.

### Module responsibilities

- **`analyse.py`** — loads CSVs, computes all statistics, writes `analysis.json`, prints the
  existing markdown summary. Gains `--json <path>`. Keeps working exactly as today when
  called without it.
- **`report.py`** — reads `analysis.json` and `commentary.md`, renders SVG figures and
  `report.md`. Flags: `--analysis`, `--commentary`, `--out`, `--label`.

> **Remove `analyse.py`'s `--out results/figures` argument.** It is declared at
> `analyse.py:203` and never used — figures were intended from the start and never built.
> Leaving it would give two modules an argument named `--out` with different meanings, one
> of which does nothing. Figure output is `report.py`'s responsibility alone.

---

## Data contract: `analysis.json`

Top-level keys. All lists sorted deterministically by their key tuple.

```
meta                 games_total, games_excluded, error_moves, label,
                     games[], configs[], agents[], budgets{game:{config:seconds}}
score_table          [{game, config, agent, w, d, l, n, score, ci_low, ci_high}]
head_to_head         [{game, config, agent, opponent, w, d, l, n, score, ci_low, ci_high}]
budget_response      [{game, agent, points:[{config, budget_s, score, ci_low, ci_high}]}]
simulations_per_root [{game, config, agent, moves, mean_simulations, median_per_root,
                       p5_per_root, pct_below_floor, verdict}]
search_depth         [{game, config, agent, median_depth, max_depth, n}]
budget_compliance    [{game, config, agent, mean_ratio, p99_ratio, max_ratio, n}]
game_length          [{game, config, mean_plies, median_plies, n, end_reasons{}}]
tag_distribution     [{agent, tag, count}]
first_move_advantage {first, second, decisive, draws_excluded, p}
```

### New statistics

- **Wilson score interval** for every score, not the normal approximation. The normal
  approximation produced a *negative* lower bound at the observed 0.050, which cannot be
  reported. Wilson is closed-form over `math` and behaves at the extremes. Draws count as
  half a win, consistent with the existing score definition.
- **Head-to-head**, per `(game, config, agent, opponent)`, pooled over both seat orders.
  The field-wide score conflates opponents — MCTS's 0.483 on Ataxx-easy averages 1.000
  against random with 0.000 against Alpha-Beta — while every finding in the project asserts
  a head-to-head claim.
- **Budget response**: **field score** (against all opponents, the same pool for every
  agent) as a function of the budget, per agent per game. This is the direct answer to "how
  does each paradigm convert time into strength." Head-to-head budget response is not
  stored separately — it is derivable from `head_to_head` by reading the three configs of a
  given `(game, agent, opponent)` triple, and duplicating it would create two numbers that
  could disagree.
- **Search depth**, **budget compliance** (elapsed/budget ratios), **game length** and
  end-reason distributions: already derivable, not currently surfaced. Budget compliance in
  particular is instrument validation and belongs in the report.

---

## Figures

SVG, via matplotlib's `Agg`/SVG backend. Four required:

| id | Figure | Content |
|---|---|---|
| `fig-score-by-agent` | Grouped bars | Score per agent, grouped by config, one panel per game, with CI error bars |
| `fig-budget-response` | Line, log-x | Score vs budget seconds, one line per agent, one panel per game |
| `fig-head-to-head` | Matrix heatmap | Agent x opponent score, one panel per game, annotated cells. **Config-pooled by summing W/D/L across the three configs then recomputing the score** — not by averaging three scores, which would weight a 40-game cell equally with a 40-game cell of different variance and is not the same number |
| `fig-sims-per-root` | Line, log-x/log-y | Median simulations per root move vs budget, per game, with the viability floor drawn as a reference line |

`fig-budget-compliance` is optional and may be dropped if it adds nothing over the table.

---

## Determinism

Same raw CSVs must give a byte-identical report. Concretely:

- **No `datetime.now()`**, anywhere, in any output. Provenance comes from the data
  (counts, configs present) plus the optional `--label` for a git tag.
- **matplotlib SVG is not deterministic by default.** It writes a `<dc:date>` metadata
  element and hashes element IDs per process. Both must be pinned:
  `savefig(..., metadata={"Date": None})` and a fixed `rcParams["svg.hashsalt"]`.
- All dict iteration sorted before output; JSON written with `sort_keys=True`.
- Floats rounded at write time to a fixed precision, so platform float repr cannot leak in.

A test asserts that generating twice from one fixture produces identical bytes.

---

## Commentary: the sidecar, and why not in-place

The generated report is **100% derived and disposable**. Hand-written prose lives in
`docs/report/commentary.md`, tracked in git, as sections keyed by stable IDs:

```markdown
<!-- section: headline-results -->
Alpha-Beta wins every cell. The interesting structure is in second place...

<!-- section: budget-response -->
<!-- TODO -->
```

`report.py` merges commentary into matching slots. A missing or `TODO`-only section renders
as a visible callout:

> **[COMMENTARY NEEDED: budget-response]**

so gaps are obvious in the output rather than silently absent.

**Why a sidecar rather than markers inside the report:** prose inside the generated file
means regeneration either destroys it or requires round-trip parsing of a file that is
supposed to be write-only. A sidecar makes "regenerate" unconditionally safe, which is the
property that lets us regenerate freely for every future run. It also makes filling
commentary a single-file task for a human or an agent, with the generated report alongside
as reference.

Commentary IDs are fixed by the report structure and validated: an ID in `commentary.md`
that matches no slot is an error, not a silent no-op, so renamed sections cannot orphan
prose.

---

## Report structure

Each section is generated content followed by its commentary slot.

| # | Section | Generated | Commentary id |
|---|---|---|---|
| 1 | Overview | run size, games, configs, budgets, label | `overview` |
| 2 | Headline results | score table + `fig-score-by-agent` | `headline-results` |
| 3 | Head-to-head | matrices + `fig-head-to-head` | `head-to-head` |
| 4 | Budget response | `fig-budget-response` + per-game table | `budget-response` |
| 5 | Search volume and viability | sims-per-root table + `fig-sims-per-root` | `search-volume` |
| 6 | Instrument validation | budget compliance, error counts, first-move advantage | `instrument-validation` |
| 7 | Game characteristics | lengths, end reasons, search depth | `game-characteristics` |
| 8 | Limitations | reproducibility note, jitter, one-sample caveat | `limitations` |

---

## Testing

- **Wilson interval** against published worked values, including the extremes where the
  normal approximation fails.
- **Head-to-head** against a hand-computed fixture, explicitly covering both seat orders
  and draws.
- **Determinism**: render twice from one fixture, assert byte equality, including SVGs.
- **Commentary merge**: present ID inserts; missing ID renders the callout; unknown ID
  raises.
- **Schema**: `analysis.json` contains every documented key, and `report.py` fails loudly
  on a missing one rather than rendering a blank section.
- Existing 178 tests keep passing; the measurement path is untouched.

---

## Delivery order

1. Analysis additions in `analyse.py` + `analysis.json` (with tests).
2. `report.py`: figures, tables, commentary merge, determinism (with tests).
3. Documentation consistency pass: README, RUNBOOK dependency split, and the spec's
   superseded §5.5 starvation framing.
4. Commentary drafted as a separate pass, once the skeleton exists.

Steps 1 and 2 are the implementation plan's scope. Step 4 is deliberately separate: the
skeleton should exist and be reviewed before prose is written against it.
