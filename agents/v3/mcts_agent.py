# Agent version v3. See docs/VERSIONING.md - frozen once a tournament has
# run against it. Any fix after that is a new version, not an edit here.
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

The tree's node cap (`max_nodes`) is set here, at construction, and nowhere
else - it is never read from SearchContext.max_nodes. Alpha-Beta and MCTS are
therefore both explicitly memory bounded, but in the natural unit of their
own search structures; this implementation does not claim that one MCTS node
is byte-equivalent to one transposition-table entry.

V3 also retains the relevant MCTS subtree between consecutive decisions made
by the same agent. After our chosen move and the opponent's reply, if the new
position was already expanded below the retained branch, that child becomes
the new root. This recycles simulations that were already paid for while
still discarding every branch that is no longer reachable from actual play.
"""
import math
import random
from typing import Any, List

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
         rollout_depth=40, max_nodes=200000):
    # type: (Any, float, float, int, int, int) -> Any

    retained_root = None

    def agent(game, state, ctx, rng):
        nonlocal retained_root
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
        cap = max_nodes

        root = _reuse_root(retained_root, state)
        if root is None:
            root = _Node(state, None, None, list(game.legal_moves(state)))
            nodes = 1
            reused_nodes = 0
        else:
            root.parent = None
            root.move = None
            nodes = _subtree_size(root)
            reused_nodes = nodes

        # Drop any reference to the obsolete pre-re-root tree immediately;
        # otherwise its siblings would remain alive for the duration of this
        # decision even though they are no longer part of the bounded active
        # tree counted by `nodes`.
        retained_root = root

        ctx.set_mcts_reused_nodes(reused_nodes)

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
            reward = _rollout(game, node.state, rng, ctx, evaluate, epsilon,
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

        ctx.set_mcts_tree_nodes(nodes)
        if not root.children:
            # The chosen fallback has no corresponding expanded child to
            # retain, so the next decision must start cold.
            retained_root = None
            return rng.choice(root.untried)
        best = max(root.children, key=lambda n: n.visits)
        # Keep only the branch actual play can still enter. The opponent's
        # next move will be one of best.children if it was already expanded;
        # otherwise _reuse_root() will correctly start a fresh tree.
        best.parent = None
        retained_root = best
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


def _rollout(game, state, rng, ctx, evaluate, epsilon, sample_k, depth_cap):
    # type: (Any, Any, random.Random, Any, Any, float, int, int) -> float
    """Play out from `state`, returning a reward in [0, 1] from the perspective
    of the side to move at `state`."""
    root_side = state.side_to_move
    current = state

    for _ in range(depth_cap):
        # legal_moves() is also the terminal oracle in every game module.
        # Reusing this list avoids the old is_terminal()->legal_moves() call
        # followed immediately by a second legal_moves() call below.
        moves = game.legal_moves(current)
        if not moves:
            value = game.result(current)
            if current.side_to_move != root_side:
                value = -value
            return (value + 1.0) / 2.0

        # An anytime agent has to be interruptible at any point, not just at
        # rollout boundaries: a UTTT rollout costs ~25.8ms, and with no check
        # inside it the worst-case overshoot is bounded below by the cost of
        # one full rollout (the 35% overshoot this fix addresses). Stopping
        # here is not a special case - a rollout cut short by the clock is
        # just a shallower rollout, exactly like one cut short by depth_cap,
        # so it falls through to the same evaluate-and-map-to-[0,1] path
        # below rather than being discarded or returning a sentinel.
        if ctx.should_stop():
            break

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


def _reuse_root(retained_root, state):
    """Return the retained node matching the current real position.

    Consecutive calls to one agent are separated by exactly the opponent's
    move, so the expected match is a direct child of the branch retained after
    our previous move. Matching the root itself as a defensive case costs
    essentially nothing and makes the helper robust to pass-through callers.
    """
    if retained_root is None:
        return None
    if retained_root.state == state:
        return retained_root
    for child in retained_root.children:
        if child.state == state:
            return child
    return None


def _subtree_size(root):
    """Count nodes that remain reachable from `root` after re-rooting."""
    total = 0
    stack = [root]
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node.children)
    return total
