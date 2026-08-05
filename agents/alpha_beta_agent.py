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
