# Agent version v3. Identical to v1 - no change has been made yet.
# Frozen once a tournament has run against it; see docs/VERSIONING.md.
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
