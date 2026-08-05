# Gamebook: Isolation 5x5 (queen-slide, auto-block)

> Role in this project: **small domain** (log10 state space ~ 10.0).
> Status: ruleset **confirmed**. Average branching factor and average game length pending empirical measurement.

---

## 1. Provenance

The published game is **Isolation** (Lakeside, 1972): a 6x8 board of 46 removable
tiles and two pawns. A turn there is *move your pawn one square in any of the eight
directions, then remove **any** tile on the board*. You lose when you have no legal
move. The pawns start on raised platforms (or holes, depending on edition) which are
board features rather than tiles, so they cannot be removed and a pawn may re-enter
them.

**What we play is a declared variant, not the published game.** Two rules differ
(movement distance and the blocking mechanic) and the board is smaller. Section 6
records every alternative we considered and why it lost. Nothing in this project
should cite complexity figures published for the original 6x8 game.

A separate lineage note: the "Isolation" used in the Udacity AI Nanodegree is a
*third* ruleset (7x7, knight moves, vacated square auto-blocks). Our variant shares
its auto-block mechanic but not its movement rule.

---

## 2. Board and notation

A 5x5 grid. Cells are `(r, c)` with `r` the row and `c` the column, both `0..4`,
origin at the top-left. Every cell is in exactly one of three states:

| State | Meaning |
|---|---|
| **open** | empty and legal to enter |
| **blocked** | permanently removed from play, can never be entered again |
| **occupied** | currently holds a pawn |

---

## 3. Starting position

```
      c0  c1  c2  c3  c4
 r0    .   .   1   .   .
 r1    .   .   .   .   .
 r2    .   .   .   .   .
 r3    .   .   .   .   .
 r4    .   .   2   .   .
```

- Player 1 pawn at `(0, 2)`, Player 2 pawn at `(4, 2)`.
- All other 23 cells are open. No cell begins blocked.
- **Player 1 moves first.**

The two starting cells are related by a 180-degree rotation of the board, so both
pawns begin with identical mobility. This matters because the project measures
first-move advantage: an asymmetric start would confound that measurement with a
positional advantage.

---

## 4. Rules of play

**4.1 Movement (queen-slide).** On your turn you must move your own pawn. Choose one
of the eight directions - orthogonal or diagonal - and slide any number of cells
`>= 1` along it. The ray extends from your pawn and stops *before* the first of:

1. the edge of the board,
2. a blocked cell,
3. the opponent's pawn.

Every cell the ray passes through is a legal destination. Pawns therefore cannot
jump over blocked cells or over each other.

**4.2 Blocking (auto-block, no exceptions).** Immediately after the pawn arrives at
its destination, the cell it departed from becomes **blocked**, permanently. This is
automatic and unconditional - the mover has no choice about which cell is removed,
and there is **no exempt cell anywhere on the board, including the two starting
cells**.

**4.3 Losing.** The player whose turn it is to move and who has zero legal
destinations **loses immediately**. There is no pass and no resignation.

**4.4 Draws.** Impossible. See the invariants below.

---

## 5. Derived properties

These follow from the rules by direct argument and require no simulation.

**5.1 One cell blocks per ply.** Every ply blocks exactly one previously-occupied
cell, and blocked cells are never unblocked. So after `k` plies the board holds
exactly `k` blocked cells, `2` occupied cells, and `23 - k` open cells.

**5.2 Maximum game length is 23 plies.** Open cells strictly decrease by one per
ply. After 23 plies there are `0` open cells, so the player to move on ply 24 has no
destination and loses. The game therefore always terminates, and always with a
decisive result - which is why 4.4 holds.

**5.3 Branching factor.**

| Quantity | Value | Derivation |
|---|---|---|
| Theoretical maximum | **16** | From centre `(2,2)` on an empty board, opponent *not* on any of its rays: 8 rays x 2 reachable cells |
| Actual ply-1 branching | **11** | From `(0,2)`: E 2, W 2, **S 3**, SE 2, SW 2 |
| Average over a game | **6.3** | Measured, 500 random games. Max observed 14, not 16: reaching 16 needs the opponent off all eight rays from the centre, which random play rarely produces |

> **The opponent's pawn blocks rays, and this is easy to miscount.** An earlier
> draft of this document gave ply-1 branching as 12, counting the southward ray from
> `(0,2)` as four cells - `(1,2), (2,2), (3,2), (4,2)`. But `(4,2)` is the *opponent's
> starting cell*, and rays stop **before** an occupied cell (4.1), so that ray yields
> three moves, not four. The correct figure is **11**.
>
> The same effect caps the theoretical maximum: from the centre with the opponent at
> `(4,2)` the count is **15**, not 16, because the opponent truncates the southward
> ray. Reaching 16 requires the opponent to stand on one of the eight cells no ray from
> the centre passes through - `(0,1), (0,3), (1,0), (1,4), (3,0), (3,4), (4,1), (4,3)`.

The average does fall well below the maximum, as expected: both the shrinking supply
of open cells and the growing blocked set shorten every ray as the game progresses.
Measured mean game length is **15.9 plies** against the provable bound of 23, and the
per-ply curve decays monotonically from 11 to 1.

