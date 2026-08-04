# Gamebook: Ultimate Tic-Tac-Toe

> Role in this project: **large domain** (log10 state space ~ 39.9, see 5.1).
> Status: ruleset **confirmed**. The state-space bound is to be tightened when the
> game is implemented (5.1).

---

## 1. Provenance

Ultimate Tic-Tac-Toe (also seen as "super", "meta", or "nine-board" tic-tac-toe) has
no single publisher and no single canonical rulebook. It circulates as a folk game
with a stable core - nine 3x3 local boards inside a 3x3 global board, and a move
sends the opponent to the correspondingly-positioned local board - and **unstable
edges**, chiefly around what happens to boards that are already decided.

That instability is the reason this document exists. Two implementations can both
call themselves Ultimate Tic-Tac-Toe and disagree about legal moves. Section 4 pins
down our reading; section 6 records the alternatives.

The game was popularised by a 2013 Math with Bad Drawings post, which is where most
online rule statements ultimately trace back to - including the recommendation that a
tied local board count for neither player (4.5).

**On "regular" versus "advanced" rules.** Some presentations of the game offer two
modes: a plain one where you may play anywhere, and an "advanced" one that adds the
send rule. **We implement the send rule** - it is what makes the game Ultimate
Tic-Tac-Toe rather than nine unrelated tic-tac-toe boards, and every complexity figure
in section 5 assumes it. Without the send constraint the state-space bound loses its
factor of 10 and the game loses essentially all of its strategic depth, so the
distinction is not a variant we could take either side of.

*Caveat on terminology:* the regular/advanced labelling appears in some published
presentations of the game, but we could not confirm it as standard naming across
sources. The substance is not in doubt; only the labels are.

---

## 2. Board and notation

Nine **local boards** arranged in a 3x3 **global board**. Both are indexed `0..8` in
reading order:

```
   global board          cell index within
   (local board id)      each local board

    0 | 1 | 2             0 | 1 | 2
   ---+---+---           ---+---+---
    3 | 4 | 5             3 | 4 | 5
   ---+---+---           ---+---+---
    6 | 7 | 8             6 | 7 | 8
```

A move is a pair `(b, c)`: play in local board `b`, cell `c`. Because both indexings
use the same 0..8 scheme, the send rule is simply "your cell index becomes their
board index".

Each local board has a status: **undecided**, **won by P1**, **won by P2**, or
**drawn**.

---

## 3. Starting position

All 81 cells empty, all nine local boards undecided, no send constraint in force.
**Player 1 moves first and may play any of the 81 cells.**

---

## 4. Rules of play

**4.1 The send rule.** After a move at `(b, c)`, the opponent must play in local
board `c`.

**4.2 The free-choice exception.** If local board `c` is **not undecided** - that is,
it has been won by either player or has been drawn - the send constraint is void and
the opponent may play in **any undecided local board**.

**4.3 Decided boards are closed.** *[CONFIRMED - and this is the standard rule]* Once
a local board is won or drawn, **no further moves may be played in it**, even if it
still has empty cells. Its remaining empty cells are dead for the rest of the game.

> Earlier drafts of this document called this the game's one genuinely contested rule,
> on the grounds that sources stated the free-choice exception but not the closure.
> **That was too cautious.** Wikipedia's dedicated article states it directly: "the
> standard rules do not permit continued play in decided local boards", and names the
> opposite reading as an explicit *variant*. Our choice is the standard rule, not a
> judgement call.
>
> The variant is also **solved**, which settles the matter for our purposes - see 6.1.

**4.4 Winning a local board.** Three of your marks in a row - horizontally,
vertically, or diagonally - wins that local board immediately.

**4.5 Drawing a local board.** A local board that becomes full with no three-in-a-row
is **drawn**. A drawn board **counts for neither player** and can never form part of
any global line.

**4.6 Winning the game.** Three local boards won by the same player, in a row on the
global board, wins the game immediately - checked as soon as a local board is won.

**4.7 Drawing the game.** If no legal move exists - every local board is decided -
and no player holds a global line, the game is a **draw**. Draws are a normal,
frequent outcome here and the tournament logging must treat them as a first-class
result, unlike Isolation where they cannot occur.

**4.8 Early draw detection.** *[ADOPTED]* The game is also drawn **as soon as neither
player can still complete a global line**, without playing the remaining boards out.

A global line is still winnable by player `P` exactly when none of its three local
boards is won by the opponent or drawn - that is, every board on the line is either
already won by `P` or still undecided. If no line satisfies this for either player,
no sequence of legal moves can produce a winner, so the result is a draw and the
game ends immediately.

*Why this is safe.* It is **outcome-preserving, not a rule change**. Playing on from
such a position cannot produce a winner by definition, so both the early-terminated
game and the played-out game score as a draw. It never changes who wins.

*Why it is worth doing.* The saving is not mainly in the real games - it is in the
**search**. The terminal test runs at every node both agents expand, and this test
collapses entire subtrees the moment a draw becomes inevitable, which happens well
before the boards fill. It is also the natural home for the observation that drives
it: a local board lost to the opponent kills every global line through it, and a
drawn board kills those lines for *both* players, so dead lines accumulate quickly.

