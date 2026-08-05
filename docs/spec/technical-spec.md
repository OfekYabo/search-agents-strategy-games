# Technical Specification

> Status: **draft, awaiting sign-off.** Decisions marked **[SIGN-OFF]** are ones PLAN.md
> left open or under-specified; they need an explicit yes before implementation.
>
> Authorities: [`PLAN.md`](../../PLAN.md) for the research design, [`docs/games/`](../games/)
> for rules. This document specifies *code*, and never restates a rule - it links to it.

Target: **Python 3.8.10, standard library only.** No third-party dependencies.

---

## 1. Repository layout

```
games/
  base.py            GameState protocol, Move types, GameResult
  isolation.py       Isolation 5x5
  ataxx.py           Ataxx 7x7
  uttt.py            Ultimate Tic-Tac-Toe
evaluation/
  base.py            Evaluator protocol
  isolation_eval.py
  ataxx_eval.py
  uttt_eval.py
agents/
  base.py            Agent protocol, SearchContext, Decision, MoveTag
  random_agent.py
  heuristic_agent.py
  alpha_beta_agent.py
  mcts_agent.py
experiments/
  runner.py          plays one game, returns a GameRecord
  calibrate.py       pilot sweep
  tournament.py      full round robin
  logger.py          CSV writers
  analyse.py         tables and figures from CSVs
tests/
  test_<module>.py   mirrors the tree above
```

---

## 2. Core types

### 2.1 States are immutable tuples of integers

Every game state is a **frozen dataclass whose fields are `int` or `tuple`**. This one
decision buys three things at once, and it is why we are not using a mutable
make/unmake design:

- **Hashable for free** - the transposition table keys on the state directly.
- **Safe for MCTS** - tree nodes hold states without defensive copying or replay.
- **Cheap to copy** - the payload is a handful of machine integers, not a board object.

The usual argument for mutable make/unmake is allocation cost, but bitboard integers
make copying nearly free, so that argument does not apply here.

```python
@dataclass(frozen=True)
class GameState:                 # structural protocol, not a base class
    side_to_move: int            # 0 or 1
```

### 2.2 The game protocol

Games are **stateless modules of pure functions**, not objects. Every function takes a
state and returns a value; nothing mutates.

```python
NAME: str                                      # e.g. "isolation"; labels every CSV row

def initial_state() -> S: ...
def legal_moves(s: S) -> List[M]: ...          # deterministic order; [] iff terminal
def apply_move(s: S, m: M) -> S: ...
def is_terminal(s: S) -> bool: ...
def result(s: S) -> float: ...                 # +1/0/-1 for side_to_move; terminal only
def end_reason(s: S) -> str: ...               # for logging, e.g. "line", "no_progress"
def move_to_str(m: M) -> str: ...
def str_to_move(text: str) -> M: ...           # must round-trip
```

**`NAME` is part of the contract, and each game's tests must assert its own value.**
The runner derives both the `game` column and every `game_id` from it. Since Ataxx and
UTTT will be written by following Isolation's module shape, a copied-and-unedited
`NAME = "isolation"` would mislabel an entire game's worth of CSV rows as another
game's, with nothing failing anywhere. `check_conformance` verifies it is a non-empty
string; only a per-game test can verify it is the *right* string.

**No game validates its own moves.** `apply_move` trusts its input, which is correct
for a hot path called at every search node - but it means the *caller* is responsible
for legality. See 7.1.

**`legal_moves` returns `[]` if and only if the state is terminal.** Ataxx is the
exception that proves the rule: a player with no move *passes*, so a pass is
represented as an explicit move in the list, never as an empty list. See
[`ataxx.md` §4.4](../games/ataxx.md).

**Move ordering is the game's job.** `legal_moves` returns moves in a deterministic,
heuristically sensible order so Alpha-Beta gets ordering for free without a separate
mechanism.

### 2.3 Reward scale

`result()` returns `+1` win / `0` draw / `-1` loss **from the perspective of
`side_to_move`**, in all three games. Evaluation functions return values **strictly
inside `(-1, +1)`**, so no heuristic estimate can ever outrank a real terminal
outcome. MCTS maps to `[0, 1]` via `(v + 1) / 2` at exactly one place. Rationale in
[`docs/games/README.md`](../games/README.md).

---

## 3. Per-game specification

Rules live in the gamebooks. This section specifies only representation and the
functions above.

