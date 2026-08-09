# Agent version v3. See docs/VERSIONING.md - frozen once a tournament has
# run against it. Any fix after that is a new version, not an edit here.
# Identical to v1 - no change has been made yet.
"""Enhanced Alpha-Beta: negamax, iterative deepening, move ordering, capped
transposition table.

Negamax exploits the zero-sum symmetry so one recursive function serves both
players, which is only correct because every value in this project is expressed
from the perspective of the side to move.

Anytime discipline: a partially completed iteration is discarded entirely, so the
returned move always comes from the last fully completed depth. That is what
makes the time-limited tag meaningful - the move is a real answer to a shallower
question rather than a half-formed answer to a deeper one.

The transposition table is created once, in `make`, and lives in the agent
object for its entire lifetime - it persists across every decision the agent
makes, not just within one. That is what makes it useful at all: positions
recur heavily between consecutive moves of the same game (the position after
the opponent's reply is frequently a state this agent already explored several
plies deep while choosing its own previous move), so a table that survived
would let those searches reuse each other's work instead of starting cold
every time. The runner therefore MUST construct a fresh agent per game -
see docs/spec/technical-spec.md section 5.0 - and never reuse one across a
matchup: reusing one would let a table already saturated near its cap from a
finished game report a memory cap on an early move of the next one, an
attribution error with nothing to reveal it.

A consequence worth stating rather than discovering from the data: once the
table reaches `max_entries` partway through a game, every remaining decision
in that same game keeps hitting the cap too (nothing is ever evicted, so a
full table stays full), so `hit_memory_cap()` - and therefore the
`memory-limited` tag - becomes sticky for the rest of that game rather than a
per-move event. A high memory-limited fraction in the study's results should
be read as "the table saturated early in some games," not as "many
independent moves each happened to hit a cap."

`max_entries` is this agent's memory cap. It is set once, at construction,
from the config's `max_entries` key, and is never read from
SearchContext.max_nodes (SearchContext.max_nodes is informational only - see
agents/base.py). It is deliberately *not* the same number as MCTS's
`max_nodes`: a transposition entry here is a fixed 4-tuple, while an MCTS
tree node holds a full game state, a child mapping and counters - plausibly
five times the size per entry - so the two caps must be calibrated
separately to equal byte footprints (docs/spec/technical-spec.md section
4.2b), not treated as interchangeable counts.
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
    from the perspective of that state's side to move.

    The transposition table is created here, once, and closed over by `agent`
    below - it lives for the lifetime of the returned callable, i.e. for every
    decision this particular agent object ever makes. Callers must build a new
    agent per game (docs/spec/technical-spec.md section 5.0)."""
    table = {}

    def agent(game, state, ctx, rng):
        # An Alpha-Beta node is genuinely cheap, and this search visits far
        # more of them per decision than heuristic_agent or mcts_agent visit
        # of their own (much more expensive) units - up to tens of thousands
        # of nodes on Isolation. Left at the should_stop() default of 512,
        # that many nodes between clock checks can be a sizeable fraction of
        # an entire shallow-budget search (e.g. ~1500 nodes total on UTTT at
        # a 0.1s budget), so the clock check meant to enforce the budget
        # barely gets a chance to fire before the budget is already blown.
        # 16 keeps the residual overshoot to about a sixteenth of that full
        # 512-node block - a small single-digit percentage - while the extra
        # clock reads stay negligible. Contrast heuristic_agent and
        # mcts_agent, which set 1: their polled units (a one-ply evaluation,
        # a full MCTS rollout) are expensive enough that even checking every
        # single one adds no meaningful overhead.
        ctx.set_check_every(16)
        best_move = None

        for depth in itertools.count(1):
            try:
                value, move = _root(game, state, depth, ctx, table,
                                    evaluate, max_entries, best_move)
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


def _root(game, state, depth, ctx, table, evaluate, cap, first=None):
    """`first`, when given and still legal, is searched before anything else.

    The root state is never itself written to the table (only positions
    reached strictly inside the search are, since only those pass through
    _negamax), so _ordered has nothing to key on at the root; without this
    hint each new deepening iteration would re-derive the root's move order
    from scratch instead of trying last iteration's best move first, which is
    the single most valuable ordering signal iterative deepening produces.
    """
    moves = _ordered(game, state, table)
    if first is not None and first in moves and first != moves[0]:
        moves = [first] + [m for m in moves if m != first]
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
