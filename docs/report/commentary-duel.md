# Version duel commentary - v2 vs v3

Hand-written interpretation, merged into `results/duel/report.md` by section id.
That file is generated and any edit to it is lost on the next run.

<!-- section: duel-overview -->
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

<!-- section: duel-method -->
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

<!-- section: duel-results -->
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

<!-- section: duel-search-volume -->
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

<!-- section: duel-limitations -->
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
