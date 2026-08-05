"""Monte Carlo Tree Search with UCT selection and a heuristic-guided rollout.

Rewards are mapped to [0, 1] in exactly one place - the rollout's return -
because UCB1's exploration term does not rescale with the reward, so every
published exploration constant assumes that range. Feeding it [-1, +1] would
halve exploration relative to value differences without anyone intending it.

Rollout policy is epsilon-greedy over at most sample_k candidates and truncated
at rollout_depth, returning the evaluator's value there. Pure random rollouts are
weak; pure greedy rollouts are deterministic and collapse the diversity the
Monte Carlo estimate depends on. These constants are hyperparameters, selected
empirically in the calibration pilot rather than asserted - only the exploration
constant has a principled derivation.
"""
import math
import random
from typing import Any, List, Optional

DEFAULT_EXPLORATION = math.sqrt(2)


class _Node(object):
    __slots__ = ("state", "parent", "move", "children", "untried",
                 "visits", "value")

    def __init__(self, state, parent, move, untried):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = []          # type: List[_Node]
        self.untried = untried      # type: List[Any]
        self.visits = 0
        # Accumulated reward from the perspective of the player who moved INTO
        # this node - i.e. the side to move at the parent. That is what lets
        # selection at a parent simply maximise child.value / child.visits.
        self.value = 0.0


def make(evaluate, exploration=DEFAULT_EXPLORATION, epsilon=0.25, sample_k=8,
         rollout_depth=40, max_nodes=None):
    # type: (Any, float, float, int, int, Optional[int]) -> Any

    def agent(game, state, ctx, rng):
        # A single simulation here is a full rollout (up to rollout_depth
        # steps, each considering up to sample_k evaluator calls), which is
        # far more expensive than the "one node visit" the default
        # check_every=512 assumes. Left at the default, the clock would only
        # be sampled every ~0.15-0.2s of real work regardless of the budget
        # requested, so a 0.05s and a 0.4s budget could both stop after the
        # same first batch of simulations - exactly the failure this
        # granularity mismatch produces. Poll every simulation instead, the
        # same fix heuristic_agent applies for its own cheap-decision case.
        ctx.set_check_every(1)
        root = _Node(state, None, None, list(game.legal_moves(state)))
        cap = max_nodes if max_nodes is not None else ctx.max_nodes
        nodes = 1

        while not ctx.should_stop():
            node = root

            # Selection: descend fully expanded nodes by UCB1.
            while not node.untried and node.children:
                node = _select(node, exploration)

            # Expansion, unless the tree is at its cap.
            if node.untried:
                if nodes < cap:
                    move = node.untried.pop(rng.randrange(len(node.untried)))
                    child_state = game.apply_move(node.state, move)
                    child = _Node(child_state, node, move,
                                  list(game.legal_moves(child_state)))
                    node.children.append(child)
                    nodes += 1
                    node = child
                else:
                    ctx.hit_memory_cap()

            # Simulation, then backpropagation with the perspective flipping at
            # every level.
            reward = _rollout(game, node.state, rng, evaluate, epsilon,
                              sample_k, rollout_depth)
            ctx.note_simulation()

            reward = 1.0 - reward       # into the parent-mover's perspective
            current = node
            while current.parent is not None:
                current.visits += 1
                current.value += reward
                reward = 1.0 - reward
                current = current.parent
            root.visits += 1

        if not root.children:
            return rng.choice(game.legal_moves(state))
        best = max(root.children, key=lambda n: n.visits)
        return best.move

    return agent


def _select(node, exploration):
    # type: (_Node, float) -> _Node
    log_parent = math.log(node.visits) if node.visits > 0 else 0.0
    best, best_score = None, -float("inf")
    for child in node.children:
        if child.visits == 0:
            return child
        score = (child.value / child.visits
                 + exploration * math.sqrt(log_parent / child.visits))
        if score > best_score:
            best, best_score = child, score
    return best


def _rollout(game, state, rng, evaluate, epsilon, sample_k, depth_cap):
    # type: (Any, Any, random.Random, Any, float, int, int) -> float
    """Play out from `state`, returning a reward in [0, 1] from the perspective
    of the side to move at `state`."""
    root_side = state.side_to_move
    current = state

    for _ in range(depth_cap):
        if game.is_terminal(current):
            value = game.result(current)
            if current.side_to_move != root_side:
                value = -value
            return (value + 1.0) / 2.0

        moves = game.legal_moves(current)
        if len(moves) == 1 or rng.random() < epsilon:
            move = rng.choice(moves)
        else:
            sample = (moves if len(moves) <= sample_k
                      else rng.sample(moves, sample_k))
            # A child's evaluation is from the opponent's perspective, so the
            # move that minimises it is the one that maximises ours.
            move = min(sample,
                       key=lambda m: evaluate(game, game.apply_move(current, m)))
        current = game.apply_move(current, move)

    value = evaluate(game, current)
    if current.side_to_move != root_side:
        value = -value
    return (value + 1.0) / 2.0
