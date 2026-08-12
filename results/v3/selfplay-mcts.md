# Self-play time scaling: MCTS

Agent: **mcts**. Every game is this agent against an identical copy of itself; the *only* difference between the two seats is the per-move time budget. Both seat orders are played with the same base seed and independent per-seat RNG streams, so a result cannot come from seat advantage or from one side consuming the other's random numbers.


This experiment exists because the main tournament **cannot** answer the budget
question. There, the agent and the budget change together - MCTS at 2.0 s faces
a heuristic that is also at 2.0 s - so a score difference never isolates time.
Here both seats are the same v3 agent with the same evaluator and the same
memory bound, and the **only** difference is the clock.

Both seat orders are played from the same base seed with independent per-seat
RNG streams, so a result cannot come from first-move advantage or from the
faster-searching side consuming random numbers the other would have drawn.

20 games per budget pair. That is enough to detect a large effect and not
enough to detect a small one; treat every interval accordingly.


**Score is from the point of view of the side with the LARGER budget.** 0.500 means extra time bought nothing; an interval that excludes 0.500 means it bought something measurable.


| game | budget | vs | score (higher budget) | 95% CI | W-D-L | games | mean plies |
|---|---|---|---|---|---|---|---|
| ataxx | 0.50s | 0.10s | 1.000  **more time wins** | [0.839, 1.000] | 20-0-0 | 20 | 70.0 |
| ataxx | 2.00s | 0.10s | 0.950  **more time wins** | [0.764, 0.991] | 19-0-1 | 20 | 44.4 |
| ataxx | 2.00s | 0.50s | 0.800  **more time wins** | [0.584, 0.919] | 16-0-4 | 20 | 86.3 |
| isolation | 0.50s | 0.10s | 0.750  **more time wins** | [0.531, 0.888] | 15-0-5 | 20 | 17.9 |
| isolation | 2.00s | 0.10s | 0.850  **more time wins** | [0.640, 0.948] | 17-0-3 | 20 | 15.6 |
| isolation | 2.00s | 0.50s | 0.700 | [0.481, 0.855] | 14-0-6 | 20 | 17.5 |
| uttt | 0.50s | 0.10s | 0.700 | [0.481, 0.855] | 12-4-4 | 20 | 49.2 |
| uttt | 2.00s | 0.10s | 0.950  **more time wins** | [0.764, 0.991] | 19-0-1 | 20 | 45.9 |
| uttt | 2.00s | 0.50s | 0.625 | [0.409, 0.800] | 11-3-6 | 20 | 47.7 |

## Reading this

6 of 9 budget pairs have an interval that excludes 0.500. A pair that includes it is not evidence that time does nothing - with these sample sizes it is usually just too few games to tell.


This experiment deliberately does **not** answer whether one algorithm beats another; every game here is an agent against itself. It isolates the budget axis alone, which the main tournament cannot do because there both the agent and the budget change together.


**More time reliably buys MCTS strength, and buys the most where MCTS is
weakest.** Five of nine budget pairs have intervals excluding 0.500, and all
three Ataxx pairs are among them:

| Ataxx | score for the larger budget |
|---|---|
| 0.5 s vs 0.1 s | **1.000** (20-0-0) |
| 2.0 s vs 0.1 s | **0.950** (19-0-1) |
| 2.0 s vs 0.5 s | **0.800** (16-0-4) |

A clean sweep at 0.5 s against 0.1 s is about as unambiguous as 20 games get.

**Read this next to the main tournament, because together they say something
neither says alone.** On Ataxx, MCTS at 2.0 s crushes MCTS at 0.1 s - and still
scores 0.113 against a one-ply heuristic. Extra time makes MCTS substantially
better *at being MCTS*. It does not move it toward the policy the heuristic
already has.

That is the sharpest available statement of finding F3. The failure on Ataxx is
not a resource shortage that more seconds would fix; it is the sampling approach
itself being a poor fit for a game 35 wide. The V3 grid made the same point from
the other direction by roughly doubling MCTS's simulations per root move with no
measurable gain against the heuristic.

**The effect is weaker on the narrow games**, which fits. Isolation shows 0.750
and 0.850 for the larger budget but only 0.700 at 2.0 s against 0.5 s, and UTTT
reaches 0.950 at 2.0 s against 0.1 s while its adjacent pairs sit at 0.700 and
0.625 with intervals containing 0.500. Diminishing returns are visible on games
where MCTS is already close to the ceiling: it needs far less time to play
Isolation well than to play Ataxx badly.

**Where an interval contains 0.500, that is not evidence that time does
nothing.** At 20 games the interval is roughly +/-0.2 wide. Four of the nine
pairs are simply unresolved.

