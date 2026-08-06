"""Calibration: verify budgets are honoured, then fix the caps and rollout
parameters that measurement has not already settled.

Time budgets are NOT swept here. They were set by direct measurement of how much
search each agent obtains at each candidate budget, and are recorded in PLAN.md.
This module confirms them and settles what remains.

Run:  python3 -m experiments.calibrate
"""
import random
import statistics
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

from agents import alpha_beta_agent, heuristic_agent, mcts_agent, random_agent
from agents.base import MoveTag, decide

# easy means MORE time; hard means LESS. Set by measurement, see PLAN.md.
BUDGETS = {
    "isolation": {"easy": 0.5, "main": 0.1, "hard": 0.02},
    "ataxx": {"easy": 2.0, "main": 0.5, "hard": 0.1},
    "uttt": {"easy": 2.0, "main": 0.5, "hard": 0.1},
}

# MCTS is not meaningfully searching below this many simulations per root move;
# any conclusion drawn about it there describes the budget, not the algorithm.
VIABILITY_FLOOR = 10.0


@dataclass(frozen=True)
class AdherenceResult:
    agent: str
    budget: float
    mean_elapsed: float
    max_elapsed: float
    within_tolerance: bool


@dataclass(frozen=True)
class CapResult:
    agent: str
    cap: int
    memory_limited_fraction: float
    moves: int


@dataclass(frozen=True)
class RolloutResult:
    epsilon: float
    sample_k: int
    rollout_depth: int
    simulations: int
    per_root: float
    score: float


def _midgame(game, plies, seed=11):
    rng = random.Random(seed)
    s = game.initial_state()
    for _ in range(plies):
        if game.is_terminal(s):
            break
        s = game.apply_move(s, rng.choice(game.legal_moves(s)))
    return s


def check_budget_adherence(game, ev, agents, budgets, tolerance=0.10, samples=5):
    # type: (Any, Any, List[Tuple[str, Any]], Tuple[float, ...], float, int) -> List[AdherenceResult]
    """Phase 0 gate. An agent that overruns has not been constrained, so every
    later phase and the tournament would be measuring the wrong thing.

    This exists because MCTS once overshot a 0.02s budget by 1283% with no
    visible symptom: the CSV looked normal and every tag was plausible.
    """
    out = []
    for name, factory in agents:
        for budget in budgets:
            elapsed = []
            for i in range(samples):
                state = _midgame(game, plies=6, seed=100 + i)
                if game.is_terminal(state):
                    continue
                d = decide(factory(), game, state, budget, 200000,
                           random.Random(i))
                elapsed.append(d.elapsed_s)
            if not elapsed:
                continue
            mean_e = statistics.mean(elapsed)
            max_e = max(elapsed)
            out.append(AdherenceResult(
                agent=name, budget=budget, mean_elapsed=mean_e,
                max_elapsed=max_e,
                within_tolerance=max_e <= budget * (1.0 + tolerance)))
    return out


def sweep_memory_caps(game, ev, budget, caps, agent="alpha_beta", plies=40):
    # type: (Any, Any, float, Tuple[int, ...], str, int) -> List[CapResult]
    """Choose the cap at which `memory-limited` is a meaningful minority.

    The two agents' caps are NOT interchangeable: a transposition entry is a
    4-tuple while an MCTS node holds a full state, a child mapping and counters.
    They are swept separately and calibrated to comparable byte footprints.
    """
    out = []
    for cap in caps:
        if agent == "alpha_beta":
            make = lambda: alpha_beta_agent.make(ev.evaluate, max_entries=cap)
        else:
            make = lambda: mcts_agent.make(ev.evaluate, max_nodes=cap)
        rng = random.Random(5)
        state = game.initial_state()
        actor = make()
        tags = []
        played = 0
        while not game.is_terminal(state) and played < plies:
            d = decide(actor, game, state, budget, 200000, rng)
            tags.append(d.tag)
            state = game.apply_move(state, d.move)
            played += 1
        limited = sum(1 for t in tags if t == MoveTag.MEMORY_LIMITED)
        out.append(CapResult(agent=agent, cap=cap, moves=len(tags),
                             memory_limited_fraction=(
                                 limited / float(len(tags)) if tags else 0.0)))
    return out


