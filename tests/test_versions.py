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


class VersionIntegrityTest(unittest.TestCase):
    def test_every_version_package_tags_itself_with_its_directory(self):
        """A clone with a stale tag inside it produces a run labelled as
        something it is not. Cheap to check, expensive to discover later."""
        import importlib
        for name in ("v2", "v3"):
            for package in ("agents", "evaluation"):
                module = importlib.import_module("%s.%s" % (package, name))
                self.assertEqual(module.VERSION, name,
                                 "%s.%s declares %r" % (package, name,
                                                        module.VERSION))

    def test_v3_keeps_the_same_roster_caps_and_rollout_family(self):
        """V3 deliberately changes search behaviour, but not the compared
        agent roster, memory-bound sizes or calibrated rollout policy."""
        import random
        from agents import v2, v3, base
        from evaluation.v2 import isolation_eval as e2
        from evaluation.v3 import isolation_eval as e3
        from games import isolation
        self.assertEqual(v2.AGENTS, v3.AGENTS)
        self.assertEqual(v2.CAPS, v3.CAPS)
        self.assertEqual(v2.MCTS_ROLLOUT, v3.MCTS_ROLLOUT)
        a2 = v2.build("heuristic", e2.evaluate)
        a3 = v3.build("heuristic", e3.evaluate)
        state = isolation.initial_state()
        for _ in range(8):
            if isolation.is_terminal(state):
                break
            m2 = a2(isolation, state, base.SearchContext(0.1, 50000),
                    random.Random(3))
            m3 = a3(isolation, state, base.SearchContext(0.1, 50000),
                    random.Random(3))
            self.assertEqual(m2, m3)
            state = isolation.apply_move(state, m2)

    def test_v3_declares_the_deliberate_rng_and_tree_reuse_changes(self):
        from agents import v3
        self.assertTrue(v3.SEPARATE_RNG_STREAMS)
        self.assertTrue(v3.params("mcts")["tree_reuse"])

class TerminalInvariantTest(unittest.TestCase):
    """The runner and the MCTS rollout both dropped their is_terminal() call
    and now treat an empty legal-move list as the terminal condition, to avoid
    generating moves twice per decision.

    That is only correct while `is_terminal(s)` and `legal_moves(s) == []`
    agree for every reachable position in every game. Nothing enforced it, and
    if a game module ever reports a decided position that still has legal
    moves - a UTTT line win with empty cells, say - games would silently play
    on past the win and every result would be wrong with no error raised.
    """

    def test_empty_legal_moves_is_exactly_the_terminal_condition(self):
        import random
        from games import isolation, uttt, ataxx
        for game, seeds, plies in ((isolation, 60, 400),
                                   (uttt, 60, 400),
                                   (ataxx, 30, 400)):
            checked = 0
            for seed in range(seeds):
                rng = random.Random(seed)
                state = game.initial_state()
                for _ in range(plies):
                    legal = game.legal_moves(state)
                    terminal = game.is_terminal(state)
                    checked += 1
                    self.assertEqual(
                        terminal, not legal,
                        "%s: is_terminal=%s but %d legal moves"
                        % (game.NAME, terminal, len(legal)))
                    if terminal:
                        break
                    state = game.apply_move(state, rng.choice(legal))
            self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
