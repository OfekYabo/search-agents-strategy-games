# Search-Based Agents for Strategy Games - Project Plan

> Academic project - Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev  
> Repository: `search-agents-strategy-games`

---

## Research Question

How do **exact tree search** (Alpha-Beta with enhancements) and **sampling-based search** (MCTS/UCT) compare in playing strength, efficiency, and degradation behavior across two-player strategy games whose state-space sizes span ~28 orders of magnitude, when both are constrained by the same realistic per-move **time and memory budget**?

Benchmarked against a random baseline and a no-search heuristic baseline.

---

## Why This Comparison Is Non-Trivial

- Explicitly avoids the course-flagged "weak project" pattern: this is **not** Minimax vs Alpha-Beta (two refinements of the same algorithm). The two compared agents come from genuinely different search paradigms.
- Three games spanning ~28 orders of magnitude in state-space size lets us test whether the paradigm comparison **shifts with scale**, rather than asserting it from one data point.
- Realistic time/memory constraints (not artificial fixed depth) give both paradigms a shared, fair resource model.
- Move-type tagging produces **explanatory data** (why performance changes) not just outcome data (that it changes).

---

## Games

| Game | Board | State-space upper bound | log10 | Role |
|---|---|---|---|---|
| Isolation 5x5 | 5x5 grid | 2 x 25 x 24 x 2^23 ~ 1.01 x 10^10 | 10.0 | Small domain |
| Attax 7x7 | 7x7 grid | 2 x 3^49 ~ 4.78 x 10^23 | 23.7 | Medium domain |
| Ultimate Tic-Tac-Toe | 9x(3x3) | 2 x 3^81 ~ 8.89 x 10^38 | 38.9 | Large domain |

### State-Space Derivations (verified)

**Isolation 5x5:** 25 cells; player A on any of 25, player B on any remaining 24, each of the other 23 cells independently open/blocked (2^23), times 2 for whose turn:  
`2 x 25 x 24 x 2^23 = 10,066,329,600 ~ 1.01 x 10^10`

**Attax 7x7:** 49 cells, each in 3 states (empty / P1 / P2): `3^49 ~ 2.39 x 10^23`, times 2:  
`2 x 3^49 ~ 4.78 x 10^23`

**Ultimate Tic-Tac-Toe:** 81 cells (9 boards x 9), each in 3 states: `3^81 ~ 4.44 x 10^38`, times 2:  
`2 x 3^81 ~ 8.89 x 10^38`

All three are loose upper bounds (do not exclude unreachable states).

### Hardness Comparison Summary

| Game | State-space (approx.) | log10 | Branching factor (avg) | Avg game length (plies) |
|---|---|---|---|---|
| Isolation 5x5 | 1.01 x 10^10 | 10.0 | TODO - pending movement rule confirmation | TODO - pending simulation |
| Attax 7x7 | 4.78 x 10^23 | 23.7 | TODO - pending simulation (reference: ~60 for canonical Ataxx) | TODO - pending simulation (reference: ~100 for canonical Ataxx) |
| Ultimate Tic-Tac-Toe | 8.89 x 10^38 | 38.9 | TODO - pending simulation (common case bounded by 9) | TODO - pending simulation |

### Branching Factor

Not a fixed constant - changes through the game. **Measure empirically** via random self-play simulation (batch of N=1000 games per game type, record legal-move count distribution at every ply). This is a natural byproduct of building the random agent.

External reference for Attax: canonical Ataxx (7x7 with two fixed blocked squares) has average branching factor ~60 and average game length ~100 plies.

> **TODO:** Finalize Isolation 5x5 movement rule - options are:
> - King-step (one cell in any of 8 directions): branching factor bounded by 8 throughout, shrinks as cells become blocked
> - Queen-slide (any number of cells in a straight line, blocked by occupied/blocked cells): theoretical max from board center on first move = 4 orthogonal directions x 2 reachable cells + 4 diagonal directions x 2 reachable cells = 16
>
> This affects branching factor calculation only, not the state-space formula.
> Fill in branching factor and average game length for all three games after running pilot simulations.

### Game Descriptions

**Isolation 5x5:** Two players each control one piece on a 5x5 grid. On each turn a player moves their piece to a legal cell, and the cell they just left becomes permanently blocked. A player with no legal move loses.

**Attax 7x7:** On a 7x7 grid, a player can either clone their piece to an adjacent empty cell (the original stays), or jump two cells away to an empty cell (the original is removed). After moving, all opponent pieces adjacent to the destination are converted to the current player's color. A player with no pieces or no legal move loses.

**Ultimate Tic-Tac-Toe:** Nine 3x3 boards arranged in a 3x3 super-grid. Playing in cell (r, c) of any small board forces the opponent to play next in the small board at super-position (r, c). Winning three small boards in a row on the super-grid wins the game. When sent to a finished board, the player may move anywhere.