def sweep_mcts_rollout(game, ev, budget, configs, trials=8, plies=20):
    # type: (Any, Any, float, Tuple[Tuple[float, int, int], ...], int, int) -> List[RolloutResult]
    """Select epsilon, sample_k and rollout_depth empirically.

    Only the exploration constant has a principled derivation. These three are
    domain-tuned hyperparameters everywhere in the literature, so they are
    measured against a fixed one-ply opponent rather than asserted.

    The range must include epsilon=1.0 (pure random rollouts) and sample_k=1: a
    prior sweep found the best configuration lay entirely outside a narrower
    range, because guidance costing k*D child evaluations per rollout starves the
    tree on wide games.
    """
    out = []
    probe = _midgame(game, plies)
    roots = max(1, len(game.legal_moves(probe)))
    for eps, k, depth in configs:
        mk = lambda: mcts_agent.make(ev.evaluate, epsilon=eps, sample_k=k,
                                     rollout_depth=depth)
        sims = decide(mk(), game, probe, budget, 200000, random.Random(1)).simulations
        wins = draws = 0
        for t in range(trials):
            rng = random.Random(700 + t)
            mc, hu = mk(), heuristic_agent.make(ev.evaluate)
            side = t % 2
            s = game.initial_state()
            played = 0
            while not game.is_terminal(s) and played < 400:
                actor = mc if s.side_to_move == side else hu
                d = decide(actor, game, s, budget, 200000, rng)
                s = game.apply_move(s, d.move)
                played += 1
            r = game.result(s) if played < 400 else 0.0
            if r == 0.0:
                draws += 1
            else:
                loser = s.side_to_move if r < 0 else 1 - s.side_to_move
                if loser != side:
                    wins += 1
        out.append(RolloutResult(
            epsilon=eps, sample_k=k, rollout_depth=depth, simulations=sims,
            per_root=sims / float(roots),
            score=(wins + 0.5 * draws) / float(trials)))
    return out


ROLLOUT_CANDIDATES = (
    (0.25, 8, 40), (0.25, 2, 40), (0.5, 2, 10),
    (0.8, 2, 10), (1.0, 1, 10), (1.0, 1, 400),
)

CAP_CANDIDATES_AB = (200, 2000, 20000, 200000)
CAP_CANDIDATES_MCTS = (50, 500, 5000, 50000)


def main():
    from evaluation import ataxx_eval, isolation_eval, uttt_eval
    from games import ataxx, isolation, uttt

    games = ((isolation, isolation_eval), (uttt, uttt_eval), (ataxx, ataxx_eval))

    print("=" * 70)
    print("PHASE 0 - budget adherence (GATE)")
    print("=" * 70)
    failures = 0
    for game, ev in games:
        agents = [
            ("random", lambda: random_agent.choose),
            ("heuristic", lambda ev=ev: heuristic_agent.make(ev.evaluate)),
            ("alpha_beta", lambda ev=ev: alpha_beta_agent.make(ev.evaluate)),
            ("mcts", lambda ev=ev: mcts_agent.make(ev.evaluate)),
        ]
        grid = tuple(sorted(BUDGETS[game.NAME].values()))
        for r in check_budget_adherence(game, ev, agents, grid):
            flag = "ok" if r.within_tolerance else "OVERRUN"
            if not r.within_tolerance:
                failures += 1
            print("  %-10s %-11s budget %-6.2f mean %-7.3f max %-7.3f  %s"
                  % (game.NAME, r.agent, r.budget, r.mean_elapsed,
                     r.max_elapsed, flag))
        sys.stdout.flush()
    if failures:
        print("\nPHASE 0 FAILED: %d agent/budget pairs overran. Stopping - every "
              "later phase would measure the wrong thing." % failures)
        return 1
    print("\nPHASE 0 PASSED")

    print("\n" + "=" * 70)
    print("PHASE 2 - memory caps")
    print("=" * 70)
    for game, ev in games:
        budget = BUDGETS[game.NAME]["main"]
        for label, agent, caps in (("alpha_beta", "alpha_beta", CAP_CANDIDATES_AB),
                                   ("mcts", "mcts", CAP_CANDIDATES_MCTS)):
            for r in sweep_memory_caps(game, ev, budget, caps, agent=agent):
                print("  %-10s %-11s cap %-8d memory-limited %5.1f%% of %d moves"
                      % (game.NAME, label, r.cap,
                         100.0 * r.memory_limited_fraction, r.moves))
            sys.stdout.flush()

    print("\n" + "=" * 70)
    print("PHASE 3 - MCTS rollout hyperparameters")
    print("=" * 70)
    for game, ev in games:
        budget = BUDGETS[game.NAME]["main"]
        print("  --- %s at %.2fs ---" % (game.NAME, budget))
        for r in sweep_mcts_rollout(game, ev, budget, ROLLOUT_CANDIDATES):
            note = "" if r.per_root >= VIABILITY_FLOOR else "  (below viability floor)"
            print("    eps%-5.2f k%-3d D%-5d sims %-6d per-root %-7.1f score %.2f%s"
                  % (r.epsilon, r.sample_k, r.rollout_depth, r.simulations,
                     r.per_root, r.score, note))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
