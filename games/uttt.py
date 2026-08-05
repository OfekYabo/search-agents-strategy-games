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
