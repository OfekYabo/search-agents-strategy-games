# Self-play time scaling: Alpha-Beta

Agent: **alpha_beta**. Every game is this agent against an identical copy of itself; the *only* difference between the two seats is the per-move time budget. Both seat orders are played with the same base seed and independent per-seat RNG streams, so a result cannot come from seat advantage or from one side consuming the other's random numbers.


The same design as the MCTS run: both seats are the identical v3 Alpha-Beta
agent with the same evaluator and the same transposition-table bound, and the
**only** difference between them is the per-move time budget. Both seat orders,
same base seed, independent per-seat RNG streams.

The main tournament cannot isolate this, because there the budget changes for
both players at once. 20 games per budget pair.


**Score is from the point of view of the side with the LARGER budget.** 0.500 means extra time bought nothing; an interval that excludes 0.500 means it bought something measurable.


| game | budget | vs | score (higher budget) | 95% CI | W-D-L | games | mean plies |
|---|---|---|---|---|---|---|---|
| ataxx | 0.50s | 0.10s | 1.000  **more time wins** | [0.839, 1.000] | 20-0-0 | 20 | 84.5 |
| ataxx | 2.00s | 0.10s | 0.950  **more time wins** | [0.764, 0.991] | 19-0-1 | 20 | 73.2 |
| ataxx | 2.00s | 0.50s | 0.550 | [0.342, 0.742] | 11-0-9 | 20 | 81.8 |
| isolation | 0.50s | 0.10s | 0.500 | [0.299, 0.701] | 10-0-10 | 20 | 17.0 |
| isolation | 2.00s | 0.10s | 0.500 | [0.299, 0.701] | 10-0-10 | 20 | 15.1 |
| isolation | 2.00s | 0.50s | 0.500 | [0.299, 0.701] | 10-0-10 | 20 | 15.0 |
| uttt | 0.50s | 0.10s | 0.250  **more time LOSES** | [0.112, 0.469] | 5-0-15 | 20 | 49.6 |
| uttt | 2.00s | 0.10s | 0.750  **more time wins** | [0.531, 0.888] | 10-10-0 | 20 | 51.1 |
| uttt | 2.00s | 0.50s | 1.000  **more time wins** | [0.839, 1.000] | 20-0-0 | 20 | 50.7 |

## Reading this

5 of 9 budget pairs have an interval that excludes 0.500. A pair that includes it is not evidence that time does nothing - with these sample sizes it is usually just too few games to tell.


This experiment deliberately does **not** answer whether one algorithm beats another; every game here is an agent against itself. It isolates the budget axis alone, which the main tournament cannot do because there both the agent and the budget change together.


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

