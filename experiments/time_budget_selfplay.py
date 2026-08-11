"""Optional asymmetric-time self-play experiment for V3 search agents.

This module is intentionally separate from experiments.tournament. Importing or
running the normal tournament never schedules these games. It answers a
different question: holding the algorithm, evaluator, game and memory bound
fixed, how much playing strength is gained by increasing only the per-move time
budget?

Example:
    python -m experiments.time_budget_selfplay \
        --game ataxx --agent mcts --budgets 0.1,0.5,2.0 \
        --trials 10 --out results/time-selfplay/ataxx-mcts
"""
import argparse
import csv
import hashlib
import json
import os
import random
from itertools import combinations

from agents.base import MoveTag, decide
from agents import v3
from experiments import runner, tournament


GAME_COLUMNS = [
    "game_id", "game", "agent", "trial", "winner", "plies", "end_reason",
    "seed", "first_budget_s", "second_budget_s", "max_nodes", "max_entries",
    "experiment",
]

MOVE_COLUMNS = [
    "game_id", "ply", "side", "budget_s", "tag", "elapsed_s", "nodes",
    "simulations", "depth", "legal_move_count", "move", "tt_lookups",
    "tt_hits", "tt_size", "mcts_tree_nodes", "mcts_reused_nodes",
]


def _seed(game_name, agent_name, low, high, trial):
    """One base seed per unordered budget pair and trial.

    Both seat orders deliberately use the same base seed. V3 then derives two
    independent side streams, so swapping which budget occupies a seat does
    not let one side's extra simulations consume the opponent's RNG stream.
    """
    key = "%s|%s|%.12g|%.12g|%d" % (
        game_name, agent_name, min(low, high), max(low, high), trial)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _game_id(game_name, agent_name, first_budget, second_budget, trial):
    return "%s.%s.%.12g-vs-%.12g.t%d" % (
        game_name, agent_name, first_budget, second_budget, trial)


def _play(game, evaluate, agent_name, budgets, trial, seed, ply_cap=300):
    agents = (v3.build(agent_name, evaluate), v3.build(agent_name, evaluate))
    rngs = (random.Random(runner._side_seed(seed, 0)),
            random.Random(runner._side_seed(seed, 1)))
    state = game.initial_state()
    move_rows = []
    ply = 0
    end_reason = None
    gid = _game_id(game.NAME, agent_name, budgets[0], budgets[1], trial)

    while True:
        legal = game.legal_moves(state)
        if not legal:
            end_reason = game.end_reason(state)
            break
        if ply_cap is not None and ply >= ply_cap:
            end_reason = "ply_cap"
            break

        side = state.side_to_move
        budget = budgets[side]
        decision = decide(
            agents[side], game, state, budget, v3.CAPS["max_nodes"],
            rngs[side])
        agent_failed = decision.move is None
        illegal = not agent_failed and decision.move not in legal
        tag = MoveTag.ERROR.value if illegal else decision.tag.value

        if agent_failed:
            move_str = "--"
        else:
            try:
                move_str = game.move_to_str(decision.move)
            except Exception:
                move_str = repr(decision.move)

        move_rows.append({
            "game_id": gid,
            "ply": ply,
            "side": side,
            "budget_s": "%.12g" % budget,
            "tag": tag,
            "elapsed_s": "%.6f" % decision.elapsed_s,
            "nodes": "" if decision.nodes is None else decision.nodes,
            "simulations": ("" if decision.simulations is None
                            else decision.simulations),
            "depth": "" if decision.depth is None else decision.depth,
            "legal_move_count": len(legal),
            "move": move_str,
            "tt_lookups": ("" if decision.tt_lookups is None
                           else decision.tt_lookups),
            "tt_hits": "" if decision.tt_hits is None else decision.tt_hits,
            "tt_size": "" if decision.tt_size is None else decision.tt_size,
            "mcts_tree_nodes": ("" if decision.mcts_tree_nodes is None
                                else decision.mcts_tree_nodes),
            "mcts_reused_nodes": ("" if decision.mcts_reused_nodes is None
                                  else decision.mcts_reused_nodes),
        })
        ply += 1

        if illegal:
            end_reason = "illegal_move"
            break
        if agent_failed:
            end_reason = "agent_error"
            break
        state = game.apply_move(state, decision.move)

    winner = runner._winner(game, state, end_reason)
    game_row = {
        "game_id": gid,
        "game": game.NAME,
        "agent": agent_name,
        "trial": trial,
        "winner": winner,
        "plies": ply,
        "end_reason": end_reason,
        "seed": seed,
        "first_budget_s": "%.12g" % budgets[0],
        "second_budget_s": "%.12g" % budgets[1],
        "max_nodes": v3.CAPS["max_nodes"],
        "max_entries": v3.CAPS["max_entries"],
        "experiment": "time_selfplay",
    }
    return game_row, move_rows


