# V3 candidates

For whoever is building v3. Everything here is measured, not proposed from theory.

**Read `docs/VERSIONING.md` first.** The short version: `agents/v3/` and
`evaluation/v3/` are yours. `agents/`, `evaluation/` (v1) and `agents/v2/`,
`evaluation/v2/` are frozen - v1 produced the published report, and v2 produced the
run you will be compared against.

---

## Where things stand

V3 is now the active development version and deliberately differs from V2. V1/V2 stay
frozen. The selected V3 changes are:

- Ataxx evaluator weights: material/exposure **0.47/0.53** instead of 0.70/0.30.
- independent RNG streams per seat, so one stochastic agent cannot consume random
  numbers that would otherwise have belonged to its opponent;
- MCTS subtree reuse between consecutive decisions of the same agent;
- bounded-memory diagnostics (TT probes/hits/occupancy and active/reused MCTS nodes);
- duplicate `legal_moves()` removal from Alpha-Beta, MCTS rollout, and the game runner;
- explicit rejection of `workers > 1` in the main tournament, keeping wall-clock
  resource comparisons sequential;
- an optional, separate `experiments/time_budget_selfplay.py` experiment for comparing
  the same search algorithm against itself under unequal time budgets.

Isolation and UTTT evaluators remain unchanged. Screening found promising static
Isolation alternatives, but their extra evaluation cost reduced Alpha-Beta search
depth enough that no search-level improvement was established. UTTT candidates did
not reliably outperform the existing evaluator.

---

## Isolation evaluator screening (not selected for V3)

This remains useful background, but V3 intentionally keeps the existing evaluator.

The v1 report found the heuristic agent scoring only **0.750 against the random agent
on Isolation**, against 0.963 on UTTT and 1.000 on Ataxx. Isolation is the designated
control game, so a weak control is a real problem.

The first hypothesis - that the declined-win defect caused it - was **tested and
refuted**. Fixing it moved the score from 0.750 [0.666, 0.819] to 0.767 [0.683, 0.833]
over 720 games per version: two extra wins in 120, intervals almost entirely
overlapping. Declining a win usually still wins from a mobility advantage, so the rate
of declined wins is not the rate of lost games. **The weak control is unexplained and
still open.**

### What is already in place

`evaluation/v3/isolation_eval.py` contains five evaluators. The one in use is bound at
the bottom of the file:

```python
evaluate = mobility_difference          # change this one line
```

It is a plain name binding, not a wrapper function, deliberately: `evaluate` is called
thousands of times per decision under a wall-clock budget, so an extra call frame per
evaluation would cost measured search time.

### Measured, 600 games each against the random agent

Reproduce with `python3 -m experiments.compare_evaluators`:

| Evaluator | Score | 95% CI | Note |
|---|---|---|---|
| **`mixed`** | **0.912** | [0.886, 0.932] | 0.7·ratio + 0.3·reach. Best measured. |
| `ratio` | 0.885 | [0.857, 0.908] | Scale-free mobility difference |
| `mobility_difference` | 0.860 | [0.830, 0.885] | **In use.** Same as v1 and v2 |
| `aggressive` | 0.802 | [0.768, 0.832] | Worse |
| `reach` | 0.802 | [0.768, 0.832] | Worse alone |

Two results worth knowing before you theorise:

- **The classic "aggressive" heuristic (`mine - 2*theirs`) is worse here**, not better.
  Penalising the opponent's mobility harder loses ground on this board.
- **Region size alone is also worse.** Flood-fill partition detection is the standard
  strong Isolation heuristic, and on its own it *loses* to plain mobility - it ignores
  the immediate position entirely. It only helps as a minority tiebreak, which is what
  `mixed` does. Neither component wins alone; the combination beats both.

### Two caveats that decide how much this is worth

1. **The screening is against the random agent only.** Beating random better does not
   guarantee beating MCTS or Alpha-Beta better. It only rejects candidates not worth a
   ten-hour run.
2. **The evaluator is injected into three agents, not one.** The heuristic agent,
   Alpha-Beta and MCTS all receive it. Changing it moves all three, and it changes the
   basis of the study's headline finding - the MCTS-versus-heuristic ordering that
   inverts between games. Measured evaluator calls per decision on Isolation:

   | Agent | hard | main | easy |
   |---|---|---|---|
   | heuristic | 5.8 | 5.8 | 5.8 |
   | alpha_beta | 1,516 | 4,515 | 16,404 |
   | mcts | 200 (17% of rollouts) | 693 (4.7%) | 1,634 (**1.8%**) |

   **MCTS barely uses it.** With `epsilon=1.0` its rollouts pick moves at random and
   consult the evaluator only when a rollout hits the 10-ply cap without ending.
   Isolation games run ~13.7 plies, so most rollouts terminate first. Expect an
   evaluator change to move the heuristic agent a lot, Alpha-Beta somewhat, and MCTS
   on Isolation almost not at all.

---

## Ataxx evaluator change selected for V3

The existing material/exposure feature set was retained because it is cheap and already
captures two useful signals. Screening showed that the old 70/30 weighting overvalued
immediate material. V3 changes only the weights to **47% material / 53% exposure**, so
the evaluator has essentially identical computational cost while improving the
one-ply policy in direct screening.

## Other V2 results that motivate V3

Run the V2 report before choosing anything else. `results/v2/report.md` will carry the
same structure as `results/report.md`, so the two are directly comparable section by
section. Places worth looking:

- **Section 6, every agent against random.** If Isolation's heuristic is still near
  0.75 with the declined-win fix in, candidate 1 is well motivated.
- **Section 5, simulations per root move.** Ataxx-hard was the only cell below the
  viability floor in v1 (20.1% of decisions, p5 = 3.9). If that persists, MCTS on
  Ataxx-hard is worth attention.
- **Section 4, budget response.** Alpha-Beta was flat across a 20x budget increase on
  UTTT and Isolation - it saturates. MCTS was the only agent converting time into
  strength, and only on Ataxx.

---

## How to measure whether your change helped

**Do not compare v3 against v1.** v1-versus-v2 is already confounded three ways: the
declined-win fix, 20 versus 25 trials, and different budgets recorded per run. v3
against v2 is the clean comparison, and it is what the version machinery exists for.

Two ways, in increasing cost:

1. **Screen it** - `python3 -m experiments.compare_evaluators`, seconds. Rejects bad
   candidates. Does not confirm good ones.
2. **A full v3 grid run** - `--agent-version v3 --out results/v3`, ~10 hours, then
   compare `results/v2/report.md` with `results/v3/report.md` section by section.

A third option still exists and is **not yet built**: playing v2 and v3 agents directly
against each other in one tournament. That is a far more powerful design than comparing
each against a common field - detecting a 0.10 improvement through field scores needs
several hundred games per arm, while a paired head-to-head needs far fewer.
`--agent-version` is currently single-valued, so this needs harness work first. The
per-game version and parameter columns in `games.csv` were added so that the result
would be analysable once it exists.

---

## Resolution: what a run can actually detect

At 25 trials and two seat orders, a head-to-head cell holds **50 games**. The resulting
confidence interval is still wide enough that small effects may not be visible. Be able
to answer, before spending ten hours: what will differ, and is it large enough to see?
If not, screen it with a targeted head-to-head at far higher repetition instead of
using the full grid as the only evidence.
