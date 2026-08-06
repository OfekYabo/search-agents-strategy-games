"""Full round-robin tournament over the grid.

Trials are interleaved across matchups rather than grouped, so that thermal
drift or background load on the host affects every agent equally rather than
accumulating against whichever ran last. This is a correctness requirement of
the methodology, not an optimisation.

Run:  python3 -m experiments.tournament --games all --configs all --trials 20
"""
import argparse
import itertools
import os
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

from agents import alpha_beta_agent, heuristic_agent, mcts_agent, random_agent
from experiments import runner
from experiments.calibrate import BUDGETS
from experiments.logger import GameLogger

AGENTS = ("random", "heuristic", "alpha_beta", "mcts")

# Alpha-Beta entries and MCTS nodes are different sizes, so these are separate
# numbers calibrated to comparable byte footprints - never one shared value.
CAPS = {"max_entries": 200000, "max_nodes": 50000}


@dataclass(frozen=True)
class Cell:
    game: str
    config: str
    agent_first: str
    agent_second: str
    trial: int


def pairings():
    # type: () -> List[Tuple[str, str]]
    """All 12 directed matchups: every unordered pair in both seat orders."""
    out = []
    for a, b in itertools.combinations(AGENTS, 2):
        out.append((a, b))
        out.append((b, a))
    return out


def build_schedule(games, configs, trials):
    # type: (Tuple[str, ...], Tuple[str, ...], int) -> List[Cell]
    """Interleaved: trial 0 of every matchup, then trial 1, and so on. No two
    consecutive cells share a matchup."""
    schedule = []
    for trial in range(trials):
        for game in games:
            for config in configs:
                for first, second in pairings():
                    schedule.append(Cell(game, config, first, second, trial))
    return schedule


def _game_module(name):
    from games import ataxx, isolation, uttt
    return {"isolation": isolation, "ataxx": ataxx, "uttt": uttt}[name]


def _evaluator(name):
    from evaluation import ataxx_eval, isolation_eval, uttt_eval
    return {"isolation": isolation_eval, "ataxx": ataxx_eval,
            "uttt": uttt_eval}[name]


def _make_agent(name, ev):
    """A fresh agent per game. Alpha-Beta's table and MCTS's tree must never
    carry across games - a table saturated by a finished game would report a
    memory cap on an early move of the next one."""
    if name == "random":
        return random_agent.choose
    if name == "heuristic":
        return heuristic_agent.make(ev.evaluate)
    if name == "alpha_beta":
        return alpha_beta_agent.make(ev.evaluate,
                                     max_entries=CAPS["max_entries"])
    if name == "mcts":
        return mcts_agent.make(ev.evaluate, max_nodes=CAPS["max_nodes"])
    raise ValueError("unknown agent %r" % (name,))


def run(schedule, out_dir, workers=1, resume=True):
    # type: (List[Cell], str, int, bool) -> int
    games_path = os.path.join(out_dir, "games.csv")
    moves_path = os.path.join(out_dir, "moves.csv")
    logger = GameLogger(games_path, moves_path)
    done = logger.completed_ids() if resume else set()

    played = 0
    for index, cell in enumerate(schedule):
        game = _game_module(cell.game)
        ev = _evaluator(cell.game)
        budget = BUDGETS[cell.game][cell.config]
        config = {"name": cell.config, "time_budget_s": budget,
                  "max_nodes": CAPS["max_nodes"],
                  "max_entries": CAPS["max_entries"]}
        seed = runner.game_seed(cell.game, cell.agent_first, cell.agent_second,
                                cell.config, cell.trial)
        # Same function the runner uses - never re-derive the format here, or
        # --resume silently stops matching and re-runs completed games.
        record_id = runner.game_id(cell.game, cell.agent_first,
                                   cell.agent_second, cell.config, cell.trial)
        if record_id in done:
            continue
        agents = (_make_agent(cell.agent_first, ev),
                  _make_agent(cell.agent_second, ev))
        record = runner.play_game(
            game, agents, (cell.agent_first, cell.agent_second), config, seed,
            ply_cap=300, trial=cell.trial, workers=workers)
        logger.write(record)
        played += 1
        if played % 20 == 0:
            print("  %d/%d games" % (index + 1, len(schedule)))
            sys.stdout.flush()
    logger.close()
    return played


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="all")
    parser.add_argument("--configs", default="all")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--out", default="results/raw")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)

    games = (("isolation", "uttt", "ataxx") if args.games == "all"
             else tuple(args.games.split(",")))
    configs = (("easy", "main", "hard") if args.configs == "all"
               else tuple(args.configs.split(",")))
    schedule = build_schedule(games, configs, args.trials)
    print("scheduled %d games across %d matchups" % (len(schedule), 12))
    played = run(schedule, args.out, workers=args.workers,
                 resume=not args.no_resume)
    print("played %d games (rest already present)" % played)
    return 0


if __name__ == "__main__":
    sys.exit(main())
