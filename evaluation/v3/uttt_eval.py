# Agent version v3. Identical to v1 - no change has been made yet.
# Frozen once a tournament has run against it; see docs/VERSIONING.md.
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
