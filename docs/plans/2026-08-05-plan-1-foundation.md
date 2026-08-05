# Plan 1: Foundation and First Vertical Slice

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A complete Isolation game plays end to end between two baseline agents, with every move tagged and the whole game logged to CSV.

**Architecture:** Games are stateless modules of pure functions over immutable, integer-backed frozen dataclasses. The resource budget is passed *into* the search through a `SearchContext` the agent polls, rather than wrapped around it - this is the design decision that made a framework unnecessary. A reusable random-playthrough conformance checker is built first, so every later game is validated by the same harness.

**Tech Stack:** Python 3.8.10, standard library only. Tests use `unittest` (stdlib), not pytest, so the zero-dependency promise holds absolutely - a collaborator clones the repo and runs it with no `pip install` at all.

## Global Constraints

- **Python 3.8.10.** No `match` statements, no `X | Y` type unions, no `dict |` merge operator. Use `typing.List`, `typing.Tuple`, `typing.Optional`.
- **Standard library only.** No third-party runtime or test dependencies.
- **Reward scale:** `+1` win / `0` draw / `-1` loss, always from the perspective of `side_to_move`. Evaluators return values strictly inside `(-1, +1)`.
- **States are immutable** frozen dataclasses whose fields are `int` or `tuple`.
- **`legal_moves` returns `[]` if and only if the state is terminal.**
- Rules are authoritative in [`docs/games/`](../games/); never restate a rule in code comments, link to the gamebook section.
- Run tests with `python -m unittest discover -s tests -v`.
- Commit messages describe the change only - no AI attribution, no co-author trailers.

---

### Task 1: Game conformance harness

The reusable validator every game's tests will call. Built first so no game is ever written without a way to check it.

**Files:**
- Create: `games/__init__.py`, `games/base.py`
- Test: `tests/__init__.py`, `tests/test_games_base.py`

**Interfaces:**
- Consumes: nothing
- Produces: `games.base.WIN`, `games.base.DRAW`, `games.base.LOSS` (floats `1.0`, `0.0`, `-1.0`); `games.base.ConformanceError(AssertionError)`; `games.base.check_conformance(game, rng, n_games=200, max_plies=1000, side_of=None) -> None` which raises `ConformanceError` on any violation. `game` is any module exposing `initial_state`, `legal_moves`, `apply_move`, `is_terminal`, `result`, `end_reason`, `move_to_str`, `str_to_move`. `side_of` defaults to reading `state.side_to_move`; override it for states that are not dataclasses (the toy game in the tests uses a tuple).

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` as an empty file. Then `tests/test_games_base.py`:

```python
import random
import unittest

from games.base import WIN, DRAW, LOSS, ConformanceError, check_conformance


class _ToyGame:
    """Minimal conforming game: count from 0 to 4, mover at 4 loses."""

    @staticmethod
    def initial_state():
        return (0, 0)  # (count, side_to_move)

    @staticmethod
    def legal_moves(s):
        return [] if s[0] >= 4 else [1, 2]

    @staticmethod
    def apply_move(s, m):
        return (s[0] + m, 1 - s[1])

    @staticmethod
    def is_terminal(s):
        return s[0] >= 4

    @staticmethod
    def result(s):
        return LOSS

    @staticmethod
    def end_reason(s):
        return "exhausted"

    @staticmethod
    def move_to_str(m):
        return str(m)

    @staticmethod
    def str_to_move(text):
        return int(text)


def _side_of(s):
    return s[1]


class ConformanceTest(unittest.TestCase):
    def test_conforming_game_passes(self):
        check_conformance(_ToyGame, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_terminal_disagreeing_with_empty_moves(self):
        class Broken(_ToyGame):
            @staticmethod
            def is_terminal(s):
                return s[0] >= 3  # terminal while moves remain

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_bad_move_string_round_trip(self):
        class Broken(_ToyGame):
            @staticmethod
            def str_to_move(text):
                return 99

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_side_not_alternating(self):
        class Broken(_ToyGame):
            @staticmethod
            def apply_move(s, m):
                return (s[0] + m, s[1])  # side never flips

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_result_outside_scale(self):
        class Broken(_ToyGame):
            @staticmethod
            def result(s):
                return -7.0

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_game_exceeding_ply_bound(self):
        class Endless(_ToyGame):
            @staticmethod
            def legal_moves(s):
                return [0]  # never progresses

            @staticmethod
            def is_terminal(s):
                return False

        with self.assertRaises(ConformanceError):
            check_conformance(Endless, random.Random(1), n_games=1,
                              max_plies=50, side_of=_side_of)

    def test_detects_non_string_end_reason(self):
        class Broken(_ToyGame):
            @staticmethod
            def end_reason(s):
                return 42

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)

    def test_detects_apply_move_rejecting_a_legal_move(self):
        # The bug class this harness exists to catch: a move generator and a
        # move applier that disagree. The raw exception must be converted, or
        # later game tests see a confusing error instead of a diagnostic.
        class Broken(_ToyGame):
            @staticmethod
            def apply_move(s, m):
                raise KeyError("bad move")

        with self.assertRaises(ConformanceError):
            check_conformance(Broken, random.Random(1), n_games=20, side_of=_side_of)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_games_base -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'games'`

- [ ] **Step 3: Write minimal implementation**

Create `games/__init__.py` as an empty file. Then `games/base.py`:

```python
"""Shared types and the conformance checker for game modules.

A "game" is a module (or any namespace) exposing pure functions:

    initial_state() -> S
    legal_moves(s: S) -> List[M]        # [] if and only if terminal
    apply_move(s: S, m: M) -> S
    is_terminal(s: S) -> bool
    result(s: S) -> float               # WIN / DRAW / LOSS for side_to_move
    end_reason(s: S) -> str
    move_to_str(m: M) -> str
    str_to_move(text: str) -> M

Rules for each game are specified in docs/games/, which is authoritative.
"""
from typing import Any, Callable, Optional

WIN = 1.0
DRAW = 0.0
LOSS = -1.0

