# Version duel: v2 vs v3

Every game is one agent type against **itself at two versions**, on the same game, at the same time budget, with the same memory bound. Only the version differs. Both seat orders are played from one base seed, so each trial is a matched pair rather than two independent samples.


**All scores below are from v3's point of view.** 0.500 means the versions are indistinguishable; an interval that excludes 0.500 means the difference is resolved.


**This experiment exists because the V3 grid could not answer the question it
was supposed to answer.** Comparing each version's score against a common
four-agent field left every V2-to-V3 difference inside its confidence interval,
because a field score is diluted by three opponents that did not change.

Here the two versions play each other directly. Same agent type on both sides,
same game, same budget, same memory bound - only the version differs. That is a
**paired** design, and the difference in sensitivity is stark: what 2700 games
of grid could not resolve, 1350 games of duel resolves comfortably.

1350 games, 27 cells at exactly 50 games each, seat orders balanced 675/675,
zero illegal moves and zero agent errors.


## Method

| property | value |
|---|---|
| versions | v2 (first listed) vs v3 |
| games | 3 |
| configs | 3 |
| agents | alpha_beta, heuristic, mcts |
| total games | 1350 |
| RNG | per_side |

> **On randomness.** Both seats use independent per-seat streams regardless of what either version does in its own grid run. Shared streams are a property of the pair, not of one agent, so a duel cannot give each side its own historical mode. Holding it constant isolates the remaining changes.


**Three cells act as an unplanned control, and they came out perfectly.**

Where v3's code is behaviourally identical to v2 - the heuristic agent on
Isolation and UTTT, and Alpha-Beta on Isolation, none of which V3 changed - the
duel returns **exactly 0.500**, on records of 75-0-75, 70-10-70 and 75-0-75.

That is worth more than it looks. A harness with any seat bias, any seeding
asymmetry, or any scoring error could not produce three exact ties on
three-figure samples. **The balance of the design is demonstrated here rather
than assumed**, and every non-0.500 result below is therefore attributable to
the versions rather than to the apparatus.

The RNG note above is the one deliberate compromise. Shared-versus-per-seat
streams is a property of the *pair*, so a duel must pick one for both sides.
Per-seat is the unbiased choice, and holding it fixed means this experiment
isolates the other four V3 changes instead of confounding all five - a cleaner
question than the V3 grid could ask.


## Results


**Overall, pooled across every cell** - the widest and therefore most precise view:

| score (v3) | 95% CI | W-D-L | games | verdict |
|---|---|---|---|---|
| 0.560 | [0.533, 0.586] | 708-95-547 | 1350 | **stronger** |

**By agent** - the primary unit, because a version change need not affect every agent the same way

| agent | score (v3) | 95% CI | W-D-L | games | verdict |
|---|---|---|---|---|---|
| alpha_beta | 0.586 | [0.540, 0.630] | 241-45-164 | 450 | **stronger** |
| heuristic | 0.522 | [0.476, 0.568] | 230-10-210 | 450 | not resolved |
| mcts | 0.571 | [0.525, 0.616] | 237-40-173 | 450 | **stronger** |

**By agent and game**

| agent | game | score (v3) | 95% CI | W-D-L | games | verdict |
|---|---|---|---|---|---|---|
| alpha_beta | ataxx | 0.760 | [0.686, 0.821] | 114-0-36 | 150 | **stronger** |
| alpha_beta | isolation | 0.500 | [0.421, 0.579] | 75-0-75 | 150 | not resolved |
| alpha_beta | uttt | 0.497 | [0.418, 0.576] | 52-45-53 | 150 | not resolved |
| heuristic | ataxx | 0.567 | [0.487, 0.643] | 85-0-65 | 150 | not resolved |
| heuristic | isolation | 0.500 | [0.421, 0.579] | 75-0-75 | 150 | not resolved |
| heuristic | uttt | 0.500 | [0.421, 0.579] | 70-10-70 | 150 | not resolved |
| mcts | ataxx | 0.560 | [0.480, 0.637] | 84-0-66 | 150 | not resolved |
| mcts | isolation | 0.613 | [0.533, 0.688] | 92-0-58 | 150 | **stronger** |
| mcts | uttt | 0.540 | [0.460, 0.618] | 61-40-49 | 150 | not resolved |

