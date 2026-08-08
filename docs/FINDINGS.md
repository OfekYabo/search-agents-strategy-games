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
10^39) and is **the hardest for both paradigms**. Confirmed by the v1 run: Alpha-Beta's
median depth on Ataxx is **3–4** across all three budgets (max 9), against 5–7 on Isolation
and 5–7 on UTTT.

The cause is branching factor: Ataxx averages 50.9 with a mid-game peak of 76, against ~6
and ~9 for the other two. This is the clearest vindication of reporting branching factor and
state-space size as **separate axes** — the two orderings genuinely disagree.

> **Two corrections from the v1 run.** The original version of this entry added "MCTS needs
> ~5 s to pass 10 simulations per root move." That was measured with the guided rollout
> defaults and is false — with the calibrated parameters MCTS clears the floor at **0.1 s**.
> See F3.
>
> Also, 50.9 and the peak of 76 come from **random self-play**, which runs 182.6 plies and
> reaches board states agent games never see. In the run, MCTS's own Ataxx decisions faced a
> mean of **23–25** legal moves. Both numbers are real; do not put the random-play branching
> figure beside a tournament result as though it were the width the agents actually faced.

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

### F3. MCTS is *beaten* on high-branching games, not starved

> **This entry replaces "MCTS is starved on high-branching games at any affordable budget."**
> That version was measured with the guided rollout defaults and before the
> simulations-per-root-move statistic was corrected (D9). Both halves of it were wrong. The
> superseded claim is kept visible here because the way it failed is itself the finding.

**It is not starved.** With the calibrated rollout parameters, Ataxx MCTS gets a median of
**23.5 / 90.3 / 347.6** simulations per root move at 0.1 / 0.5 / 2.0 s, and **no decision in
the entire 2160-game run fell below 1 per root move**. Only Ataxx-hard is thin, and only in
its lower tail: p5 = 3.9, with 20.1% of decisions below the viability floor of 10.

**And it still loses.** Head-to-head against the one-ply heuristic, both seat orders,
40 games per cell:

| budget | W–D–L | score | 95% CI |
|---|---|---|---|
| 0.1 s | 2–0–38 | **0.050** | [0.000, 0.118] |
| 0.5 s | 7–0–33 | **0.175** | [0.057, 0.293] |
| 2.0 s | 18–0–22 | **0.450** | [0.296, 0.604] |

Against Alpha-Beta it scores **0.000** at every budget (0–0–40, three times); against the
random agent, **1.000**. Not broken — beaten.

Two things the starvation reading hid:

1. **Clearing the viability floor is not sufficiency.** Ataxx at 0.5 s is "ample" by the
   spec's `>= 30` threshold and still scores 0.175. The floor buys the ability to try each
   candidate once; it does not buy competitive play at width 25–30.
2. **The budget response is steep and monotone** — 0.050 → 0.175 → 0.450 across a 20x budget
   increase, reaching statistical parity with the heuristic at 2.0 s. Budget still binds hard
   at 0.1 s even where the sims-per-root figure looks respectable.

So the defensible claim is not "MCTS cannot convert a realistic budget into meaningful search
on a high-branching game." It is: **MCTS converts budget into search efficiently on Ataxx and
converts search into strength very inefficiently there** — it needs on the order of 350
simulations per root move to match a one-ply evaluator that examines every move exactly once.
That is a statement about the algorithm, which is what the research question asked for, and a
stronger result than the one it replaces.

> **How the wrong version survived so long.** The pilot's error was configuration, not
> measurement: guided rollouts at `k=8, D=40` starved the tree (F2), and the starvation was
> then attributed to Ataxx's branching factor rather than to the rollout policy. The
> corrected statistic (D9) then inflated the replacement figures by 4–8x, which nearly let a
> second wrong number through in the opposite direction. **The same observation — "MCTS loses
> on Ataxx" — was consistent with three different underlying stories**, and only measuring
> simulations per root move *correctly* distinguished them.

### F4. Isolation is saturated and is a control, not a degradation datapoint

Alpha-Beta *solves* mid-game Isolation positions at depth 5 in 508 nodes **regardless of
budget** — 0.02 s and 5 s give identical results. MCTS is nowhere near the viability floor
either: in the run its median is **258.6** simulations per root move at the tightest 0.02 s
budget (minimum 25.1), rising to 11,705.6 at 0.5 s, with **0.0%** of decisions below the
floor at any budget. Neither agent is budget-limited, so Isolation measures something
different from the other two games and should be presented that way.