---

## Agents (Four Static Identities)

| Agent | Family | Role |
|---|---|---|
| Random | No search | Sanity-check baseline |
| Heuristic (one-ply) | No search, domain knowledge | Tight baseline - isolates what search contributes |
| Enhanced Alpha-Beta | Exact tree search | Strongest of the exact-search family |
| MCTS / UCT | Sampling-based search | Strongest of the sampling-based family |

All four play as **static identities** in a round-robin tournament (not seat-based P1/P2).

### Agent Details

#### Random
Selects uniformly among legal moves. No time or memory pressure expected. Included to keep tagging infrastructure uniform and as a sanity-check floor.

#### Heuristic (one-ply)
Evaluates each legal move with a domain-specific function, picks best-scoring without any lookahead. Evaluation is **incremental** (running best-so-far) so a time cutoff mid-evaluation returns a valid tagged move rather than failing.

**This same evaluation function is used by Alpha-Beta at its search horizon**, so performance differences between Heuristic and Alpha-Beta are attributable to search depth, not to different evaluation functions.

Starter evaluation functions (to be tuned during development):
- **Isolation:** own legal-move count minus opponent legal-move count (mobility difference)
- **Attax:** piece-count difference + number of opponent pieces immediately convertible by the candidate move + positional stability term
- **Ultimate Tic-Tac-Toe:** small boards won (weighted) + in-board threats (two-in-a-row with third cell open) - blocked opponent threats + bonus for center/corner boards

#### Enhanced Alpha-Beta
- Minimax with alpha-beta pruning
- Iterative deepening (anytime: always returns best move from last fully completed depth)
- Move ordering (improves pruning efficiency)
- Transposition table (avoids re-evaluating repeated states)
- Implemented as **Negamax** (exploits zero-sum symmetry - one recursive function for both players)

#### MCTS / UCT
- Monte Carlo Tree Search with UCT selection rule
- **Heuristic-informed rollout** (not pure random) - uses the same domain heuristic as above for rollout policy
- Anytime by nature: returns most-visited root action when time expires
- **Why heuristic-guided and not vanilla:** published comparisons show that vanilla MCTS with uninformed random rollouts can be considerably weaker than even a shallow Alpha-Beta search. Adding domain-specific guidance to the rollout/evaluator closes much of that gap, making the comparison between the two paradigms a fair strongest-vs-strongest test rather than a penalized version of MCTS.

---

## Resource-Constrained Play

### Shared Time Budget
All search-capable agents use the same per-move time budget per experimental condition (not fixed depth). Clock is checked every ~500-1000 nodes/simulations (not every node) to keep overhead low.

- **Alpha-Beta:** stops mid-iteration, returns best move from last fully completed depth
- **MCTS:** stops simulation loop, returns most-visited root child

### Memory Cap
- Alpha-Beta: capped transposition table with replace-on-collision eviction
- MCTS: capped tree node count with pruning of lowest-visit branches
- Both prevent MemoryError without depending on OS-level memory monitoring as the primary mechanism

### Move-Type Tagging
Every move from every agent is tagged (one flag per move, not per node - negligible overhead):

| Tag | Meaning |
|---|---|
| `normal` | Search/evaluation completed as intended |
| `time-limited` | Clock cutoff before search would have finished |
| `memory-limited` | Size cap hit before time limit |
| `error` | Unexpected exception - logged separately, excluded from main stats |

Detection logic per agent:
- **Alpha-Beta:** normal = deepest iteration completed; time-limited = clock cut mid-iteration; memory-limited = transposition table cap forced degradation before clock
- **MCTS:** normal = target sim count completed; time-limited = clock cut sim loop (expected to be the common case); memory-limited = tree node cap forced pruning before clock
- **Heuristic:** normal = all legal moves evaluated; time-limited = incremental evaluation cut off early

Tagging is implemented as a **shared decision wrapper** (timer + memory check + try/except) that every agent's move-selection function runs inside, so statistics are directly comparable across agents.

---

## Parameter Calibration (Pilot Phase)

> **TODO:** Run this pilot before the main tournament. Fill in final chosen values below.

Budgets cannot be chosen a priori. Procedure per game:

1. Run a small pilot between Alpha-Beta and MCTS across candidate time budgets: `[0.1s, 0.25s, 0.5s, 1s, 2s, 5s]`
2. Record move-tag distribution at each candidate
3. **Main budget** = candidate producing a balanced mix (neither near-0% nor near-100% time-limited)
4. **Easy config** = generous budget (mostly `normal` tags)
5. **Hard config** = tight budget (mostly `time-limited` tags)

| Game | Easy | Main (balanced) | Hard |
|---|---|---|---|
| Isolation 5x5 | TODO | TODO | TODO |
| Attax 7x7 | TODO | TODO | TODO |
| Ultimate Tic-Tac-Toe | TODO | TODO | TODO |