def run(game_names, agent_name, budgets, trials, out_dir, ply_cap=300):
    if agent_name not in ("alpha_beta", "mcts"):
        raise ValueError("self-play time scaling is intended for alpha_beta or mcts")
    if len(set(budgets)) < 2:
        raise ValueError("provide at least two distinct time budgets")
    if any(b <= 0 for b in budgets):
        raise ValueError("time budgets must be positive")

    os.makedirs(out_dir, exist_ok=True)
    games_path = os.path.join(out_dir, "games.csv")
    moves_path = os.path.join(out_dir, "moves.csv")

    summary = {"experiment": "time_selfplay", "games": 0,
               "first_wins": 0, "second_wins": 0, "draws": 0,
               "higher_budget_wins": 0, "lower_budget_wins": 0}
    with open(games_path, "w", newline="") as gf, open(moves_path, "w", newline="") as mf:
        gw = csv.DictWriter(gf, fieldnames=GAME_COLUMNS)
        mw = csv.DictWriter(mf, fieldnames=MOVE_COLUMNS)
        gw.writeheader()
        mw.writeheader()

        for game_name in game_names:
            game = tournament._game_module(game_name)
            evaluate = tournament.evaluator_source("v3", game_name).evaluate
            for low, high in combinations(sorted(set(budgets)), 2):
                for trial in range(trials):
                    base_seed = _seed(game_name, agent_name, low, high, trial)
                    # Both seat orders: the only intended difference is which
                    # side receives the larger time budget.
                    for seat_budgets in ((low, high), (high, low)):
                        game_row, move_rows = _play(
                            game, evaluate, agent_name, seat_budgets, trial,
                            base_seed, ply_cap=ply_cap)
                        gw.writerow(game_row)
                        mw.writerows(move_rows)
                        summary["games"] += 1
                        if game_row["winner"] == "first":
                            summary["first_wins"] += 1
                            winner_budget = seat_budgets[0]
                        elif game_row["winner"] == "second":
                            summary["second_wins"] += 1
                            winner_budget = seat_budgets[1]
                        else:
                            summary["draws"] += 1
                            winner_budget = None
                        if winner_budget is not None:
                            if winner_budget == high:
                                summary["higher_budget_wins"] += 1
                            elif winner_budget == low:
                                summary["lower_budget_wins"] += 1

    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default="all",
                        help="isolation, ataxx, uttt, or all")
    parser.add_argument("--agent", choices=("alpha_beta", "mcts"), required=True)
    parser.add_argument("--budgets", default="0.1,0.5,2.0",
                        help="comma-separated per-move seconds")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--out", default="results/time-selfplay")
    parser.add_argument("--ply-cap", type=int, default=300)
    args = parser.parse_args(argv)

    game_names = (("isolation", "ataxx", "uttt") if args.game == "all"
                  else tuple(g.strip() for g in args.game.split(",") if g.strip()))
    budgets = tuple(float(x.strip()) for x in args.budgets.split(",") if x.strip())
    summary = run(game_names, args.agent, budgets, args.trials, args.out,
                  ply_cap=args.ply_cap)
    print("completed %d games: first=%d second=%d draws=%d" % (
        summary["games"], summary["first_wins"], summary["second_wins"],
        summary["draws"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
