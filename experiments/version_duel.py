"""Head-to-head duel between two agent versions.

Separate from experiments.tournament on purpose: the tournament plays a field
of four different agents at one version, while this plays **one agent type
against itself across two versions**, holding the game, the budget and the
memory bound fixed. Only the version differs.

That is a *paired* design and it is far more sensitive than comparing each
version's score against a common field. The V3 grid could not resolve any
V2-to-V3 difference because a field score is diluted by three opponents that
did not change; here every game is a direct comparison.

    python3 -m experiments.version_duel --trials 40 --out results/duel

RNG: both seats always get **independent per-seat streams**, regardless of what
either version does in its own grid run. Shared-versus-separate streams is a
property of the *pair*, not of one agent - "shared" means seat A's draws depend
on how many numbers seat B consumed - so a duel cannot give one side each. Per
seat is the unbiased choice, and it has a useful side effect: it holds the RNG
change constant, so this experiment isolates the other V3 changes instead of
confounding all of them.

Crash-safe, like the tournament and unlike the self-play experiment: at nine
hours a run that lost everything on a stumble would be unaffordable. Move rows
are written and flushed before the game row, so a `game_id` present in
games.csv implies all of its moves are durable, and a restart resumes.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import sys

from agents.base import MoveTag, decide
from experiments import runner, tournament

GAME_COLUMNS = [
    "game_id", "game", "config", "agent", "trial",
    "first_version", "second_version", "winner", "plies", "end_reason",
    "seed", "time_budget_s", "max_nodes", "max_entries", "experiment",
]

MOVE_COLUMNS = [
    "game_id", "ply", "side", "version", "tag", "elapsed_s", "nodes",
    "simulations", "depth", "move", "legal_move_count",
    "tt_lookups", "tt_hits", "tt_size",
    "mcts_tree_nodes", "mcts_reused_nodes",
]

# The random agent is excluded: it ignores the evaluator, the search and the
# budget, so a duel of it against itself measures nothing about a version.
AGENTS = ("heuristic", "alpha_beta", "mcts")


def duel_seed(game, config, agent, trial):
    # type: (str, str, str, int) -> int
    """One base seed per (game, config, agent, trial).

    Deliberately NOT a function of which version sits first: both seat orders
    of the same trial share it, so the pair differs only in seating.
    """
    key = "duel|%s|%s|%s|%d" % (game, config, agent, trial)
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8],
                          "big")


def duel_game_id(game, config, agent, versions, trial):
    # type: (str, str, str, tuple, int) -> str
    return "%s.%s.%s.%s-%s.t%d" % (game, config, agent, versions[0],
                                   versions[1], trial)


def _play(game, config_name, budget, agent_name, versions, trial, caps,
          ply_cap=300):
    """One duel game. versions[0] plays first."""
    sources = [tournament.agent_source(v) for v in versions]
    evaluators = [tournament.evaluator_source(v, game.NAME) for v in versions]
    agents = tuple(sources[i].build(agent_name, evaluators[i].evaluate)
                   for i in (0, 1))

    seed = duel_seed(game.NAME, config_name, agent_name, trial)
    rngs = (random.Random(runner._side_seed(seed, 0)),
            random.Random(runner._side_seed(seed, 1)))

    gid = duel_game_id(game.NAME, config_name, agent_name, versions, trial)
    state = game.initial_state()
    move_rows = []
    ply = 0
    end_reason = None

    while True:
        legal = game.legal_moves(state)
        if not legal:
            end_reason = game.end_reason(state)
            break
        if ply_cap is not None and ply >= ply_cap:
            end_reason = "ply_cap"
            break

        side = state.side_to_move
        decision = decide(agents[side], game, state, budget,
                          caps["max_nodes"], rngs[side])
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
            "game_id": gid, "ply": ply, "side": side,
            "version": versions[side], "tag": tag,
            "elapsed_s": "%.6f" % decision.elapsed_s,
            "nodes": "" if decision.nodes is None else decision.nodes,
            "simulations": ("" if decision.simulations is None
                            else decision.simulations),
            "depth": "" if decision.depth is None else decision.depth,
            "move": move_str, "legal_move_count": len(legal),
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

    game_row = {
        "game_id": gid, "game": game.NAME, "config": config_name,
        "agent": agent_name, "trial": trial,
        "first_version": versions[0], "second_version": versions[1],
        "winner": runner._winner(game, state, end_reason),
        "plies": ply, "end_reason": end_reason, "seed": seed,
        "time_budget_s": budget,
        "max_nodes": caps["max_nodes"], "max_entries": caps["max_entries"],
        "experiment": "version_duel",
    }
    return game_row, move_rows


def completed_ids(games_path):
    # type: (str) -> set
    if not os.path.exists(games_path):
        return set()
    with open(games_path, newline="") as handle:
        return {r["game_id"] for r in csv.DictReader(handle) if r.get("game_id")}


def run(games, configs, agents, versions, trials, out_dir, ply_cap=300):
    os.makedirs(out_dir, exist_ok=True)
    games_path = os.path.join(out_dir, "games.csv")
    moves_path = os.path.join(out_dir, "moves.csv")
    done = completed_ids(games_path)

    games_new = not os.path.exists(games_path) or os.path.getsize(games_path) == 0
    moves_new = not os.path.exists(moves_path) or os.path.getsize(moves_path) == 0
    gf = open(games_path, "a", newline="")
    mf = open(moves_path, "a", newline="")
    gw = csv.DictWriter(gf, fieldnames=GAME_COLUMNS)
    mw = csv.DictWriter(mf, fieldnames=MOVE_COLUMNS)
    if games_new:
        gw.writeheader()
    if moves_new:
        mw.writeheader()

    # Interleaved by trial, exactly as the tournament is, so drift over a long
    # run reaches every cell equally instead of accumulating in whichever ran
    # last.
    played = skipped = 0
    total = len(games) * len(configs) * len(agents) * trials * 2
    for trial in range(trials):
        for game_name in games:
            game = tournament._game_module(game_name)
            for config_name in configs:
                budget = tournament.BUDGETS[game_name][config_name]
                for agent_name in agents:
                    for order in ((versions[0], versions[1]),
                                  (versions[1], versions[0])):
                        caps = getattr(tournament.agent_source(order[0]),
                                       "CAPS", tournament.CAPS)
                        gid = duel_game_id(game_name, config_name, agent_name,
                                           order, trial)
                        if gid in done:
                            skipped += 1
                            continue
                        row, moves = _play(game, config_name, budget,
                                           agent_name, order, trial, caps,
                                           ply_cap=ply_cap)
                        mw.writerows(moves)
                        mf.flush()
                        gw.writerow(row)
                        gf.flush()
                        played += 1
                        if played % 20 == 0:
                            print("  %d/%d games" % (played + skipped, total))
                            sys.stdout.flush()
    gf.close()
    mf.close()
    return played


def write_meta(path, games, configs, agents, versions, trials, out_dir):
    meta = {
        "experiment": "version_duel",
        "versions": list(versions),
        "games": list(games),
        "configs": list(configs),
        "agents": list(agents),
        "trials": trials,
        "rng_streams": "per_side",
        "rng_note": ("Both seats use independent per-seat streams regardless "
                     "of what either version does in its own grid run. Shared "
                     "streams are a property of the pair, not of one agent, so "
                     "a duel cannot give each side its own historical mode. "
                     "Holding it constant isolates the remaining changes."),
        "roster": dict(
            (v, dict((a, tournament.agent_source(v).params(a))
                     for a in agents)) for v in versions),
    }
    meta.update(tournament.host_info() and {"host": tournament.host_info()})
    meta["python"] = sys.version.split()[0]
    with open(path, "w") as handle:
        json.dump(meta, handle, sort_keys=True, indent=2)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="all")
    parser.add_argument("--configs", default="all")
    parser.add_argument("--agents", default=",".join(AGENTS))
    parser.add_argument("--versions", default="v2,v3")
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--out", default="results/duel")
    parser.add_argument("--ply-cap", type=int, default=300)
    args = parser.parse_args(argv)

    games = (("isolation", "uttt", "ataxx") if args.games == "all"
             else tuple(g.strip() for g in args.games.split(",") if g.strip()))
    configs = (("easy", "main", "hard") if args.configs == "all"
               else tuple(c.strip() for c in args.configs.split(",") if c.strip()))
    agents = tuple(a.strip() for a in args.agents.split(",") if a.strip())
    versions = tuple(v.strip() for v in args.versions.split(",") if v.strip())
    if len(versions) != 2 or versions[0] == versions[1]:
        raise ValueError("--versions needs two different versions, e.g. v2,v3")

    total = len(games) * len(configs) * len(agents) * args.trials * 2
    print("duel %s vs %s: %d games across %d cells"
          % (versions[0], versions[1], total,
             len(games) * len(configs) * len(agents)))
    os.makedirs(args.out, exist_ok=True)
    write_meta(os.path.join(args.out, "run_meta.json"), games, configs,
               agents, versions, args.trials, args.out)
    played = run(games, configs, agents, versions, args.trials, args.out,
                 ply_cap=args.ply_cap)
    print("played %d games (rest already present)" % played)
    return 0


if __name__ == "__main__":
    sys.exit(main())
