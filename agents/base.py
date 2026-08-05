"""Agent contract, resource budget, and the tagged decision wrapper.

The budget is passed *into* the search rather than wrapped around it, so the
clock check, node counting and memory cap live inside the search loop where
the phenomenon being studied actually happens. See docs/spec/technical-spec.md
section 4.

An agent is any callable:

    agent(game, state, ctx: SearchContext, rng: random.Random) -> move
"""
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class MoveTag(str, Enum):
    NORMAL = "normal"
    TIME_LIMITED = "time-limited"
    MEMORY_LIMITED = "memory-limited"
    ERROR = "error"


@dataclass(frozen=True)
class Decision:
    move: Any
    tag: MoveTag
    elapsed_s: float
    nodes: int
    simulations: Optional[int]
    depth: Optional[int]
    error: Optional[str]


class SearchContext:
    """The resource budget an agent searches inside.

    should_stop() polls the wall clock only once every `check_every` calls, so
    timing overhead stays negligible even when called at every node. PLAN.md
    specifies checking every ~500-1000 nodes.
    """

    def __init__(self, time_budget_s, max_nodes, check_every=512,
                 clock=time.monotonic):
        self._budget = time_budget_s
        self.max_nodes = max_nodes
        self._check_every = check_every
        self._clock = clock
        self._start = clock()
        self._since_poll = 0
        self._stopped = False
        self.nodes = 0
        self.simulations = 0
        self.memory_capped = False
        self.finished = False

    def should_stop(self):
        # type: () -> bool
        if self._stopped:
            return True
        self._since_poll += 1
        if self._since_poll < self._check_every:
            return False
        self._since_poll = 0
        if self._clock() - self._start >= self._budget:
            self._stopped = True
        return self._stopped

    def note_node(self):
        # type: () -> None
        self.nodes += 1

    def note_simulation(self):
        # type: () -> None
        self.simulations += 1

    def hit_memory_cap(self):
        # type: () -> None
        self.memory_capped = True

    def completed(self):
        # type: () -> None
        self.finished = True

    def elapsed(self):
        # type: () -> float
        return self._clock() - self._start


def decide(agent, game, state, time_budget_s, max_nodes, rng,
           check_every=512, clock=time.monotonic):
    # type: (Any, Any, Any, float, int, Any, int, Any) -> Decision
    """Run one agent decision under budget and tag the outcome.

    Tag precedence, top down (spec section 4.3):
      1. an exception escaped          -> ERROR
      2. the agent called completed()  -> NORMAL
      3. the agent called hit_memory_cap() at any point -> MEMORY_LIMITED
      4. otherwise                     -> TIME_LIMITED

    Memory outranks time because it is the rarer and more informative event: if
    the cap bound at all, that is the finding, even though the clock also ran
    out afterwards.
    """
    ctx = SearchContext(time_budget_s, max_nodes, check_every=check_every,
                        clock=clock)
    error = None
    depth = None
    try:
        move = agent(game, state, ctx, rng)
    except Exception:
        error = traceback.format_exc(limit=3)
        # Fall back to a legal move so the game and the tournament continue.
        move = rng.choice(game.legal_moves(state))

    if error is not None:
        tag = MoveTag.ERROR
    elif ctx.finished:
        tag = MoveTag.NORMAL
    elif ctx.memory_capped:
        tag = MoveTag.MEMORY_LIMITED
    else:
        tag = MoveTag.TIME_LIMITED

    return Decision(
        move=move,
        tag=tag,
        elapsed_s=ctx.elapsed(),
        nodes=ctx.nodes,
        # Reported only by agents that actually run simulations, so the CSV
        # column stays empty for Alpha-Beta rather than reading a misleading 0.
        # Auto-detected rather than passed in by the caller: a flag would have
        # to be threaded through play_game, and forgetting it would silently
        # drop every MCTS simulation count.
        simulations=ctx.simulations if ctx.simulations else None,
        depth=getattr(ctx, "depth_reached", None),
        error=error,
    )