_RESULTS = (WIN, DRAW, LOSS)


class ConformanceError(AssertionError):
    """A game module violated the interface contract."""


def _default_side_of(state):
    return state.side_to_move


def check_conformance(game, rng, n_games=200, max_plies=1000, side_of=None):
    # type: (Any, Any, int, int, Optional[Callable[[Any], int]]) -> None
    """Play random games, raising ConformanceError on any contract violation.

    Checks, at every ply of every game:
      - is_terminal(s) agrees exactly with legal_moves(s) being empty
      - result() at a terminal state is one of WIN / DRAW / LOSS
      - move strings round-trip: str_to_move(move_to_str(m)) == m
      - apply_move returns a new state and flips the side to move
      - no game exceeds max_plies
    """
    if side_of is None:
        side_of = _default_side_of

    for game_index in range(n_games):
        state = game.initial_state()
        for ply in range(max_plies + 1):
            terminal = game.is_terminal(state)
            moves = game.legal_moves(state)

            if terminal != (len(moves) == 0):
                raise ConformanceError(
                    "game %d ply %d: is_terminal()=%r but legal_moves() has %d "
                    "entries; they must agree exactly"
                    % (game_index, ply, terminal, len(moves))
                )

            if terminal:
                outcome = game.result(state)
                if outcome not in _RESULTS:
                    raise ConformanceError(
                        "game %d ply %d: result()=%r is not one of %r"
                        % (game_index, ply, outcome, _RESULTS)
                    )
                if not isinstance(game.end_reason(state), str):
                    raise ConformanceError(
                        "game %d ply %d: end_reason() must return str"
                        % (game_index, ply)
                    )
                break

            move = rng.choice(moves)
            restored = game.str_to_move(game.move_to_str(move))
            if restored != move:
                raise ConformanceError(
                    "game %d ply %d: move string did not round-trip: "
                    "%r -> %r -> %r"
                    % (game_index, ply, move, game.move_to_str(move), restored)
                )

            before = side_of(state)
            try:
                state = game.apply_move(state, move)
            except ConformanceError:
                raise
            except Exception as exc:
                # A move generator and a move applier that disagree is exactly
                # the bug class this harness exists to catch, so it must surface
                # as a diagnostic rather than as the game's raw exception.
                raise ConformanceError(
                    "game %d ply %d: apply_move(%r) raised %s: %s"
                    % (game_index, ply, move, type(exc).__name__, exc)
                )
            if side_of(state) == before:
                raise ConformanceError(
                    "game %d ply %d: apply_move did not flip side_to_move"
                    % (game_index, ply)
                )
        else:
            raise ConformanceError(
                "game %d did not terminate within %d plies"
                % (game_index, max_plies)
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_games_base -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add games/ tests/
git commit -m "Add game module contract and random-playthrough conformance checker

Every game is validated by the same harness rather than by bespoke tests,
so the invariants that matter most - that is_terminal agrees exactly with
legal_moves being empty, that move strings round-trip, and that no game
exceeds its ply bound - are checked identically for all three games."
```

---

### Task 2: Decision wrapper and SearchContext

The project's core instrument. Everything else exists to serve this.

**Files:**
- Create: `agents/__init__.py`, `agents/base.py`
- Test: `tests/test_agents_base.py`

**Interfaces:**
- Consumes: nothing from Task 1
- Produces:
  - `agents.base.MoveTag` - `str` Enum with members `NORMAL="normal"`, `TIME_LIMITED="time-limited"`, `MEMORY_LIMITED="memory-limited"`, `ERROR="error"`
  - `agents.base.Decision` - frozen dataclass `(move, tag, elapsed_s, nodes, simulations, depth, error)`
  - `agents.base.SearchContext(time_budget_s, max_nodes, check_every=512, clock=time.monotonic)` with methods `should_stop() -> bool`, `note_node() -> None`, `hit_memory_cap() -> None`, `completed() -> None`, and read-only attributes `nodes`, `memory_capped`, `finished`
  - `agents.base.decide(agent, game, state, time_budget_s, max_nodes, rng, clock=time.monotonic) -> Decision`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agents_base.py`:

```python
import random
import unittest

from agents.base import Decision, MoveTag, SearchContext, decide


class FakeClock:
    """Manually advanced clock, so timing tests are deterministic."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _StubGame:
    @staticmethod
    def legal_moves(s):
        return [10, 20, 30]


class SearchContextTest(unittest.TestCase):
    def test_does_not_stop_before_budget_expires(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=1, clock=clock)
        clock.advance(0.5)
        self.assertFalse(ctx.should_stop())

    def test_stops_once_budget_expires(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=1, clock=clock)
        clock.advance(1.5)
        self.assertTrue(ctx.should_stop())

    def test_polls_clock_only_every_check_every_calls(self):
        clock = FakeClock()
        ctx = SearchContext(1.0, max_nodes=100, check_every=4, clock=clock)
        clock.advance(99.0)
        # First three calls fall between polls and must not observe the clock.
        self.assertFalse(ctx.should_stop())
        self.assertFalse(ctx.should_stop())
        self.assertFalse(ctx.should_stop())
        self.assertTrue(ctx.should_stop())

    def test_counts_nodes(self):
        ctx = SearchContext(1.0, max_nodes=100, clock=FakeClock())
        for _ in range(7):
            ctx.note_node()
        self.assertEqual(ctx.nodes, 7)

    def test_records_memory_cap_and_completion_flags(self):
        ctx = SearchContext(1.0, max_nodes=100, clock=FakeClock())
        self.assertFalse(ctx.memory_capped)
        self.assertFalse(ctx.finished)
        ctx.hit_memory_cap()
        ctx.completed()
        self.assertTrue(ctx.memory_capped)
        self.assertTrue(ctx.finished)


class DecideTest(unittest.TestCase):
    def test_tags_normal_when_agent_reports_completion(self):
        def agent(game, state, ctx, rng):
            ctx.completed()
            return 20

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.NORMAL)
        self.assertEqual(d.move, 20)

    def test_tags_time_limited_when_agent_does_not_complete(self):
        def agent(game, state, ctx, rng):
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.TIME_LIMITED)

    def test_memory_outranks_time_when_both_apply(self):
        def agent(game, state, ctx, rng):
            ctx.hit_memory_cap()
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.MEMORY_LIMITED)

    def test_completion_outranks_memory(self):
        def agent(game, state, ctx, rng):
            ctx.hit_memory_cap()
            ctx.completed()
            return 10

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.NORMAL)

    def test_exception_is_tagged_error_and_falls_back_to_a_legal_move(self):
        def agent(game, state, ctx, rng):
            raise ValueError("boom")

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=FakeClock())
        self.assertEqual(d.tag, MoveTag.ERROR)
        self.assertIn(d.move, [10, 20, 30])
        self.assertIn("boom", d.error)

    def test_records_elapsed_time_and_node_count(self):
        clock = FakeClock()

        def agent(game, state, ctx, rng):
            ctx.note_node()
            ctx.note_node()
            clock.advance(0.25)
            ctx.completed()
            return 30

        d = decide(agent, _StubGame, None, 1.0, 100, random.Random(0), clock=clock)
        self.assertEqual(d.nodes, 2)
        self.assertAlmostEqual(d.elapsed_s, 0.25)

    def test_decision_is_immutable(self):
        d = Decision(move=1, tag=MoveTag.NORMAL, elapsed_s=0.0, nodes=0,
                     simulations=None, depth=None, error=None)
        with self.assertRaises(Exception):
            d.move = 2


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_agents_base -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents'`

- [ ] **Step 3: Write minimal implementation**

Create `agents/__init__.py` as an empty file. Then `agents/base.py`:

```python
"""Agent contract, resource budget, and the tagged decision wrapper.

The budget is passed *into* the search rather than wrapped around it, so the
clock check, node counting and memory cap live inside the search loop where
the phenomenon being studied actually happens. See docs/spec/technical-spec.md
section 4.

An agent is any callable:

    agent(game, state, ctx: SearchContext, rng: random.Random) -> move
"""
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class MoveTag(str, Enum):
    NORMAL = "normal"
    TIME_LIMITED = "time-limited"
    MEMORY_LIMITED = "memory-limited"
    ERROR = "error"


@dataclass(frozen=True)
class Decision:
    move: Any
    tag: MoveTag
    elapsed_s: float
    nodes: Optional[int]        # Alpha-Beta nodes expanded; None for MCTS
    simulations: Optional[int]  # MCTS rollouts run; None for Alpha-Beta
    depth: Optional[int]
    error: Optional[str]


class SearchContext:
    """The resource budget an agent searches inside.

    should_stop() polls the wall clock only once every `check_every` calls, so
    timing overhead stays negligible even when called at every node. PLAN.md
    specifies checking every ~500-1000 nodes.
    """

    def __init__(self, time_budget_s, max_nodes, check_every=512,
                 clock=time.monotonic):
        self._budget = time_budget_s
        self.max_nodes = max_nodes
        self._check_every = check_every
        self._clock = clock
        self._start = clock()
        self._since_poll = 0
        self._stopped = False
        self.nodes = 0
        self.simulations = 0
        self.memory_capped = False
        self.finished = False

    def should_stop(self):
        # type: () -> bool
        if self._stopped:
            return True
        self._since_poll += 1
        if self._since_poll < self._check_every:
            return False
        self._since_poll = 0
        if self._clock() - self._start >= self._budget:
            self._stopped = True
        return self._stopped

    def note_node(self):
        # type: () -> None
        self.nodes += 1

    def note_simulation(self):
        # type: () -> None
        self.simulations += 1

    def hit_memory_cap(self):
        # type: () -> None
        self.memory_capped = True

    def completed(self):
        # type: () -> None
        self.finished = True

    def elapsed(self):
        # type: () -> float
        return self._clock() - self._start


def decide(agent, game, state, time_budget_s, max_nodes, rng,
           check_every=512, clock=time.monotonic):
    # type: (Any, Any, Any, float, int, Any, int, Any) -> Decision
    """Run one agent decision under budget and tag the outcome.

    Tag precedence, top down (spec section 4.3):
      1. an exception escaped          -> ERROR
      2. the agent called completed()  -> NORMAL
      3. the agent called hit_memory_cap() at any point -> MEMORY_LIMITED
      4. otherwise                     -> TIME_LIMITED

    Memory outranks time because it is the rarer and more informative event: if
    the cap bound at all, that is the finding, even though the clock also ran
    out afterwards.
    """
    ctx = SearchContext(time_budget_s, max_nodes, check_every=check_every,
                        clock=clock)
    error = None
    depth = None
    try:
        move = agent(game, state, ctx, rng)
    except Exception:
        error = traceback.format_exc(limit=3)
        # Fall back to a legal move so the game and the tournament continue.
        move = rng.choice(game.legal_moves(state))

    if error is not None:
        tag = MoveTag.ERROR
    elif ctx.finished:
        tag = MoveTag.NORMAL
    elif ctx.memory_capped:
        tag = MoveTag.MEMORY_LIMITED
    else:
        tag = MoveTag.TIME_LIMITED

    return Decision(
        move=move,
        tag=tag,
        elapsed_s=ctx.elapsed(),
        nodes=ctx.nodes,
        # Reported only by agents that actually run simulations, so the CSV
        # column stays empty for Alpha-Beta rather than reading a misleading 0.
        # Auto-detected rather than passed in by the caller: a flag would have
        # to be threaded through play_game, and forgetting it would silently
        # drop every MCTS simulation count.
        simulations=ctx.simulations if ctx.simulations else None,
        depth=getattr(ctx, "depth_reached", None),
        error=error,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_agents_base -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Commit**

```bash
git add agents/ tests/test_agents_base.py
git commit -m "Add search context and tagged decision wrapper

The budget is passed into the search rather than wrapped around it, so the
clock check, node counting and memory cap sit inside the search loop where
the degradation being studied actually occurs.

Tag precedence puts memory ahead of time: if the cap bound at any point that
is the finding, even though the clock also expired afterwards. An escaping
exception is tagged and falls back to a random legal move so one agent bug
cannot abort a tournament."
```

---

### Task 3: Isolation 5x5

**Files:**
- Create: `games/isolation.py`
- Test: `tests/test_isolation.py`

Rules are authoritative in [`docs/games/isolation.md`](../games/isolation.md): queen-slide movement, the vacated cell blocks with no exceptions, pawns start `(0,2)` and `(4,2)`, a player with no legal move loses, draws are impossible.

**Interfaces:**
- Consumes: `games.base.WIN/DRAW/LOSS`, `games.base.check_conformance`
- Produces: `games.isolation` module with `NAME = "isolation"`, `IsolationState(blocked: int, pawns: Tuple[int, int], side_to_move: int)`, and the eight contract functions. Cell indices are `r * 5 + c`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_isolation.py`:

```python
import random
import unittest

from games import isolation
from games.base import LOSS, check_conformance


def cell(r, c):
    return r * 5 + c


class IsolationRulesTest(unittest.TestCase):
    def test_initial_position(self):
        s = isolation.initial_state()
        self.assertEqual(s.blocked, 0)
        self.assertEqual(s.pawns, (cell(0, 2), cell(4, 2)))
        self.assertEqual(s.side_to_move, 0)

    def test_ply_one_branching_factor_is_eleven(self):
        # From (0,2) on an empty board: E 2, W 2, S 3, SE 2, SW 2.
        # The southward ray yields THREE, not four: it stops before (4,2),
        # which is the opponent's starting cell. Gamebook section 5.3.
        s = isolation.initial_state()
        self.assertEqual(len(isolation.legal_moves(s)), 11)

    def test_maximum_branching_factor_from_centre_is_sixteen(self):
        # 16 requires the opponent to stand on one of the eight cells no ray
        # from the centre passes through; (0,1) is one of them.
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(2, 2), cell(0, 1)),
                                     side_to_move=0)
        self.assertEqual(len(isolation.legal_moves(s)), 16)

    def test_opponent_pawn_truncates_a_ray_from_the_centre(self):
        # Same centre position but the opponent on the southward ray: 15, not 16.
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(2, 2), cell(4, 2)),
                                     side_to_move=0)
        self.assertEqual(len(isolation.legal_moves(s)), 15)

    def test_ray_stops_before_a_blocked_cell(self):
        s = isolation.IsolationState(blocked=1 << cell(2, 2),
                                     pawns=(cell(0, 2), cell(4, 4)),
                                     side_to_move=0)
        moves = isolation.legal_moves(s)
        self.assertIn(cell(1, 2), moves)      # reachable, before the block
        self.assertNotIn(cell(2, 2), moves)   # the blocked cell itself
        self.assertNotIn(cell(3, 2), moves)   # beyond it - no jumping

    def test_ray_stops_before_the_opponent_pawn(self):
        s = isolation.IsolationState(blocked=0,
                                     pawns=(cell(0, 2), cell(2, 2)),
                                     side_to_move=0)
        moves = isolation.legal_moves(s)
        self.assertIn(cell(1, 2), moves)
        self.assertNotIn(cell(2, 2), moves)
        self.assertNotIn(cell(3, 2), moves)

    def test_vacated_cell_becomes_blocked(self):
        s = isolation.initial_state()
        start = s.pawns[0]
        s2 = isolation.apply_move(s, cell(1, 2))
        self.assertTrue(s2.blocked & (1 << start))
        self.assertEqual(s2.pawns[0], cell(1, 2))
        self.assertEqual(s2.side_to_move, 1)

    def test_starting_cells_are_not_exempt_from_blocking(self):
        # Gamebook 4.2: no exempt cells anywhere, including the start cells.
        s = isolation.initial_state()
        s2 = isolation.apply_move(s, cell(1, 2))
        self.assertTrue(s2.blocked & (1 << cell(0, 2)))

    def test_player_with_no_move_loses(self):
        # Pawn at corner (0,0) with both neighbours on its rays blocked.
        blocked = (1 << cell(0, 1)) | (1 << cell(1, 0)) | (1 << cell(1, 1))
        s = isolation.IsolationState(blocked=blocked,
                                     pawns=(cell(0, 0), cell(4, 4)),
                                     side_to_move=0)
        self.assertEqual(isolation.legal_moves(s), [])
        self.assertTrue(isolation.is_terminal(s))
        self.assertEqual(isolation.result(s), LOSS)

    def test_move_string_round_trips(self):
        for index in range(25):
            self.assertEqual(
                isolation.str_to_move(isolation.move_to_str(index)), index)


class IsolationInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(isolation, random.Random(7), n_games=300, max_plies=30)

    def test_exactly_one_cell_blocks_per_ply_and_no_game_exceeds_23(self):
        rng = random.Random(11)
        for _ in range(200):
            s = isolation.initial_state()
            plies = 0
            while not isolation.is_terminal(s):
                expected_blocked = plies
                self.assertEqual(bin(s.blocked).count("1"), expected_blocked)
                s = isolation.apply_move(s, rng.choice(isolation.legal_moves(s)))
                plies += 1
            self.assertLessEqual(plies, 23)

    def test_no_game_ever_draws(self):
        rng = random.Random(13)
        for _ in range(200):
            s = isolation.initial_state()
            while not isolation.is_terminal(s):
                s = isolation.apply_move(s, rng.choice(isolation.legal_moves(s)))
            self.assertEqual(isolation.result(s), LOSS)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_isolation -v`
Expected: FAIL with `ImportError: cannot import name 'isolation'`

- [ ] **Step 3: Write minimal implementation**

Create `games/isolation.py`:

```python
"""Isolation 5x5 - queen-slide movement with uniform auto-blocking.

Rules are authoritative in docs/games/isolation.md. This is a declared variant
of the 1972 published game, not the published game itself.
"""
from dataclasses import dataclass
from typing import List, Tuple

from games.base import LOSS

NAME = "isolation"
SIZE = 5
CELLS = SIZE * SIZE

_DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1),
               (0, 1), (1, -1), (1, 0), (1, 1))

# _RAYS[cell] is a tuple of rays; each ray is a tuple of cell indices in
# increasing distance from `cell`. Precomputed once at import.
def _build_rays():
    rays = []
    for index in range(CELLS):
        r, c = divmod(index, SIZE)
        per_cell = []
        for dr, dc in _DIRECTIONS:
            ray = []
            rr, cc = r + dr, c + dc
            while 0 <= rr < SIZE and 0 <= cc < SIZE:
                ray.append(rr * SIZE + cc)
                rr += dr
                cc += dc
            if ray:
                per_cell.append(tuple(ray))
        rays.append(tuple(per_cell))
    return tuple(rays)


_RAYS = _build_rays()

_START = (0 * SIZE + 2, 4 * SIZE + 2)


@dataclass(frozen=True)
class IsolationState:
    blocked: int                 # 25-bit mask; bit (r*5+c) set means blocked
    pawns: Tuple[int, int]       # cell index per player
    side_to_move: int


def initial_state():
    # type: () -> IsolationState
    return IsolationState(blocked=0, pawns=_START, side_to_move=0)


def legal_moves(s):
    # type: (IsolationState) -> List[int]
    """Destination cell indices. Rays stop before the edge, a blocked cell, or
    the opponent's pawn - pawns never jump over anything."""
    blocked = s.blocked
    opponent = s.pawns[1 - s.side_to_move]
    moves = []
    for ray in _RAYS[s.pawns[s.side_to_move]]:
        for target in ray:
            if target == opponent or (blocked >> target) & 1:
                break
            moves.append(target)
    return moves


def apply_move(s, m):
    # type: (IsolationState, int) -> IsolationState
    side = s.side_to_move
    vacated = s.pawns[side]
    pawns = (m, s.pawns[1]) if side == 0 else (s.pawns[0], m)
    return IsolationState(blocked=s.blocked | (1 << vacated),
                          pawns=pawns,
                          side_to_move=1 - side)


def is_terminal(s):
    # type: (IsolationState) -> bool
    return not legal_moves(s)


def result(s):
    # type: (IsolationState) -> float
    """The side to move has no move and has therefore lost. Draws are
    impossible - see docs/games/isolation.md section 5.2."""
    return LOSS


def end_reason(s):
    # type: (IsolationState) -> str
    return "no_moves"


def move_to_str(m):
    # type: (int) -> str
    r, c = divmod(m, SIZE)
    return "%s%d" % (chr(ord("a") + c), SIZE - r)


def str_to_move(text):
    # type: (str) -> int
    column = ord(text[0]) - ord("a")
    row = SIZE - int(text[1:])
    return row * SIZE + column
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_isolation -v`
Expected: PASS, 13 tests

- [ ] **Step 5: Commit**

```bash
git add games/isolation.py tests/test_isolation.py
git commit -m "Implement Isolation 5x5

Queen-slide movement with rays precomputed at import, and uniform auto-
blocking with no exempt cells, which keeps move generation a single code path
and makes the 23-ply bound provable.

Tests assert the derived properties from the gamebook directly: eleven moves
at ply one, sixteen from the centre when the opponent stands off its rays,
fifteen when the opponent truncates one, exactly one cell blocking per ply, no
game exceeding 23 plies, and no draws. The eleven is deliberate: the southward
ray from the starting cell yields three moves, not four, because it stops
before the opposing pawn."
```

---

### Task 4: Random and Heuristic agents

**Files:**
- Create: `agents/random_agent.py`, `agents/heuristic_agent.py`, `evaluation/__init__.py`, `evaluation/isolation_eval.py`
- Test: `tests/test_baseline_agents.py`

**Interfaces:**
- Consumes: `agents.base.SearchContext`, `games.isolation`
- Produces:
  - `agents.random_agent.choose(game, state, ctx, rng) -> move`
  - `agents.heuristic_agent.make(evaluate) -> agent_callable` where `evaluate(game, state) -> float` in `(-1, 1)`
  - `evaluation.isolation_eval.evaluate(game, state) -> float`

- [ ] **Step 1: Write the failing test**

Create `tests/test_baseline_agents.py`:

```python
import random
import unittest

from agents import heuristic_agent, random_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class RandomAgentTest(unittest.TestCase):
    def test_returns_a_legal_move_and_reports_completion(self):
        s = isolation.initial_state()
        ctx = SearchContext(1.0, 100, clock=_Clock())
        move = random_agent.choose(isolation, s, ctx, random.Random(3))
        self.assertIn(move, isolation.legal_moves(s))
        self.assertTrue(ctx.finished)

    def test_is_deterministic_for_a_given_seed(self):
        s = isolation.initial_state()
        a = random_agent.choose(isolation, s, SearchContext(1.0, 100, clock=_Clock()),
                                random.Random(5))
        b = random_agent.choose(isolation, s, SearchContext(1.0, 100, clock=_Clock()),
                                random.Random(5))
        self.assertEqual(a, b)

    def test_is_tagged_normal_through_the_wrapper(self):
        s = isolation.initial_state()
        d = decide(random_agent.choose, isolation, s, 1.0, 100,
                   random.Random(0), clock=_Clock())
        self.assertEqual(d.tag, MoveTag.NORMAL)


class IsolationEvaluatorTest(unittest.TestCase):
    def test_returns_a_value_strictly_inside_the_reward_range(self):
        s = isolation.initial_state()
        v = isolation_eval.evaluate(isolation, s)
        self.assertGreater(v, -1.0)
        self.assertLess(v, 1.0)

    def test_prefers_greater_mobility_for_the_side_to_move(self):
        # Side 0 in the open centre; side 1 boxed into a corner.
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = isolation.IsolationState(blocked=blocked, pawns=(12, 0),
                                     side_to_move=0)
        self.assertGreater(isolation_eval.evaluate(isolation, s), 0.0)


class HeuristicAgentTest(unittest.TestCase):
    def test_picks_the_highest_scoring_move(self):
        target = isolation.legal_moves(isolation.initial_state())[2]

        def evaluate(game, state):
            # `state` here is the CHILD, whose side_to_move is the opponent, so
            # evaluate() scores it from the opponent's perspective and the agent
            # negates it. The move we want chosen must therefore look BAD here.
            return -0.9 if state.pawns[0] == target else 0.9

        agent = heuristic_agent.make(evaluate)
        s = isolation.initial_state()
        ctx = SearchContext(1.0, 100, clock=_Clock())
        self.assertEqual(agent(isolation, s, ctx, random.Random(1)), target)

    def test_reports_completion_when_every_move_was_evaluated(self):
        agent = heuristic_agent.make(lambda game, state: 0.0)
        ctx = SearchContext(1.0, 100, clock=_Clock())
        agent(isolation, isolation.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.finished)

    def test_returns_a_valid_move_when_cut_off_mid_evaluation(self):
        s = isolation.initial_state()

        class Stopped(SearchContext):
            def should_stop(self):
                return True

        ctx = Stopped(1.0, 100, clock=_Clock())
        agent = heuristic_agent.make(lambda game, state: 0.0)
        move = agent(isolation, s, ctx, random.Random(1))
        self.assertIn(move, isolation.legal_moves(s))
        self.assertFalse(ctx.finished)

    def test_breaks_ties_randomly_not_by_move_order(self):
        # All moves score equally; over many seeds more than one must be chosen,
        # otherwise the agent is silently inheriting legal_moves ordering.
        agent = heuristic_agent.make(lambda game, state: 0.5)
        s = isolation.initial_state()
        chosen = set()
        for seed in range(40):
            ctx = SearchContext(1.0, 100, clock=_Clock())
            chosen.add(agent(isolation, s, ctx, random.Random(seed)))
        self.assertGreater(len(chosen), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_baseline_agents -v`
Expected: FAIL with `ImportError: cannot import name 'random_agent'`

- [ ] **Step 3: Write minimal implementation**

Create `agents/random_agent.py`:

```python
"""Uniform random baseline. The sanity-check floor for every tournament."""


def choose(game, state, ctx, rng):
    moves = game.legal_moves(state)
    ctx.note_node()
    ctx.completed()
    return rng.choice(moves)
```

Create `agents/heuristic_agent.py`:

```python
"""One-ply heuristic agent.

Evaluation is incremental - a running best - so a mid-evaluation cutoff still
returns a valid move rather than failing. Uses the same evaluator Alpha-Beta
applies at its horizon, so the difference between the two agents isolates
search depth rather than evaluation quality.
"""


def make(evaluate):
    """Build an agent from evaluate(game, state) -> float in (-1, 1)."""

    def agent(game, state, ctx, rng):
        moves = game.legal_moves(state)
        best_score = None
        best_moves = []
        evaluated = 0

        for move in moves:
            if ctx.should_stop() and best_moves:
                break
            child = game.apply_move(state, move)
            ctx.note_node()
            # The child's value is from the opponent's perspective; negate it.
            score = -evaluate(game, child)
            evaluated += 1
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        if not best_moves:
            return rng.choice(moves)

        if evaluated == len(moves):
            ctx.completed()

        # Tie-break randomly: taking the first would silently inherit the move
        # ordering that legal_moves provides for Alpha-Beta's benefit.
        return rng.choice(best_moves)

    return agent
```

Create `evaluation/__init__.py` as an empty file, then `evaluation/isolation_eval.py`:

```python
"""Isolation evaluation: mobility difference.

Queen-slide mobility varies sharply between positions, which makes this a
well-matched heuristic for the variant - see docs/games/isolation.md section 7.
"""
from games.isolation import IsolationState, legal_moves

_MAX_MOBILITY = 16.0   # theoretical maximum, gamebook section 5.3


def evaluate(game, state):
    # type: (object, IsolationState) -> float
    """Own mobility minus the opponent's, from the perspective of the side to
    move, squashed strictly inside (-1, 1)."""
    mine = len(legal_moves(state))
    theirs = len(legal_moves(
        IsolationState(blocked=state.blocked,
                       pawns=state.pawns,
                       side_to_move=1 - state.side_to_move)))
    difference = mine - theirs
    return difference / (2.0 * _MAX_MOBILITY)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_baseline_agents -v`
Expected: PASS, 9 tests

- [ ] **Step 5: Commit**

```bash
git add agents/random_agent.py agents/heuristic_agent.py evaluation/ tests/test_baseline_agents.py
git commit -m "Add random and heuristic baseline agents with the Isolation evaluator

Heuristic evaluation is incremental, so a cutoff mid-evaluation still yields a
valid move, and ties are broken by seeded random choice rather than by taking
the first candidate. Taking the first would make the agent's play an artefact
of legal_moves ordering, which exists to help Alpha-Beta prune, so the
heuristic agent would silently inherit Alpha-Beta's move ordering."
```

---

### Task 5: Game runner and CSV logging

Closes the vertical slice: a full game plays and is logged.

**Files:**
- Create: `experiments/__init__.py`, `experiments/runner.py`, `experiments/logger.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `agents.base.decide`, `agents.base.Decision`, `games.isolation`, `agents.random_agent`
- Produces:
  - `experiments.runner.MoveRecord` - frozen dataclass `(ply, agent, side, tag, elapsed_s, nodes, simulations, depth, move, legal_move_count)`
  - `experiments.runner.GameRecord` - frozen dataclass `(game_id, game, config, time_budget_s, max_nodes, agent_first, agent_second, winner, plies, end_reason, seed, workers, moves)`
  - `experiments.runner.game_seed(game_name, agent_a, agent_b, config_name, trial) -> int`
  - `experiments.runner.play_game(game, agents, agent_names, config, seed, ply_cap=None) -> GameRecord` where `agents` is a 2-tuple of callables and `config` is a dict with keys `name`, `time_budget_s`, `max_nodes`
  - `experiments.logger.GameLogger(games_path, moves_path)` with `write(record)`, `completed_ids()`, `close()`

- [ ] **Step 1: Write the failing test**

Create `tests/test_runner.py`:

```python
import csv
import os
import random
import shutil
import tempfile
import unittest

from agents import random_agent
from experiments import runner
from experiments.logger import GameLogger
from games import isolation

CONFIG = {"name": "test", "time_budget_s": 1.0, "max_nodes": 1000}


class SeedTest(unittest.TestCase):
    def test_seed_is_deterministic(self):
        a = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        b = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertEqual(a, b)

    def test_seed_varies_with_every_input(self):
        base = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertNotEqual(base, runner.game_seed("ataxx", "random", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "mcts", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "hard", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "main", 4))


class PlayGameTest(unittest.TestCase):
    def _play(self, seed=1):
        return runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed,
        )

    def test_produces_a_decisive_result_within_the_ply_bound(self):
        record = self._play()
        self.assertIn(record.winner, ("first", "second"))
        self.assertLessEqual(record.plies, 23)
        self.assertEqual(record.end_reason, "no_moves")

    def test_records_one_move_row_per_ply(self):
        record = self._play()
        self.assertEqual(len(record.moves), record.plies)
        self.assertEqual([m.ply for m in record.moves], list(range(record.plies)))

    def test_agents_alternate_sides(self):
        record = self._play()
        self.assertEqual([m.side for m in record.moves[:4]], [0, 1, 0, 1])

    def test_records_legal_move_count_for_branching_factor_measurement(self):
        record = self._play()
        first = record.moves[0]
        self.assertEqual(first.legal_move_count, 11)

    def test_is_reproducible_from_its_seed(self):
        a = self._play(seed=42)
        b = self._play(seed=42)
        self.assertEqual([m.move for m in a.moves], [m.move for m in b.moves])
        self.assertEqual(a.winner, b.winner)

    def test_different_seeds_give_different_games(self):
        moves = set()
        for seed in range(8):
            moves.add(tuple(m.move for m in self._play(seed=seed).moves))
        self.assertGreater(len(moves), 1)

    def test_ply_cap_ends_the_game_and_is_reported(self):
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("a", "b"),
            CONFIG,
            seed=1,
            ply_cap=4,
        )
        self.assertEqual(record.plies, 4)
        self.assertEqual(record.end_reason, "ply_cap")


class LoggerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.games_path = os.path.join(self.dir, "games.csv")
        self.moves_path = os.path.join(self.dir, "moves.csv")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def _write_one(self):
        logger = GameLogger(self.games_path, self.moves_path)
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed=1,
        )
        logger.write(record)
        logger.close()
        return record

    def test_writes_one_game_row_and_one_row_per_move(self):
        record = self._write_one()
        with open(self.games_path) as handle:
            games = list(csv.DictReader(handle))
        with open(self.moves_path) as handle:
            moves = list(csv.DictReader(handle))
        self.assertEqual(len(games), 1)
        self.assertEqual(len(moves), record.plies)
        self.assertEqual(games[0]["game"], "isolation")
        self.assertEqual(int(games[0]["plies"]), record.plies)

    def test_node_and_simulation_counts_are_separate_columns(self):
        self._write_one()
        with open(self.moves_path) as handle:
            header = next(csv.reader(handle))
        self.assertIn("nodes", header)
        self.assertIn("simulations", header)

    def test_completed_ids_supports_resume(self):
        record = self._write_one()
        logger = GameLogger(self.games_path, self.moves_path)
        self.assertIn(record.game_id, logger.completed_ids())
        logger.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_runner -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments'`

- [ ] **Step 3: Write minimal implementation**

