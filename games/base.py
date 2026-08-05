"""Shared types and the conformance checker for game modules.

A "game" is a module (or any namespace) exposing pure functions:

    initial_state() -> S
    legal_moves(s: S) -> List[M]        # [] if and only if terminal
    apply_move(s: S, m: M) -> S
    is_terminal(s: S) -> bool
    result(s: S) -> float               # WIN / DRAW / LOSS for side_to_move
    end_reason(s: S) -> str
    move_to_str(m: M) -> str
    str_to_move(text: str) -> M

Rules for each game are specified in docs/games/, which is authoritative.
"""
from typing import Any, Callable, Optional

WIN = 1.0
DRAW = 0.0
LOSS = -1.0

_RESULTS = (WIN, DRAW, LOSS)


class ConformanceError(AssertionError):
    """A game module violated the interface contract."""


def _default_side_of(state):
    return state.side_to_move


def check_conformance(game, rng, n_games=200, max_plies=1000, side_of=None):
    # type: (Any, Any, int, int, Optional[Callable[[Any], int]]) -> None
    """Play random games, raising ConformanceError on any contract violation.

    Checks, at every ply of every game:
      - is_terminal(s) agrees exactly with legal_moves(s) being empty
      - result() at a terminal state is one of WIN / DRAW / LOSS
      - move strings round-trip: str_to_move(move_to_str(m)) == m
      - apply_move returns a new state and flips the side to move
      - no game exceeds max_plies
    """
    if side_of is None:
        side_of = _default_side_of

    for game_index in range(n_games):
        state = game.initial_state()
        for ply in range(max_plies + 1):
            terminal = game.is_terminal(state)
            moves = game.legal_moves(state)

            if terminal != (len(moves) == 0):
                raise ConformanceError(
                    "game %d ply %d: is_terminal()=%r but legal_moves() has %d "
                    "entries; they must agree exactly"
                    % (game_index, ply, terminal, len(moves))
                )

            if terminal:
                outcome = game.result(state)
                if outcome not in _RESULTS:
                    raise ConformanceError(
                        "game %d ply %d: result()=%r is not one of %r"
                        % (game_index, ply, outcome, _RESULTS)
                    )
                if not isinstance(game.end_reason(state), str):
                    raise ConformanceError(
                        "game %d ply %d: end_reason() must return str"
                        % (game_index, ply)
                    )
                break

            move = rng.choice(moves)
            restored = game.str_to_move(game.move_to_str(move))
            if restored != move:
                raise ConformanceError(
                    "game %d ply %d: move string did not round-trip: "
                    "%r -> %r -> %r"
                    % (game_index, ply, move, game.move_to_str(move), restored)
                )

            before = side_of(state)
            try:
                state = game.apply_move(state, move)
            except ConformanceError:
                raise
            except Exception as exc:
                raise ConformanceError(
                    "game %d ply %d: apply_move(%r) raised %s: %s"
                    % (game_index, ply, move, type(exc).__name__, exc)
                )
            if side_of(state) == before:
                raise ConformanceError(
                    "game %d ply %d: apply_move did not flip side_to_move"
                    % (game_index, ply)
                )
        else:
            raise ConformanceError(
                "game %d did not terminate within %d plies"
                % (game_index, max_plies)
            )