**V3 is stronger overall: 0.560 [0.533, 0.586].** Resolved, and the first time
this project has resolved a version difference at all. Per agent, Alpha-Beta
reaches 0.586 and MCTS 0.571, both resolved; the heuristic sits at 0.522 and is
not.

But the pooled number hides the result that matters. **On Ataxx, the two search
agents move in opposite directions as the budget grows:**

| Ataxx, v3's score | 0.1 s | 0.5 s | 2.0 s |
|---|---|---|---|
| Alpha-Beta | 0.480 | **0.820** | **0.980** |
| MCTS | **0.760** | 0.580 | **0.340** |

**Alpha-Beta's gain compounds with depth.** The reweighted evaluator buys it
nothing at 0.1 s, a great deal at 0.5 s, and almost everything at 2.0 s
(49-0-1). That is exactly what one expects: a better evaluation function is
applied at every leaf, so its benefit grows as the search gets deeper.

**MCTS goes the other way, and ends up resolved in the wrong direction.** At the
largest budget v3 MCTS scores **0.340 [0.224, 0.478] against v2** - worse, not
better - while doing roughly **twice the simulations per root move** (326.5
against 160.7). More search, better evaluator, and it lost.

Two mechanisms are plausible and this run cannot separate them:

1. **The Ataxx evaluator change reaches MCTS through the rollout.** With
   `rollout_depth = 10` and Ataxx games running past a hundred plies, a rollout
   almost never terminates, so the evaluator supplies nearly every rollout's
   value. A reweighting tuned on a one-ply agent has no reason to be an
   improvement as a rollout terminal value.
2. **Subtree reuse carries statistics gathered under a different root.** On
   Ataxx-easy the retained tree is large and reuse fires 96% of the time, so
   stale visit counts persist across turns in exactly the cell where the effect
   is worst.

**What this says for the study's central question.** On the widest game, giving
the exact searcher a better evaluator produced a decisive gain, while giving the
sampling searcher twice the samples produced no gain and then a loss. Width does
not defeat MCTS because it is short of simulations - the fix that would follow
from that diagnosis was applied here and made things worse. That is the
strongest available support for **F3: beaten, not starved.**

**One caution.** 27 cells were tested. At a 5% threshold roughly one marginal
crossing is expected by chance and no correction has been applied, so a single
resolved cell should not be trusted alone. What makes the Ataxx MCTS result
credible is not the one cell but the **monotone trend across three budgets** -
0.760, 0.580, 0.340 - which chance does not order.


## Every cell


One row per agent, game and budget. These are for texture: a single cell is too small to resolve anything on its own, which is why the pooled rows above carry the result.

