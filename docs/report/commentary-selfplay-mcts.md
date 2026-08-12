# Self-play time-scaling commentary - mcts

Hand-written interpretation, merged into `results/v3/selfplay-mcts.md` by
section id. That file is generated and any edit to it is lost on the next run.

<!-- section: selfplay-overview -->
This experiment exists because the main tournament **cannot** answer the budget
question. There, the agent and the budget change together - MCTS at 2.0 s faces
a heuristic that is also at 2.0 s - so a score difference never isolates time.
Here both seats are the same v3 agent with the same evaluator and the same
memory bound, and the **only** difference is the clock.

Both seat orders are played from the same base seed with independent per-seat
RNG streams, so a result cannot come from first-move advantage or from the
faster-searching side consuming random numbers the other would have drawn.

20 games per budget pair. That is enough to detect a large effect and not
enough to detect a small one; treat every interval accordingly.

<!-- section: selfplay-results -->
**More time reliably buys MCTS strength, and buys the most where MCTS is
weakest.** Five of nine budget pairs have intervals excluding 0.500, and all
three Ataxx pairs are among them:

| Ataxx | score for the larger budget |
|---|---|
| 0.5 s vs 0.1 s | **1.000** (20-0-0) |
| 2.0 s vs 0.1 s | **0.950** (19-0-1) |
| 2.0 s vs 0.5 s | **0.800** (16-0-4) |

A clean sweep at 0.5 s against 0.1 s is about as unambiguous as 20 games get.

**Read this next to the main tournament, because together they say something
neither says alone.** On Ataxx, MCTS at 2.0 s crushes MCTS at 0.1 s - and still
scores 0.113 against a one-ply heuristic. Extra time makes MCTS substantially
better *at being MCTS*. It does not move it toward the policy the heuristic
already has.

That is the sharpest available statement of finding F3. The failure on Ataxx is
not a resource shortage that more seconds would fix; it is the sampling approach
itself being a poor fit for a game 35 wide. The V3 grid made the same point from
the other direction by roughly doubling MCTS's simulations per root move with no
measurable gain against the heuristic.

**The effect is weaker on the narrow games**, which fits. Isolation shows 0.750
and 0.850 for the larger budget but only 0.700 at 2.0 s against 0.5 s, and UTTT
reaches 0.950 at 2.0 s against 0.1 s while its adjacent pairs sit at 0.700 and
0.625 with intervals containing 0.500. Diminishing returns are visible on games
where MCTS is already close to the ceiling: it needs far less time to play
Isolation well than to play Ataxx badly.

**Where an interval contains 0.500, that is not evidence that time does
nothing.** At 20 games the interval is roughly +/-0.2 wide. Four of the nine
pairs are simply unresolved.
