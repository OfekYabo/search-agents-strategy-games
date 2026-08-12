# Self-play time scaling: Alpha-Beta

Agent: **alpha_beta**. Every game is this agent against an identical copy of itself; the *only* difference between the two seats is the per-move time budget. Both seat orders are played with the same base seed and independent per-seat RNG streams, so a result cannot come from seat advantage or from one side consuming the other's random numbers.


> **[COMMENTARY NEEDED: selfplay-overview]**


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


> **[COMMENTARY NEEDED: selfplay-results]**

