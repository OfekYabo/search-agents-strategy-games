# Search-Based Agents for Strategy Games - Project Plan

> Academic project - Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev  
> Repository: `search-agents-strategy-games`

---

## Research Question

How do **exact tree search** (Alpha-Beta with enhancements) and **sampling-based search** (MCTS/UCT) compare in playing strength, efficiency, and degradation behavior across two-player strategy games whose state-space sizes span ~30 orders of magnitude, when both are constrained by the same realistic per-move **time and memory budget**?

Benchmarked against a random baseline and a no-search heuristic baseline.

---

## Why This Comparison Is Non-Trivial

- Explicitly avoids the course-flagged "weak project" pattern: this is **not** Minimax vs Alpha-Beta (two refinements of the same algorithm). The two compared agents come from genuinely different search paradigms.
- Three games spanning ~30 orders of magnitude in state-space size lets us test whether the paradigm comparison **shifts with scale**, rather than asserting it from one data point.
- Realistic time/memory constraints (not artificial fixed depth) give both paradigms a shared, fair resource model.
- Move-type tagging produces **explanatory data** (why performance changes) not just outcome data (that it changes).

---

## Games

| Game | Board | State-space upper bound | log10 | Role |
|---|---|---|---|---|
| Isolation 5x5 | 5x5 grid | 2 x 25 x 24 x 2^23 ~ 1.01 x 10^10 | 10.0 | Small domain |
| Ataxx 7x7 | 7x7 grid | 2 x 3^49 ~ 4.78 x 10^23 | 23.7 | Medium domain |
| Ultimate Tic-Tac-Toe | 9x(3x3) | 2 x 10 x 3^81 ~ 8.89 x 10^39 | 39.9 | Large domain |

### State-Space Derivations (verified)

**Isolation 5x5:** 25 cells; player A on any of 25, player B on any remaining 24, each of the other 23 cells independently open/blocked (2^23), times 2 for whose turn:  
`2 x 25 x 24 x 2^23 = 10,066,329,600 ~ 1.01 x 10^10`

**Ataxx 7x7:** 49 cells, each in 3 states (empty / P1 / P2): `3^49 ~ 2.39 x 10^23`, times 2:  
`2 x 3^49 ~ 4.78 x 10^23`

**Ultimate Tic-Tac-Toe:** 81 cells (9 boards x 9), each in 3 states: `3^81 ~ 4.44 x 10^38`, times 2 for whose turn, times 10 for the **send constraint** (the player to move is sent to one of 9 local boards, or is unconstrained):  
`2 x 10 x 3^81 ~ 8.89 x 10^39`

> The send constraint is genuine state, not derivable from the cell contents: two positions with identical cells but different send constraints have different legal moves. The earlier `2 x 3^81` figure omitted it. See [`docs/games/ultimate-tic-tac-toe.md`](docs/games/ultimate-tic-tac-toe.md) section 5.1, which also records that a materially tighter bound is reachable once the rules are in code - **to be revisited at implementation time.**

All three are loose upper bounds (do not exclude unreachable states). A tighter published figure for Ataxx alone is `5.98 x 10^22`, about a quarter of our `3^49` term and consistent with it.

### Hardness Comparison Summary

Maxima below are **derived from the rules** and need no simulation. Averages are deliberately deferred: they will be measured by the random agent against the tested implementations, so that every published figure comes from code that has been verified.

| Game | State-space | log10 | Max branching | Avg branching | Max length | Avg length |
|---|---|---|---|---|---|---|
| Isolation 5x5 | 1.01 x 10^10 | 10.0 | **16** (11 at ply 1) | pending | **23** plies | pending |
| Ataxx 7x7 | 4.78 x 10^23 | 23.7 | **<= 17e** (`<= 765`) | pending (ref. ~60) | **300** plies, enforced | pending (ref. ~100) |
| Ultimate Tic-Tac-Toe | 8.89 x 10^39 | 39.9 | **81** at ply 1, then <= 9 forced / up to ~70 free | pending | **81** plies | pending |

**Branching factor is not monotonic in state-space size.** Ataxx is by far the widest (~60) while Ultimate Tic-Tac-Toe, whose state space is sixteen orders of magnitude larger, is usually bounded by 9. UTTT gets its size from *depth* - up to 81 plies - not width. Any claim in the report about one game being "harder" must say which axis it means, because the two orderings genuinely disagree.