*Cost.* Negligible. Precompute the 8 global lines once; the check is 8 lines x 3
boards x 2 players, and it only needs re-running when a local board's status changes
- at most 9 times per game, not once per ply. Roughly six lines of code.

> **Declare this in the report.** Average game length is a reported metric, and this
> optimisation shortens it relative to an implementation that plays every board out.
> The figure is still correct for our implementation; it simply is not comparable to
> one that lacks the check.

---

## 5. Derived properties

**5.1 State-space upper bound.** PLAN.md currently gives:

```
2  x  3^81  =  2 x 4.44 x 10^38  ~  8.89 x 10^38          log10 = 38.9
```

**This omits part of the state.** Which local board the player to move is sent to is
not derivable from the cell contents alone - two identical-looking positions can have
different legal moves - so the send constraint is a genuine state component, with 10
values (nine boards, or unconstrained):

```
2  x  10  x  3^81  ~  8.89 x 10^39                        log10 = 39.9
```

**Adopted: the second form**, shown with this derivation, on the grounds that it is
simply the more truthful bound. It is more defensible under questioning, and it
barely moves the narrative - the project's span goes from ~28.9 to ~29.9 orders of
magnitude.

Both remain loose upper bounds. Neither excludes unreachable configurations, of which
there are very many - any position where both players hold a completed line, any
position where one player has played more than one move more than the other, and
every configuration inside a local board that could not arise from alternating play.

> **To revisit when the game is implemented.** A materially tighter bound is
> reachable once the rules are in code: counting only local-board configurations
> legally reachable under alternating play, and accounting for the fact that the send
> constraint is *determined* by the previous move's cell index rather than free. That
> work is worth doing properly with the implementation in front of us rather than
> guessed at now, and it may change the headline figure again.

**5.2 Branching factor.** This is where PLAN.md's "common case bounded by 9" needs
care:

| Situation | Branching factor |
|---|---|
| Ply 1 | **81** |
| Sent to an undecided board (the usual case) | **<= 9**, and falls as that board fills |
| Free choice (sent to a decided board) | **all empty cells in all undecided boards** - up to ~70 early on |
| Average over a game | *pending* - to be measured by the random agent |

The free-choice case cannot arise before ply 5, since a local board needs at least
three of one player's marks to be won. It becomes common in the middle game, and it
produces branching-factor spikes far above 9. A search implementation that assumes a
hard cap of 9 will be wrong.

**5.3 Game length.** Exactly one cell is filled per ply and no cell is ever vacated,
so the game lasts **at most 81 plies**. In practice it ends well short of that, for
two compounding reasons: cells inside decided boards are abandoned (4.3), and drawn
games are cut off as soon as the draw becomes inevitable (4.8). The average is
*pending* measurement.

**5.4 Note for the report.** UTTT has by far the largest state space of the three
games and by far the *smallest* typical branching factor. Its size comes from
**depth** - up to 81 plies - not width. This is the cleanest illustration in the
project that "state-space size" and "search difficulty" are different axes, and it
should be expected to affect the two paradigms differently: deep-and-narrow suits
iterative-deepening Alpha-Beta, whereas MCTS's advantage usually shows up in
wide-and-shallow domains like Ataxx.

**5.5 There is a published prediction about this game, and our experiment tests it.**

Wikipedia's article states that Ultimate Tic-Tac-Toe "cannot be reasonably solved
using any brute-force tactics", that minimax-style search struggles because the game
"lacks any simple heuristic evaluation function", and that Monte Carlo tree search
algorithms "have no problem in playing this game" and "can consistently beat human
opponents".

That is a direct, testable claim about the exact comparison this project makes, on
this exact game - **MCTS should beat Alpha-Beta here, and the stated mechanism is the
weakness of the evaluation function, not the size of the tree.** Two consequences:

- It gives us a **prior to report against**. Confirming it is a result; contradicting
  it is a more interesting one. Either way the report should state the prediction up
  front rather than appear to discover it.
- It raises the stakes on the evaluation function. PLAN.md deliberately gives
  Alpha-Beta and the Heuristic agent the *same* evaluation function so that their
  difference isolates search depth. If that shared function is weak on UTTT - exactly
  what the claim asserts - then a poor Alpha-Beta result here is ambiguous between
  "exact search scales badly" and "our heuristic was bad". **The evaluation function
  for UTTT needs more care than the other two**, and its quality should be reported,
  not assumed.

Note also that the claim is uncited on Wikipedia, so it is a prior and not an
established result.

---

## 6. Alternatives considered and rejected

**6.1 Decided boards remain playable.** Under this reading, a won local board keeps
its empty cells in play; moves there cannot change its owner, and being sent to one is
legal and unremarkable. Wikipedia records it as a named variant: "a variant of the
game requires players to continue playing in already decided boxes if there are still
empty spaces."

*Rejected*, for three reasons, the last of which is decisive:

