# Plan 2: Remaining Games and Search Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All three games implemented and validated, and both search agents playing under time and memory budgets — everything the tournament needs except the tournament itself.

**Architecture:** Continues Plan 1's interfaces unchanged: games are stateless modules of pure functions over immutable integer-backed frozen dataclasses; agents receive their budget through a `SearchContext` they poll. Games come first so that a move-generator bug is caught by the conformance harness and the Ataxx branching-curve gate *before* any agent result depends on it.

**Tech Stack:** Python 3.8.10, standard library only. Tests use `unittest`.

## Global Constraints

- **Python 3.8.10.** No `match`, no `X | Y` unions, no `dict |`. Use `typing.List`, `typing.Tuple`, `typing.Optional`.
- **Standard library only.** No third-party runtime or test dependencies.
- **Reward scale:** terminals return exactly `+1` / `0` / `-1` **from the perspective of `side_to_move`**. Evaluations return values **strictly inside** `(-1, +1)`, so no heuristic estimate can outrank a real win.
- **`legal_moves` returns `[]` if and only if the state is terminal.** Ataxx is the case that proves the rule: a player with no move **passes**, represented as an explicit move in the list — never an empty list.
- **`NAME` is part of the game contract** and each game's tests must assert its own value.
- **States are immutable frozen dataclasses over `int` and `tuple`** — hashable for the transposition table, safe to hold in MCTS tree nodes.
- **Agents that carry structure across moves are constructed once per game.** Never reuse one across a matchup; a table still near its cap from a finished game would tag an early move of the next game `memory-limited` for the wrong reason.
- Rules are authoritative in [`docs/games/`](../games/); never restate a rule in code, link to the gamebook section.
- Run tests with `python3 -m unittest discover -s tests`.
- Commit messages describe the change only — **no mention of Claude, AI, or any agent; no `Co-Authored-By` trailer.**

## Interfaces from Plan 1 (already built, do not modify)

```python
# games/base.py
WIN, DRAW, LOSS = 1.0, 0.0, -1.0
class ConformanceError(AssertionError): ...
def check_conformance(game, rng, n_games=200, max_plies=1000, side_of=None) -> None

# agents/base.py
class MoveTag(str, Enum):  NORMAL, TIME_LIMITED, MEMORY_LIMITED, ERROR
@dataclass(frozen=True)
class Decision: move, tag, elapsed_s, nodes, simulations, depth, error
class SearchContext:
    def __init__(self, time_budget_s, max_nodes, check_every=512, clock=time.monotonic)
    def should_stop(self) -> bool          # polls clock every check_every calls
    def set_check_every(self, n) -> None   # shallow agents request finer granularity
    def note_node(self) -> None
    def note_simulation(self) -> None
    def hit_memory_cap(self) -> None
    def completed(self) -> None
    def elapsed(self) -> float
    depth_reached: Optional[int]           # iterative-deepening hook
def decide(agent, game, state, time_budget_s, max_nodes, rng,
           check_every=512, clock=time.monotonic) -> Decision

# an agent is any callable
agent(game, state, ctx, rng) -> move
```

---

### Task 1: Ultimate Tic-Tac-Toe

Rules are authoritative in [`docs/games/ultimate-tic-tac-toe.md`](../games/ultimate-tic-tac-toe.md). The load-bearing ones: a local board that is won **or drawn** is **closed** to further play; being sent to a closed board frees you to play in any undecided board; a drawn local board counts for **neither** player; and the game is drawn **as soon as neither player can still complete a global line**, without playing the remaining boards out.

**Files:**
- Create: `games/uttt.py`
- Test: `tests/test_uttt.py`

**Interfaces:**
- Consumes: `games.base.WIN/DRAW/LOSS`, `games.base.check_conformance`
- Produces: `games.uttt` with `NAME = "uttt"`, `LINES` (the 8 winning index triples), and
  `UtttState(marks: Tuple[int, int], status: Tuple[int, ...], send: int, side_to_move: int, winnable: Tuple[int, int], global_winner: int)`, plus the eight contract functions. Moves are ints `0..80`, where `move = board * 9 + cell`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_uttt.py`:

```python
import random
import unittest

from games import uttt
from games.base import DRAW, LOSS, WIN, check_conformance


def mv(board, cell):
    return board * 9 + cell


class UtttRulesTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(uttt.NAME, "uttt")

    def test_initial_state_allows_all_81_cells(self):
        s = uttt.initial_state()
        self.assertEqual(s.send, -1)
        self.assertEqual(s.side_to_move, 0)
        self.assertEqual(len(uttt.legal_moves(s)), 81)

    def test_send_rule_restricts_to_the_cell_index_just_played(self):
        s = uttt.initial_state()
        s = uttt.apply_move(s, mv(4, 7))       # cell 7 sends opponent to board 7
        self.assertEqual(s.send, 7)
        moves = uttt.legal_moves(s)
        self.assertEqual(len(moves), 9)
        self.assertTrue(all(m // 9 == 7 for m in moves))

    def test_a_won_local_board_is_closed_and_frees_the_opponent(self):
        # P0 takes cells 0,1,2 of board 0. Interleave P1 moves so the send
        # constraint keeps landing P0 back on board 0.
        s = uttt.initial_state()
        for m in (mv(0, 0), mv(0, 3), mv(0, 1), mv(0, 4), mv(0, 2)):
            s = uttt.apply_move(s, m)
        self.assertEqual(s.status[0], 1)               # board 0 won by player 0
        # P1 was sent to board 2 (cell index of the last move). Play there,
        # choosing cell 0 so the reply would be sent to the closed board 0.
        s = uttt.apply_move(s, mv(2, 0))
        self.assertEqual(s.send, 0)
        moves = uttt.legal_moves(s)
        self.assertTrue(all(m // 9 != 0 for m in moves),
                        "closed board must offer no moves")
        self.assertGreater(len(moves), 9,
                           "being sent to a closed board must free the mover")

    def test_a_full_local_board_with_no_winner_is_drawn_and_counts_for_neither(self):
        s = uttt.initial_state()
        # Fill board 0 in an order that produces no three-in-a-row:
        # P0 -> 0,1,5,6,7 ; P1 -> 2,3,4,8  (checked by hand: no line for either)
        order = [0, 2, 1, 3, 5, 4, 6, 8, 7]
        state = s
        for i, cell in enumerate(order):
            # force every move into board 0 by rebuilding the send constraint
            state = uttt.UtttState(marks=state.marks, status=state.status,
                                   send=0, side_to_move=state.side_to_move,
                                   winnable=state.winnable,
                                   global_winner=state.global_winner)
            state = uttt.apply_move(state, mv(0, cell))
        self.assertEqual(state.status[0], 3, "full, no winner -> drawn")
        # A drawn board forms part of no global line for either player.
        for player in (0, 1):
            for line_index, line in enumerate(uttt.LINES):
                if 0 in line:
                    self.assertFalse((state.winnable[player] >> line_index) & 1)

    def test_winning_three_boards_in_a_row_wins_the_game(self):
        # Hand-built terminal position: P0 owns boards 0, 1, 2.
        s = uttt.UtttState(marks=(0, 0), status=(1, 1, 1, 0, 0, 0, 0, 0, 0),
                           send=-1, side_to_move=1,
                           winnable=(0, 0), global_winner=1)
        self.assertTrue(uttt.is_terminal(s))
        self.assertEqual(uttt.result(s), LOSS)      # side to move (P1) lost
        self.assertEqual(uttt.end_reason(s), "line")

    def test_result_is_a_win_from_the_winner_s_own_perspective(self):
        s = uttt.UtttState(marks=(0, 0), status=(1, 1, 1, 0, 0, 0, 0, 0, 0),
                           send=-1, side_to_move=0,
                           winnable=(0, 0), global_winner=1)
        self.assertEqual(uttt.result(s), WIN)

    def test_early_draw_when_no_global_line_remains_winnable(self):
        # Every board decided such that no line is winnable by either player,
        # but empty cells would still exist under a naive rule.
        status = (1, 2, 1,
                  2, 1, 2,
                  1, 2, 3)
        s = uttt.initial_state()
        s = uttt.UtttState(marks=s.marks, status=status, send=-1,
                           side_to_move=0,
                           winnable=uttt.winnable_masks(status),
                           global_winner=uttt.global_winner_of(status))
        self.assertEqual(s.global_winner, 0, "no line is owned outright")
        self.assertEqual(s.winnable, (0, 0))
        self.assertTrue(uttt.is_terminal(s))
        self.assertEqual(uttt.result(s), DRAW)
        self.assertEqual(uttt.end_reason(s), "early_draw")

    def test_winnable_masks_agree_with_recomputation_on_every_transition(self):
        # A cached derived field whose incremental update drifts would corrupt
        # terminal detection silently, so check it against a from-scratch value.
        rng = random.Random(5)
        for _ in range(60):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                self.assertEqual(s.winnable, uttt.winnable_masks(s.status))
                self.assertEqual(s.global_winner,
                                 uttt.global_winner_of(s.status))
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))

    def test_move_string_round_trips(self):
        for m in range(81):
            self.assertEqual(uttt.str_to_move(uttt.move_to_str(m)), m)


class UtttInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(uttt, random.Random(11), n_games=200, max_plies=100)

    def test_no_game_exceeds_81_plies_and_cells_never_vacate(self):
        rng = random.Random(13)
        for _ in range(100):
            s = uttt.initial_state()
            plies = 0
            occupied = 0
            while not uttt.is_terminal(s):
                total = bin(s.marks[0] | s.marks[1]).count("1")
                self.assertEqual(total, occupied)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))
                occupied += 1
                plies += 1
            self.assertLessEqual(plies, 81)

    def test_players_never_occupy_the_same_cell(self):
        rng = random.Random(17)
        for _ in range(100):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                self.assertEqual(s.marks[0] & s.marks[1], 0)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))

    def test_no_move_is_ever_offered_in_a_decided_board(self):
        rng = random.Random(19)
        for _ in range(100):
            s = uttt.initial_state()
            while not uttt.is_terminal(s):
                for m in uttt.legal_moves(s):
                    self.assertEqual(s.status[m // 9], 0)
                s = uttt.apply_move(s, rng.choice(uttt.legal_moves(s)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_uttt -v`
Expected: FAIL with `ImportError: cannot import name 'uttt'`

- [ ] **Step 3: Write minimal implementation**

Create `games/uttt.py`:

```python
"""Ultimate Tic-Tac-Toe - nine 3x3 local boards inside a 3x3 global board.

Rules are authoritative in docs/games/ultimate-tic-tac-toe.md. The load-bearing
ones: a local board that is won or drawn is closed to further play (4.3), being
sent to a closed board frees the mover (4.2), a drawn local board counts for
neither player (4.5), and the game is drawn as soon as no global line remains
winnable by either player (4.8).
"""
from dataclasses import dataclass
from typing import List, Tuple

from games.base import DRAW, LOSS, WIN

NAME = "uttt"

# The eight winning triples, used identically for local and global boards -
# they are structurally the same 3x3 grid.
LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6))

UNDECIDED, DRAWN = 0, 3

# _LINE_MASKS[b][i] is the 81-bit mask of line i inside local board b.
_LINE_MASKS = tuple(
    tuple(sum(1 << (b * 9 + c) for c in line) for line in LINES)
    for b in range(9)
)
_BOARD_MASKS = tuple(sum(1 << (b * 9 + c) for c in range(9)) for b in range(9))


@dataclass(frozen=True)
class UtttState:
    marks: Tuple[int, int]        # 81-bit mask of cells held, per player
    status: Tuple[int, ...]       # 9 entries: 0 undecided, 1 P1, 2 P2, 3 drawn
    send: int                     # 0..8 target board, or -1 for free choice
    side_to_move: int
    winnable: Tuple[int, int]     # per player, 8-bit mask of winnable global lines
    global_winner: int            # 0 none, 1 P1, 2 P2


def winnable_masks(status):
    # type: (Tuple[int, ...]) -> Tuple[int, int]
    """Per player, which global lines could still be completed.

    A line stays winnable for player p while none of its three boards is held by
    the opponent or drawn. Exposed (not private) so tests can check the cached
    field against a from-scratch recomputation - a drifting incremental update
    would corrupt terminal detection with no crash.
    """
    masks = [0, 0]
    for player in (0, 1):
        mine, theirs = player + 1, 2 - player
        for index, line in enumerate(LINES):
            if all(status[b] in (UNDECIDED, mine) for b in line):
                masks[player] |= 1 << index
    return (masks[0], masks[1])


def global_winner_of(status):
    # type: (Tuple[int, ...]) -> int
    for line in LINES:
        first = status[line[0]]
        if first in (1, 2) and all(status[b] == first for b in line):
            return first
    return 0


def initial_state():
    # type: () -> UtttState
    status = (UNDECIDED,) * 9
    return UtttState(marks=(0, 0), status=status, send=-1, side_to_move=0,
                     winnable=winnable_masks(status), global_winner=0)


def legal_moves(s):
    # type: (UtttState) -> List[int]
    if s.global_winner or s.winnable == (0, 0):
        return []
    occupied = s.marks[0] | s.marks[1]
    if s.send >= 0 and s.status[s.send] == UNDECIDED:
        boards = (s.send,)
    else:
        boards = tuple(b for b in range(9) if s.status[b] == UNDECIDED)
    moves = []
    for b in boards:
        base = b * 9
        for c in range(9):
            if not (occupied >> (base + c)) & 1:
                moves.append(base + c)
    return moves


def apply_move(s, m):
    # type: (UtttState, int) -> UtttState
    side = s.side_to_move
    board, cell = divmod(m, 9)
    mine = s.marks[side] | (1 << m)
    marks = (mine, s.marks[1]) if side == 0 else (s.marks[0], mine)

    status = s.status
    if status[board] == UNDECIDED:
        if any(mine & mask == mask for mask in _LINE_MASKS[board]):
            status = status[:board] + (side + 1,) + status[board + 1:]
        elif (marks[0] | marks[1]) & _BOARD_MASKS[board] == _BOARD_MASKS[board]:
            status = status[:board] + (DRAWN,) + status[board + 1:]

    if status is s.status:
        winnable, winner = s.winnable, s.global_winner
    else:
        winnable, winner = winnable_masks(status), global_winner_of(status)

    return UtttState(marks=marks, status=status, send=cell,
                     side_to_move=1 - side, winnable=winnable,
                     global_winner=winner)


def is_terminal(s):
    # type: (UtttState) -> bool
    return not legal_moves(s)


def result(s):
    # type: (UtttState) -> float
    """From the perspective of the side to move."""
    if s.global_winner == 0:
        return DRAW
    return WIN if s.global_winner == s.side_to_move + 1 else LOSS


def end_reason(s):
    # type: (UtttState) -> str
    if s.global_winner:
        return "line"
    if s.winnable == (0, 0):
        return "early_draw"
    return "no_moves"


def move_to_str(m):
    # type: (int) -> str
    board, cell = divmod(m, 9)
    return "%d.%d" % (board, cell)


def str_to_move(text):
    # type: (str) -> int
    board, cell = text.split(".")
    return int(board) * 9 + int(cell)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_uttt -v`
Expected: PASS, 14 tests

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: PASS, 80 tests

- [ ] **Step 6: Report — do not commit**

Report per the dispatch contract. The orchestrator commits.

---

### Task 2: Ataxx 7x7

Rules are authoritative in [`docs/games/ataxx.md`](../games/ataxx.md). The load-bearing ones: **clone** to Chebyshev distance 1 (source stays) or **jump** to Chebyshev distance exactly 2 (source vacates); **all 16 jump destinations are the whole distance-2 ring**, the 8 straight/diagonal two-steps *and* the 8 knight-shaped cells; clones **deduplicate by destination**; every opponent piece in the destination's 8-neighbourhood converts; a player with no legal move **passes and does not lose**; the game ends when the board fills, a player reaches zero pieces, or **30 plies pass without progress**, where progress is a clone or any conversion, and a pass is not progress.

**Files:**
- Create: `games/ataxx.py`
- Test: `tests/test_ataxx.py`

**Interfaces:**
- Consumes: `games.base.WIN/DRAW/LOSS`, `games.base.check_conformance`
- Produces: `games.ataxx` with `NAME = "ataxx"`, `PASS`, `NO_PROGRESS_LIMIT = 30`, and
  `AtaxxState(boards: Tuple[int, int], side_to_move: int, plies_since_progress: int)`, plus the eight contract functions. A move is `(src, dst)` with `src = -1` for a clone; `PASS = (-2, -2)`. Cell index is `r * 7 + c`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ataxx.py`:

```python
import random
import unittest

from games import ataxx
from games.base import DRAW, LOSS, WIN, check_conformance


def cell(r, c):
    return r * 7 + c


def mask(*cells):
    m = 0
    for c in cells:
        m |= 1 << c
    return m


class AtaxxRulesTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ataxx.NAME, "ataxx")

    def test_initial_position(self):
        s = ataxx.initial_state()
        self.assertEqual(s.boards[0], mask(cell(0, 0), cell(6, 6)))
        self.assertEqual(s.boards[1], mask(cell(0, 6), cell(6, 0)))
        self.assertEqual(s.side_to_move, 0)
        self.assertEqual(s.plies_since_progress, 0)

    def test_jump_ring_has_all_sixteen_cells_including_knight_shapes(self):
        # A lone piece at the centre with an otherwise empty board: 8 clone
        # destinations and 16 jump destinations. Missing the knight-shaped
        # cells - the classic bug - would give 8 jumps instead of 16.
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3)), mask(cell(0, 0))),
                             side_to_move=0, plies_since_progress=0)
        moves = ataxx.legal_moves(s)
        clones = [m for m in moves if m[0] == -1]
        jumps = [m for m in moves if m[0] >= 0]
        self.assertEqual(len(clones), 8)
        self.assertEqual(len(jumps), 16)
        # (1,2)-shaped destination must be present
        self.assertIn((cell(3, 3), cell(1, 2)), jumps)
        # straight two-step must also be present
        self.assertIn((cell(3, 3), cell(1, 3)), jumps)

    def test_clones_are_deduplicated_by_destination(self):
        # Two adjacent friendly pieces both able to clone into the same cell.
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3), cell(3, 5)), mask(cell(0, 0))),
                             side_to_move=0, plies_since_progress=0)
        clone_dests = [m[1] for m in ataxx.legal_moves(s) if m[0] == -1]
        self.assertEqual(len(clone_dests), len(set(clone_dests)))
        self.assertIn(cell(3, 4), clone_dests)

    def test_clone_keeps_the_source_and_adds_a_piece(self):
        s = ataxx.initial_state()
        before = bin(s.boards[0]).count("1")
        s2 = ataxx.apply_move(s, (-1, cell(0, 1)))
        self.assertEqual(bin(s2.boards[0]).count("1"), before + 1)
        self.assertTrue(s2.boards[0] & (1 << cell(0, 0)))

    def test_jump_vacates_the_source_and_keeps_the_count(self):
        s = ataxx.initial_state()
        before = bin(s.boards[0]).count("1")
        s2 = ataxx.apply_move(s, (cell(0, 0), cell(0, 2)))
        self.assertEqual(bin(s2.boards[0]).count("1"), before)
        self.assertFalse(s2.boards[0] & (1 << cell(0, 0)))
        self.assertTrue(s2.boards[0] & (1 << cell(0, 2)))

    def test_conversion_flips_all_eight_neighbours_and_is_not_chained(self):
        # P1 ring around (3,3); a P1 piece two cells further out must NOT flip.
        ring = [cell(2, 2), cell(2, 3), cell(2, 4), cell(3, 2),
                cell(3, 4), cell(4, 2), cell(4, 3), cell(4, 4)]
        outer = cell(1, 1)
        s = ataxx.AtaxxState(boards=(mask(cell(6, 6)), mask(*(ring + [outer]))),
                             side_to_move=0, plies_since_progress=0)
        s2 = ataxx.apply_move(s, (-1, cell(3, 3)))   # arrives adjacent to the ring
        for c in ring:
            self.assertTrue(s2.boards[0] & (1 << c), "ring cell must convert")
        self.assertTrue(s2.boards[1] & (1 << outer),
                        "conversion must not chain to the outer piece")

    def test_occupied_count_never_decreases(self):
        rng = random.Random(3)
        for _ in range(40):
            s = ataxx.initial_state()
            occupied = 4
            while not ataxx.is_terminal(s):
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))
                now = bin(s.boards[0] | s.boards[1]).count("1")
                self.assertGreaterEqual(now, occupied)
                occupied = now

    def test_a_player_with_no_move_passes_rather_than_losing(self):
        # P1 has a single piece walled in by P0 pieces at every distance <= 2.
        p1 = mask(cell(0, 0))
        p0_cells = [cell(r, c) for r in range(3) for c in range(3)
                    if (r, c) != (0, 0)]
        s = ataxx.AtaxxState(boards=(mask(*p0_cells), p1),
                             side_to_move=1, plies_since_progress=0)
        moves = ataxx.legal_moves(s)
        self.assertEqual(moves, [ataxx.PASS])
        self.assertFalse(ataxx.is_terminal(s))
        s2 = ataxx.apply_move(s, ataxx.PASS)
        self.assertEqual(s2.side_to_move, 0)
        self.assertEqual(s2.plies_since_progress, 1,
                         "a pass is not progress")

    def test_zero_pieces_loses(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0)), 0),
                             side_to_move=1, plies_since_progress=0)
        self.assertTrue(ataxx.is_terminal(s))
        self.assertEqual(ataxx.result(s), LOSS)
        self.assertEqual(ataxx.end_reason(s), "eliminated")

    def test_no_progress_limit_ends_the_game(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)),
                                     mask(cell(6, 6), cell(6, 5))),
                             side_to_move=0,
                             plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertTrue(ataxx.is_terminal(s))
        self.assertEqual(ataxx.end_reason(s), "no_progress")
        self.assertEqual(ataxx.result(s), DRAW)   # counts are level

    def test_progress_counter_resets_on_a_clone_and_on_a_conversion(self):
        s = ataxx.AtaxxState(boards=(mask(cell(3, 3)), mask(cell(6, 6))),
                             side_to_move=0, plies_since_progress=7)
        self.assertEqual(ataxx.apply_move(s, (-1, cell(3, 4))).plies_since_progress, 0)
        # A jump with no conversion is not progress.
        s2 = ataxx.apply_move(s, (cell(3, 3), cell(3, 5)))
        self.assertEqual(s2.plies_since_progress, 8)

    def test_scoring_is_by_piece_count(self):
        s = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)), mask(cell(6, 6))),
                             side_to_move=1,
                             plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertEqual(ataxx.result(s), LOSS)    # side to move has fewer
        s2 = ataxx.AtaxxState(boards=(mask(cell(0, 0), cell(0, 1)), mask(cell(6, 6))),
                              side_to_move=0,
                              plies_since_progress=ataxx.NO_PROGRESS_LIMIT)
        self.assertEqual(ataxx.result(s2), WIN)

    def test_move_string_round_trips_for_clones_jumps_and_pass(self):
        self.assertEqual(ataxx.str_to_move(ataxx.move_to_str(ataxx.PASS)),
                         ataxx.PASS)
        for m in ((-1, cell(1, 1)), (cell(0, 0), cell(2, 2)),
                  (cell(6, 6), cell(4, 5))):
            self.assertEqual(ataxx.str_to_move(ataxx.move_to_str(m)), m)


class AtaxxInvariantsTest(unittest.TestCase):
    def test_conforms_to_the_game_contract(self):
        check_conformance(ataxx, random.Random(23), n_games=60, max_plies=400)

    def test_players_never_occupy_the_same_cell(self):
        rng = random.Random(29)
        for _ in range(40):
            s = ataxx.initial_state()
            while not ataxx.is_terminal(s):
                self.assertEqual(s.boards[0] & s.boards[1], 0)
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))

    def test_a_double_pass_never_occurs(self):
        # docs/games/ataxx.md 4.4.1 proves this cannot happen: whenever an empty
        # cell exists at least one player can move. A failure here is a bug.
        rng = random.Random(31)
        for _ in range(40):
            s = ataxx.initial_state()
            previous_was_pass = False
            while not ataxx.is_terminal(s):
                moves = ataxx.legal_moves(s)
                is_pass = moves == [ataxx.PASS]
                self.assertFalse(is_pass and previous_was_pass,
                                 "double pass is provably impossible")
                previous_was_pass = is_pass
                s = ataxx.apply_move(s, rng.choice(moves))

    def test_a_full_board_is_never_a_draw(self):
        # 49 cells is odd, so a full board cannot be level on pieces.
        rng = random.Random(37)
        for _ in range(40):
            s = ataxx.initial_state()
            while not ataxx.is_terminal(s):
                s = ataxx.apply_move(s, rng.choice(ataxx.legal_moves(s)))
            if bin(s.boards[0] | s.boards[1]).count("1") == 49:
                self.assertNotEqual(ataxx.result(s), DRAW)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_ataxx -v`
Expected: FAIL with `ImportError: cannot import name 'ataxx'`

- [ ] **Step 3: Write minimal implementation**

Create `games/ataxx.py`:

```python
"""Ataxx 7x7, no blocked squares.

Rules are authoritative in docs/games/ataxx.md. Naming note: the game is Ataxx,
originally released as Infection in 1988 and as the Leland arcade title Ataxx in
1990.
"""
from dataclasses import dataclass
from typing import List, Tuple

from games.base import DRAW, LOSS, WIN

NAME = "ataxx"
SIZE = 7
CELLS = SIZE * SIZE
NO_PROGRESS_LIMIT = 30

PASS = (-2, -2)
FULL_MASK = (1 << CELLS) - 1


def _build_tables():
    """Clone destinations, jump destinations, and 8-neighbourhood masks.

    Offsets are classified by max(abs(dr), abs(dc)): 1 is a clone, 2 is a jump.
    Enumerating jumps this way yields the entire distance-2 ring - all 16 cells,
    the 8 straight and diagonal two-steps AND the 8 knight-shaped ones. Writing
    the jumps out as eight straight-line offsets instead silently drops half the
    ring, which is the classic implementation bug for this game.
    """
    clones, jumps, neighbours = [], [], []
    for index in range(CELLS):
        r, c = divmod(index, SIZE)
        cl, jp, nb = [], [], 0
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if not (0 <= rr < SIZE and 0 <= cc < SIZE):
                    continue
                target = rr * SIZE + cc
                if max(abs(dr), abs(dc)) == 1:
                    cl.append(target)
                    nb |= 1 << target
                else:
                    jp.append(target)
        clones.append(tuple(cl))
        jumps.append(tuple(jp))
        neighbours.append(nb)
    return tuple(clones), tuple(jumps), tuple(neighbours)


_CLONE_TARGETS, _JUMP_TARGETS, NEIGHBOUR_MASKS = _build_tables()

_START = (
    (1 << 0) | (1 << (CELLS - 1)),                       # P1: (0,0) and (6,6)
    (1 << (SIZE - 1)) | (1 << (CELLS - SIZE)),           # P2: (0,6) and (6,0)
)


@dataclass(frozen=True)
class AtaxxState:
    boards: Tuple[int, int]      # 49-bit mask of cells held, per player
    side_to_move: int
    plies_since_progress: int


def initial_state():
    # type: () -> AtaxxState
    return AtaxxState(boards=_START, side_to_move=0, plies_since_progress=0)


def legal_moves(s):
    # type: (AtaxxState) -> List[Tuple[int, int]]
    """Clones are deduplicated by destination - cloning into a cell gives the
    same position whichever adjacent friendly piece is regarded as the source -
    while jumps are (source, destination) pairs because the vacated cell differs.
    Returns [PASS] when no real move exists; never an empty list unless the
    state is terminal (docs/games/ataxx.md 4.4).
    """
    # Forced terminals are checked FIRST. Without this, a position at the
    # no-progress limit would still have legal moves, is_terminal would report
    # False, and the 30-ply rule would never fire.
    if _forced_terminal(s):
        return []

    mine = s.boards[s.side_to_move]
    empty = FULL_MASK & ~(s.boards[0] | s.boards[1])
    clone_dests = set()
    jumps = []
    for index in range(CELLS):
        if not (mine >> index) & 1:
            continue
        for target in _CLONE_TARGETS[index]:
            if (empty >> target) & 1:
                clone_dests.add(target)
        for target in _JUMP_TARGETS[index]:
            if (empty >> target) & 1:
                jumps.append((index, target))
    moves = [(-1, dest) for dest in sorted(clone_dests)] + jumps
    # Immobility is a pass, not a loss (docs/games/ataxx.md 4.4), so the move
    # list is never empty here - only _forced_terminal above returns [].
    return moves if moves else [PASS]


def _forced_terminal(s):
    # type: (AtaxxState) -> bool
    """True when the position is over regardless of whose turn it is."""
    if s.boards[0] == 0 or s.boards[1] == 0:
        return True
    if (s.boards[0] | s.boards[1]) == FULL_MASK:
        return True
    return s.plies_since_progress >= NO_PROGRESS_LIMIT


def apply_move(s, m):
    # type: (AtaxxState, Tuple[int, int]) -> AtaxxState
    side = s.side_to_move
    if m == PASS:
        return AtaxxState(boards=s.boards, side_to_move=1 - side,
                          plies_since_progress=s.plies_since_progress + 1)

    src, dst = m
    mine = s.boards[side] | (1 << dst)
    if src >= 0:
        mine &= ~(1 << src)
    theirs = s.boards[1 - side]

    converted = theirs & NEIGHBOUR_MASKS[dst]
    theirs &= ~converted
    mine |= converted

    is_progress = src < 0 or converted != 0
    counter = 0 if is_progress else s.plies_since_progress + 1

    boards = (mine, theirs) if side == 0 else (theirs, mine)
    return AtaxxState(boards=boards, side_to_move=1 - side,
                      plies_since_progress=counter)


def is_terminal(s):
    # type: (AtaxxState) -> bool
    return not legal_moves(s)


def result(s):
    # type: (AtaxxState) -> float
    """By piece count, from the perspective of the side to move. A full board can
    never draw - 49 is odd - so draws imply the game ended with cells empty."""
    mine = bin(s.boards[s.side_to_move]).count("1")
    theirs = bin(s.boards[1 - s.side_to_move]).count("1")
    if mine > theirs:
        return WIN
    if mine < theirs:
        return LOSS
    return DRAW


def end_reason(s):
    # type: (AtaxxState) -> str
    if s.boards[0] == 0 or s.boards[1] == 0:
        return "eliminated"
    if (s.boards[0] | s.boards[1]) == FULL_MASK:
        return "board_full"
    if s.plies_since_progress >= NO_PROGRESS_LIMIT:
        return "no_progress"
    return "no_moves"


def _cell_to_str(index):
    # type: (int) -> str
    r, c = divmod(index, SIZE)
    return "%s%d" % (chr(ord("a") + c), SIZE - r)


def _str_to_cell(text):
    # type: (str) -> int
    return (SIZE - int(text[1])) * SIZE + (ord(text[0]) - ord("a"))


def move_to_str(m):
    # type: (Tuple[int, int]) -> str
    if m == PASS:
        return "--"
    src, dst = m
    if src < 0:
        return _cell_to_str(dst)
    return _cell_to_str(src) + _cell_to_str(dst)


def str_to_move(text):
    # type: (str) -> Tuple[int, int]
    if text == "--":
        return PASS
    if len(text) == 2:
        return (-1, _str_to_cell(text))
    return (_str_to_cell(text[:2]), _str_to_cell(text[2:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_ataxx -v`
Expected: PASS, 18 tests

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: PASS, 98 tests

- [ ] **Step 6: Report — do not commit**

---

### Task 3: Ataxx branching-factor validation gate

**This is the highest-value check in the whole project, and it must pass before any agent result on Ataxx is trusted.** Ribeiro and Figueiredo (ENIAC 2018, archived in [`docs/references/`](../references/)) measured 7x7 Ataxx branching factor at roughly **20 at ply 1**, peaking at **92 near ply 25**, with a second peak around **90 near ply 52**. If our random agent reproduces that double-humped shape, the move generator is almost certainly right. **If the curve comes out flat, there is a bug** — most likely the eight knight-shaped jump destinations, which would roughly halve the jump count.

Our variant has **no blocked squares**, so 49 playable cells against the reference's 47; our figures should therefore land slightly *above* theirs. We check the **shape**, not exact equality.

**Files:**
- Create: `experiments/measure_branching.py`
- Test: `tests/test_branching_validation.py`

**Interfaces:**
- Consumes: `games.ataxx`, `games.uttt`, `games.isolation`, `agents.random_agent`
- Produces: `experiments.measure_branching.measure(game, n_games, seed) -> BranchingStats` with fields `mean`, `median`, `max_b`, `mean_by_ply` (a list indexed by ply), `mean_length`, `n_games`; and `main()` printing a per-ply table for all three games.

- [ ] **Step 1: Write the failing test**

Create `tests/test_branching_validation.py`:

```python
import unittest

from experiments.measure_branching import measure
from games import ataxx, isolation, uttt


class MeasurementShapeTest(unittest.TestCase):
    def test_isolation_matches_its_derived_bounds(self):
        stats = measure(isolation, n_games=300, seed=1)
        self.assertEqual(stats.mean_by_ply[0], 11.0,
                         "ply-1 branching is 11 - the southward ray stops "
                         "before the opposing pawn")
        self.assertLessEqual(stats.max_b, 16, "16 is the theoretical maximum")
        self.assertLessEqual(stats.mean_length, 23.0)

    def test_uttt_first_ply_offers_all_81_cells(self):
        stats = measure(uttt, n_games=200, seed=2)
        self.assertEqual(stats.mean_by_ply[0], 81.0)
        self.assertLessEqual(stats.mean_length, 81.0)


class AtaxxCurveGateTest(unittest.TestCase):
    """The gate. Reference: Ribeiro and Figueiredo, ENIAC 2018 - about 20 at
    ply 1, peaking near 92 around ply 25. Ours has 49 playable cells against
    their 47, so ours should run slightly higher; we assert the shape."""

    @classmethod
    def setUpClass(cls):
        cls.stats = measure(ataxx, n_games=120, seed=3)

    def test_first_ply_branching_is_in_the_reference_neighbourhood(self):
        # Reference ~20. A generator missing the 8 knight-shaped jump
        # destinations would land near 12.
        first = self.stats.mean_by_ply[0]
        self.assertGreaterEqual(first, 16.0)
        self.assertLessEqual(first, 30.0)

    def test_the_curve_has_a_pronounced_mid_game_peak(self):
        # This is the flat-curve detector. Reference peak ~92 against ~20 at
        # ply 1 - a factor above 3. A broken jump generator flattens this.
        first = self.stats.mean_by_ply[0]
        peak = max(self.stats.mean_by_ply)
        self.assertGreater(peak, 60.0, "mid-game peak far below the reference")
        self.assertGreater(peak / first, 2.5, "curve is too flat to be correct")

    def test_the_peak_occurs_in_the_middle_game_not_at_the_start(self):
        peak_ply = self.stats.mean_by_ply.index(max(self.stats.mean_by_ply))
        self.assertGreater(peak_ply, 10)
        self.assertLess(peak_ply, 60)

    def test_average_game_length_is_in_the_reference_neighbourhood(self):
        # Reference ~100 plies. Ours is capped at 300 by the no-progress rule.
        self.assertGreater(self.stats.mean_length, 40.0)
        self.assertLess(self.stats.mean_length, 200.0)


if __name__ == "__main__":
    unittest.main()
```


- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_branching_validation -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'experiments.measure_branching'`

- [ ] **Step 3: Write minimal implementation**

Create `experiments/measure_branching.py`:

```python
"""Measure branching factor per ply and game length by random self-play.

This is the project's primary move-generator validation. For Ataxx the measured
curve is compared against Ribeiro and Figueiredo (ENIAC 2018): roughly 20 at ply
1, peaking near 92 around ply 25. Reproducing that double-humped shape is strong
evidence the generator is right; a flat curve indicates a bug, most likely the
eight knight-shaped jump destinations.

Run directly for a per-ply table:  python3 -m experiments.measure_branching
"""
import random
import statistics
from dataclasses import dataclass
from typing import Any, List


@dataclass(frozen=True)
class BranchingStats:
    game: str
    n_games: int
    mean: float
    median: float
    max_b: int
    mean_by_ply: List[float]
    mean_length: float


def measure(game, n_games=200, seed=0, max_plies=400):
    # type: (Any, int, int, int) -> BranchingStats
    """Play n_games random games, recording the legal-move count at every ply."""
    rng = random.Random(seed)
    all_counts = []          # type: List[int]
    by_ply = []              # type: List[List[int]]
    lengths = []             # type: List[int]

    for _ in range(n_games):
        state = game.initial_state()
        ply = 0
        while ply < max_plies:
            moves = game.legal_moves(state)
            if not moves:
                break
            count = len(moves)
            all_counts.append(count)
            while len(by_ply) <= ply:
                by_ply.append([])
            by_ply[ply].append(count)
            state = game.apply_move(state, rng.choice(moves))
            ply += 1
        lengths.append(ply)

    return BranchingStats(
        game=game.NAME,
        n_games=n_games,
        mean=statistics.mean(all_counts),
        median=statistics.median(all_counts),
        max_b=max(all_counts),
        mean_by_ply=[statistics.mean(counts) for counts in by_ply],
        mean_length=statistics.mean(lengths),
    )


def _report(stats, reference=None):
    # type: (BranchingStats, Any) -> None
    print("\n=== %s (%d random games) ===" % (stats.game, stats.n_games))
    print("  mean b %.2f | median b %.1f | max b %d | mean length %.1f plies"
          % (stats.mean, stats.median, stats.max_b, stats.mean_length))
    peak = max(stats.mean_by_ply)
    print("  ply-1 b %.1f | peak b %.1f at ply %d"
          % (stats.mean_by_ply[0], peak, stats.mean_by_ply.index(peak)))
    if reference:
        print("  reference: %s" % reference)
    step = max(1, len(stats.mean_by_ply) // 25)
    cells = ["%d:%.0f" % (p, stats.mean_by_ply[p])
             for p in range(0, len(stats.mean_by_ply), step)]
    print("  by ply -> " + "  ".join(cells))


def main():
    from games import ataxx, isolation, uttt
    _report(measure(isolation, n_games=500, seed=1),
            "derived: 11 at ply 1, max 16, at most 23 plies")
    _report(measure(uttt, n_games=300, seed=2),
            "derived: 81 at ply 1, at most 81 plies")
    _report(measure(ataxx, n_games=200, seed=3),
            "Ribeiro and Figueiredo 2018: ~20 at ply 1, peak ~92 near ply 25, "
            "~100 plies average (on 47 playable cells; ours has 49)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_branching_validation -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Print the curve for the record**

Run: `python3 -m experiments.measure_branching`

Paste the **full output** into your report. This table is cited in the final write-up as evidence the move generators are correct, so it needs to be recorded verbatim, not summarised.

- [ ] **Step 6: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: PASS, 104 tests

- [ ] **Step 7: Report — do not commit**

**If the Ataxx gate fails, stop and report BLOCKED rather than adjusting the thresholds.** A failing gate means the move generator is wrong, and loosening the assertion would hide exactly the defect the gate exists to find.

---

*Tasks 4-6 (Alpha-Beta, MCTS, and the remaining evaluators) are appended below.*

### Task 4: Enhanced Alpha-Beta

Negamax with alpha-beta pruning, iterative deepening, move ordering, and a capped
transposition table, all under the `SearchContext` budget.

**Files:**
- Create: `agents/alpha_beta_agent.py`
- Test: `tests/test_alpha_beta.py`

**Interfaces:**
- Consumes: `agents.base.SearchContext`, `games.base.WIN/DRAW/LOSS`, all three game modules
- Produces: `agents.alpha_beta_agent.make(evaluate, max_entries=200000, max_depth=64) -> agent`,
  plus `EXACT`, `LOWER`, `UPPER` flag constants.

**Anytime discipline:** a partially completed iteration is **discarded entirely** - the
returned move always comes from the last *fully completed* depth. This is what makes the
`time-limited` tag meaningful: the move is a real answer to a shallower question, not a
half-formed answer to a deeper one.

- [ ] **Step 1: Write the failing test**

Create `tests/test_alpha_beta.py`:

```python
import random
import unittest

from agents import alpha_beta_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation as iso


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class AlphaBetaTest(unittest.TestCase):
    def setUp(self):
        self.agent = alpha_beta_agent.make(isolation_eval.evaluate)

    def test_returns_a_legal_move(self):
        s = iso.initial_state()
        ctx = SearchContext(0.5, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertIn(move, iso.legal_moves(s))

    def test_records_the_depth_it_reached(self):
        ctx = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertIsNotNone(ctx.depth_reached)
        self.assertGreaterEqual(ctx.depth_reached, 1)

    def test_expands_nodes_and_reports_them(self):
        ctx = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertGreater(ctx.nodes, 0)
        self.assertEqual(ctx.simulations, 0, "alpha-beta runs no simulations")

    def test_deeper_budget_reaches_deeper(self):
        shallow = SearchContext(0.02, 100000)
        deep = SearchContext(0.5, 100000)
        self.agent(iso, iso.initial_state(), shallow, random.Random(1))
        self.agent(iso, iso.initial_state(), deep, random.Random(1))
        self.assertGreaterEqual(deep.depth_reached, shallow.depth_reached)

    def test_takes_an_immediate_win_when_one_exists(self):
        # P0 at (2,2); P1 at (0,0) with its only escapes blocked, so any P0 move
        # that does not free P1 wins immediately. Verify AB reports a proven win.
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=0)
        self.assertEqual(iso.legal_moves(
            iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=1)), [])
        ctx = SearchContext(1.0, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        after = iso.apply_move(s, move)
        self.assertTrue(iso.is_terminal(after), "should end the game at once")

    def test_beats_the_heuristic_agent_more_often_than_not(self):
        # The whole point of search: same evaluator, deeper look. If Alpha-Beta
        # does not beat the one-ply agent, either the search or the sign is wrong.
        from agents import heuristic_agent
        heur = heuristic_agent.make(isolation_eval.evaluate)
        wins = 0
        games = 20
        for seed in range(games):
            rng = random.Random(seed)
            s = iso.initial_state()
            ab_side = seed % 2
            ab = alpha_beta_agent.make(isolation_eval.evaluate)
            while not iso.is_terminal(s):
                actor = ab if s.side_to_move == ab_side else heur
                d = decide(actor, iso, s, 0.05, 100000, rng)
                s = iso.apply_move(s, d.move)
            if s.side_to_move != ab_side:
                wins += 1
        self.assertGreater(wins, games // 2,
                           "alpha-beta won %d/%d against one-ply" % (wins, games))

    def test_discards_an_incomplete_iteration(self):
        # A clock that expires partway through the first deepening still yields a
        # legal move, and the move is not tagged normal.
        clock = FakeClock()

        class Tight(SearchContext):
            def should_stop(self):
                clock.advance(0.005)
                return SearchContext.should_stop(self)

        ctx = Tight(0.01, 100000, check_every=1, clock=clock)
        s = iso.initial_state()
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertIn(move, iso.legal_moves(s))

    def test_memory_cap_is_reported(self):
        tiny = alpha_beta_agent.make(isolation_eval.evaluate, max_entries=8)
        ctx = SearchContext(0.3, 100000)
        tiny(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.memory_capped,
                        "an 8-entry table must fill and report the cap")

    def test_tagged_time_limited_under_a_very_tight_budget(self):
        s = iso.initial_state()
        d = decide(self.agent, iso, s, 0.0005, 100000, random.Random(1))
        self.assertIn(d.tag, (MoveTag.TIME_LIMITED, MoveTag.MEMORY_LIMITED))
        self.assertIn(d.move, iso.legal_moves(s))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_alpha_beta -v`
Expected: FAIL with `ImportError: cannot import name 'alpha_beta_agent'`

- [ ] **Step 3: Write minimal implementation**

Create `agents/alpha_beta_agent.py`:

```python
"""Enhanced Alpha-Beta: negamax, iterative deepening, move ordering, capped
transposition table.

Negamax exploits the zero-sum symmetry so one recursive function serves both
players, which is only correct because every value in this project is expressed
from the perspective of the side to move.

Anytime discipline: a partially completed iteration is discarded entirely, so the
returned move always comes from the last fully completed depth. That is what
makes the time-limited tag meaningful - the move is a real answer to a shallower
question rather than a half-formed answer to a deeper one.

The transposition table lives in the agent, so it persists across the moves of a
game. The runner constructs one agent per game; reusing one across a matchup
would let a table already near its cap from a finished game report a memory cap
on an early move of the next one.
"""
import itertools
from typing import Any

EXACT, LOWER, UPPER = 0, 1, 2

_INF = float("inf")
_PROVEN = 1.0        # terminal rewards are exactly +-1; evaluations stay inside


class _Timeout(Exception):
    """Raised deep in the search when the budget expires, unwinding to the
    iterative-deepening loop, which then discards the partial iteration."""


def make(evaluate, max_entries=200000, max_depth=64):
    # type: (Any, int, int) -> Any
    """Build an Alpha-Beta agent. `evaluate(game, state) -> float` in (-1, 1),
    from the perspective of that state's side to move."""

    def agent(game, state, ctx, rng):
        table = {}
        best_move = None

        for depth in itertools.count(1):
            try:
                value, move = _root(game, state, depth, ctx, table,
                                    evaluate, max_entries)
            except _Timeout:
                break                      # discard this iteration entirely

            best_move = move
            ctx.depth_reached = depth

            if abs(value) >= _PROVEN:       # a proven win or loss; no deeper
                ctx.completed()
                break
            if depth >= max_depth:
                ctx.completed()
                break
            if ctx.should_stop():
                break

        if best_move is None:               # cut off before depth 1 finished
            return rng.choice(game.legal_moves(state))
        return best_move

    return agent


def _root(game, state, depth, ctx, table, evaluate, cap):
    moves = _ordered(game, state, table)
    alpha, best_value, best_move = -_INF, -_INF, moves[0]
    for move in moves:
        child = game.apply_move(state, move)
        value = -_negamax(game, child, depth - 1, -_INF, -alpha,
                          ctx, table, evaluate, cap)
        if value > best_value:
            best_value, best_move = value, move
        if best_value > alpha:
            alpha = best_value
    return best_value, best_move


def _negamax(game, state, depth, alpha, beta, ctx, table, evaluate, cap):
    if ctx.should_stop():
        raise _Timeout
    ctx.note_node()

    if game.is_terminal(state):
        return game.result(state)
    if depth <= 0:
        return evaluate(game, state)

    entry = table.get(state)
    if entry is not None:
        e_depth, e_value, e_flag, _ = entry
        if e_depth >= depth:
            if e_flag == EXACT:
                return e_value
            if e_flag == LOWER and e_value > alpha:
                alpha = e_value
            elif e_flag == UPPER and e_value < beta:
                beta = e_value
            if alpha >= beta:
                return e_value

    original_alpha = alpha
    moves = _ordered(game, state, table)
    best_value, best_move = -_INF, moves[0]

    for move in moves:
        child = game.apply_move(state, move)
        value = -_negamax(game, child, depth - 1, -beta, -alpha,
                          ctx, table, evaluate, cap)
        if value > best_value:
            best_value, best_move = value, move
        if best_value > alpha:
            alpha = best_value
        if alpha >= beta:
            break

    if best_value <= original_alpha:
        flag = UPPER
    elif best_value >= beta:
        flag = LOWER
    else:
        flag = EXACT

    if len(table) < cap:
        table[state] = (depth, best_value, flag, best_move)
    else:
        # Cap reached: stop caching rather than evicting. The degradation is
        # real - later searches lose the table's benefit - and is exactly what
        # the memory-limited tag is meant to record.
        ctx.hit_memory_cap()

    return best_value


def _ordered(game, state, table):
    """Legal moves with the table's best move first.

    Everything after that keeps the game's own ordering, which each game module
    already returns in a heuristically sensible order.
    """
    moves = game.legal_moves(state)
    entry = table.get(state)
    if entry is None:
        return moves
    tt_move = entry[3]
    if tt_move is None or tt_move not in moves:
        return moves
    ordered = [tt_move]
    ordered.extend(m for m in moves if m != tt_move)
    return ordered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_alpha_beta -v`
Expected: PASS, 9 tests

- [ ] **Step 5: Report — do not commit**

---

### Task 5: MCTS / UCT

**Files:**
- Create: `agents/mcts_agent.py`
- Test: `tests/test_mcts.py`

**Interfaces:**
- Consumes: `agents.base.SearchContext`, all three game modules, the evaluators
- Produces: `agents.mcts_agent.make(evaluate, exploration=math.sqrt(2), epsilon=0.25, sample_k=8, rollout_depth=40, max_nodes=None) -> agent`

**Two things that must be right.** Rewards are mapped to `[0, 1]` **in exactly one
place** - the rollout's return - because UCB1's exploration term does not rescale with
the reward and every published exploration constant assumes that range. And the tree is
**capped**: on reaching the cap, expansion stops while selection and backpropagation
continue, and `ctx.hit_memory_cap()` is called.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcts.py`:

```python
import math
import random
import unittest

from agents import mcts_agent
from agents.base import MoveTag, SearchContext, decide
from evaluation import isolation_eval
from games import isolation as iso


class MctsTest(unittest.TestCase):
    def setUp(self):
        self.agent = mcts_agent.make(isolation_eval.evaluate)

    def test_returns_a_legal_move(self):
        s = iso.initial_state()
        ctx = SearchContext(0.2, 100000)
        self.assertIn(self.agent(iso, s, ctx, random.Random(1)),
                      iso.legal_moves(s))

    def test_runs_simulations_and_reports_them_not_nodes(self):
        ctx = SearchContext(0.2, 100000)
        self.agent(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertGreater(ctx.simulations, 0)
        self.assertEqual(ctx.nodes, 0, "MCTS counts simulations, not nodes")

    def test_a_larger_budget_buys_more_simulations(self):
        small = SearchContext(0.05, 100000)
        large = SearchContext(0.4, 100000)
        self.agent(iso, iso.initial_state(), small, random.Random(1))
        self.agent(iso, iso.initial_state(), large, random.Random(1))
        self.assertGreater(large.simulations, small.simulations)

    def test_is_essentially_never_tagged_normal(self):
        # Anytime by construction: it consumes whatever budget it is given, so
        # the normal tag is an Alpha-Beta phenomenon, not an MCTS one.
        d = decide(self.agent, iso, iso.initial_state(), 0.1, 100000,
                   random.Random(1))
        self.assertEqual(d.tag, MoveTag.TIME_LIMITED)

    def test_node_cap_is_reported(self):
        tiny = mcts_agent.make(isolation_eval.evaluate, max_nodes=4)
        ctx = SearchContext(0.2, 4)
        tiny(iso, iso.initial_state(), ctx, random.Random(1))
        self.assertTrue(ctx.memory_capped)

    def test_takes_an_immediate_win_when_one_exists(self):
        blocked = (1 << 1) | (1 << 5) | (1 << 6)
        s = iso.IsolationState(blocked=blocked, pawns=(12, 0), side_to_move=0)
        ctx = SearchContext(0.5, 100000)
        move = self.agent(iso, s, ctx, random.Random(1))
        self.assertTrue(iso.is_terminal(iso.apply_move(s, move)))

    def test_beats_the_random_agent_convincingly(self):
        from agents import random_agent
        wins = 0
        games = 20
        for seed in range(games):
            rng = random.Random(seed)
            s = iso.initial_state()
            mcts_side = seed % 2
            agent = mcts_agent.make(isolation_eval.evaluate)
            while not iso.is_terminal(s):
                actor = agent if s.side_to_move == mcts_side else random_agent.choose
                d = decide(actor, iso, s, 0.03, 100000, rng)
                s = iso.apply_move(s, d.move)
            if s.side_to_move != mcts_side:
                wins += 1
        self.assertGreaterEqual(wins, 15,
                                "MCTS won only %d/%d against random" % (wins, games))

    def test_rollout_rewards_stay_inside_the_unit_interval(self):
        rng = random.Random(2)
        for _ in range(200):
            r = mcts_agent._rollout(iso, iso.initial_state(), rng,
                                    isolation_eval.evaluate, 0.25, 8, 40)
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)

    def test_default_exploration_constant_is_root_two(self):
        # UCB1's constant is only meaningful for rewards in [0, 1].
        self.assertAlmostEqual(mcts_agent.DEFAULT_EXPLORATION, math.sqrt(2))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_mcts -v`
Expected: FAIL with `ImportError: cannot import name 'mcts_agent'`

- [ ] **Step 3: Write minimal implementation**

Create `agents/mcts_agent.py`:

```python
"""Monte Carlo Tree Search with UCT selection and a heuristic-guided rollout.

Rewards are mapped to [0, 1] in exactly one place - the rollout's return -
because UCB1's exploration term does not rescale with the reward, so every
published exploration constant assumes that range. Feeding it [-1, +1] would
halve exploration relative to value differences without anyone intending it.

Rollout policy is epsilon-greedy over at most sample_k candidates and truncated
at rollout_depth, returning the evaluator's value there. Pure random rollouts are
weak; pure greedy rollouts are deterministic and collapse the diversity the
Monte Carlo estimate depends on. These constants are hyperparameters, selected
empirically in the calibration pilot rather than asserted - only the exploration
constant has a principled derivation.
"""
import math
import random
from typing import Any, List, Optional

DEFAULT_EXPLORATION = math.sqrt(2)


class _Node(object):
    __slots__ = ("state", "parent", "move", "children", "untried",
                 "visits", "value")

    def __init__(self, state, parent, move, untried):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []          # type: List[_Node]
        self.untried = untried      # type: List[Any]
        self.visits = 0
        # Accumulated reward from the perspective of the player who moved INTO
        # this node - i.e. the side to move at the parent. That is what lets
        # selection at a parent simply maximise child.value / child.visits.
        self.value = 0.0


def make(evaluate, exploration=DEFAULT_EXPLORATION, epsilon=0.25, sample_k=8,
         rollout_depth=40, max_nodes=None):
    # type: (Any, float, float, int, int, Optional[int]) -> Any

    def agent(game, state, ctx, rng):
        root = _Node(state, None, None, list(game.legal_moves(state)))
        cap = max_nodes if max_nodes is not None else ctx.max_nodes
        nodes = 1

        while not ctx.should_stop():
            node = root

            # Selection: descend fully expanded nodes by UCB1.
            while not node.untried and node.children:
                node = _select(node, exploration)

            # Expansion, unless the tree is at its cap.
            if node.untried:
                if nodes < cap:
                    move = node.untried.pop(rng.randrange(len(node.untried)))
                    child_state = game.apply_move(node.state, move)
                    child = _Node(child_state, node, move,
                                  list(game.legal_moves(child_state)))
                    node.children.append(child)
                    nodes += 1
                    node = child
                else:
                    ctx.hit_memory_cap()

            # Simulation, then backpropagation with the perspective flipping at
            # every level.
            reward = _rollout(game, node.state, rng, evaluate, epsilon,
                              sample_k, rollout_depth)
            ctx.note_simulation()

            reward = 1.0 - reward       # into the parent-mover's perspective
            current = node
            while current.parent is not None:
                current.visits += 1
                current.value += reward
                reward = 1.0 - reward
                current = current.parent
            root.visits += 1

        if not root.children:
            return rng.choice(game.legal_moves(state))
        best = max(root.children, key=lambda n: n.visits)
        return best.move

    return agent


def _select(node, exploration):
    # type: (_Node, float) -> _Node
    log_parent = math.log(node.visits) if node.visits > 0 else 0.0
    best, best_score = None, -float("inf")
    for child in node.children:
        if child.visits == 0:
            return child
        score = (child.value / child.visits
                 + exploration * math.sqrt(log_parent / child.visits))
        if score > best_score:
            best, best_score = child, score
    return best


def _rollout(game, state, rng, evaluate, epsilon, sample_k, depth_cap):
    # type: (Any, Any, random.Random, Any, float, int, int) -> float
    """Play out from `state`, returning a reward in [0, 1] from the perspective
    of the side to move at `state`."""
    root_side = state.side_to_move
    current = state

    for _ in range(depth_cap):
        if game.is_terminal(current):
            value = game.result(current)
            if current.side_to_move != root_side:
                value = -value
            return (value + 1.0) / 2.0

        moves = game.legal_moves(current)
        if len(moves) == 1 or rng.random() < epsilon:
            move = rng.choice(moves)
        else:
            sample = (moves if len(moves) <= sample_k
                      else rng.sample(moves, sample_k))
            # A child's evaluation is from the opponent's perspective, so the
            # move that minimises it is the one that maximises ours.
            move = min(sample,
                       key=lambda m: evaluate(game, game.apply_move(current, m)))
        current = game.apply_move(current, move)

    value = evaluate(game, current)
    if current.side_to_move != root_side:
        value = -value
    return (value + 1.0) / 2.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_mcts -v`
Expected: PASS, 9 tests

- [ ] **Step 5: Report — do not commit**

---

### Task 6: Evaluators for Ataxx and Ultimate Tic-Tac-Toe

**Files:**
- Create: `evaluation/ataxx_eval.py`, `evaluation/uttt_eval.py`
- Test: `tests/test_evaluators.py`

**Interfaces:**
- Produces: `evaluation.ataxx_eval.evaluate(game, state) -> float`,
  `evaluation.uttt_eval.evaluate(game, state) -> float`. Both strictly inside `(-1, +1)`,
  from the perspective of `state.side_to_move`.

**Ataxx exposure, and why the Othello intuition does not transfer:** in Ataxx **no piece
is ever permanently safe**, because any piece can be converted by an opponent landing
next to it. The usable notion is *exposure* - a piece is vulnerable exactly when it has
an empty neighbouring cell - so the term counts empty neighbours, negated. Corners have
3 neighbours and edges 5 against 8 for a central cell, which is why corners are
structurally safer here: the same conclusion as Othello for an entirely different reason.

**UTTT's evaluator carries unusual weight.** There is a published claim that this game
"lacks any simple heuristic evaluation function" and that minimax struggles for that
reason. Since Alpha-Beta and the Heuristic agent share this function by design, a weak
one makes a poor Alpha-Beta result ambiguous between "exact search scales badly" and
"our heuristic was bad". Its quality must be reported, not assumed.

- [ ] **Step 1: Write the failing test**

Create `tests/test_evaluators.py`:

```python
import random
import unittest

from evaluation import ataxx_eval, isolation_eval, uttt_eval
from games import ataxx, isolation, uttt

_CASES = ((ataxx, ataxx_eval), (uttt, uttt_eval), (isolation, isolation_eval))


class EvaluatorRangeTest(unittest.TestCase):
    def test_all_evaluators_stay_strictly_inside_the_reward_range(self):
        # Terminal rewards are exactly +-1, so an evaluation reaching that
        # magnitude would let a heuristic estimate outrank a real win.
        for game, module in _CASES:
            rng = random.Random(7)
            for _ in range(40):
                s = game.initial_state()
                while not game.is_terminal(s):
                    v = module.evaluate(game, s)
                    self.assertGreater(v, -1.0, game.NAME)
                    self.assertLess(v, 1.0, game.NAME)
                    s = game.apply_move(s, rng.choice(game.legal_moves(s)))

    def test_all_evaluators_are_antisymmetric(self):
        # The same position seen from the other side must invert. A fixed-player
        # evaluation would silently flip sign on alternate plies.
        for game, module in _CASES:
            rng = random.Random(9)
            for _ in range(20):
                s = game.initial_state()
                for _ in range(6):
                    if game.is_terminal(s):
                        break
                    flipped = _flip_side(s)
                    self.assertAlmostEqual(
                        module.evaluate(game, s),
                        -module.evaluate(game, flipped), places=9,
                        msg="%s evaluation is not antisymmetric" % game.NAME)
                    s = game.apply_move(s, rng.choice(game.legal_moves(s)))


def _flip_side(s):
    import dataclasses
    return dataclasses.replace(s, side_to_move=1 - s.side_to_move)


class AtaxxEvaluatorTest(unittest.TestCase):
    def test_prefers_having_more_pieces(self):
        few = ataxx.AtaxxState(boards=(1 << 0, (1 << 48) | (1 << 47) | (1 << 41)),
                               side_to_move=0, plies_since_progress=0)
        self.assertLess(ataxx_eval.evaluate(ataxx, few), 0.0)

    def test_prefers_less_exposed_pieces_at_equal_material(self):
        # Same count for both sides; one side's pieces sit in a corner cluster
        # (fewer empty neighbours), the other's in the open centre.
        corner = ataxx.AtaxxState(
            boards=((1 << 0) | (1 << 1) | (1 << 7),
                    (1 << 24) | (1 << 25) | (1 << 31)),
            side_to_move=0, plies_since_progress=0)
        self.assertGreater(ataxx_eval.evaluate(ataxx, corner), 0.0)


class UtttEvaluatorTest(unittest.TestCase):
    def test_prefers_owning_more_local_boards(self):
        status = (1, 1, 0, 0, 0, 0, 0, 0, 0)
        s = uttt.UtttState(marks=(0, 0), status=status, send=-1, side_to_move=0,
                           winnable=uttt.winnable_masks(status),
                           global_winner=uttt.global_winner_of(status))
        self.assertGreater(uttt_eval.evaluate(uttt, s), 0.0)

    def test_prefers_the_centre_board_over_an_edge_board(self):
        centre = (0, 0, 0, 0, 1, 0, 0, 0, 0)
        edge = (0, 1, 0, 0, 0, 0, 0, 0, 0)

        def value(status):
            s = uttt.UtttState(marks=(0, 0), status=status, send=-1,
                               side_to_move=0,
                               winnable=uttt.winnable_masks(status),
                               global_winner=uttt.global_winner_of(status))
            return uttt_eval.evaluate(uttt, s)

        self.assertGreater(value(centre), value(edge))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_evaluators -v`
Expected: FAIL with `ImportError: cannot import name 'ataxx_eval'`

- [ ] **Step 3: Write minimal implementation**

Create `evaluation/ataxx_eval.py`:

```python
"""Ataxx evaluation: material difference plus exposure.

In Ataxx no piece is ever permanently safe - any piece can be converted by an
opponent landing next to it - so the Othello notion of stability does not
transfer. The usable notion is exposure: a piece is vulnerable exactly when it
has an empty neighbouring cell, so the term counts empty neighbours, negated.
Corners have 3 neighbours and edges 5 against 8 for a central cell, which is why
corners are structurally safer, for an entirely different reason than in Othello.
"""
from games.ataxx import CELLS, FULL_MASK, NEIGHBOUR_MASKS

_MATERIAL_WEIGHT = 0.7
_EXPOSURE_WEIGHT = 0.3
_SCALE = 0.95          # keeps the result strictly inside (-1, 1)
_MAX_EXPOSURE = 8.0 * CELLS


def _bits(mask):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def _exposure(pieces, empty):
    total = 0
    for index in _bits(pieces):
        total += bin(NEIGHBOUR_MASKS[index] & empty).count("1")
    return total


def evaluate(game, state):
    """From the perspective of state.side_to_move; strictly inside (-1, 1)."""
    mine = state.boards[state.side_to_move]
    theirs = state.boards[1 - state.side_to_move]
    empty = FULL_MASK & ~(mine | theirs)

    material = (bin(mine).count("1") - bin(theirs).count("1")) / float(CELLS)
    # Fewer empty neighbours is safer, so their exposure minus ours.
    exposure = (_exposure(theirs, empty) - _exposure(mine, empty)) / _MAX_EXPOSURE

    return _SCALE * (_MATERIAL_WEIGHT * material + _EXPOSURE_WEIGHT * exposure)
```

Create `evaluation/uttt_eval.py`:

```python
"""Ultimate Tic-Tac-Toe evaluation.

Local boards are weighted by how many global lines they participate in - the
centre board sits on 4 lines, corners on 3, edges on 2 - plus a term for
two-in-a-row threats with the third cell open, minus the opponent's.

This evaluator carries unusual weight: there is a published claim that this game
lacks any simple heuristic evaluation function and that minimax struggles for
that reason. Alpha-Beta and the one-ply Heuristic agent share it by design, so a
weak function makes a poor Alpha-Beta result ambiguous between "exact search
scales badly" and "our heuristic was bad". Its quality must be reported, not
assumed. See docs/games/ultimate-tic-tac-toe.md section 5.5.
"""
from games.uttt import LINES, UNDECIDED

# How many of the 8 global lines each board index participates in.
_LINE_COUNT = tuple(
    sum(1 for line in LINES if b in line) for b in range(9)
)
_MAX_BOARD_SCORE = float(sum(_LINE_COUNT))       # 24
_MAX_THREATS = 9.0 * 8.0

_BOARD_WEIGHT = 0.75
_THREAT_WEIGHT = 0.25
_SCALE = 0.95


def _threats(marks_mine, marks_theirs, status):
    """Lines inside undecided boards holding two of mine and no opponent mark."""
    total = 0
    for board in range(9):
        if status[board] != UNDECIDED:
            continue
        base = board * 9
        for line in LINES:
            mine = sum(1 for c in line if (marks_mine >> (base + c)) & 1)
            theirs = sum(1 for c in line if (marks_theirs >> (base + c)) & 1)
            if theirs == 0 and mine == 2:
                total += 1
    return total


def evaluate(game, state):
    """From the perspective of state.side_to_move; strictly inside (-1, 1)."""
    side = state.side_to_move
    mine_id, theirs_id = side + 1, 2 - side
    mine_marks = state.marks[side]
    theirs_marks = state.marks[1 - side]

    board_score = 0
    for board, owner in enumerate(state.status):
        if owner == mine_id:
            board_score += _LINE_COUNT[board]
        elif owner == theirs_id:
            board_score -= _LINE_COUNT[board]
    boards = board_score / _MAX_BOARD_SCORE

    threats = (_threats(mine_marks, theirs_marks, state.status)
               - _threats(theirs_marks, mine_marks, state.status)) / _MAX_THREATS

    return _SCALE * (_BOARD_WEIGHT * boards + _THREAT_WEIGHT * threats)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_evaluators -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Run the full suite**

Run: `python3 -m unittest discover -s tests`
Expected: PASS, all tests green

- [ ] **Step 6: Report — do not commit**

---

## What Plan 2 delivers

All three games implemented and validated by the conformance harness, with Ataxx checked
against a published branching-factor curve; both search agents playing under time and
memory budgets, reporting depth, nodes, simulations and cap events; and evaluators for
all three games sharing one perspective convention and one reward scale.

**Plan 3** then adds the three-phase calibration pilot (time budgets, memory caps in
bytes, MCTS hyperparameters), the tournament runner with interleaved trials, and the
analysis producing the tables and figures.