### Branching Factor

Not a fixed constant - changes through the game. **Measure empirically** via random self-play simulation (batch of N=1000 games per game type, record legal-move count distribution at every ply). This is a natural byproduct of building the random agent.

**External reference for Ataxx** - Ribeiro and Figueiredo (ENIAC 2018) report *measured* branching factors on 7x7 Ataxx: ~20 at the first ply, peaking at **92** around ply 25, and ~90 again around ply 52. The curve is double-humped, which makes it a far better validation target than any single average: if our measurement comes out flat, the move generator is wrong. Paper archived at [`docs/references/`](docs/references/).

> The widely-repeated "average branching factor ~60, average game length ~100 plies" figures come from a complexity section of the Wikipedia article on Ataxx **that no longer exists**, surviving only in mirrors of an old revision. They are **not peer-reviewed** and carry no primary citation, and the attribution of them to a board "with two fixed blocked squares" is unsupported - the source describes a standard unobstructed 7x7 board. Cite them as an unsourced estimate or not at all. See [`docs/games/ataxx.md`](docs/games/ataxx.md) section 9.2.

### Game Descriptions

> **Full, implementable rulesets live in [`docs/games/`](docs/games/)** - one gamebook per game, each with the formal rules, starting position, derived complexity, sourced references, and the alternative rulesets we considered and rejected. Shared cross-game conventions are in [`docs/games/README.md`](docs/games/README.md). The summaries below are orientation only; the gamebooks are authoritative.

**Isolation 5x5** ([gamebook](docs/games/isolation.md)) - a **declared variant**, not the published 1972 game. Two players each control one pawn on a 5x5 grid, starting at `(0,2)` and `(4,2)`. On your turn you slide your pawn any distance along one of 8 directions (**queen-slide**), stopping before the board edge, a blocked cell, or the opponent's pawn. The cell you left then becomes permanently blocked - **uniformly, with no exempt cells**. A player with no legal move loses. Draws are impossible.

**Ataxx 7x7** ([gamebook](docs/games/ataxx.md)) - on a 7x7 grid with pieces starting at opposite corners, a player either **clones** into an empty cell at Chebyshev distance 1 (the original stays) or **jumps** a piece to an empty cell at Chebyshev distance exactly 2 (the original is removed). All opponent pieces adjacent to the destination are then converted. **A player with no legal move passes; they do not lose.** A player is eliminated only by reaching zero pieces. The game ends when the board fills, a player is eliminated, 30 plies pass without progress, or a 300-ply cap is reached; most pieces wins.

**Ultimate Tic-Tac-Toe** ([gamebook](docs/games/ultimate-tic-tac-toe.md)) - nine 3x3 boards in a 3x3 super-grid. Playing cell `c` of any local board sends the opponent to local board `c`. Three local boards won in a row wins the game. A local board that is won or drawn is **closed to further play**, and being sent to one frees the opponent to play in any undecided board. A drawn local board counts for neither player.

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

Starter evaluation functions (to be tuned during development). All are scored **from the perspective of the player to move**, never from a fixed player's - an evaluation written from Player 1's fixed perspective silently inverts on every other ply.

- **Isolation:** own legal-move count minus opponent legal-move count (mobility difference). Well matched to the queen-slide variant, whose mobility varies far more sharply between positions than king-step mobility would.
- **Ataxx:** piece-count difference + number of opponent pieces immediately convertible by the candidate move + **exposure** term (see below).
- **Ultimate Tic-Tac-Toe:** small boards won (weighted) + in-board threats (two-in-a-row with third cell open) - blocked opponent threats + bonus for center/corner boards

> **Defining "positional stability" for Ataxx.** The Othello intuition does not transfer: **in Ataxx no piece is ever permanently safe**, because any piece can be converted by an opponent landing adjacent to it. The usable notion is **exposure** - a piece is vulnerable exactly when it has at least one empty neighbouring cell - so the term counts empty neighbours, negated. Corners have 3 neighbours and edges 5, against 8 for a central cell, which is why corners are structurally safer here. Same conclusion as Othello, entirely different reason.

#### Shared reward scale

