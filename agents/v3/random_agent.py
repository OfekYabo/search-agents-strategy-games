# Agent version v3. See docs/VERSIONING.md - frozen once a tournament has
# run against it. Any fix after that is a new version, not an edit here.
# Identical to v1 - no change has been made yet.
"""Uniform random baseline. The sanity-check floor for every tournament."""


def choose(game, state, ctx, rng):
    moves = game.legal_moves(state)
    ctx.note_node()
    ctx.completed()
    return rng.choice(moves)
