# Gamebooks and shared conventions

One gamebook per game, each formalising the exact ruleset we implement, the starting
position, derived complexity properties, and the alternative rulesets considered and
rejected.

| Game | Role | log10 state space | Status |
|---|---|---|---|
| [Isolation 5x5](isolation.md) | small domain | 10.0 | ruleset confirmed |
| [Ataxx 7x7](ataxx.md) | medium domain | 23.7 | ruleset confirmed |
| [Ultimate Tic-Tac-Toe](ultimate-tic-tac-toe.md) | large domain | 39.9 | ruleset confirmed; bound to be tightened at implementation |

Each gamebook is the authority for its own rules. This file holds only what must be
**identical across all three**, because the experiment compares agents *across*
domains - anything that differs per game becomes a confound.

---

## Terminal reward scale

**Every game returns `+1` for a win, `0` for a draw, `-1` for a loss, from the
perspective of the player to move.** No game deviates.

Isolation never returns `0`, since draws are impossible there (see its section 5.2).
That is fewer values on the same scale, not a different scale.

**Alpha-Beta** consumes this directly - negamax flips perspective with `-v`, which is
exactly why the scale is symmetric about zero.

**MCTS converts to `[0, 1]` via `(v + 1) / 2`**, in one place, immediately before
backpropagation.

> **Why the conversion exists.** Alpha-Beta is invariant to any increasing affine
> transform of the reward, so the scale is free as far as it is concerned. UCB1 is
> not: in `mean + C * sqrt(ln N / n)` the mean rescales with the reward but the
> exploration term does not, so changing the value range silently changes how much
> the agent explores. Every published exploration constant - `C = sqrt(2)` and
> friends - assumes rewards in `[0, 1]`. Feeding it `[-1, +1]` unchanged halves
> exploration relative to value differences without anyone intending it.

> **Why the loss value must sit strictly below the draw value.** A scale of
> `win = 1, draw = 0, loss = 0` makes drawing and losing indistinguishable, so an
> agent in a lost position has no reason to salvage a draw. Ataxx and Ultimate
> Tic-Tac-Toe both reach draws, so this would surface as a strength difference in the
> win/draw/loss tables that has nothing to do with search quality.

---

## Perspective convention

All values, evaluations and rewards are **from the perspective of the player to
move**, never from a fixed player's. This is what makes a single negamax routine
correct for both players, and it must hold in the evaluation functions too - an
evaluation written from Player 1's fixed perspective will silently invert on every
other ply.

---

## Move notation

Every game defines a **round-trippable string form** for its moves: parsing a logged
move string must reproduce the same move object. This is what makes the CSV logs
replayable and lets a logged game be checked against an external implementation.

Per-game formats are defined in each gamebook (for example, Ataxx section 2).

---

## Terminal detection

The terminal test is evaluated **before** the side to move acts, never after their
opponent's move. Games where "no legal move" is meaningful differ in what it means,
and the difference is easy to get wrong:

| Game | No legal move for the side to move |
|---|---|
| Isolation | that player **loses** |
| Ataxx | that player **passes**; losing requires zero pieces (see 4.4) |
| Ultimate Tic-Tac-Toe | reachable only when every local board is decided, which is a **draw** unless a global line exists |

---

## Game length bounds

Every game must have a provable or enforced maximum length, so no tournament run can
hang.

| Game | Bound | Source |
|---|---|---|
| Isolation 5x5 | 23 plies | provable - one cell blocks per ply |
| Ataxx 7x7 | 300 plies | **enforced** - the published rules do not terminate (see 4.6) |
| Ultimate Tic-Tac-Toe | 81 plies | provable - one cell filled per ply, never vacated |
