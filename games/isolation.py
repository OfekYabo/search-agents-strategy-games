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