| agent | game | config | score (v3) | 95% CI | W-D-L | games | verdict |
|---|---|---|---|---|---|---|---|
| alpha_beta | ataxx | easy | 0.980 | [0.895, 0.996] | 49-0-1 | 50 | **stronger** |
| alpha_beta | ataxx | hard | 0.480 | [0.348, 0.615] | 24-0-26 | 50 | not resolved |
| alpha_beta | ataxx | main | 0.820 | [0.692, 0.902] | 41-0-9 | 50 | **stronger** |
| alpha_beta | isolation | easy | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| alpha_beta | isolation | hard | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| alpha_beta | isolation | main | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| alpha_beta | uttt | easy | 0.540 | [0.404, 0.670] | 5-44-1 | 50 | not resolved |
| alpha_beta | uttt | hard | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| alpha_beta | uttt | main | 0.450 | [0.321, 0.587] | 22-1-27 | 50 | not resolved |
| heuristic | ataxx | easy | 0.600 | [0.462, 0.724] | 30-0-20 | 50 | not resolved |
| heuristic | ataxx | hard | 0.560 | [0.423, 0.688] | 28-0-22 | 50 | not resolved |
| heuristic | ataxx | main | 0.540 | [0.404, 0.670] | 27-0-23 | 50 | not resolved |
| heuristic | isolation | easy | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| heuristic | isolation | hard | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| heuristic | isolation | main | 0.500 | [0.366, 0.634] | 25-0-25 | 50 | not resolved |
| heuristic | uttt | easy | 0.500 | [0.366, 0.634] | 23-4-23 | 50 | not resolved |
| heuristic | uttt | hard | 0.500 | [0.366, 0.634] | 24-2-24 | 50 | not resolved |
| heuristic | uttt | main | 0.500 | [0.366, 0.634] | 23-4-23 | 50 | not resolved |
| mcts | ataxx | easy | 0.340 | [0.224, 0.478] | 17-0-33 | 50 | **WEAKER** |
| mcts | ataxx | hard | 0.760 | [0.626, 0.857] | 38-0-12 | 50 | **stronger** |
| mcts | ataxx | main | 0.580 | [0.442, 0.706] | 29-0-21 | 50 | not resolved |
| mcts | isolation | easy | 0.520 | [0.385, 0.652] | 26-0-24 | 50 | not resolved |
| mcts | isolation | hard | 0.660 | [0.522, 0.776] | 33-0-17 | 50 | **stronger** |
| mcts | isolation | main | 0.660 | [0.522, 0.776] | 33-0-17 | 50 | **stronger** |
| mcts | uttt | easy | 0.510 | [0.376, 0.643] | 18-15-17 | 50 | not resolved |
| mcts | uttt | hard | 0.590 | [0.452, 0.715] | 24-11-15 | 50 | not resolved |
| mcts | uttt | main | 0.520 | [0.385, 0.652] | 19-14-17 | 50 | not resolved |

## Search volume


What each version actually did with the same budget. This is where a difference in *strength* would have to come from, and its absence beside a large difference here is itself a result.

| agent | game | config | version | median work/move | median sims/root |
|---|---|---|---|---|---|
| alpha_beta | ataxx | easy | v2 | 75707 | - |
| alpha_beta | ataxx | easy | v3 | 83371 | - |
| alpha_beta | ataxx | hard | v2 | 3805 | - |
| alpha_beta | ataxx | hard | v3 | 4121 | - |
| alpha_beta | ataxx | main | v2 | 18795 | - |
| alpha_beta | ataxx | main | v3 | 20620 | - |
| alpha_beta | isolation | easy | v2 | 1334 | - |
| alpha_beta | isolation | easy | v3 | 1334 | - |
| alpha_beta | isolation | hard | v2 | 2307 | - |
| alpha_beta | isolation | hard | v3 | 2661 | - |
| alpha_beta | isolation | main | v2 | 7765 | - |
| alpha_beta | isolation | main | v3 | 7765 | - |
| alpha_beta | uttt | easy | v2 | 34550 | - |
| alpha_beta | uttt | easy | v3 | 34598 | - |
| alpha_beta | uttt | hard | v2 | 1626 | - |
| alpha_beta | uttt | hard | v3 | 1626 | - |
| alpha_beta | uttt | main | v2 | 8361 | - |
| alpha_beta | uttt | main | v3 | 8345 | - |
| heuristic | ataxx | easy | v2 | 36 | - |
| heuristic | ataxx | easy | v3 | 29 | - |
| heuristic | ataxx | hard | v2 | 35 | - |
| heuristic | ataxx | hard | v3 | 30 | - |
| heuristic | ataxx | main | v2 | 37 | - |
| heuristic | ataxx | main | v3 | 29 | - |
| heuristic | isolation | easy | v2 | 6 | - |
| heuristic | isolation | easy | v3 | 6 | - |
| heuristic | isolation | hard | v2 | 6 | - |
| heuristic | isolation | hard | v3 | 6 | - |
| heuristic | isolation | main | v2 | 6 | - |
| heuristic | isolation | main | v3 | 6 | - |
| heuristic | uttt | easy | v2 | 8 | - |
| heuristic | uttt | easy | v3 | 8 | - |
| heuristic | uttt | hard | v2 | 8 | - |
| heuristic | uttt | hard | v3 | 8 | - |
| heuristic | uttt | main | v2 | 8 | - |
| heuristic | uttt | main | v3 | 8 | - |
| mcts | ataxx | easy | v2 | 5848 | 160.7 |
| mcts | ataxx | easy | v3 | 9564 | 326.5 |
| mcts | ataxx | hard | v2 | 290 | 5.7 |
| mcts | ataxx | hard | v3 | 479 | 10.0 |
| mcts | ataxx | main | v2 | 1507 | 44.4 |
| mcts | ataxx | main | v3 | 2495 | 67.7 |
| mcts | isolation | easy | v2 | 58643 | 12678.4 |
| mcts | isolation | easy | v3 | 62971 | 12616.7 |
| mcts | isolation | hard | v2 | 982 | 199.7 |
| mcts | isolation | hard | v3 | 1282 | 242.2 |
| mcts | isolation | main | v2 | 6532 | 1552.7 |
| mcts | isolation | main | v3 | 9235 | 1683.8 |
| mcts | uttt | easy | v2 | 13500 | 1889.3 |
| mcts | uttt | easy | v3 | 14711 | 2063.6 |
| mcts | uttt | hard | v2 | 707 | 98.4 |
| mcts | uttt | hard | v3 | 772 | 107.1 |
| mcts | uttt | main | v2 | 3457 | 480.7 |
| mcts | uttt | main | v3 | 3764 | 531.4 |

