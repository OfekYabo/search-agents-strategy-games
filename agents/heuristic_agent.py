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
            # The child's value is from the opponent's perspective; negate it.
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