1. It is the **variant**, not the standard rule (4.3).
2. It makes the free-choice rule in 4.2 redundant for won boards, and it lets players
   spend moves inside dead boards purely to steer where the opponent is sent - a
   substantially different strategic game.
3. **It is solved.** "It was shown in 2020 that this set of rules ... admits a winning
   strategy for the first player." A solved game is close to useless as a research
   domain here: the large domain exists to be the one neither paradigm can exhaust,
   and a known first-player win would confound the first-move-advantage analysis that
   PLAN.md treats as a headline result. Our standard-rules version has **no** published
   solution.

**6.2 Free choice only on a *full* board, not a won one.** A middle reading: you are
sent to a won-but-not-full board and must play there. *Rejected:* the sources
consistently group won and drawn boards together when stating the exception.

**6.2b A drawn local board is claimed by whoever has more marks in it.** A third
tie-handling variant, attested alongside the other two. *Rejected:* it is the least
attested of the three, and it changes the game more than it first appears - a local
board has **9 cells, an odd number**, so a full board can never be tied on marks and
**every** full board would be claimed by someone. The "drawn board" status would cease
to exist entirely, and with it the global draw as a normal outcome. That would remove
a result category the experiment reports on.

**6.3 A drawn local board counts for both players** (some house rules let a tied
board count toward either player's global line). *Rejected:* the sources state
explicitly that a tie forms part of no three-in-a-row, and counting it for both
would allow both players to hold a winning line at once.

**6.4 Global win by majority of local boards** when the board fills without a line.
*Rejected:* not part of the standard rules; 4.7's draw is the standard outcome, and
draws are analytically useful to us as a distinct result to log.

**6.5 Keeping PLAN.md's `2 x 3^81` state-space bound.** *Rejected* in favour of 5.1's
corrected form, which accounts for the send constraint - though the choice is
cosmetic, since both are loose upper bounds.

---

## 7. Implementation notes

- State: 81 cell values, 9 local-board statuses, the send constraint (`0..8` or
  "free"), and the side to move. The local-board statuses are derived data, but
  caching them is worthwhile - they are read on every move generation.
- The send constraint **must be part of the transposition-table key**. Two positions
  with identical cells but different send constraints have different legal moves and
  different values; conflating them corrupts the table.
- Check the global win only after a local board's status changes to *won*. Checking
  every ply is wasted work.
- Run the early-draw check of 4.8 in the same place, on the same trigger - a local
  board's status changing is the only event that can make a global line unwinnable.
  Keep a per-player bitmask of still-winnable lines and clear bits as boards resolve;
  the game is drawn when both masks are empty. This makes the check O(1) per ply after
  the update.
- Precompute the eight winning lines as index triples and reuse the same table for
  local and global boards - they are structurally identical.
- Move generation has exactly two paths (constrained and free). Both must skip
  decided boards, per 4.3.

---

## 8. References

**Video explanation**

- [How To Play Ultimate Tic-Tac-Toe (YouTube)](https://www.youtube.com/watch?v=wNs4R48GLa0) - detailed walkthrough. Notably it sets out the three tie-handling options side by side (claimed by whoever has more marks; counts for both; counts for neither) and observes that the manual does not settle the question. We take the third, which is also what the popularising source recommends - see 4.5, 6.2b and 6.3.

**Primary rule sources**

- [Ultimate tic-tac-toe - Wikipedia](https://en.wikipedia.org/wiki/Ultimate_tic-tac-toe) - **the closest thing to an authoritative statement.** Confirms the send rule, free choice when sent to a won or full board, and crucially that "the standard rules do not permit continued play in decided local boards" (4.3). Names the continue-in-decided-boards variant and reports that it was **shown in 2020 to admit a winning strategy for the first player** (6.1). Also the source of the claim in 5.5 that MCTS handles this game well while minimax struggles for want of a good evaluation function.
- [Ultimate Tic-Tac-Toe - Math with Bad Drawings (2013)](https://mathwithbaddrawings.com/2013/06/16/ultimate-tic-tac-toe/) - the post that popularised the game, and the origin of most online rule statements. Recommends that a tied local board "counts for neither X nor O", and offers counting it for both as a deliberate variant.
- [Ultimate Tic-Tac-Toe Rules - tictactoefree.com](https://tictactoefree.com/ultimate-tic-tac-toe/rules) - the send rule; free choice when sent to a board already won *or* tied; a tied local board forms part of no three-in-a-row; overall draw when no global line is made.
- [Tic-tac-toe variants - Wikipedia](https://en.wikipedia.org/wiki/Tic-tac-toe_variants) - structural definition of the nine-board game.
- [Ultimate Tic-Tac-Toe - BoardGameGeek](https://boardgamegeek.com/boardgame/42336/ultimate-tic-tac-toe) - game entry and rule discussion.
- [Ultimate Tic-Tac-Toe (printable rules, PDF)](https://www.thepaintedturtle.org/sites/main/files/file-attachments/ultimate_tic-tac-toe_instructions_0.pdf) - independent statement of the same core rules.
