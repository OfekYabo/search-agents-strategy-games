# Self-play time scaling: MCTS

Agent: **mcts**. Every game is this agent against an identical copy of itself; the *only* difference between the two seats is the per-move time budget. Both seat orders are played with the same base seed and independent per-seat RNG streams, so a result cannot come from seat advantage or from one side consuming the other's random numbers.


> **[COMMENTARY NEEDED: selfplay-overview]**


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


> **[COMMENTARY NEEDED: selfplay-results]**