Create `experiments/__init__.py` as an empty file. Then `experiments/runner.py`:

```python
"""Plays one game between two agents and records everything about it."""
import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from agents.base import decide
from games.base import DRAW, LOSS, WIN


@dataclass(frozen=True)
class MoveRecord:
    ply: int
    agent: str
    side: int
    tag: str
    elapsed_s: float
    nodes: int
    simulations: Optional[int]
    depth: Optional[int]
    move: str
    legal_move_count: int


@dataclass(frozen=True)
class GameRecord:
    game_id: str
    game: str
    config: str
    time_budget_s: float
    max_nodes: int
    agent_first: str
    agent_second: str
    winner: str            # "first" | "second" | "draw"
    plies: int
    end_reason: str
    seed: int
    workers: int
    moves: List[MoveRecord] = field(default_factory=list)


def game_seed(game_name, agent_a, agent_b, config_name, trial):
    # type: (str, str, str, str, int) -> int
    """Deterministic per-game seed, so any single game can be replayed for
    debugging without re-running the tournament. Python's hash() is salted per
    process, so use a stable digest instead."""
    key = "|".join((game_name, agent_a, agent_b, config_name, str(trial)))
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _game_id(game_name, agent_a, agent_b, config_name, trial):
    # type: (str, str, str, str, int) -> str
    return "%s.%s.%s-%s.t%d" % (game_name, config_name, agent_a, agent_b, trial)


def play_game(game, agents, agent_names, config, seed, ply_cap=None,
              trial=0, workers=1, clock=None):
    # type: (Any, Tuple[Any, Any], Tuple[str, str], dict, int, Optional[int], int, int, Any) -> GameRecord
    """Play one complete game. Fully determined by `seed`.

    `ply_cap` is a runner-level guard, not a game rule. Ataxx needs one because
    jump moves leave the occupied-cell count unchanged, so the published rules
    do not guarantee termination - see docs/games/ataxx.md section 4.6. It lives
    here rather than in the state because putting a total ply count into the
    state would put it into the transposition-table key and destroy the table.
    """
    rng = random.Random(seed)
    state = game.initial_state()
    moves = []                      # type: List[MoveRecord]
    ply = 0
    end_reason = None

    kwargs = {} if clock is None else {"clock": clock}

    while True:
        if game.is_terminal(state):
            end_reason = game.end_reason(state)
            break
        if ply_cap is not None and ply >= ply_cap:
            end_reason = "ply_cap"
            break

        side = state.side_to_move
        legal_count = len(game.legal_moves(state))
        decision = decide(agents[side], game, state,
                          config["time_budget_s"], config["max_nodes"], rng,
                          **kwargs)
        moves.append(MoveRecord(
            ply=ply,
            agent=agent_names[side],
            side=side,
            tag=decision.tag.value,
            elapsed_s=decision.elapsed_s,
            nodes=decision.nodes,
            simulations=decision.simulations,
            depth=decision.depth,
            move=game.move_to_str(decision.move),
            legal_move_count=legal_count,
        ))
        state = game.apply_move(state, decision.move)
        ply += 1

    winner = _winner(game, state, end_reason)

    return GameRecord(
        game_id=_game_id(game.NAME, agent_names[0], agent_names[1],
                         config["name"], trial),
        game=game.NAME,
        config=config["name"],
        time_budget_s=config["time_budget_s"],
        max_nodes=config["max_nodes"],
        agent_first=agent_names[0],
        agent_second=agent_names[1],
        winner=winner,
        plies=ply,
        end_reason=end_reason,
        seed=seed,
        workers=workers,
        moves=moves,
    )


def _winner(game, state, end_reason):
    # type: (Any, Any, str) -> str
    if end_reason == "ply_cap":
        return "draw"
    outcome = game.result(state)      # from the perspective of side_to_move
    if outcome == DRAW:
        return "draw"
    mover_won = outcome == WIN
    mover_is_first = state.side_to_move == 0
    return "first" if mover_won == mover_is_first else "second"
```