---

## Experimental Design

### Tournament Structure
- 4 static agents -> 6 unique unordered pairings (C(4,2) = 6)
- Each pairing: both agents start first an equal number of times -> 12 directed matchups
- Repeated across multiple trials per matchup for statistical reliability
- Run across all 3 games and all 3 budget configs (easy / main / hard)

### First-Move Advantage Analysis
- Win rate recorded separately by starting position (first vs second mover)
- Measured globally across all pairings and per individual pairing
- Statistical significance check: binomial test against 50/50 null hypothesis
- Key question: does first-move advantage change as state-space size increases?

### Metrics
- Win / loss / draw rate per agent, per game, per config, by starting position
- Average move time and nodes-expanded / simulations-run per agent
- Move-tag distribution per agent, per game, per config
- Average search depth reached by Alpha-Beta
- Scaling behavior: how all the above shift from Isolation -> Attax -> Ultimate Tic-Tac-Toe

### Results Output
- Every game logged to **CSV** (one row per move or per game depending on metric)
- CSV includes: agent identities, starting player, outcome, move times, nodes, tags
- Summary tables and graphs generated programmatically from CSVs
- Code for running experiments and generating graphs linked in final report (course requirement)

---

## Implementation Approach

### Framework: OpenSpiel (primary choice)

> **TODO:** Confirm via a short hands-on trial (implement one game, e.g. Ultimate Tic-Tac-Toe) before committing. If too heavy, use fallback below.

OpenSpiel (Google DeepMind) provides:
- Tested Alpha-Beta (minimax) and MCTS/UCT implementations
- Standard game API (Game/State interface) that custom games implement
- Verified against known values and paper results - mitigates implementation-quality bias
- MCTS evaluator is swappable (plug in heuristic rollout without forking core code)
- Custom games implemented purely in Python by subclassing their API

OpenSpiel does **not** provide: time/memory budget stopping mechanism, move-type tagging. These are a thin wrapper we write around the standard search calls.

OpenSpiel's recommended workflow for custom games is to start from a structurally similar existing game in their repo and verify correctness via random-playthrough simulation tests (run random games and check that state transitions, legal-move lists, and terminal conditions never raise errors or produce illegal states). This doubles as an early bug-catcher for our game logic before any agent touches it.

### Fallback: easyAI + reference MCTS
If OpenSpiel setup is too heavy:
- `easyAI` for Negamax/alpha-beta with iterative deepening and transposition tables
- Small well-documented public MCTS reference implementation
- Custom game-environment interface per game (simpler than OpenSpiel's full API)

### Division of Work

| Component | Source |
|---|---|
| Core Alpha-Beta / Negamax search logic | Framework (OpenSpiel or easyAI) |
| Core MCTS selection / expansion / backprop | Framework (OpenSpiel or reference) |
| Isolation 5x5 game implementation | Ours |
| Attax 7x7 game implementation | Ours |
| Ultimate Tic-Tac-Toe game implementation | Ours |
| Evaluation functions per game | Ours |
| Time budget / memory cap wrapper | Ours |
| Move-type tagging and statistics collection | Ours |
| Calibration pilot and tournament harness | Ours |
| CSV logging and graph generation | Ours |

---

## Proposed Repository Structure

```
search-agents-strategy-games/
- agents/
  - random_agent.py
  - heuristic_agent.py
  - alpha_beta_agent.py
  - mcts_agent.py
  - base_agent.py          # shared interface + decision wrapper (tagging, timing, memory cap)
- games/
  - isolation.py
  - attax.py
  - ultimate_ttt.py
  - base_game.py           # shared game interface
- evaluation/
  - isolation_eval.py
  - attax_eval.py
  - uttt_eval.py
- experiments/
  - calibrate.py           # pilot sweep per game
  - tournament.py          # full round-robin runner
  - logger.py              # CSV output
- results/
  - raw/                   # CSV logs
  - figures/               # generated graphs
- report/                  # final academic report
- PLAN.md                  # this file
- README.md
- requirements.txt
```

---

## Open Items Summary

1. **Isolation movement rule** - king-step vs queen-slide vs other. Needed to finalize rules description and branching factor.
2. **Calibrated time/memory budgets** - fill in after pilot sweep (see Section 5).
3. **Branching factor + average game length** - fill in after running random self-play simulations.
4. **OpenSpiel vs fallback** - confirm after hands-on trial with one game.

---

## References

- Russell, S. and Norvig, P. *Artificial Intelligence: A Modern Approach.* 2020 (chapters 3-5).
- Korf, R. E. *Heuristic Search.* 2009.
- Edelkamp, S. *Heuristic Search: Theory and Applications.*
- Ataxx complexity: average branching factor ~60, average game length ~100 plies (canonical 7x7 board).
- Course syllabus and project guidelines, Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev.