### 3.1 Isolation 5x5 — [`isolation.md`](../games/isolation.md)

```python
@dataclass(frozen=True)
class IsolationState:
    blocked: int        # 25-bit mask, bit (r*5+c)
    pawns: Tuple[int, int]   # cell index 0..24 per player
    side_to_move: int
```

- `initial_state()` - `blocked=0`, `pawns=(2, 22)` i.e. `(0,2)` and `(4,2)`, `side=0`.
- `legal_moves` - 8 ray directions from `pawns[side]`, each extending until the board
  edge, a set bit in `blocked`, or the opponent's cell. Moves are destination cell
  indices. Precompute the 25x8 ray tables at import time.
- `apply_move` - set the departed cell's bit in `blocked`, move the pawn, flip side.
- `is_terminal` - `legal_moves(s) == []`. **Evaluated for the side to move, before
  they act.**
- `result` - always `-1`: the side to move has lost. **Draws are impossible.**
- Move string - `"c1"` style, file `a`-`e` by column, rank `5`-`1` by row.

### 3.2 Ataxx 7x7 — [`ataxx.md`](../games/ataxx.md)

```python
@dataclass(frozen=True)
class AtaxxState:
    boards: Tuple[int, int]      # 49-bit masks, bit (r*7+c), per player
    side_to_move: int
    plies_since_progress: int    # drives the 30-ply no-progress rule
```

- `legal_moves` - scan offsets `dr, dc in -2..2` excluding `(0,0)`, classify on
  `max(abs(dr), abs(dc))`: `1` is a clone, `2` is a jump. **Clones deduplicate by
  destination**; jumps are `(src, dst)` pairs. Clone is `(None, dst)`. If empty, return
  `[PASS]`.
- `apply_move` - place, clear source if a jump, then convert every opponent piece in the
  destination's 8-neighbourhood by mask. Recompute `plies_since_progress`: reset to 0
  on a clone or on any conversion, else increment. **A pass increments it.**
- `is_terminal` - board full, or either player at zero pieces, or
  `plies_since_progress >= 30`.

> **The 300-ply hard cap is a runner-level guard, not a game rule. [GAP - now
> resolved]** Enforcing it inside `is_terminal` would require the *total* ply count in
> the state, and therefore in the transposition-table key - which would make every
> position at a different ply count a distinct entry and **destroy the transposition
> table's entire purpose**. The 30-ply no-progress counter is genuinely part of the
> position and stays in the state; the 300-ply cap is a safety net enforced by
> `runner.play_game`, which ends the game and scores it by piece count. Search does not
> model it, which is acceptable because [`ataxx.md` §4.6](../games/ataxx.md) chose 300
> precisely so it should essentially never fire. Games ending this way are logged with
> `end_reason = "ply_cap"` so that "essentially never" is verified rather than assumed.
- `result` - by piece count; equal counts draw. Note a **full board can never draw**
  (49 is odd), so draws imply the game ended early.
- Move string - `"b6"` clone, `"a7c5"` jump, `"--"` pass.

**`plies_since_progress` is part of the transposition-table key.** Two positions with
identical boards but different counters have different values.

### 3.3 Ultimate Tic-Tac-Toe — [`uttt.md`](../games/ultimate-tic-tac-toe.md)

```python
@dataclass(frozen=True)
class UtttState:
    cells: Tuple[int, ...]       # 9 ints, each a pair of 9-bit masks packed per player
    status: Tuple[int, ...]      # 9 entries: 0 undecided, 1 P1, 2 P2, 3 drawn
    send: int                    # 0..8 target board, or -1 for free choice
    side_to_move: int
    winnable: Tuple[int, int]    # per player, 8-bit mask of still-winnable global lines
```

- `legal_moves` - if `send >= 0` and `status[send] == 0`, only that board; else every
  empty cell in every undecided board.
- `apply_move` - mark the cell; if that decides the local board, update `status`, refresh
  both `winnable` masks, and check the global win. Set `send = cell`.
- `is_terminal` - a global line exists, **or both `winnable` masks are zero** (early
  draw, [§4.8](../games/ultimate-tic-tac-toe.md)), or no legal move remains.
- `winnable` is maintained incrementally: a line stays winnable for `P` while none of its
  three boards is opponent-won or drawn. **Only recomputed when a board's status
  changes** - at most 9 times per game, not once per ply.
