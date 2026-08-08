# search-agents-strategy-games

Comparing exact tree search and sampling-based search agents across strategy games of increasing state-space complexity, under realistic time and memory constraints.

Course project - Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev.

---

## Research Question

How do exact tree search and sampling-based search compare in playing strength, efficiency, and degradation behavior as state-space size increases, when both are constrained by the same realistic per-move time and memory budget?

---

## Games

| Game | State-space (approx.) | log10 | Role |
|---|---|---|---|
| Isolation 5x5 | ~1.0 x 10^10 | 10.0 | Small domain |
| Ataxx 7x7 | ~4.8 x 10^23 | 23.7 | Medium domain |
| Ultimate Tic-Tac-Toe | ~8.9 x 10^39 | 39.9 | Large domain |

Isolation 5x5 is a **declared variant** of the 1972 original, not the published game. Full rulesets, sources and rejected alternatives for all three games are in [`docs/games/`](docs/games/).

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

## Dependencies

**Running the tournament needs nothing installed** — Python 3.8+ and the standard library. That is deliberate, not minimalism: the measurement uses wall-clock per-move budgets, so a lean environment is part of the instrument, and a bare checkout must reproduce a run.

**Reproducing the figures** needs `matplotlib` and `numpy` (`requirements-analysis.txt`). They are imported only by `experiments/analyse.py`, `experiments/report.py` and `experiments/figures.py`, never by the measurement path.

```bash
python3 -m unittest discover -s tests            # 228 tests, no dependencies

python3 -m experiments.analyse --raw results/raw \
        --json results/analysis.json --label v1-tournament
python3 -m experiments.report --analysis results/analysis.json
```

The report is regenerated from scratch every time and is byte-identical for identical input. Hand-written interpretation lives in `docs/report/commentary.md` and is merged in by section id — never edit `results/report.md` directly.

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
- games/           # Custom game logic (Isolation, Ataxx, Ultimate Tic-Tac-Toe)
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
