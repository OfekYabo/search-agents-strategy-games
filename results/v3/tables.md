games 2700 (excluded 0 containing 0 error moves)

## Score rate by agent

| game | config | agent | W | D | L | score |
|---|---|---|---|---|---|---|
| ataxx | easy | alpha_beta | 150 | 0 | 0 | 1.000 |
| ataxx | easy | heuristic | 88 | 0 | 62 | 0.587 |
| ataxx | easy | mcts | 62 | 0 | 88 | 0.413 |
| ataxx | easy | random | 0 | 0 | 150 | 0.000 |
| ataxx | hard | alpha_beta | 150 | 0 | 0 | 1.000 |
| ataxx | hard | heuristic | 100 | 0 | 50 | 0.667 |
| ataxx | hard | mcts | 50 | 0 | 100 | 0.333 |
| ataxx | hard | random | 0 | 0 | 150 | 0.000 |
| ataxx | main | alpha_beta | 150 | 0 | 0 | 1.000 |
| ataxx | main | heuristic | 95 | 0 | 55 | 0.633 |
| ataxx | main | mcts | 55 | 0 | 95 | 0.367 |
| ataxx | main | random | 0 | 0 | 150 | 0.000 |
| isolation | easy | alpha_beta | 141 | 0 | 9 | 0.940 |
| isolation | easy | heuristic | 42 | 0 | 108 | 0.280 |
| isolation | easy | mcts | 106 | 0 | 44 | 0.707 |
| isolation | easy | random | 11 | 0 | 139 | 0.073 |
| isolation | hard | alpha_beta | 145 | 0 | 5 | 0.967 |
| isolation | hard | heuristic | 51 | 0 | 99 | 0.340 |
| isolation | hard | mcts | 93 | 0 | 57 | 0.620 |
| isolation | hard | random | 11 | 0 | 139 | 0.073 |
| isolation | main | alpha_beta | 139 | 0 | 11 | 0.927 |
| isolation | main | heuristic | 53 | 0 | 97 | 0.353 |
| isolation | main | mcts | 104 | 0 | 46 | 0.693 |
| isolation | main | random | 4 | 0 | 146 | 0.027 |
| uttt | easy | alpha_beta | 121 | 13 | 16 | 0.850 |
| uttt | easy | heuristic | 49 | 4 | 97 | 0.340 |
| uttt | easy | mcts | 113 | 14 | 23 | 0.800 |
| uttt | easy | random | 1 | 1 | 148 | 0.010 |
| uttt | hard | alpha_beta | 126 | 12 | 12 | 0.880 |
| uttt | hard | heuristic | 49 | 9 | 92 | 0.357 |
| uttt | hard | mcts | 104 | 16 | 30 | 0.747 |
| uttt | hard | random | 2 | 1 | 147 | 0.017 |
| uttt | main | alpha_beta | 124 | 16 | 10 | 0.880 |
| uttt | main | heuristic | 52 | 2 | 96 | 0.353 |
| uttt | main | mcts | 107 | 16 | 27 | 0.767 |
| uttt | main | random | 0 | 0 | 150 | 0.000 |

## First-move advantage (decisive games only)
first 1368, second 1280, decisive 2648, draws excluded 52, p = 0.0909

## Move-tag distribution
  alpha_beta   memory-limited   1705
  alpha_beta   normal           3613
  alpha_beta   time-limited     17903
  heuristic    normal           23460
  mcts         memory-limited   10
  mcts         time-limited     23404
  random       normal           14340

## Simulations per root move (MCTS)

| game | config | agent | mean sims | median /root | p5 /root | % below 10 | verdict |
|---|---|---|---|---|---|---|---|
| ataxx | easy | mcts | 22267.4 | 505.8 | 205.2 | 0.0% | ample |
| ataxx | hard | mcts | 656.7 | 35.6 | 8.9 | 5.9% | ample |
| ataxx | main | mcts | 4196.7 | 140.5 | 55.2 | 0.0% | ample |
| isolation | easy | mcts | 85789.1 | 10620.1 | 1388.1 | 0.0% | ample |
| isolation | hard | mcts | 3208.3 | 341.7 | 58.9 | 0.0% | ample |
| isolation | main | mcts | 16848.4 | 1640.7 | 299.0 | 0.0% | ample |
| uttt | easy | mcts | 54250.0 | 2042.1 | 442.9 | 0.0% | ample |
| uttt | hard | mcts | 1846.4 | 100.9 | 21.4 | 2.6% | ample |
| uttt | main | mcts | 11127.5 | 502.0 | 111.5 | 0.0% | ample |

A STARVED row means the budget, not the algorithm, is what the result describes.

The headline is the MEDIAN of the per-decision simulations/legal-moves ratio. The mean of that ratio is not reported because positions with a single legal move contribute a ratio equal to the entire simulation count and inflate it by 4-8x; `p5 /root` and `% below 10` are given because the viability floor is a property of each decision, not of the average.
