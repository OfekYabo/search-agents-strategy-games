# Version duel: v2 vs v3

Every game is one agent type against **itself at two versions**, on the same game, at the same time budget, with the same memory bound. Only the version differs. Both seat orders are played from one base seed, so each trial is a matched pair rather than two independent samples.


**All scores below are from v3's point of view.** 0.500 means the versions are indistinguishable; an interval that excludes 0.500 means the difference is resolved.


> **[COMMENTARY NEEDED: duel-overview]**


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


> **[COMMENTARY NEEDED: duel-method]**


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

> **[COMMENTARY NEEDED: duel-results]**


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

> **[COMMENTARY NEEDED: duel-search-volume]**


## Limitations


> **[COMMENTARY NEEDED: duel-limitations]**