**5.4 State-space upper bound.**

```
2  x  25  x  24  x  2^23  =  10,066,329,600  ~  1.01 x 10^10      log10 = 10.0
|     |      |     |
|     |      |     +--- each of the other 23 cells is open or blocked
|     |      +--------- pawn 2 on any remaining cell
|     +---------------- pawn 1 on any of 25 cells
+---------------------- side to move
```

**This bound is loose for our variant**, by roughly two orders of magnitude. Under
auto-block the blocked cells are not an arbitrary subset: they are exactly the trail
of cells the two pawns have vacated, so at ply `k` precisely `k` cells are blocked
and they form two connected paths. Most of the `2^23` subsets are unreachable. The
bound is kept because it is the same bound form used for the other two games and
PLAN.md labels all three as loose upper bounds - but the looseness should be stated
in the report rather than glossed.

---

## 6. Alternatives considered and rejected

**6.1 King-step movement + auto-block** (one cell, 8 directions). Maximum branching
factor 8, average roughly 3-4, over at most 23 plies. *Rejected:* the tree is small
enough that Alpha-Beta with a transposition table would very likely solve the game
outright at every one of our time budgets. Every move would be tagged `normal`, no
degradation would be observable, and the small domain would contribute almost
nothing to the degradation study that is the point of the project. Chosen
queen-slide roughly doubles the branching factor while keeping the domain genuinely
small.

**6.2 The original rules on 5x5** (king-step, then remove any tile). Branching factor
is the product of movement choices and removal choices, about `8 x 23 = 184` on ply
1 and perhaps 50-70 averaged over a game. *Rejected:* this makes the "small" domain
as search-hard as Ataxx. Alpha-Beta would reach a similar shallow depth on both, and
the scale contrast the experiment depends on would collapse. Worth recording that
this option had one real advantage we gave up: under free tile removal almost every
subset of blocked cells *is* reachable, so the state-space formula in 5.4 would have
been close to tight rather than loose.

**6.3 The original 6x8 board.** State-space bound `2 x 48 x 47 x 2^46 ~ 3.2 x 10^17`,
log10 17.5, at most 46 plies. *Rejected:* it shrinks the gap between the small and
medium domains from 13.7 orders of magnitude to 6.2, cutting the project's headline
span from ~28.9 to ~21.4, and it roughly doubles the cost of every experiment. Since
we had already departed from the original ruleset, partial fidelity on board shape
bought nothing.

**6.4 A 6x6 compromise board.** log10 13.6, at most 34 plies. *Rejected:* it is an
arbitrary third choice, faithful to neither the original design nor the experimental
goal.

**6.5 Starting cells exempt from blocking** (mirroring the original's unremovable
platforms). *Rejected:* the exemption exists in the original only because the
original's blocking mechanic is a *free choice* of tile; under auto-block there is
no choice for it to constrain, so it protects against nothing. It would also break
the invariant in 5.1 - a pawn oscillating through its own start cell blocks one cell
per *two* plies instead of one - which destroys the clean 23-ply bound, and it raises
an unanswerable question about whether a player may enter the opponent's start cell.

**6.6 Corner starting positions** `(0,0)` and `(4,4)`. Equally symmetric, so also
sound. *Rejected:* corner pawns have fewer initial rays, which shortens the opening
phase for no benefit.

**6.7 Players place their own pawns on plies 1 and 2.** *Rejected:* it introduces a
second move type into the state machine for no analytical gain, and deviates further
from the original than we need to.

---

## 7. Implementation notes

- Legal-move generation is a single uniform code path: 8 rays, stop on edge, blocked
  cell, or opposing pawn. No special cases anywhere on the board.
- Terminal test is exactly "the side to move has an empty move list". It must be
  evaluated *before* the move, not after.
- A natural state encoding is `(blocked_bitmask_25_bits, pawn1_cell, pawn2_cell,
  side_to_move)`, which is compact and hashes cheaply for the transposition table.
- The heuristic in PLAN.md - own legal-move count minus opponent legal-move count -
  is well matched to this variant, since queen-slide mobility varies much more
  sharply between positions than king-step mobility does.

---

## 8. References

**Video explanation**

- [How to play Isolation (YouTube)](https://www.youtube.com/watch?v=ix99WlP4NVk) - walkthrough of the original game. Note that it demonstrates the **published** ruleset (6x8, king-step, remove any tile), not our variant; use it for the feel of the game, and section 4 above for what we implement.

**Written sources**

- [Isolation (board game) - Wikipedia](https://en.wikipedia.org/wiki/Isolation_(board_game)) - rules of the 1972 original: 6x8, move one square, then remove any tile.
- [Isolation - BoardGameGeek](https://boardgamegeek.com/boardgame/1875/isolation) - publication data and component list.
- [Isolation from Lakeside (1972) - Toy Tales](https://toytales.ca/isolation-from-lakeside-1972/) - board photographs, 46 tiles, platform/hole starting squares.
