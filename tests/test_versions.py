import unittest


class EvaluatorVersionTest(unittest.TestCase):
    def test_v2_declares_its_version(self):
        from evaluation import v2
        self.assertEqual(v2.VERSION, "v2")

    def test_v2_evaluators_agree_with_v1_on_the_same_states(self):
        """The v2 evaluators start as exact clones. If they ever diverge it
        must be a deliberate, reviewed change - not a transcription slip."""
        import random
        from evaluation import isolation_eval, ataxx_eval, uttt_eval
        from evaluation.v2 import (isolation_eval as i2, ataxx_eval as a2,
                                   uttt_eval as u2)
        from games import isolation, ataxx, uttt
        for game, old, new in ((isolation, isolation_eval, i2),
                               (ataxx, ataxx_eval, a2),
                               (uttt, uttt_eval, u2)):
            rng = random.Random(7)
            state = game.initial_state()
            for _ in range(30):
                if game.is_terminal(state):
                    break
                self.assertAlmostEqual(old.evaluate(game, state),
                                       new.evaluate(game, state), places=12)
                state = game.apply_move(state, rng.choice(
                    game.legal_moves(state)))


if __name__ == "__main__":
    unittest.main()
