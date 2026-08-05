"""Uniform random baseline. The sanity-check floor for every tournament."""


def choose(game, state, ctx, rng):
    moves = game.legal_moves(state)
    ctx.note_node()
    ctx.completed()
    return rng.choice(moves)