- Move string - `"4.7"` for board 4, cell 7.

---

## 4. The decision wrapper — the project's core instrument

This is the part the research question is actually about. Everything else serves it.

### 4.1 Types

```python
class MoveTag(str, Enum):
    NORMAL          = "normal"
    TIME_LIMITED    = "time-limited"
    MEMORY_LIMITED  = "memory-limited"
    ERROR           = "error"

@dataclass(frozen=True)
class Decision:
    move: M
    tag: MoveTag
    elapsed_s: float
    nodes: Optional[int]        # Alpha-Beta nodes expanded; None for MCTS
    simulations: Optional[int]  # MCTS rollouts run; None for Alpha-Beta
    depth: Optional[int]        # deepest completed iteration; Alpha-Beta only
    error: Optional[str]
```

**Both counters are `Optional` and auto-detected**, not switched on by the caller: a
reported `0` is indistinguishable in a CSV from "this agent does not count this
thing", and MCTS never calls `note_node()` while Alpha-Beta never calls
`note_simulation()`. Reporting `0` would put a false "expanded 0 nodes" on every MCTS
row of the file the headline results are computed from. Auto-detection also means no
caller can silently drop a count by forgetting a flag.

### 4.2 `SearchContext` — what the agent is handed

Rather than wrapping the search from outside, the budget is passed *into* it. This is
the whole reason we are not using a framework.

```python
class SearchContext:
    def __init__(self, time_budget_s, max_nodes, check_every=512): ...

    def should_stop(self) -> bool: ...   # polled by the agent; checks clock every
                                         # `check_every` calls to keep overhead low
    def note_node(self) -> None: ...     # increments the node counter
    def hit_memory_cap(self) -> None: ...# agent reports its structure reached capacity
    def completed(self) -> None: ...     # agent reports the search finished naturally
```

`should_stop()` polls the clock only every `check_every` invocations, per PLAN.md's
"check every ~500-1000 nodes" requirement, so timing overhead stays negligible.

**The polling interval is not agent-neutral, and getting this wrong silently deletes a
tag.** The default of 512 is sized for agents that expand thousands of nodes per
decision. A **one-ply agent calls `should_stop()` once per candidate move** - at most
16 in Isolation, about 92 at Ataxx's peak branching factor - so the counter never
reaches 512, **the clock is never read at all**, and the agent reports `normal` even
against a budget that expired before it was invoked. Its `time-limited` tag becomes
unreachable by construction while still appearing in the taxonomy.

Shallow agents therefore call `ctx.set_check_every(1)` before searching. The cost is a
few dozen clock reads per decision - microseconds against budgets of 50ms and up.

> **Expected result, to be stated in the report rather than discovered in a table.**
> With the check made genuine, the Heuristic agent is still expected to be tagged
> `normal` essentially always: evaluating at most ~92 positions takes tens of
> microseconds against a minimum budget three orders of magnitude larger. The
> difference is that this now becomes a **measured property** - "the one-ply baseline
> always completes within budget" - rather than an artifact of a polling constant. The
> distinction matters because the same table reports MCTS as essentially never
> `normal`, and a reader is entitled to know which of those two facts is about the
> algorithm and which is about the instrument.

### 4.2b Memory caps must be calibrated, not guessed **[GAP - now specified]**

PLAN.md requires a memory cap and a `memory-limited` tag but **never says how large the
cap is**. This is not a detail: if `max_nodes` and `max_entries` are set generously, the
cap never binds, the `memory-limited` tag never fires, and **an entire dimension of the
study silently disappears** - we would report a four-value taxonomy with one value
permanently empty.

The caps are therefore **calibrated exactly like the time budgets**, in the same pilot:

| Agent | Capped structure | Cap parameter |
|---|---|---|
| Alpha-Beta | transposition table | `max_entries` |
| MCTS | search tree | `max_nodes` |

The pilot sweeps candidate caps and records the resulting tag distribution. The chosen
cap is the one where `memory-limited` appears **as a meaningful minority** at the main
time budget - present enough to analyse, not so tight that it dominates and turns the
experiment into a memory study.

**The two caps are separate config keys, and equal counts are not equal memory.**
`max_entries` (Alpha-Beta) and `max_nodes` (MCTS) must be **calibrated to comparable
byte footprints**, not set to the same number. A transposition-table entry is a
4-tuple of `(depth, value, flag, best_move)`; an MCTS tree node holds a full game
state, a child mapping, a visit count and a value accumulator - plausibly five times
the size or more.

