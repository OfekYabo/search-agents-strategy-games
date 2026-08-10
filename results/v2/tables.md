games 2700 (excluded 0 containing 0 error moves)

## Score rate by agent

| game | config | agent | W | D | L | score |
|---|---|---|---|---|---|---|
| ataxx | easy | alpha_beta | 150 | 0 | 0 | 1.000 |
| ataxx | easy | heuristic | 77 | 0 | 73 | 0.513 |
| ataxx | easy | mcts | 73 | 0 | 77 | 0.487 |
| ataxx | easy | random | 0 | 0 | 150 | 0.000 |
| ataxx | hard | alpha_beta | 150 | 0 | 0 | 1.000 |
| ataxx | hard | heuristic | 100 | 0 | 50 | 0.667 |
| ataxx | hard | mcts | 50 | 0 | 100 | 0.333 |
| ataxx | hard | random | 0 | 0 | 150 | 0.000 |
| ataxx | main | alpha_beta | 147 | 0 | 3 | 0.980 |
| ataxx | main | heuristic | 95 | 0 | 55 | 0.633 |
| ataxx | main | mcts | 58 | 0 | 92 | 0.387 |
| ataxx | main | random | 0 | 0 | 150 | 0.000 |
| isolation | easy | alpha_beta | 138 | 0 | 12 | 0.920 |
| isolation | easy | heuristic | 37 | 0 | 113 | 0.247 |
| isolation | easy | mcts | 111 | 0 | 39 | 0.740 |
| isolation | easy | random | 14 | 0 | 136 | 0.093 |
| isolation | hard | alpha_beta | 149 | 0 | 1 | 0.993 |
| isolation | hard | heuristic | 55 | 0 | 95 | 0.367 |
| isolation | hard | mcts | 87 | 0 | 63 | 0.580 |
| isolation | hard | random | 9 | 0 | 141 | 0.060 |
| isolation | main | alpha_beta | 134 | 0 | 16 | 0.893 |
| isolation | main | heuristic | 44 | 0 | 106 | 0.293 |
| isolation | main | mcts | 112 | 0 | 38 | 0.747 |
| isolation | main | random | 10 | 0 | 140 | 0.067 |
| uttt | easy | alpha_beta | 123 | 12 | 15 | 0.860 |
| uttt | easy | heuristic | 48 | 2 | 100 | 0.327 |
| uttt | easy | mcts | 113 | 13 | 24 | 0.797 |
| uttt | easy | random | 2 | 1 | 147 | 0.017 |
| uttt | hard | alpha_beta | 131 | 11 | 8 | 0.910 |
| uttt | hard | heuristic | 53 | 7 | 90 | 0.377 |
| uttt | hard | mcts | 100 | 9 | 41 | 0.697 |
| uttt | hard | random | 2 | 1 | 147 | 0.017 |
| uttt | main | alpha_beta | 125 | 12 | 13 | 0.873 |
| uttt | main | heuristic | 49 | 5 | 96 | 0.343 |
| uttt | main | mcts | 110 | 12 | 28 | 0.773 |
| uttt | main | random | 1 | 1 | 148 | 0.010 |

## First-move advantage (decisive games only)
first 1373, second 1284, decisive 2657, draws excluded 43, p = 0.0878

## Move-tag distribution
  alpha_beta   memory-limited   1637
  alpha_beta   normal           3552
  alpha_beta   time-limited     17450
  heuristic    normal           22181
  mcts         time-limited     23118
  random       normal           14402

## Simulations per root move (MCTS)

| game | config | agent | mean sims | median /root | p5 /root | % below 10 | verdict |
|---|---|---|---|---|---|---|---|
| ataxx | easy | mcts | 15177.7 | 320.8 | 123.9 | 0.0% | ample |
| ataxx | hard | mcts | 388.4 | 18.2 | 3.6 | 32.4% | viable |
| ataxx | main | mcts | 2703.7 | 91.7 | 36.2 | 0.0% | ample |
| isolation | easy | mcts | 84803.4 | 10076.9 | 1114.2 | 0.0% | ample |
| isolation | hard | mcts | 2869.1 | 274.0 | 47.1 | 0.0% | ample |
| isolation | main | mcts | 15784.4 | 1457.0 | 230.6 | 0.0% | ample |
| uttt | easy | mcts | 53169.8 | 1891.2 | 484.9 | 0.0% | ample |
| uttt | hard | mcts | 1481.9 | 94.3 | 19.8 | 2.5% | ample |
| uttt | main | mcts | 10287.1 | 469.9 | 93.9 | 0.0% | ample |

A STARVED row means the budget, not the algorithm, is what the result describes.

The headline is the MEDIAN of the per-decision simulations/legal-moves ratio. The mean of that ratio is not reported because positions with a single legal move contribute a ratio equal to the entire simulation count and inflate it by 4-8x; `p5 /root` and `% below 10` are given because the viability floor is a property of each decision, not of the average.