**Every game returns `+1` win / `0` draw / `-1` loss, from the perspective of the player to move**, identically across all three games so that agent behaviour stays comparable between domains. Alpha-Beta consumes this directly (negamax flips with `-v`). **MCTS converts to `[0, 1]` via `(v + 1) / 2`** in one place before backpropagation, because UCB1's exploration term does not rescale with the reward and every published exploration constant assumes rewards in `[0, 1]`. Full rationale in [`docs/games/README.md`](docs/games/README.md).

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

> **Deferred by design - does not block the spec or the implementation.** These values are *outputs* of the pilot, not inputs to it: they cannot be chosen a priori, because the right budget is defined relative to how the agents actually degrade on this hardware. The pilot must run after the games and agents exist and before the main tournament. Everything upstream of the tournament runner can be specified, built and tested with the budget left as a parameter.

Budgets cannot be chosen a priori. Procedure per game:

1. Run a small pilot between Alpha-Beta and MCTS across candidate time budgets: `[0.1s, 0.25s, 0.5s, 1s, 2s, 5s]`
2. Record move-tag distribution at each candidate
3. **Main budget** = candidate producing a balanced mix (neither near-0% nor near-100% time-limited)
4. **Easy config** = generous budget (mostly `normal` tags)
5. **Hard config** = tight budget (mostly `time-limited` tags)

| Game | Easy | Main (balanced) | Hard |
|---|---|---|---|
| Isolation 5x5 | *pilot output* | *pilot output* | *pilot output* |
| Ataxx 7x7 | *pilot output* | *pilot output* | *pilot output* |
| Ultimate Tic-Tac-Toe | *pilot output* | *pilot output* | *pilot output* |

Record the **hardware and Python version** alongside these values. A time budget is only meaningful relative to the machine that produced it, and the report needs that for reproducibility.

---

## Experimental Design

### Tournament Structure

- 4 static agents -> 6 unique unordered pairings (C(4,2) = 6)
- Each pairing: both agents start first an equal number of times -> 12 directed matchups
- Repeated across `T` trials per directed matchup for statistical reliability
- Run across all 3 games and all budget configs (easy / main / hard)

**The experimental grid.** Every game played is one cell of:

```
   3 games        x  6 pairings  x  2 seat orders  x  C configs  x  T trials
```

`T = 30` with 3 configs gives 3,240 games; `T = 20` with 2 configs gives 1,440.

The first three factors are **fixed and not negotiable**: dropping a game destroys the state-space scale axis the research question rests on, dropping a pairing breaks the round robin, and dropping a seat order destroys the first-move-advantage analysis. **`T` and the budget configs are the only levers.**

**`T` and the budget configs do different jobs, and cost differently:**

| Lever | Buys | Cost behaviour |
|---|---|---|
| `T` (trials) | statistical confidence - standard error on a win rate is `sqrt(p(1-p)/n)`, so `T=20` gives about +-7.9pp per pairing, `T=30` about +-6.5pp, `T=50` about +-5.0pp | linear |
| Budget configs | the **degradation story**, which is the project's actual contribution - three points describe a curve, two only a direction | **dominant** - an easy config at 2s/move costs ~20x a hard config at 0.1s/move |

Because cost is dominated by the budget values rather than by `T`, the cheapest useful saving is to *lower* the easy budget rather than to drop the easy config.

> **The grid is a configuration parameter, not a constant.** Its final values are an **output of the calibration pilot**, whose entire job is to measure the tag distribution and real seconds-per-game at each candidate budget on this hardware. Fixing the grid before that measurement would mean guessing at something we are about to measure.

**Fallback ladder if time runs short**, in the order to pull:

1. Lower the easy budget (largest saving per unit of analytical loss)
2. Reduce `T` (30 -> 20)
3. Drop the easy config entirely (loses the third degradation point)
4. *Last resort:* drop a game - this guts the research question and should be treated as project failure rather than scope reduction

> **Expect MCTS to be time-limited almost always.** It is anytime by construction and consumes whatever budget it is given, so the `normal` tag is largely an *Alpha-Beta* phenomenon. The easy config's real function is giving Alpha-Beta enough time to complete iterations. This should be stated in the report rather than discovered by a reader.

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
- Scaling behavior: how all the above shift from Isolation -> Ataxx -> Ultimate Tic-Tac-Toe

### Results Output
- Every game logged to **CSV** (one row per move or per game depending on metric)
- CSV includes: agent identities, starting player, outcome, move times, nodes, tags
- Summary tables and graphs generated programmatically from CSVs
- Code for running experiments and generating graphs linked in final report (course requirement)