> **Why this is not a detail.** The research question promises "the same realistic
> per-move **time and memory** budget". If the two agents are capped at equal object
> *counts*, that promise is false and the memory axis of the comparison is
> meaningless - while every table still looks perfectly normal. Pilot phase 2
> therefore measures the actual per-object footprint of each structure (`sys.getsizeof`
> over a populated sample, including the contained state) and sets the two caps so the
> **byte budgets match**. Report both the byte budget and the resulting entry and node
> counts, so a reader can see the conversion rather than trust it.

### 4.3 Tag precedence **[SIGN-OFF]**

PLAN.md defines the four tags but not what happens when several conditions apply at
once. Specified precedence, evaluated top down:

1. An exception escaped the agent -> **`error`**
2. The agent called `completed()` -> **`normal`**
3. The agent called `hit_memory_cap()` at any point during this decision -> **`memory-limited`**
4. Otherwise -> **`time-limited`**

Memory outranks time because it is the rarer and more informative event: if the cap
bound at all, that is the finding, even though the clock also ran out afterwards.

**Consequence worth stating in the report:** MCTS is anytime by construction and
consumes whatever budget it is given, so it will essentially never be tagged `normal`.
The `normal` tag is largely an **Alpha-Beta** phenomenon.

### 4.4 Error handling

An exception is caught, recorded, tagged `error`, and **a uniformly random legal move
is played** so the game can continue and the tournament does not abort. Error moves are
logged and excluded from the main statistics, per PLAN.md.

**The fallback is itself guarded.** If `legal_moves` also raises, or returns `[]` so
that choosing from it fails, `decide` returns `move = None` with both failures recorded
in the error text rather than letting the second exception escape. The guarantee is
that a failing agent costs **one tagged move, never the run** - an unguarded fallback
would have relocated the crash rather than contained it. `runner.play_game` must
therefore treat `move is None` as an aborted game rather than attempting to apply it.

---

## 5. Agents

All four implement `choose_move(state, ctx) -> M`.

### 5.0 Agent lifetime: one instance per game

`SearchContext` is scoped to a single decision, so any structure that must outlive one
move - Alpha-Beta's transposition table, MCTS's tree - lives in the agent object or
closure instead. **The runner therefore constructs a fresh agent per game**, never
reusing one across a matchup.

> **Why this is a correctness requirement, not a style preference.** Reusing one
> Alpha-Beta closure across the games of a matchup is a natural performance instinct,
> and it would silently corrupt the memory measurement: a table already near its cap
> from *earlier, unrelated games* would trigger `hit_memory_cap()` on an early move of
> a later game, tagging that move `memory-limited` because of memory consumed by a game
> that had already finished. The tag would be real and the attribution wrong, with
> nothing to reveal it.

State must not leak between games in any form. Two games with the same seed must
produce identical move sequences regardless of what ran before them - which is testable
and should be tested.

### 5.1 Random
Uniform over `legal_moves`. Calls `ctx.completed()` immediately. Seeded per game.

### 5.2 Heuristic (one-ply)
Evaluates each legal move, keeping a running best so a cutoff still yields a valid
move. Calls `completed()` only if every move was evaluated. Uses the **same evaluator**
as Alpha-Beta's horizon, so their difference isolates search depth.

**Tie-breaking is by seeded random choice among equal-scoring moves**, not by taking the
first. *[GAP - now specified]* Taking the first would make the agent's play an artefact
of `legal_moves` ordering - and since that ordering exists to help Alpha-Beta prune
(2.2), the Heuristic agent would silently inherit Alpha-Beta's move-ordering heuristic
as a tiebreak. Determinism is preserved through the per-game seed (7.2).

### 5.3 Enhanced Alpha-Beta

Negamax with alpha-beta, iterative deepening, a capped transposition table, and move
ordering.

```python
for depth in itertools.count(1):
    value, move = negamax(state, depth, -INF, +INF, ctx)
    if ctx.should_stop(): break          # discard this iteration, keep the last
    best = move
```

**Anytime discipline:** a partially completed iteration is *discarded entirely*; the
returned move is always from the last fully completed depth.

