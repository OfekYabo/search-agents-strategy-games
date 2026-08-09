"""Screen candidate evaluators: one-ply agent against random, one game.

A focused A/B harness, separate from the tournament, so a candidate can be
rejected in seconds rather than after a ten-hour grid run.

**This module contains no evaluation logic.** The candidates live in
`evaluation/v3/isolation_eval.py` beside the one in use, and are imported here.
A copy of the mobility calculation living in this file could drift from the one
that ships, and the screening would then measure something other than what a
run would actually use - the same shape of defect as D9.

Standard library only, like the rest of the measurement path.

Run:  python3 -m experiments.compare_evaluators
      python3 -m experiments.compare_evaluators --seeds 1000

What this does NOT tell you, and both matter:

  - It measures play against the RANDOM agent only. Beating random better does
    not guarantee beating MCTS or Alpha-Beta better.
  - The evaluator is injected into three agents, not one. A change moves
    Alpha-Beta and MCTS too. On Isolation, MCTS consults the evaluator in only
    1.8-17% of its rollouts, so the effect there may be near zero.

Use it to screen. Use a v2-versus-v3 tournament to decide.
"""
import argparse
import random
import sys

from agents import base
from agents.v3 import heuristic_agent
from evaluation.v3 import isolation_eval
from experiments.analyse import wilson_interval
from games import isolation

# Named candidates, in the order they are reported. `evaluate` is whichever
# one the module currently binds, so it always appears under its own name.
CANDIDATES = (
    ("mobility_difference", isolation_eval.mobility_difference),
    ("aggressive", isolation_eval.aggressive),
    ("ratio", isolation_eval.ratio),
    ("reach", isolation_eval.reach),
    ("mixed", isolation_eval.mixed),
)


def play_against_random(evaluate, seeds, budget=0.02):
    # type: (object, object, float) -> tuple
    """Both seat orders per seed, so seat advantage cannot skew the result."""
    agent = heuristic_agent.make(evaluate)
    wins = draws = losses = 0
    for seed in seeds:
        for agent_first in (True, False):
            rng = random.Random(seed)
            state = isolation.initial_state()
            ply = 0
            while not isolation.is_terminal(state):
                agent_to_move = (ply % 2 == 0) == agent_first
                if agent_to_move:
                    move = agent(isolation, state,
                                 base.SearchContext(budget, 50000), rng)
                else:
                    move = rng.choice(isolation.legal_moves(state))
                state = isolation.apply_move(state, move)
                ply += 1
            # The side to move at a terminal state is the one with no moves.
            loser_is_first = (ply % 2 == 0)
            if isolation.result(state) == 0:
                draws += 1
            elif loser_is_first == agent_first:
                losses += 1
            else:
                wins += 1
    return wins, draws, losses


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=300)
    args = parser.parse_args(argv)

    in_use = None
    for name, function in CANDIDATES:
        if function is isolation_eval.evaluate:
            in_use = name

    seeds = range(args.seeds)
    print("Isolation: one-ply agent vs random, %d seeds x both seats = %d games"
          % (args.seeds, args.seeds * 2))
    print("evaluation/v3/isolation_eval.py currently binds: %s\n" % in_use)
    print("%-22s %8s  %-18s %s" % ("evaluator", "score", "95% CI", "W-D-L"))
    rows = []
    for name, evaluate in CANDIDATES:
        wins, draws, losses = play_against_random(evaluate, seeds)
        result = wilson_interval(wins, draws, losses)
        rows.append((result["score"], name, result, wins, draws, losses))
    for score, name, result, wins, draws, losses in sorted(rows, reverse=True):
        marker = "  <- in use" if name == in_use else ""
        print("%-22s %8.3f  [%.3f, %.3f]     %d-%d-%d%s"
              % (name, score, result["ci_low"], result["ci_high"],
                 wins, draws, losses, marker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