> The original entry said "exceeds 1000 simulations per root move even at the tightest
> budget." That figure came from the inflated statistic corrected in D9; the true median at
> 0.02 s is 258.6. The conclusion is unaffected — 258.6 is 26x the floor — but quote the
> corrected number.

### F5. Random self-play and agent play give very different game lengths

| Game | Random self-play | Real agent play (v1 run, 720 games each) |
|---|---|---|
| Isolation | 15.9 plies | **13.7** |
| UTTT | 59.5 | **38.8** |
| **Ataxx** | **182.6** | **39.0** |

Competent agents convert and eliminate; random agents shuffle with unproductive jumps that
never fill the board. Ataxx is the extreme case: agent play is **4.7x shorter** than random
self-play.

> The agent-play column originally held 14.6 / 42.2 / 45.0, measured on the 24-game smoke
> test. The figures above are from the full 2160-game run and supersede them.

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

### D9. The viability statistic was averaged the wrong way, and the spec said to do it

`analyse.py` reported simulations per root move as the **mean of each decision's
`simulations / legal_move_count` ratio**. A position with a single legal move contributes a
ratio equal to the entire simulation count — tens of thousands — despite involving no search
decision at all. **10–14% of Ataxx MCTS decisions and 20–25% of Isolation ones have exactly
one legal move**, so the reported figure was dominated by positions where nothing was
chosen. Inflation: **4–8x**.

It moved Ataxx-hard from `viable` to `ample`, and it is the number the spec requires beside
**every** MCTS result — the one figure that distinguishes "MCTS lost" from "MCTS never got
to search". It would have been quoted throughout the report.

Two things make this the most instructive defect in the list:

- **The specification asserted the error explicitly, with a justification that was exactly
  backwards.** `docs/plans/2026-08-06-plan-3-experiments.md` said: *"Use the mean of per-move
  ratios, not the ratio of means, which would flatter MCTS on positions with few legal
  moves."* The mean of ratios does not protect against low-width positions; it is
  **dominated** by them. The code implemented the instruction faithfully, and a unit test
  pinned the wrong behaviour with a comment explaining why it was right.
- **It produced a table that was internally consistent and superficially reasonable.** Every
  cell read `ample`. Nothing was missing, malformed, or out of range.

Now the median of the per-decision ratio, with `p5` and the percentage of decisions below the
viability floor reported beside it — because the floor is a property of each decision, not of
the average. Ataxx-hard's 20.1%-below-floor was invisible under any single-number summary.

---

## The pattern

Of the nine defects above, **all nine originated in specifications rather than in
implementation** — written top-down before any code existed. Every one was caught by a review
or a gate, never by the specification's own author.

Four mechanisms did the catching, in ascending order of value:

1. **Unit tests** — caught the least. They ran agents only on Isolation and missed D2
   entirely, and in D9 a unit test actively *defended* the defect.
2. **Per-task and whole-branch reviews** — caught D5, D6, D8 by comparing files that each
   looked correct alone.
3. **End-to-end gates on real data** — caught D1, D2, D3, D4, D7. The 2-minute pipeline smoke
   test found two budget bugs that 164 unit tests had missed.
4. **Arithmetic sanity-checking of the finished table against independent domain knowledge**
   — caught D9, and *only* D9. It survived all three mechanisms above.

**D9 is the one that should worry the methodology section most.** It was not caught by any
automated gate, because no gate existed that could catch it: the output was well-formed,
in-range, internally consistent, and confirmed by a passing test that encoded the same
misconception. It was caught by a human reading the published table and noticing that the
numbers did not square with a branching factor measured elsewhere in the project.

**The lesson for the report's methodology section:** when the deliverable is numbers, tests
that assert on *code behaviour* are necessary but insufficient. What finds the dangerous
class of defect is measuring the instrument against an independent oracle — a published
branching curve, a hand-derived constant, an inverted mutant, a budget stopwatch. And when
the oracle is a statistic the specification itself defined, **the specification is inside the
blast radius**: D9 could only be found by checking the reported number against a quantity the
spec had no hand in producing.
