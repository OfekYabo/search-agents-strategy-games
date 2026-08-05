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
