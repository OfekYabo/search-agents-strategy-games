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
def initial_state() -> S: ...
def legal_moves(s: S) -> List[M]: ...          # deterministic order; [] iff terminal
def apply_move(s: S, m: M) -> S: ...
def is_terminal(s: S) -> bool: ...
def result(s: S) -> float: ...                 # +1/0/-1 for side_to_move; terminal only
def end_reason(s: S) -> str: ...               # for logging, e.g. "line", "no_progress"
def move_to_str(m: M) -> str: ...
def str_to_move(text: str) -> M: ...           # must round-trip
```

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
  `plies_since_progress >= 30`, or ply count `>= 300`.
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
    nodes: int              # nodes expanded (AB) or simulations run (MCTS)
    depth: Optional[int]    # deepest completed iteration; AB only
    error: Optional[str]
```

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

---

## 5. Agents

All four implement `choose_move(state, ctx) -> M`.

### 5.1 Random
Uniform over `legal_moves`. Calls `ctx.completed()` immediately. Seeded per game.

### 5.2 Heuristic (one-ply)
Evaluates each legal move, keeping a running best so a cutoff still yields a valid
move. Calls `completed()` only if every move was evaluated. Uses the **same evaluator**
as Alpha-Beta's horizon, so their difference isolates search depth.

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
- **Move ordering** - TT best move first, then the game's own `legal_moves` order.
- `completed()` is called if an iteration proves a win/loss or exhausts the tree.

### 5.4 MCTS / UCT

Standard four phases, UCB1 selection with `C = sqrt(2)` over values in `[0, 1]`.
Returns the **most-visited** root child.

Two decisions PLAN.md leaves open:

**Rollout policy [SIGN-OFF].** Pure random rollouts are known to be weak; pure greedy
rollouts are deterministic and collapse diversity. Specified: **epsilon-greedy**, with
`epsilon = 0.25` random and otherwise the evaluator's best move, scoring at most `k = 8`
randomly sampled moves per rollout step to bound cost in wide positions like Ataxx.

**Rollout depth [SIGN-OFF].** Rolling out to a terminal state costs ~100 plies in
Ataxx. Specified: **truncate at `D = 40` plies** and return the evaluator's value
(mapped to `[0, 1]`). Both `epsilon` and `D` are configuration parameters, and the pilot
can revisit them.

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
Fully deterministic given `seed`.

### 7.2 Seeding **[SIGN-OFF]**

Every game's seed is derived deterministically:
`seed = hash((game_name, agent_a, agent_b, config_name, trial_index))`. This makes any
single game individually reproducible for debugging without re-running the tournament.

### 7.3 `calibrate.py`

For each game, plays Alpha-Beta vs MCTS across candidate budgets
`[0.1, 0.25, 0.5, 1, 2, 5]` s, recording the tag distribution and **real
seconds-per-game**. Outputs the easy/main/hard budgets *and* a projected total runtime
for the full grid, so the grid can be sized against the calendar with measured numbers
rather than estimates.

### 7.4 `tournament.py`

Runs the grid from PLAN.md: 3 games x 6 pairings x 2 seat orders x configs x `T` trials.

**Trials are interleaved across matchups**, never grouped by agent, so thermal drift or
background load affects every agent equally. This is a correctness requirement of the
methodology, not an optimisation.

Supports `--resume` from an existing CSV so an interrupted overnight run is not lost.

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
| `elapsed_s`, `nodes`, `depth` | `depth` empty for non-AB agents |
| `move` | the round-trippable move string |
| `legal_move_count` | **this is the branching-factor measurement**, free here |

Logging is **streamed and flushed per game**, so an interrupted run keeps its data.

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
9. `calibrate.py` -> **run the pilot**
10. `tournament.py` -> **run the tournament**
11. `analyse.py` -> tables and figures

Step 2 deliberately precedes the harder games: Isolation is simple enough that any
interface mistake surfaces cheaply, while discovering the same mistake inside Ataxx
would be expensive.
