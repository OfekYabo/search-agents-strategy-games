# Agent version v3. Identical to v1 - no change has been made yet.
# Frozen once a tournament has run against it; see docs/VERSIONING.md.
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
