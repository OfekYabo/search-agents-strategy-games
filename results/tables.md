games 2160 (excluded 0 containing 0 error moves)

## Score rate by agent

| game | config | agent | W | D | L | score |
|---|---|---|---|---|---|---|
| ataxx | easy | alpha_beta | 120 | 0 | 0 | 1.000 |
| ataxx | easy | heuristic | 62 | 0 | 58 | 0.517 |
| ataxx | easy | mcts | 58 | 0 | 62 | 0.483 |
| ataxx | easy | random | 0 | 0 | 120 | 0.000 |
| ataxx | hard | alpha_beta | 119 | 0 | 1 | 0.992 |
| ataxx | hard | heuristic | 79 | 0 | 41 | 0.658 |
| ataxx | hard | mcts | 42 | 0 | 78 | 0.350 |
| ataxx | hard | random | 0 | 0 | 120 | 0.000 |
| ataxx | main | alpha_beta | 118 | 0 | 2 | 0.983 |
| ataxx | main | heuristic | 75 | 0 | 45 | 0.625 |
| ataxx | main | mcts | 47 | 0 | 73 | 0.392 |
| ataxx | main | random | 0 | 0 | 120 | 0.000 |
| isolation | easy | alpha_beta | 111 | 0 | 9 | 0.925 |
| isolation | easy | heuristic | 31 | 0 | 89 | 0.258 |
| isolation | easy | mcts | 86 | 0 | 34 | 0.717 |
| isolation | easy | random | 12 | 0 | 108 | 0.100 |
| isolation | hard | alpha_beta | 116 | 0 | 4 | 0.967 |
| isolation | hard | heuristic | 39 | 0 | 81 | 0.325 |
| isolation | hard | mcts | 78 | 0 | 42 | 0.650 |
| isolation | hard | random | 7 | 0 | 113 | 0.058 |
| isolation | main | alpha_beta | 108 | 0 | 12 | 0.900 |
| isolation | main | heuristic | 33 | 0 | 87 | 0.275 |
| isolation | main | mcts | 88 | 0 | 32 | 0.733 |
| isolation | main | random | 11 | 0 | 109 | 0.092 |
| uttt | easy | alpha_beta | 99 | 15 | 6 | 0.887 |
| uttt | easy | heuristic | 38 | 1 | 81 | 0.321 |
| uttt | easy | mcts | 86 | 15 | 19 | 0.779 |
| uttt | easy | random | 1 | 1 | 118 | 0.013 |
| uttt | hard | alpha_beta | 102 | 8 | 10 | 0.883 |
| uttt | hard | heuristic | 40 | 5 | 75 | 0.354 |
| uttt | hard | mcts | 87 | 6 | 27 | 0.750 |
| uttt | hard | random | 1 | 1 | 118 | 0.013 |
| uttt | main | alpha_beta | 99 | 13 | 8 | 0.879 |
| uttt | main | heuristic | 39 | 4 | 77 | 0.342 |
| uttt | main | mcts | 85 | 14 | 21 | 0.767 |
| uttt | main | random | 1 | 1 | 118 | 0.013 |

## First-move advantage (decisive games only)
first 1095, second 1023, decisive 2118, draws excluded 42, p = 0.1229

## Move-tag distribution
  alpha_beta   memory-limited   1380
  alpha_beta   normal           2822
  alpha_beta   time-limited     14238
  heuristic    normal           17796
  mcts         time-limited     18427
  random       normal           11210

## Simulations per root move (MCTS)

| game | config | agent | mean sims | median /root | p5 /root | % below 10 | verdict |
|---|---|---|---|---|---|---|---|
| ataxx | easy | mcts | 17916.8 | 347.6 | 122.1 | 0.0% | ample |
| ataxx | hard | mcts | 410.6 | 23.5 | 3.9 | 20.1% | viable |
| ataxx | main | mcts | 3142.1 | 90.3 | 36.9 | 0.0% | ample |
| isolation | easy | mcts | 92519.9 | 11705.6 | 1183.7 | 0.0% | ample |
| isolation | hard | mcts | 3150.3 | 258.6 | 49.1 | 0.0% | ample |
| isolation | main | mcts | 16776.0 | 1612.7 | 245.2 | 0.0% | ample |
| uttt | easy | mcts | 56875.1 | 1972.4 | 450.1 | 0.0% | ample |
| uttt | hard | mcts | 1621.9 | 96.6 | 20.5 | 2.5% | ample |
| uttt | main | mcts | 12197.9 | 485.3 | 91.3 | 0.0% | ample |

A STARVED row means the budget, not the algorithm, is what the result describes.

The headline is the MEDIAN of the per-decision simulations/legal-moves ratio. The mean of that ratio is not reported because positions with a single legal move contribute a ratio equal to the entire simulation count and inflate it by 4-8x; `p5 /root` and `% below 10` are given because the viability floor is a property of each decision, not of the average.
