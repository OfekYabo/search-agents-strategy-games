# Self-play time-scaling commentary - alpha_beta

Hand-written interpretation, merged into `results/v3/selfplay-alpha_beta.md` by
section id. That file is generated and any edit to it is lost on the next run.

<!-- section: selfplay-overview -->
The same design as the MCTS run: both seats are the identical v3 Alpha-Beta
agent with the same evaluator and the same transposition-table bound, and the
**only** difference between them is the per-move time budget. Both seat orders,
same base seed, independent per-seat RNG streams.

The main tournament cannot isolate this, because there the budget changes for
both players at once. 20 games per budget pair.

<!-- section: selfplay-results -->
**Alpha-Beta on Isolation is exactly indifferent to time.** Three budget pairs,
three identical results:

| Isolation | score for the larger budget | record |
|---|---|---|
| 0.5 s vs 0.1 s | 0.500 | 10-0-10 |
| 2.0 s vs 0.1 s | 0.500 | 10-0-10 |
| 2.0 s vs 0.5 s | 0.500 | 10-0-10 |

A 20x budget increase produces a dead-even split, twenty times out of twenty,
in every pair. **This is the cleanest confirmation in the project that
Isolation is a control rather than a degradation datapoint.** Every previous
run inferred saturation indirectly - from Alpha-Beta spending only 34-54% of
its budget, or from a flat field-score curve. This measures it head-on: the
extra seconds buy literally nothing because the position is already solved at
the smallest budget.

**On Ataxx, time clearly helps at the bottom of the range and stops helping at
the top.** 1.000 at 0.5 s against 0.1 s and 0.950 at 2.0 s against 0.1 s, but
0.550 [0.342-0.742] at 2.0 s against 0.5 s. Alpha-Beta's returns flatten between
0.5 s and 2.0 s - consistent with its median depth on Ataxx being 3-4 across the
whole grid, since another factor of four in time is not enough to buy a further
ply against a branching factor above 30.

**One anomaly, which should not be believed yet.** UTTT at 0.5 s scores **0.250
[0.112-0.469] against 0.1 s** - flagged "more time LOSES" - while 2.0 s beats
both (0.750 and 1.000). A non-monotonic budget response like that is the
signature of **search pathology**, where a deeper search can evaluate a position
*worse* than a shallower one because the horizon lands on a different parity of
move. It is a real phenomenon in game-tree search and UTTT's structure makes it
plausible.

But three reasons to hold off:

1. **20 games**, with an interval that only just excludes 0.500.
2. **Nine comparisons per agent.** At a 5% threshold, roughly one marginal
   crossing is expected by chance across this many tests, and no correction has
   been applied.
3. The **2.0 s results contradict it** - if more search were genuinely harmful
   on UTTT, 2.0 s should not beat 0.5 s 20-0.

Worth a targeted run at several hundred games on that one cell before it goes in
a report as a finding. Recording it here so it is not quietly lost.
