# search-agents-strategy-games

Comparing exact tree search and sampling-based search agents across strategy games of increasing state-space complexity, under realistic time and memory constraints.

Course project - Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev.

---

## Research Question

How do exact tree search and sampling-based search compare in playing strength, efficiency, and degradation behavior as state-space size increases, when both are constrained by the same realistic per-move time and memory budget?

---

## Games

| Game | State-space (approx.) | Role |
|---|---|---|
| Isolation 5x5 | ~1.0 x 10^10 | Small domain |
| Attax 7x7 | ~4.8 x 10^23 | Medium domain |
| Ultimate Tic-Tac-Toe | ~8.9 x 10^38 | Large domain |

---

## Agents

| Agent | Family |
|---|---|
| Random | Baseline (no search) |
| Heuristic one-ply | Baseline (no search, domain knowledge) |
| Enhanced Alpha-Beta | Exact tree search |
| MCTS / UCT | Sampling-based search |

All search agents operate under a shared per-move time budget and a bounded memory footprint. Each move is tagged as **normal**, **time-limited**, or **memory-limited** to explain performance differences, not only report them.

---

## Experiment Design

- Round-robin tournament: 6 unique agent pairings per game, both agents starting first an equal number of times
- First-move advantage tracked explicitly
- Three time/memory budget configurations per game: easy, balanced, and hard (calibrated via a pilot sweep)
- All results logged to CSV; tables and graphs generated programmatically

---

## Metrics

- Win / loss / draw rate per agent, per game, per budget configuration
- Average move time, nodes expanded, simulations run
- Move-tag distribution (normal / time-limited / memory-limited)
- Scaling behavior across games and budget configurations

---

## Project Structure

```
search-agents-strategy-games/
- agents/          # Agent implementations (Random, Heuristic, Alpha-Beta, MCTS)
- games/           # Custom game logic (Isolation, Attax, Ultimate Tic-Tac-Toe)
- experiments/     # Tournament runner, calibration pilot, logging
- results/         # CSV logs and generated graphs
- report/          # Final report
```

---

## Setup

```bash
git clone https://github.com/<your-username>/search-agents-strategy-games.git
cd search-agents-strategy-games
pip install -r requirements.txt
```

---

## Running Experiments

```bash
# Calibration pilot (finds balanced time budget per game)
python experiments/calibrate.py --game isolation

# Full tournament
python experiments/tournament.py --game all --config balanced
```

---

## Authors

Ben-Gurion University of the Negev - Semester B 2025/26
