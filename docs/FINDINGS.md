# Findings and decisions

The durable record of what this project found and why it decided what it did.
Extracted from the development ledgers, which live in git-ignored scratch.

Two kinds of entry:
- **Research findings** — things about the games and algorithms that belong in the report.
- **Engineering defects** — bugs found and fixed. Included because several would have
  produced *plausible but wrong results with no visible symptom*, which is a methodological
  point in its own right.

---

## Research findings

### F1. Width, not state-space size, is what defeats search

Ataxx is the **middle** game by state space (10^23, against Isolation's 10^10 and UTTT's
10^39) and is **the hardest for both paradigms**. Alpha-Beta reaches only depth 2–4 even at
a 5 s budget; MCTS needs ~5 s to pass 10 simulations per root move.

The cause is branching factor: Ataxx averages 50.9 with a mid-game peak of 76, against ~6
and ~9 for the other two. This is the clearest vindication of reporting branching factor and
state-space size as **separate axes** — the two orderings genuinely disagree.

### F2. Rollout guidance can cost more than it buys, and did

PLAN.md motivated heuristic-guided rollouts on the grounds that vanilla MCTS "can be
considerably weaker than even a shallow Alpha-Beta search." **On this project the reasoning
inverted.**

Guided rollouts cost up to `sample_k x rollout_depth` = 320 child evaluations each. Measured
at a 0.1 s budget, that left MCTS with **6 simulations per move on UTTT** — fewer than its
legal moves, so it could not try each candidate once.

| Rollout config | Simulations | Score vs one-ply agent |
|---|---|---|
| `eps=0.25, k=8, D=40` (guided default) | 6 | 0.29 |
| `eps=0.8, k=2, D=10` | 115 | 0.62 |
| **`eps=1.0` (pure random), D=10** | **407** | **1.00** |

Calibration phase 3 selected pure random rollouts on **all three games**. The finding:
**rollout guidance has a cost/quality optimum, and being on the wrong side of it cripples
the agent more thoroughly than having no guidance at all.**

Only visible because simulations-per-move was measured. A results table showing MCTS losing
would have looked entirely plausible.

### F3. MCTS is starved on high-branching games at any affordable budget

On Ataxx, MCTS scores **0.00 against the one-ply heuristic** at every rollout configuration
tried, while still beating random 0.95 — starved, not broken. It needs ~5 s to reach
viability, and one 5 s Ataxx config costs ~30 h of compute.

Reported rather than engineered around. **That MCTS cannot convert a realistic budget into
meaningful search on a high-branching game is an answer to the research question.**

### F4. Isolation is saturated and is a control, not a degradation datapoint

Alpha-Beta *solves* mid-game Isolation positions at depth 5 in 508 nodes **regardless of
budget** — 0.02 s and 5 s give identical results. MCTS exceeds 1000 simulations per root move
even at the tightest budget. Neither agent is budget-limited, so Isolation measures something
different from the other two games and should be presented that way.

### F5. Random self-play and agent play give very different game lengths

| Game | Random self-play | Real agent play |
|---|---|---|
| Isolation | 15.9 plies | 14.6 |
| UTTT | 59.5 | 42.2 |
| **Ataxx** | **182.6** | **45.0** |

Competent agents convert and eliminate; random agents shuffle with unproductive jumps that
never fill the board. On Ataxx, 17 of 24 agent games ended by **elimination**.

**Consequence:** a runtime estimate built on random-play lengths overestimated the tournament
by 2.5x (21 h projected, ~8 h measured). Branching-factor measurements from random play are
still valid — they are move *counts* — but game *lengths* from random play must not be used
to size an agent tournament.

### F6. A seed does not make a wall-clock-budgeted search reproducible

The seed fixes every *random choice* — the random agent's picks, tie-breaks, MCTS expansion
order and rollouts. It cannot fix how many nodes Alpha-Beta expands, which depends on how
fast the machine was for those milliseconds.

Observed: the same code over the same 20 seeds at a 50 ms budget scored **20/20 in one run
and 18/20 in another**.

Intrinsic to using wall clock as the budget — which is the only unit that is fair across two
different search paradigms. Consequences: **the CSV is one sample, not a replayable
artifact**, and figures need confidence intervals rather than bare percentages. Only the two
baseline agents are bit-reproducible.

### F7. Machine noise is measurable and matters

A single Alpha-Beta decision was observed at **0.290 s against a 0.1 s budget** while the
test suite ran concurrently. Sixty successive decisions on an idle machine gave a maximum of
0.1017 s (+1.7%).

Confirmed on the dedicated VM: worst overshoot anywhere **+9.4%**, against +18% on WSL2.
Hence: run on an idle machine, disable guest timers, and interleave trials so drift reaches
every agent equally.

### F8. Ataxx's widely-quoted complexity figures are not peer-reviewed

The "~60 average branching factor, ~100 plies" figures come from a **complexity section of
Wikipedia's Ataxx article that no longer exists**, surviving only in mirrors of an old
revision. No primary citation. The attribution to a board "with two fixed blocked squares" is
also unsupported — the source describes a plain 7x7 board.

Replaced by Ribeiro and Figueiredo (ENIAC 2018), archived in `docs/references/`, which
reports *measured* branching factors: ~20 at ply 1, peaking at 92 near ply 25.

Our own random-play measurement gives 16 at ply 1 and a peak of 76 at ply 62 — the same
*shape* (a rise to ~4.6x the opening width, then decline) at different absolute values,
because the reference is not measuring uniformly random play and our board has 49 playable
cells against its 47.

### F9. The Ultimate Tic-Tac-Toe variant we rejected is solved

