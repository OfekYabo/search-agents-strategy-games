# Agent version v3. See docs/VERSIONING.md - frozen once a tournament has run
# against it. Any fix after that is a new version, not an edit here.
"""Isolation evaluation.

Queen-slide mobility varies sharply between positions, which makes this a
well-matched heuristic for the variant - see docs/games/isolation.md section 7.

`evaluate` is currently `mobility_difference`, identical to v1 and v2. The
other functions below are **measured candidates for v3**; see the table on
`evaluate` for how they compare and `docs/v3-candidates.md` for the caveats.

To adopt a candidate, change the one binding at the bottom of this file. It is
a plain name binding rather than a wrapper function on purpose: `evaluate` is
called thousands of times per decision under a wall-clock budget, so an extra
call frame per evaluation would cost measured search time.
"""
from games.isolation import IsolationState, _RAYS, legal_moves

_MAX_MOBILITY = 16.0   # theoretical maximum, gamebook section 5.3


def _mobility(state, side):
    # type: (IsolationState, int) -> int
    return len(legal_moves(IsolationState(blocked=state.blocked,
                                          pawns=state.pawns,
                                          side_to_move=side)))


def _reachable(state, side):
    # type: (IsolationState, int) -> int
    """Cells reachable by repeated slides - the classic partition heuristic.

    Once the board splits into disjoint regions the game is decided by who owns
    the larger one, and immediate mobility stops being the right question.
    """
    blocked = state.blocked
    opponent = state.pawns[1 - side]
    seen = set()
    frontier = [state.pawns[side]]
    while frontier:
        cell = frontier.pop()
        for ray in _RAYS[cell]:
            for target in ray:
                if target == opponent or (blocked >> target) & 1:
                    break
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
    return len(seen)


def mobility_difference(game, state):
    # type: (object, IsolationState) -> float
    """Own mobility minus the opponent's, from the perspective of the side to
    move, squashed strictly inside (-1, 1). What v1 and v2 use."""
    difference = (_mobility(state, state.side_to_move)
                  - _mobility(state, 1 - state.side_to_move))
    return difference / (2.0 * _MAX_MOBILITY)


def aggressive(game, state):
    # type: (object, IsolationState) -> float
    """Penalise the opponent's mobility twice as hard. The classic "aggressive"
    Isolation heuristic - and measured WORSE here, not better."""
    mine = _mobility(state, state.side_to_move)
    theirs = _mobility(state, 1 - state.side_to_move)
    return (mine - 2.0 * theirs) / (3.0 * _MAX_MOBILITY)


def ratio(game, state):
    # type: (object, IsolationState) -> float
    """Scale-free mobility difference. The same gap of two moves matters far
    more when four remain than when twenty do, which a fixed divisor cannot
    express."""
    mine = _mobility(state, state.side_to_move)
    theirs = _mobility(state, 1 - state.side_to_move)
    return (mine - theirs) / float(mine + theirs + 1)


def reach(game, state):
    # type: (object, IsolationState) -> float
    """Region size alone. Measured WORSE than mobility on its own: it ignores
    immediate mobility entirely, and is useful only as a tiebreak."""
    mine = _reachable(state, state.side_to_move)
    theirs = _reachable(state, 1 - state.side_to_move)
    return (mine - theirs) / float(mine + theirs + 1)


def mixed(game, state):
    # type: (object, IsolationState) -> float
    """Mobility, with region size as a tiebreak. The best candidate measured.

    Neither component wins alone - `ratio` beats `mobility_difference` by a
    little and `reach` loses to it outright - but weighting mobility with a
    minority contribution from region size beats both.
    """
    return 0.7 * ratio(game, state) + 0.3 * reach(game, state)


# ---------------------------------------------------------------------------
# THE V3 CANDIDATE SWITCH. Change this one line to adopt a candidate.
#
# Measured against the random agent, 600 games per candidate, both seat orders
# (python3 -m experiments.compare_evaluators):
#
#     mixed                 0.912 [0.886, 0.932]   <- best measured
#     ratio                 0.885 [0.857, 0.908]
#     mobility_difference   0.860 [0.830, 0.885]   <- in use, same as v1/v2
#     aggressive            0.802 [0.768, 0.832]
#     reach                 0.802 [0.768, 0.832]
#
# Two caveats before adopting one, both in docs/v3-candidates.md:
#   - the screening is against the RANDOM agent only, and beating random
#     better does not guarantee beating MCTS or Alpha-Beta better;
#   - this evaluator is injected into the heuristic, Alpha-Beta AND MCTS, so
#     changing it moves all three. On Isolation, MCTS consults it in only
#     1.8-17% of rollouts, so the effect there may be near zero.
#
# Decide with a v2-versus-v3 tournament. The number above only screens out
# candidates that are not worth a ten-hour run.
# ---------------------------------------------------------------------------
evaluate = mobility_difference
