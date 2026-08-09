"""Plays one game between two agents and records everything about it."""
import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from agents.base import MoveTag, decide
from games.base import DRAW, LOSS, WIN


@dataclass(frozen=True)
class MoveRecord:
    ply: int
    agent: str
    side: int
    tag: str
    elapsed_s: float
    nodes: Optional[int]
    simulations: Optional[int]
    depth: Optional[int]
    move: str
    legal_move_count: int


@dataclass(frozen=True)
class GameRecord:
    game_id: str
    game: str
    config: str
    time_budget_s: float
    max_nodes: int
    agent_first: str
    agent_second: str
    winner: str            # "first" | "second" | "draw"
    plies: int
    end_reason: str
    seed: int
    workers: int
    max_entries: int = 0
    # Version and hyperparameters per agent, per game. run_meta.json holds
    # one roster for a whole run, which cannot describe a comparison run
    # where two versions of one agent carry different parameters in the
    # same game - these columns can.
    agent_first_version: str = "v1"
    agent_second_version: str = "v1"
    agent_first_params: str = "{}"
    agent_second_params: str = "{}"
    moves: List[MoveRecord] = field(default_factory=list)


def game_seed(game_name, agent_a, agent_b, config_name, trial):
    # type: (str, str, str, str, int) -> int
    """Deterministic per-game seed, so any single game can be replayed for
    debugging without re-running the tournament. Python's hash() is salted per
    process, so use a stable digest instead."""
    key = "|".join((game_name, agent_a, agent_b, config_name, str(trial)))
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def game_id(game_name, agent_a, agent_b, config_name, trial):
    # type: (str, str, str, str, int) -> str
    """Public so the tournament runner calls the exact same id function
    rather than re-deriving the format - two copies would silently desync
    and break --resume with no error."""
    return "%s.%s.%s-%s.t%d" % (game_name, config_name, agent_a, agent_b, trial)


def play_game(game, agents, agent_names, config, seed, ply_cap=None,
              trial=0, workers=1, clock=None, agent_versions=None,
              agent_params=None):
    # type: (Any, Tuple[Any, Any], Tuple[str, str], dict, int, Optional[int], int, int, Any) -> GameRecord
    """Play one complete game. Fully determined by `seed`.

    `ply_cap` is a runner-level guard, not a game rule. Ataxx needs one because
    jump moves leave the occupied-cell count unchanged, so the published rules
    do not guarantee termination - see docs/games/ataxx.md section 4.6. It lives
    here rather than in the state because putting a total ply count into the
    state would put it into the transposition-table key and destroy the table.

    agents.base.decide() is guaranteed to never raise: if the agent itself
    fails, decide() falls back to a random legal move, and if that fallback
    also fails (legal_moves() itself raises, or returns nothing to choose
    from) it returns a Decision with move=None and the ERROR tag instead of
    letting the exception escape. play_game must not call apply_move(None);
    it ends the game immediately, tagging it "agent_error" and scoring it a
    draw, since there is no principled way to say who would have won.

    decide() only substitutes a random legal move when the agent *raises*;
    it never checks that a returned move is actually legal. Random and
    Heuristic draw straight from legal_moves() so they cannot trigger this,
    but a search agent (Alpha-Beta, MCTS) could return a wrong-but-plausible
    move from a real bug - a stale transposition-table hit, an off-by-one in
    best-move bookkeeping - and apply_move() itself performs no validation
    (correct, since it runs at every search node). So play_game validates
    the returned move against legal_moves() itself: an illegal move ends the
    game immediately, tagged "illegal_move" and scored a draw, for the same
    reason as "agent_error" above - the game was never resolved, so there is
    no principled winner to report.
    """
    rng = random.Random(seed)
    state = game.initial_state()
    moves = []                      # type: List[MoveRecord]
    ply = 0
    end_reason = None

    kwargs = {} if clock is None else {"clock": clock}

    while True:
        if game.is_terminal(state):
            end_reason = game.end_reason(state)
            break
        if ply_cap is not None and ply >= ply_cap:
            end_reason = "ply_cap"
            break

        side = state.side_to_move
        legal = game.legal_moves(state)
        decision = decide(agents[side], game, state,
                          config["time_budget_s"], config["max_nodes"], rng,
                          **kwargs)
        agent_failed = decision.move is None
        illegal = not agent_failed and decision.move not in legal

        if illegal:
            tag = MoveTag.ERROR.value
            try:
                move_str = game.move_to_str(decision.move)
            except Exception:
                move_str = repr(decision.move)
        else:
            tag = decision.tag.value
            move_str = "--" if agent_failed else game.move_to_str(decision.move)

        moves.append(MoveRecord(
            ply=ply,
            agent=agent_names[side],
            side=side,
            tag=tag,
            elapsed_s=decision.elapsed_s,
            nodes=decision.nodes,
            simulations=decision.simulations,
            depth=decision.depth,
            move=move_str,
            legal_move_count=len(legal),
        ))
        ply += 1
        if illegal:
            end_reason = "illegal_move"
            break
        if agent_failed:
            end_reason = "agent_error"
            break
        state = game.apply_move(state, decision.move)

    winner = _winner(game, state, end_reason)

    # Sorted keys keep the CSV byte-deterministic across runs.
    versions = agent_versions or ("v1", "v1")
    params = agent_params or ({}, {})
    return GameRecord(
        game_id=game_id(game.NAME, agent_names[0], agent_names[1],
                        config["name"], trial),
        game=game.NAME,
        config=config["name"],
        time_budget_s=config["time_budget_s"],
        max_nodes=config["max_nodes"],
        agent_first=agent_names[0],
        agent_second=agent_names[1],
        winner=winner,
        plies=ply,
        end_reason=end_reason,
        seed=seed,
        workers=workers,
        max_entries=config.get("max_entries", 0),
        agent_first_version=versions[0],
        agent_second_version=versions[1],
        agent_first_params=json.dumps(params[0], sort_keys=True),
        agent_second_params=json.dumps(params[1], sort_keys=True),
        moves=moves,
    )


def _winner(game, state, end_reason):
    # type: (Any, Any, str) -> str
    if end_reason in ("ply_cap", "agent_error", "illegal_move"):
        # A ply-cap, agent-failure, or illegal-move ending gives no
        # principled winner: the game was cut off, not resolved, so scoring
        # it draw is the only choice that does not invent a result.
        return "draw"
    outcome = game.result(state)      # from the perspective of side_to_move
    if outcome == DRAW:
        return "draw"
    mover_won = outcome == WIN
    mover_is_first = state.side_to_move == 0
    return "first" if mover_won == mover_is_first else "second"