Wikipedia states the standard rules close a decided local board. The opposite reading — the
"continue playing in decided boxes" variant — **was shown in 2020 to admit a winning strategy
for the first player**. Had we chosen it, the largest domain would have been a solved game,
useless as a domain neither paradigm can exhaust and fatal to the first-move-advantage
analysis.

### F10. Two arithmetic corrections worth stating

- **Isolation ply-1 branching is 11, not 12.** The southward ray from `(0,2)` yields three
  cells, not four, because it stops before `(4,2)` — the opponent's starting cell. An earlier
  draft had 12.
- **Ataxx ply-1 branching is exactly 16**, derivable by hand: from each of two corners, 3
  adjacent empty cells and 5 on-board distance-2 cells, clones deduplicating by destination,
  giving `6 + 10`. Two of those five are knight-shaped, so a generator enumerating only
  straight and diagonal two-steps yields **12**. That single equality catches the classic
  implementation bug for this game and is asserted in the validation gate.

---

## Engineering defects — and why they matter methodologically

Every one of these would have produced a **complete, plausible CSV with wrong numbers and no
crash**. That is the characteristic hazard of a project whose deliverable is measurements.

### D1. MCTS overran its time budget by up to 1283%

`should_stop()` sampled the clock every 512 calls — calibrated for cheap per-node polling.
MCTS polls once per *simulation*, and a rollout costs ~0.35 ms, so 512 of them is ~0.18 s and
any budget below that was **never checked at all**. A 0.02 s budget consumed 0.277 s.

Equal per-move time is the premise the entire comparison rests on, and the overshoot grew as
the budget shrank — so the bias was systematic and **largest in the `hard` config that exists
specifically to expose degradation**.

### D2. The same fix was then applied incompletely

After D1 the rule was generalised into the spec — *any agent whose polled unit is expensive
must poll more finely* — and applied to the heuristic agent and MCTS, **but not to
Alpha-Beta**, which still polled every 512 nodes on a game where it expands ~1,500 per
decision. Measured **+85%** on UTTT.

Caught only by a full-pipeline smoke test over 72 real games; 164 unit tests missed it
because they only ever ran agents on Isolation.

### D3. MCTS rollouts were not interruptible

Even polling before every simulation, a rollout could not be stopped once begun, so overshoot
was floored by rollout cost — 25.8 ms on UTTT, a 35% overrun on a 0.1 s budget. Fixed by
truncating the rollout on the clock, which is the same operation the depth cap already
performed. Cost ~14% of simulations.

### D4. The tournament ignored calibration entirely

`_make_agent` passed only the node cap, so the rollout parameters fell through to constructor
defaults — the configuration phase 3 ranked **worst**. Calibration was producing numbers
nobody consumed. Measured impact on UTTT at 0.1 s: **407 simulations with the calibrated
parameters, 9 with the defaults.**

### D5. Alpha-Beta's memory cap was disconnected from the memory budget

MCTS read its cap from the search context; Alpha-Beta's was fixed at construction. The runner
passed one `max_nodes` for every agent and the logger wrote it into **every** row. A memory
sweep would have moved MCTS's `memory-limited` rate while Alpha-Beta's stayed pinned, under a
column implying it governed both.

Each agent now takes its cap from its own config key. The two are not interchangeable: a
transposition entry is a 4-tuple, an MCTS node holds a full state, a child mapping and
counters.

### D6. The transposition table had the wrong lifetime

Rebuilt every *decision* rather than persisting for a game, contradicting both its own
docstring and the spec. Cost 45% more nodes on the second decision of a game — but worse, a
table that restarts empty each move only saturates at absurdly small caps, so the
`memory-limited` tag was **unreachable at any realistic cap** while still appearing in every
results table.

### D7. CSV logging was not crash-safe

The games row was written first, then move rows, then both flushed. Python buffers at 8 KB;
a games row is ~120 B and never auto-flushes, but an Ataxx game's ~183 move rows are ~13.5 KB
and **do**. A hard kill mid-game left orphan move rows with no games row — reproduced:
`games.csv` 0 bytes, `moves.csv` 130 rows. On resume the game was replayed and its moves
appended **again**, duplicating rows and silently inflating the tag-distribution and
simulations-per-root tables.

Move rows are now flushed first and the games row last, so **a `game_id` in `games.csv`
implies all its moves are durable**; orphans are dropped atomically on reopen. This is what
makes a `Restart=on-failure` supervisor safe rather than dangerous.

### D8. `_winner` had no test that could fail if it inverted

The mapping from a side-to-move-relative result onto `first`/`second` was correct, but every
assertion touching it would have passed against an inverted implementation. An inverted
`_winner` reverses **every win rate in the study** while producing a well-formed CSV.

---

## The pattern

Of the eight defects above, **all eight originated in specifications rather than in
implementation** — written top-down before any code existed. Every one was caught by a review
or a gate, never by the specification's own author.

Three mechanisms did the catching, in ascending order of value:

1. **Unit tests** — caught the least. They ran agents only on Isolation and missed D2 entirely.
2. **Per-task and whole-branch reviews** — caught D5, D6, D8 by comparing files that each
   looked correct alone.
3. **End-to-end gates on real data** — caught D1, D2, D3, D4, D7. The 2-minute pipeline smoke
   test found two budget bugs that 164 unit tests had missed.

**The lesson for the report's methodology section:** when the deliverable is numbers, tests
that assert on *code behaviour* are necessary but insufficient. What finds the dangerous
class of defect is measuring the instrument against an independent oracle — a published
branching curve, a hand-derived constant, an inverted mutant, a budget stopwatch.
