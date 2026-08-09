"""Agent version v2.

Hyperparameters live here rather than in the harness, because they are
properties of an agent and two versions must be able to declare different
ones. In v1 they lived in experiments/tournament.py, which is what allowed
defect D4 - the tournament silently ran the rollout defaults that calibration
had ranked worst. See docs/VERSIONING.md.

Frozen once a tournament has run against it. Any fix after that is a new
version, not an edit here.
"""
from typing import Any, Dict

from agents.v2 import (alpha_beta_agent, heuristic_agent, mcts_agent,
                       random_agent)

VERSION = "v2"

AGENTS = ("random", "heuristic", "alpha_beta", "mcts")

# Alpha-Beta entries and MCTS nodes are different sizes, so these are separate
# numbers calibrated to comparable byte footprints - never one shared value.
CAPS = {"max_entries": 200000, "max_nodes": 50000}

# Selected by calibrate.py phase 3, not assumed. epsilon=1.0 with sample_k=1
# means pure random rollouts: no evaluator call inside the playout at all.
# Phase 3 scored this best on all three games.
MCTS_ROLLOUT = {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10}


def params(label):
    # type: (str) -> Dict[str, Any]
    """The hyperparameters this version gives `label`.

    Logged per game in games.csv, because a run-level roster cannot describe
    a comparison run where two versions of one agent carry different values.
    """
    if label == "alpha_beta":
        return {"max_entries": CAPS["max_entries"]}
    if label == "mcts":
        out = {"max_nodes": CAPS["max_nodes"]}
        out.update(MCTS_ROLLOUT)
        return out
    return {}


def build(label, evaluate):
    # type: (str, Any) -> Any
    """A fresh agent per game. Alpha-Beta's table and MCTS's tree must never
    carry across games - a table saturated by a finished game would report a
    memory cap on an early move of the next one."""
    if label == "random":
        return random_agent.choose
    if label == "heuristic":
        return heuristic_agent.make(evaluate)
    if label == "alpha_beta":
        return alpha_beta_agent.make(evaluate,
                                     max_entries=CAPS["max_entries"])
    if label == "mcts":
        return mcts_agent.make(evaluate, max_nodes=CAPS["max_nodes"],
                               **MCTS_ROLLOUT)
    raise ValueError("unknown agent %r" % (label,))