Then `experiments/logger.py`:

```python
"""Streaming CSV logging.

Rows are flushed per game, so an interrupted overnight run keeps everything it
had already produced.
"""
import csv
import os
from typing import Set

GAME_COLUMNS = [
    "game_id", "game", "config", "time_budget_s", "max_nodes",
    "agent_first", "agent_second", "winner", "plies", "end_reason",
    "seed", "workers",
]

# nodes and simulations are deliberately separate: an Alpha-Beta node is a
# static evaluation at a horizon and an MCTS simulation is a rollout, so they
# are not the same unit of work and must never share an axis.
MOVE_COLUMNS = [
    "game_id", "ply", "agent", "side", "tag", "elapsed_s",
    "nodes", "simulations", "depth", "move", "legal_move_count",
]


class GameLogger:
    def __init__(self, games_path, moves_path):
        self._games_path = games_path
        for path in (games_path, moves_path):
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

        games_is_new = not os.path.exists(games_path) or os.path.getsize(games_path) == 0
        moves_is_new = not os.path.exists(moves_path) or os.path.getsize(moves_path) == 0

        self._games_file = open(games_path, "a", newline="")
        self._moves_file = open(moves_path, "a", newline="")
        self._games = csv.DictWriter(self._games_file, fieldnames=GAME_COLUMNS)
        self._moves = csv.DictWriter(self._moves_file, fieldnames=MOVE_COLUMNS)
        if games_is_new:
            self._games.writeheader()
        if moves_is_new:
            self._moves.writeheader()

    def write(self, record):
        self._games.writerow({
            "game_id": record.game_id,
            "game": record.game,
            "config": record.config,
            "time_budget_s": record.time_budget_s,
            "max_nodes": record.max_nodes,
            "agent_first": record.agent_first,
            "agent_second": record.agent_second,
            "winner": record.winner,
            "plies": record.plies,
            "end_reason": record.end_reason,
            "seed": record.seed,
            "workers": record.workers,
        })
        for move in record.moves:
            self._moves.writerow({
                "game_id": record.game_id,
                "ply": move.ply,
                "agent": move.agent,
                "side": move.side,
                "tag": move.tag,
                "elapsed_s": "%.6f" % move.elapsed_s,
                "nodes": move.nodes,
                "simulations": "" if move.simulations is None else move.simulations,
                "depth": "" if move.depth is None else move.depth,
                "move": move.move,
                "legal_move_count": move.legal_move_count,
            })
        self._games_file.flush()
        self._moves_file.flush()

    def completed_ids(self):
        # type: () -> Set[str]
        """Game ids already present, so an interrupted run can resume."""
        if not os.path.exists(self._games_path):
            return set()
        with open(self._games_path, newline="") as handle:
            return {row["game_id"] for row in csv.DictReader(handle)}

    def close(self):
        self._games_file.close()
        self._moves_file.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_runner -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Run the whole suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS, 54 tests across five modules (8 + 12 + 13 + 9 + 12)

- [ ] **Step 6: Commit**

```bash
git add experiments/ tests/test_runner.py
git commit -m "Add game runner and streaming CSV logging

Seeds come from a stable digest rather than hash(), which is salted per
process and would make games unreproducible across runs. Every game is
replayable from its seed alone.

The ply cap is a runner-level guard rather than a game rule: putting a total
ply count into the state would put it into the transposition-table key and
make the same position at different ply counts distinct entries, destroying
the table in the game that needs it most.

Node and simulation counts are separate CSV columns because an alpha-beta node
and an MCTS rollout are not the same unit of work, and legal_move_count is
recorded per move so the branching-factor measurement comes free."
```

---

## What Plan 1 delivers

At the end of Task 5, `python -m unittest discover -s tests` passes and a complete Isolation game plays between two agents with every move tagged and both CSVs written. The interfaces that Plans 2 and 3 depend on - the game contract, `SearchContext`, `decide`, `GameRecord`, the CSV schema - have all been exercised by real code rather than only specified.

**Plan 2** adds Ultimate Tic-Tac-Toe, Ataxx, Alpha-Beta, MCTS and the remaining evaluators against these now-proven interfaces. **Plan 3** adds the Ataxx branching-factor validation gate, the three-phase calibration pilot, the tournament, and the analysis.