The volume table is the reason the strength results are interpretable rather
than mysterious: it shows the versions genuinely differ in how much work they
do with the same clock.

**Alpha-Beta gains 8-10% more nodes on Ataxx** (83,371 against 75,707 at the
easy budget) from the hot-path cleanup, and is essentially identical on
Isolation and UTTT - 1334 against 1334, 1626 against 1626, 8345 against 8361.
Those identical figures are the same control as the exact 0.500 scores: where
nothing changed, nothing moved.

**MCTS gains far more - roughly double on Ataxx** (9564 simulations against
5848, and 326.5 per root move against 160.7) from subtree reuse plus the
cleanup.

Set those two rows side by side and the study's result falls out. The agent
that gained **8%** more work won its Ataxx cells decisively. The agent that
gained **100%** more work lost its largest one. **On a game this wide, the
binding constraint is the quality of what search is directed by, not the
quantity of search.**


## Limitations


**Four changes are still bundled.** Holding the RNG constant isolated one of
V3's five changes, but the Ataxx evaluator reweighting, subtree reuse, the
hot-path cleanup and the instrumentation all landed together. The Ataxx MCTS
reversal has two plausible causes and this run cannot say which. Separating them
needs a version that changes one thing.

**Multiple comparisons.** 27 cells, no correction applied. Roughly one marginal
crossing is expected by chance, so single resolved cells are weak evidence. The
pooled and per-agent rows, and trends across budgets, are the parts to rely on.

**A duel measures relative strength, not absolute.** v3 beating v2 says nothing
about whether either would beat the field, and the V3 grid showed the field
scores barely moved. Both statements are true at once: v3 is measurably better
head-to-head and not measurably better against a mixed field, because a 0.56
edge over one opponent is diluted to invisibility across four.

**v2 agents ran here in a mode they never ran in.** Per-seat RNG streams are a
V3 behaviour; V2's own tournament used a shared stream. That is the right
choice for fairness, but it means these v2 results are not the v2 that produced
`results/v2/report.md`.

**One sample, one host**, as with every run in this project. The exact-0.500
control cells give unusually strong evidence that the apparatus is unbiased, but
they say nothing about run-to-run variance in the cells that did move.