- **Transposition table** - `dict` keyed on the state, storing
  `(depth, value, flag, best_move)` with `flag in {EXACT, LOWER, UPPER}`. Capped at
  `max_entries`; on overflow, **replace-on-collision**. Reaching the cap calls
  `ctx.hit_memory_cap()`.
- **Report the transposition-table hit rate per game.** This is a required metric, not
  a diagnostic. Ataxx's state carries `plies_since_progress` (0..29), which is
  load-bearing for the no-progress rule and therefore part of the key - a position one
  ply from a no-progress draw genuinely is not the same position as one at counter 0.
  That fragments Ataxx's table by up to 30x relative to the other two games. Since the
  study compares Alpha-Beta *across* games, an unmeasured per-game difference in table
  effectiveness would be attributed to the game's size rather than to its rules.
  Measuring it converts a confound into a finding.

  > This is distinct from the total ply count, which is deliberately **not** in state
  > (see 7.1): that counter is unbounded and never resets, so it would make every
  > position at every ply unique and destroy the table outright rather than fragmenting
  > it. The bounded, frequently-resetting no-progress counter is a different case.
- **Move ordering** - TT best move first, then the game's own `legal_moves` order.
- `completed()` is called if an iteration proves a win/loss or exhausts the tree.

### 5.4 MCTS / UCT

Standard four phases, UCB1 selection with `C = sqrt(2)` over values in `[0, 1]`.
Returns the **most-visited** root child.

**Rollout policy.** Pure random rollouts are weak; pure greedy rollouts are
deterministic and collapse rollout diversity, which destroys the Monte Carlo estimate.
Specified: **epsilon-greedy** - with probability `epsilon` a uniformly random move,
otherwise the evaluator's best among at most `k` randomly sampled moves, bounding
per-step cost in wide positions.

**Rollout depth.** Rolling out to terminal costs ~100 plies in Ataxx. Specified:
**truncate at `D` plies** and return the evaluator's value mapped to `[0, 1]`.

### 5.5 Where the MCTS constants come from **[GAP - now specified]**

An earlier draft asserted `epsilon = 0.25`, `k = 8`, `D = 40` as if they were
established values. **They are not, and the report must not present them that way.**
The honest position, separated by what can and cannot be cited:

| Constant | Status |
|---|---|
| `C = sqrt(2)` | **Citable.** Follows from the UCB1 regret bound (Auer, Cesa-Bianchi and Fischer, 2002) as applied to trees by Kocsis and Szepesvari (2006). Assumes rewards in `[0, 1]`, which is exactly why 2.3 maps them. The exact constant depends on how the formula is written, so **state our formula explicitly in the report**. |
| `epsilon`, `k`, `D` | **Not citable.** These are domain-tuned hyperparameters everywhere in the literature; Browne et al. (2012), *A Survey of Monte Carlo Tree Search Methods*, IEEE TCIAIG, catalogues the design space precisely because no universal setting exists. |

**Therefore they are measured, not asserted.** The calibration pilot is extended with a
small MCTS hyperparameter sweep: vary one parameter at a time against a **fixed
Alpha-Beta opponent** at the main time budget, and select on win rate. This turns "we
chose 0.25" into a reported result with numbers behind it.

Starting candidates: `epsilon in {0.1, 0.25, 0.5}`, `D in {20, 40, terminal}`, `k = 8`
held fixed (it only binds on Ataxx, so it is swept only if Ataxx results look
anomalous).

### 5.6 The constants are shared across all three games **[SIGN-OFF]**

**This is a methodological requirement, not a convenience.**

Alpha-Beta has no rollout hyperparameters to tune. If MCTS were tuned per game and
Alpha-Beta were not, MCTS would carry a per-domain advantage that varies with the
domain - and the scaling conclusion becomes uninterpretable, because "MCTS scales
better" could not be separated from "we tuned MCTS harder on that game". Since the
scaling comparison *is* the research question, that confound is fatal.

Note that fixed constants already produce genuinely different behaviour per game,
because the games differ:

| | Isolation (b~8, <=23 plies) | UTTT (b~7, ~50 plies) | Ataxx (b~60, ~100 plies) |
|---|---|---|---|
| `k = 8` | scores every move | scores every move | samples 8 of ~60 |
| `D = 40` | never binds - full rollouts | binds sometimes | binds usually |

That is the honest form of uniformity: one rule, applied identically, adapting because
the domains differ.

