import random
import unittest

from agents import base


def _declined_wins(game, agent, seeds):
    """Count positions where an immediate win existed and was not taken."""
    offered = declined = 0
    for seed in seeds:
        rng = random.Random(seed)
        state = game.initial_state()
        turn = 0
        while not game.is_terminal(state):
            moves = game.legal_moves(state)
            if turn % 2 == 0:
                wins = [m for m in moves
                        if game.is_terminal(game.apply_move(state, m))
                        and game.result(game.apply_move(state, m)) != 0]
                ctx = base.SearchContext(0.1, 50000)
                chosen = agent(game, state, ctx, rng)
                if wins:
                    offered += 1
                    if chosen not in wins:
                        declined += 1
            else:
                chosen = rng.choice(moves)
            state = game.apply_move(state, chosen)
            turn += 1
    return offered, declined


class HeuristicTakesWinsTest(unittest.TestCase):
    """v1's one-ply agent scores children with -evaluate(child) and never
    checks whether a child is terminal. A winning child leaves the opponent
    with no moves, so mobility difference scores it ours/32 - while a
    non-winning child that leaves us more room scores (ours-1)/32, which can
    be larger. The agent then declines the win.
    """

    def test_v2_heuristic_never_declines_an_immediate_win(self):
        from agents.v2 import heuristic_agent
        from evaluation.v2 import isolation_eval
        from games import isolation
        agent = heuristic_agent.make(isolation_eval.evaluate)
        offered, declined = _declined_wins(isolation, agent, range(60))
        self.assertGreater(offered, 0, "test found no winning positions")
        self.assertEqual(declined, 0)

    def test_the_v1_agent_still_declines_them(self):
        """Guards the fix against being quietly back-ported, and documents
        that v1 is left alone deliberately rather than by oversight."""
        from agents import heuristic_agent
        from evaluation import isolation_eval
        from games import isolation
        agent = heuristic_agent.make(isolation_eval.evaluate)
        offered, declined = _declined_wins(isolation, agent, range(60))
        self.assertGreater(declined, 0)

    def test_v2_heuristic_takes_wins_on_uttt_too(self):
        from agents.v2 import heuristic_agent
        from evaluation.v2 import uttt_eval
        from games import uttt
        agent = heuristic_agent.make(uttt_eval.evaluate)
        offered, declined = _declined_wins(uttt, agent, range(40))
        self.assertGreater(offered, 0)
        self.assertEqual(declined, 0)


class RosterTest(unittest.TestCase):
    def test_build_returns_a_callable_for_every_label(self):
        from agents import v2
        from evaluation.v2 import isolation_eval
        for label in v2.AGENTS:
            self.assertTrue(callable(v2.build(label, isolation_eval.evaluate)))

    def test_unknown_label_raises(self):
        from agents import v2
        from evaluation.v2 import isolation_eval
        with self.assertRaises(ValueError):
            v2.build("nope", isolation_eval.evaluate)

    def test_params_expose_the_hyperparameters_for_logging(self):
        from agents import v2
        self.assertEqual(v2.params("mcts")["epsilon"], 1.0)
        self.assertEqual(v2.params("alpha_beta")["max_entries"], 200000)
        self.assertEqual(v2.params("random"), {})


if __name__ == "__main__":
    unittest.main()