---

## Implementation Approach

### Framework: none - our own implementation, Python standard library only *[DECIDED]*

Frameworks were surveyed against the actual requirements rather than their advertised features. **None clears the bar**, and one structural argument decides it.

**The instrumentation is the research.** This project's contribution is not "Alpha-Beta vs MCTS" - that comparison exists in the literature. It is the **move-type tagging** (`normal` / `time-limited` / `memory-limited`) and the resource-bounded degradation analysis built on it. Every framework surveyed treats search as a closed call that returns a move, so tagging, the clock check and the memory cap all have to be bolted on from *outside* the search loop - which is exactly where they need to live. Writing our own puts the object of study at the centre of the design.

**Survey results:**

| Option | What it actually provides | Why not |
|---|---|---|
| **OpenSpiel** | `MCTSBot` with UCT, swappable evaluator, MCTS-Solver | `alpha_beta_search` has **no** iterative deepening, **no** transposition table, **no** move ordering, **no** time limit - zero of our four enhancements. `MCTSBot` takes `max_simulations` only, so anytime behaviour means forking `mcts_search`. Needs Python 3.11+ (wheels are cp311/312/313); we have 3.8.10. Games must become `pyspiel.Game` subclasses with integer action IDs. **None of our three games ship with it**, so the "verified implementations" benefit does not apply to us. |
| **easyAI** | Negamax + alpha-beta + transposition tables + `id_solve`; a light `TwoPlayersGame` API | The closest call. Gives three of four AB enhancements, and move ordering comes free by ordering the returned move list. But **no MCTS at all**, no time budget, no node counting, no memory cap, and `id_solve` solves from the root rather than acting as an anytime move-chooser. Net effect is a wash: ~1 day saved on Alpha-Beta, paid back conforming three games and instrumenting from outside. |
| **Ludii** | 1000+ games, built-in UCT and alpha-beta, GGP competition framework | **Java**, and games are written in a `.lud` ludeme DSL. Learning cost is far beyond the schedule. *Keep in mind as a rule cross-check* if an implementation is ever in doubt. |
| **PettingZoo** | Multi-agent RL environment API | RL-oriented, no search agents, none of our games. Pure overhead. |

**Consequences of building our own:**
- **Zero dependencies.** Standard library only, so it runs unchanged on WSL2, Multipass, macOS and AWS, on the Python already installed. A collaborator clones the repo and runs it.
- **No framework overhead** inside an experiment whose independent variable is wall-clock time - framework call costs would otherwise be measured as if they were algorithmic.
- **The cost we accept:** correctness of the search code rests on our own tests rather than on a framework's reputation. Mitigated by TDD, and by the validation check below.

> **Highest-value validation.** Before the full tournament, measure Ataxx's branching factor per ply with the random agent and compare against Ribeiro and Figueiredo: ~20 at ply 1, peaking at **92** near ply 25, ~90 again near ply 52. Reproducing that double-humped curve is strong evidence the move generator is correct. A flat curve means a bug - caught before a night of compute is spent on it.

### Execution Platform *[DECIDED]*

Timed runs happen on **one fixed machine**: a Multipass Ubuntu VM on the Dell i7 (32 GB), given a **fixed CPU and memory allocation** so the environment is declarable and reportable. A fixed allocation is preferable to WSL2, which balloons memory and takes all cores by default.

Report the CPU model, allocated vCPU and RAM, OS and Python version alongside every result - a time budget is meaningless without them.

**Method requirements:**
- **Interleave trials across matchups.** Never run all of one agent's games and then another's; any thermal drift or background load must hit every agent equally. This is the highest-value methodological detail in the run, and it is free.
- Mains power, performance profile, background applications closed.
- If parallelising, pin one worker per physical core and leave at least one core for the host.

AWS (`c6i` or another **dedicated-CPU** family) is the fallback if the laptop proves too noisy or too slow. **Never a burstable `t3`/`t4g` instance** - CPU credit throttling would silently slow later matchups and corrupt precisely the quantity being measured.

### Division of Work

| Component | Source |
|---|---|
| Core Alpha-Beta / Negamax search logic | **Ours** |
| Core MCTS selection / expansion / backprop | **Ours** |
| Isolation 5x5 game implementation | Ours |
| Ataxx 7x7 game implementation | Ours |
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
  - ataxx.py
  - ultimate_ttt.py
  - base_game.py           # shared game interface
