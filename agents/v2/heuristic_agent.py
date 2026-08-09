# Agent version v2. See docs/VERSIONING.md - frozen once a tournament has
# run against it. Any fix after that is a new version, not an edit here.
"""One-ply heuristic agent.

Evaluation is incremental - a running best - so a mid-evaluation cutoff still
returns a valid move rather than failing. Uses the same evaluator Alpha-Beta
applies at its horizon, so the difference between the two agents isolates
search depth rather than evaluation quality.
"""


def make(evaluate):
    """Build an agent from evaluate(game, state) -> float in (-1, 1)."""

    def agent(game, state, ctx, rng):
        # A one-ply agent evaluates far fewer candidates than the default
        # node-search polling interval (check_every=512), so without this
        # should_stop() would never actually sample the clock and an expired
        # budget would go undetected.
        ctx.set_check_every(1)
        moves = game.legal_moves(state)
        best_score = None
        best_moves = []
        evaluated = 0

        for move in moves:
            if ctx.should_stop() and best_moves:
                break
            child = game.apply_move(state, move)
            ctx.note_node()
            # A terminal child has to be scored from the rules, not from the
            # evaluator. `evaluate` is static and has no terminal awareness: a
            # winning child leaves the opponent with no moves, which mobility
            # difference scores as ours/32 - while a non-winning child that
            # leaves us more room scores (ours-1)/32, which can be larger. v1
            # therefore declined an available immediate win in 28.0% of such
            # positions on Isolation, 11.6% on UTTT and 3.2% on Ataxx. v2
            # declines none.
            #
            # It does NOT explain the weak Isolation control. Measured over
            # 720 games per version, the heuristic's score against the random
            # agent moves 0.750 [0.666, 0.819] -> 0.767 [0.683, 0.833]: two
            # extra wins in 120, intervals almost entirely overlapping. The
            # rate of declined wins is not the rate of lost games, because
            # declining one usually still wins from a mobility advantage. The
            # fix is kept because conceding a forced win is indefensible
            # regardless of how often it costs the game, not because it
            # repairs that finding - it does not.
            #
            # Alpha-Beta and MCTS never had this bug: both check is_terminal
            # before evaluating. Only the one-ply agent skipped it.
            if game.is_terminal(child):
                # Both result() and evaluate() are from the perspective of the
                # side to move in the child - the opponent - so the same
                # negation applies to each.
                score = -game.result(child)
            else:
                score = -evaluate(game, child)
            evaluated += 1
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        if not best_moves:
            return rng.choice(moves)

        if evaluated == len(moves):
            ctx.completed()

        # Tie-break randomly: taking the first would silently inherit the move
        # ordering that legal_moves provides for Alpha-Beta's benefit.
        return rng.choice(best_moves)

    return agent