**The risk, and its mitigation.** A shared value could be badly wrong for one game,
handicapping MCTS there and manufacturing a false "MCTS scales badly" conclusion. The
sweep therefore reports **per-game sensitivity**, not just the pooled winner, so a
domain where the shared choice is clearly poor is visible rather than silently baked
into the result.

- **Node cap** - the tree is capped at `max_nodes`; on reaching it, expansion stops
  (selection and backpropagation continue) and `ctx.hit_memory_cap()` is called.

---

## 6. Evaluation functions

All return a float **strictly inside `(-1, +1)`**, from the perspective of
`side_to_move`. Each is `evaluate(state) -> float`.

- **Isolation** - mobility difference, `(own_moves - opp_moves)`, squashed into range.
  Well matched to queen-slide, whose mobility varies sharply between positions.
- **Ataxx** - weighted sum of piece-count difference, pieces convertible by the
  candidate move, and **exposure** (a piece is vulnerable exactly when it has an empty
  neighbour, so the term counts empty neighbours, negated). See PLAN.md for why the
  Othello notion of stability does not transfer.
- **UTTT** - local boards won (weighted by how many global lines they participate in),
  plus two-in-a-row threats with the third cell open, minus the opponent's, plus a
  centre/corner board bonus.

> **UTTT's evaluator carries unusual weight.** There is a published claim that this game
> "lacks any simple heuristic evaluation function" and that minimax struggles on it for
> that reason ([§5.5](../games/ultimate-tic-tac-toe.md)). Since Alpha-Beta and the
> Heuristic agent share this function by design, a weak one makes a poor Alpha-Beta
> result ambiguous between "exact search scales badly" and "our heuristic was bad".
> **Its quality must be reported, not assumed.**

---

## 7. Experiment runner

### 7.1 `runner.play_game(game, agent_a, agent_b, config, seed) -> GameRecord`

Alternates agents, wraps each decision, appends a `MoveRecord`, stops at terminal.
Fully deterministic given `seed`. Constructs a **fresh agent per game** (5.0).

**The runner validates every returned move against `legal_moves` before applying it.
[CRITICAL]** `apply_move` deliberately performs no validation - it is called at every
search node and cannot afford to - and `decide()` substitutes a random legal move only
when the agent *raises*. Nothing else stands between a wrong move and the data.

The failure this prevents is the worst kind available in this project. Alpha-Beta and
MCTS are exactly the code that returns a **wrong-but-plausible** move under a real bug:
a stale transposition-table hit from a different depth, an off-by-one in best-move
bookkeeping, a tree node whose move list went stale after pruning. Applied unchecked,
such a move produces a game that runs to a decisive conclusion, is tagged `normal`,
renders fine through `move_to_str`, and yields a CSV row **indistinguishable from a
correct game**. There is no crash and no failing test - the study simply reports wrong
numbers.

The check is free: `play_game` already computes `legal_moves` for the
`legal_move_count` column, so it reuses that list rather than calling again. It runs
**outside** the agent's timing so validation is never charged to the agent.

On violation: record the move with the `error` tag, end the game with
`end_reason = "illegal_move"`, and score it a **draw** - the same containment as
`agent_error`, so one agent's bug costs one game rather than the run. **A nonzero
`illegal_move` count in the results is a bug report, not a data point**, and must be
investigated rather than averaged.

### 7.2 Seeding **[SIGN-OFF]**

Every game's seed is derived deterministically:
`seed = hash((game_name, agent_a, agent_b, config_name, trial_index))`. This makes any
single game individually reproducible for debugging without re-running the tournament.

> **What the seed does and does not guarantee. [IMPORTANT - state this in the report.]**
> The seed makes every *random choice* reproducible: the random agent's picks, the
> heuristic agent's tie-breaks, MCTS's expansion order and rollouts. It does **not**
> make a wall-clock-budgeted search bit-reproducible, because how many nodes
> Alpha-Beta expands or how many simulations MCTS runs depends on how fast the machine
> happened to be for those milliseconds. Re-running the identical seed can therefore
> produce a different game.
>
> Observed directly: Alpha-Beta versus the Heuristic agent over the same 20 seeds at a
> 50ms budget scored 20/20 in one run and 18/20 in another. Both are the same code and
> the same seeds.
>
> This is **intrinsic to the experimental design, not a defect** - it is the price of
> using wall-clock time as the budget, which section 5 of PLAN.md argues is the only
> fair unit across two different search paradigms. Two consequences to handle honestly:
>
> - **The CSV is one sample, not a replayable artifact.** A logged game can be
>   *inspected* move by move, but replaying its seed need not reproduce it.
> - **Trial counts must be large enough that this variance is absorbed**, and reported
>   figures need confidence intervals rather than bare percentages. It is a further
>   argument for the interleaving requirement in 7.4: run-to-run timing noise must hit
>   every agent equally rather than accumulating against whichever ran last.
>
> Only the two baseline agents are genuinely bit-reproducible, since neither consults
> the clock in a way that changes its choice.