- evaluation/
  - isolation_eval.py
  - ataxx_eval.py
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

**Resolved**

1. ~~**Isolation movement rule**~~ - **queen-slide** on 5x5, vacated cell auto-blocks uniformly with no exempt cells, pawns start `(0,2)` and `(4,2)`. Max branching 16 (11 at ply 1), max 23 plies, no draws possible. See [gamebook](docs/games/isolation.md).
2. ~~**Ataxx rules**~~ - a player with no legal move **passes**, it does not lose (the original wording here was wrong). Termination is guaranteed by a 30-ply no-progress rule with a 300-ply hard cap, because the published rules do not terminate: jump moves leave the occupied-cell count unchanged, so jump-only play can run forever.
3. ~~**Ultimate Tic-Tac-Toe rules**~~ - a local board that is won or drawn is **closed** to further play; a drawn local board counts for neither player.
4. ~~**Terminal reward scale**~~ - `+1 / 0 / -1` in all three games, mapped to `[0, 1]` for MCTS.
5. ~~**Ataxx complexity citation**~~ - the ~60/~100 figures are unsourced (a deleted Wikipedia section). Replaced by Ribeiro and Figueiredo (ENIAC 2018), archived in [`docs/references/`](docs/references/).

6. ~~**OpenSpiel vs fallback**~~ - **neither.** Own implementation, Python standard library only. Frameworks were surveyed against requirements; see Implementation Approach for the evidence and the deciding argument.
7. ~~**Execution platform**~~ - fixed Multipass Ubuntu VM on the Dell i7 with a pinned CPU and memory allocation; AWS `c6i` as fallback. Trials interleaved across matchups.
8. ~~**Experimental grid**~~ - fully parameterised; final values are an output of the calibration pilot. Fallback ladder documented in Experimental Design.

**All four original open items are now closed.** The remainder are deferred by design, not blocked.

**Deferred - waiting on measurement, does not block implementation**

9. **Calibrated time/memory budgets** - an output of the pilot sweep. Cannot be resolved a priori; blocks only the tournament run.
10. **Average branching factor + average game length** - to be measured by the random agent against the tested implementations, so that every published figure comes from verified code. Maxima are already derived and need no simulation.
11. **Ultimate Tic-Tac-Toe state-space bound** - the adopted `2 x 10 x 3^81` is correct but loose; a tighter bound is reachable once the rules are in code. Revisit at implementation time.

**Housekeeping**

12. **Read Ribeiro and Figueiredo in full** - it evaluates MCTS variants on Ataxx, so it is related work for the research question, not merely a source of branching-factor numbers. Figures cited so far come from its abstract and indexing metadata. *(No PDF text extractor is installed; `apt-get install poppler-utils` provides `pdftotext`.)*
13. **Python version** - target is **3.8.10**, the system Python in the dev environment. Avoid newer syntax: no `match` statements, no `X | Y` type unions, no `dict |` merge operator.
14. **Video reference for Ultimate Tic-Tac-Toe gamebook** - a walkthrough link is present; Isolation and Ataxx also have theirs. Nothing outstanding unless a better source appears.

---

## References

- Russell, S. and Norvig, P. *Artificial Intelligence: A Modern Approach.* 2020 (chapters 3-5).
- Korf, R. E. *Heuristic Search.* 2009.
- Edelkamp, S. *Heuristic Search: Theory and Applications.*
- Ribeiro, L. and Figueiredo, D. R. *Performance of Monte Carlo Tree Search Algorithms when Playing the Game Ataxx.* ENIAC 2018, Sao Paulo. DOI [10.5753/eniac.2018.4423](https://doi.org/10.5753/eniac.2018.4423). Measured Ataxx branching factors, and related work on MCTS for this exact game. Archived in [`docs/references/`](docs/references/).
- Ataxx complexity, unsourced: average branching factor ~60, average game length ~100 plies (standard 7x7 board). From a deleted section of the Wikipedia article - **not peer-reviewed**, see [`docs/games/ataxx.md`](docs/games/ataxx.md) section 9.2.
- Per-game rulesets, sources and rejected alternatives: [`docs/games/`](docs/games/).
- Course syllabus and project guidelines, Search Methods in Artificial Intelligence (237-2-5513), Ben-Gurion University of the Negev.