### 7.3 `calibrate.py`

Three phases, run in order. Each produces numbers the report can cite.

**Phase 1 - time budgets.** For each game, Alpha-Beta vs MCTS across candidate budgets
`[0.1, 0.25, 0.5, 1, 2, 5]` s, recording the tag distribution and **real
seconds-per-game**. Outputs the easy/main/hard budgets.

**Phase 2 - memory caps (4.2b).** Sweep `max_entries` and `max_nodes` at the chosen main
budget, and select caps where `memory-limited` appears as a meaningful minority.
**Without this phase the `memory-limited` tag never fires and a quarter of the tag
taxonomy is dead.**

**Phase 3 - MCTS hyperparameters (5.5).** Sweep `epsilon` and `D` against a fixed
Alpha-Beta opponent, one parameter at a time, reporting win rate **per game as well as
pooled** so a domain where the shared choice is poor stays visible.

**Final output: a projected total runtime for the full grid**, from measured
seconds-per-game rather than estimates - which is what lets the grid be sized against
the calendar (PLAN.md's fallback ladder).

### 7.4 `tournament.py`

Runs the grid from PLAN.md: 3 games x 6 pairings x 2 seat orders x configs x `T` trials.

**Trials are interleaved across matchups**, never grouped by agent, so thermal drift or
background load affects every agent equally. This is a correctness requirement of the
methodology, not an optimisation.

Supports `--resume` from an existing CSV so an interrupted overnight run is not lost;
completed `game_id`s are read back and skipped.

**Parallelism [GAP - now specified].** Games are independent, so the grid parallelises
perfectly - but this is a *timing* experiment, and contended cores would corrupt exactly
the quantity being measured. Specified:

- `--workers N` defaults to **1**, and a single-worker run is the reference result.
- With `N > 1`, **one worker per physical core, leaving at least one core for the host**,
  and workers pinned where the OS allows it.
- **The worker count is recorded in `games.csv`.** If the pilot shows the per-move timing
  distribution shifting between `N=1` and `N>1`, the parallel results are not comparable
  to the sequential ones and the run must be sequential.

Given the measured budgets, the full grid is expected to be an overnight run at `N=1`,
so parallelism should be treated as a fallback for a squeezed schedule rather than the
default.

---

## 8. CSV schema

Two files, because the natural row differs.

**`results/raw/games.csv`** - one row per game:

| Column | Notes |
|---|---|
| `game_id` | stable, derived from the seed inputs |
| `game` | isolation / ataxx / uttt |
| `config` | easy / main / hard |
| `time_budget_s`, `max_nodes` | the actual budget applied |
| `agent_first`, `agent_second` | static agent identities |
| `winner` | `first` / `second` / `draw` |
| `plies` | game length |
| `end_reason` | from `end_reason()` - line, no_progress, cap, no_moves, early_draw |
| `seed` | for exact replay |

**`results/raw/moves.csv`** - one row per move:

| Column | Notes |
|---|---|
| `game_id`, `ply`, `agent`, `side` | |
| `tag` | normal / time-limited / memory-limited / error |
| `elapsed_s` | wall-clock for this decision |
| `nodes` | Alpha-Beta nodes expanded; **empty for MCTS** |
| `simulations` | MCTS rollouts run; **empty for Alpha-Beta** |
| `depth` | deepest completed iteration; Alpha-Beta only |
| `move` | the round-trippable move string |
| `legal_move_count` | **this is the branching-factor measurement**, free here |

> **`nodes` and `simulations` are deliberately separate columns. [GAP - now fixed]** An
> earlier draft pooled them into one, which would have silently invited the analysis to
> compare them. **An Alpha-Beta node and an MCTS simulation are not the same unit of
> work** - one is a static evaluation at a horizon, the other a rollout of up to `D`
> plies. Any figure plotting "work done" must not put them on a shared axis, and
> separate columns make that mistake hard to commit by accident.

Logging is **streamed and flushed per game**, so an interrupted run keeps its data.

---

## 8b. Analysis and statistics **[GAP - now specified]**

PLAN.md names the metrics but not how draws are handled, and with draws present that
ambiguity changes the headline numbers.

**Scoring.** Report **both**, because they answer different questions:

- **Score rate** = `(wins + 0.5 * draws) / games` - the standard tournament measure, and
  the right one for ranking agents.
- **Win / draw / loss rates** separately - because a draw-heavy result is itself a
  finding, and score rate hides it. UTTT in particular is expected to draw often, while
  Isolation cannot draw at all.

Never report "win rate" alone without saying which of these is meant.

**First-move advantage.** PLAN.md specifies a binomial test against a 50/50 null, which
is undefined when draws exist. Specified: **exclude draws and test the decisive games
only** - null `p = 0.5` on `wins_first / (wins_first + wins_second)`. Report the number
of excluded draws alongside, since a test on 20 decisive games out of 100 is much weaker
than it looks, and a reader must be able to see that.

**Aggregation levels.** Global (all pairings pooled), per pairing, per game, per config.
The global test is the well-powered one; per-pairing claims at low `T` should be
reported with their confidence intervals rather than as bare percentages.

**Excluded from all statistics:** moves tagged `error`, and the games containing them,
per PLAN.md. Both counts are reported separately - a nonzero error count is a bug
report, not a data point.

---

## 9. Testing strategy

TDD throughout, since the framework decision means correctness rests on our tests.

**Per game:** the starting position; move generation on hand-checked positions;
round-trip `str_to_move(move_to_str(m)) == m`; terminal detection at each end condition;
`legal_moves == []` iff terminal; a random-playthrough fuzz test asserting no illegal
state ever arises and every game terminates within its bound.

**Game-specific properties worth asserting directly**, because each caught a real
specification error while writing the gamebooks:
- Isolation - exactly one cell blocks per ply; no game exceeds 23 plies; no draws.
- Ataxx - all 16 jump destinations generated, including the 8 knight-shaped ones;
  clones deduplicated by destination; occupied count never decreases; **no double pass
  ever occurs** ([§4.4.1](../games/ataxx.md) proves it cannot, so a failure is a bug).
- UTTT - decided boards produce no legal moves; early-draw detection agrees with
  playing the position out.

**Agents:** the wrapper tags correctly under a forced timeout, a forced memory cap, and
a raised exception; Alpha-Beta never returns a move from an incomplete iteration; MCTS
returns the most-visited child.

**The highest-value validation, before any tournament run:** measure Ataxx's branching
factor per ply with the random agent and compare against Ribeiro and Figueiredo - ~20 at
ply 1, peaking at **92** near ply 25, ~90 again near ply 52. Reproducing that
double-humped curve is strong evidence the move generator is right; a flat curve means a
bug, caught before a night of compute is spent on it.

---

## 10. Build order

Each step is independently verifiable, and nothing downstream starts before its
dependency has tests passing.

1. `games/base.py`, `agents/base.py`, `SearchContext`, the decision wrapper — **tests first**
2. Isolation + its tests *(simplest game; proves the interfaces)*
3. Random + Heuristic agents + a trivial evaluator *(proves the wrapper end to end)*
4. `runner.py` + `logger.py` *(a full game now runs and logs)*
5. UTTT, then Ataxx *(hardest last, with the interfaces already settled)*
6. Alpha-Beta
7. MCTS
8. Real evaluation functions for all three games
9. **Validation gate** - measure Ataxx branching factor per ply with the random agent and
   check it against Ribeiro and Figueiredo (section 9). **Do not proceed past this step
   on a flat curve.**
10. `calibrate.py` -> **run the pilot** (all three phases: time budgets, memory caps,
    MCTS hyperparameters)
11. `tournament.py` -> **run the tournament**
12. `analyse.py` -> tables and figures per section 8b

Step 2 deliberately precedes the harder games: Isolation is simple enough that any
interface mistake surfaces cheaply, while discovering the same mistake inside Ataxx
would be expensive.
