import csv
import os
import random
import shutil
import tempfile
import unittest
from dataclasses import replace

from agents import random_agent
from experiments import runner
from experiments.logger import GAME_COLUMNS, MOVE_COLUMNS, GameLogger
from games import isolation
from games.base import DRAW, LOSS, WIN

CONFIG = {"name": "test", "time_budget_s": 1.0, "max_nodes": 1000}


class SeedTest(unittest.TestCase):
    def test_seed_is_deterministic(self):
        a = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        b = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertEqual(a, b)

    def test_seed_varies_with_every_input(self):
        base = runner.game_seed("isolation", "random", "heuristic", "main", 3)
        self.assertNotEqual(base, runner.game_seed("ataxx", "random", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "mcts", "heuristic", "main", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "hard", 3))
        self.assertNotEqual(base, runner.game_seed("isolation", "random", "heuristic", "main", 4))


class PlayGameTest(unittest.TestCase):
    def _play(self, seed=1):
        return runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed,
        )

    def test_produces_a_decisive_result_within_the_ply_bound(self):
        record = self._play()
        self.assertIn(record.winner, ("first", "second"))
        self.assertLessEqual(record.plies, 23)
        self.assertEqual(record.end_reason, "no_moves")

    def test_records_one_move_row_per_ply(self):
        record = self._play()
        self.assertEqual(len(record.moves), record.plies)
        self.assertEqual([m.ply for m in record.moves], list(range(record.plies)))

    def test_agents_alternate_sides(self):
        record = self._play()
        self.assertEqual([m.side for m in record.moves[:4]], [0, 1, 0, 1])

    def test_records_legal_move_count_for_branching_factor_measurement(self):
        record = self._play()
        first = record.moves[0]
        self.assertEqual(first.legal_move_count, 11)

    def test_is_reproducible_from_its_seed(self):
        a = self._play(seed=42)
        b = self._play(seed=42)
        self.assertEqual([m.move for m in a.moves], [m.move for m in b.moves])
        self.assertEqual(a.winner, b.winner)

    def test_different_seeds_give_different_games(self):
        moves = set()
        for seed in range(8):
            moves.add(tuple(m.move for m in self._play(seed=seed).moves))
        self.assertGreater(len(moves), 1)

    def test_ply_cap_ends_the_game_and_is_reported(self):
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("a", "b"),
            CONFIG,
            seed=1,
            ply_cap=4,
        )
        self.assertEqual(record.plies, 4)
        self.assertEqual(record.end_reason, "ply_cap")


class _StubResultGame(object):
    """A game double whose result() is fixed, so _winner()'s mapping from
    "the side to move's outcome" onto "first"/"second" can be exercised for
    every case directly, without needing a real terminal position for each
    one."""

    def __init__(self, outcome):
        self._outcome = outcome

    def result(self, state):
        return self._outcome


class _StubState(object):
    def __init__(self, side_to_move):
        self.side_to_move = side_to_move


class WinnerMappingTest(unittest.TestCase):
    """_winner() decides who won every game in the study. Every other test
    touching .winner is satisfiable by an inverted (first/second-swapped)
    mapping too - see PlayGameTest and LoggerTest, none of which would catch
    the comparison being flipped. These tests call the module-private
    _winner() directly and are deliberately exhaustive, because this mapping
    is too consequential to leave to indirect coverage alone."""

    def test_winner_mapping_is_exhaustively_correct(self):
        cases = [
            (WIN, 0, "first"),
            (WIN, 1, "second"),
            (LOSS, 0, "second"),
            (LOSS, 1, "first"),
            (DRAW, 0, "draw"),
            (DRAW, 1, "draw"),
        ]
        for outcome, side_to_move, expected in cases:
            with self.subTest(outcome=outcome, side_to_move=side_to_move):
                game = _StubResultGame(outcome)
                state = _StubState(side_to_move)
                self.assertEqual(
                    runner._winner(game, state, "no_moves"), expected)

    def test_winner_agrees_with_replaying_the_logged_moves(self):
        for seed in range(6):
            record = runner.play_game(
                isolation,
                (random_agent.choose, random_agent.choose),
                ("random_a", "random_b"),
                CONFIG,
                seed=seed,
            )
            # Independently rebuild the terminal position from the logged
            # move strings alone, exercising the move_to_str/str_to_move
            # round trip end to end, then derive the winner from Isolation's
            # own rule (the side to move at a terminal state has no legal
            # move and has therefore lost) rather than from _winner itself.
            state = isolation.initial_state()
            for move in record.moves:
                state = isolation.apply_move(
                    state, isolation.str_to_move(move.move))
            self.assertTrue(isolation.is_terminal(state))
            expected = "first" if state.side_to_move == 1 else "second"
            self.assertEqual(record.winner, expected)


class _FlakyLegalMovesGame(object):
    """Wraps a real game module and forwards everything except
    legal_moves(), which works once and then raises.

    play_game() calls legal_moves() once per ply to record
    legal_move_count, and decide()'s error fallback calls it again to pick a
    replacement move. Failing on the second call makes both the agent and
    the fallback fail, which is exactly the case play_game must survive
    without ever calling apply_move(None).
    """

    def __init__(self, game):
        self._game = game
        self._calls = 0

    def legal_moves(self, state):
        self._calls += 1
        if self._calls > 1:
            raise RuntimeError("legal_moves exhausted")
        return self._game.legal_moves(state)

    def __getattr__(self, name):
        return getattr(self._game, name)


def _raising_agent(game, state, ctx, rng):
    raise RuntimeError("agent blew up")


def _illegal_move_agent(game, state, ctx, rng):
    """Returns a deliberately illegal move, standing in for a real
    Alpha-Beta/MCTS bug (stale transposition-table hit, off-by-one in
    best-move bookkeeping) that returns a wrong-but-plausible move without
    raising."""
    legal = game.legal_moves(state)
    return next(c for c in range(25) if c not in legal)


class ErrorHandlingTest(unittest.TestCase):
    def test_agent_returning_no_move_ends_the_game_as_an_error(self):
        wrapped = _FlakyLegalMovesGame(isolation)
        record = runner.play_game(
            wrapped,
            (_raising_agent, random_agent.choose),
            ("bad", "random_b"),
            CONFIG,
            seed=1,
        )
        self.assertEqual(record.end_reason, "agent_error")
        self.assertEqual(record.winner, "draw")
        self.assertEqual(record.moves[-1].tag, "error")
        self.assertEqual(record.moves[-1].move, "--")

    def test_illegal_move_ends_the_game_and_is_recorded(self):
        record = runner.play_game(
            isolation,
            (_illegal_move_agent, random_agent.choose),
            ("bad", "random_b"),
            CONFIG,
            seed=1,
        )
        self.assertEqual(record.end_reason, "illegal_move")
        self.assertEqual(record.winner, "draw")
        self.assertEqual(record.moves[-1].tag, "error")


class LoggerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.games_path = os.path.join(self.dir, "games.csv")
        self.moves_path = os.path.join(self.dir, "moves.csv")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def _write_one(self):
        logger = GameLogger(self.games_path, self.moves_path)
        record = runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed=1,
        )
        logger.write(record)
        logger.close()
        return record

    def test_writes_one_game_row_and_one_row_per_move(self):
        record = self._write_one()
        with open(self.games_path) as handle:
            games = list(csv.DictReader(handle))
        with open(self.moves_path) as handle:
            moves = list(csv.DictReader(handle))
        self.assertEqual(len(games), 1)
        self.assertEqual(len(moves), record.plies)
        self.assertEqual(games[0]["game"], "isolation")
        self.assertEqual(int(games[0]["plies"]), record.plies)

    def test_node_and_simulation_counts_are_separate_columns(self):
        self._write_one()
        with open(self.moves_path) as handle:
            header = next(csv.reader(handle))
        self.assertIn("nodes", header)
        self.assertIn("simulations", header)

    def test_completed_ids_supports_resume(self):
        record = self._write_one()
        logger = GameLogger(self.games_path, self.moves_path)
        self.assertIn(record.game_id, logger.completed_ids())
        logger.close()


class CrashDurabilityTest(unittest.TestCase):
    """Pins the crash-durability invariant: a game_id in games.csv implies
    all of its move rows are already durable, and reopening a GameLogger
    after a mid-write kill cleans up any orphaned move rows exactly once,
    without disturbing a clean moves.csv."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.games_path = os.path.join(self.dir, "games.csv")
        self.moves_path = os.path.join(self.dir, "moves.csv")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def _play(self, seed):
        return runner.play_game(
            isolation,
            (random_agent.choose, random_agent.choose),
            ("random_a", "random_b"),
            CONFIG,
            seed,
        )

    def _write_games_header_only(self):
        with open(self.games_path, "w", newline="") as handle:
            csv.DictWriter(handle, fieldnames=GAME_COLUMNS).writeheader()

    def _write_raw_moves(self, rows):
        with open(self.moves_path, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MOVE_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def _move_row(self, game_id, ply):
        return {
            "game_id": game_id,
            "ply": ply,
            "agent": "random_a",
            "side": ply % 2,
            "tag": "search",
            "elapsed_s": "0.010000",
            "nodes": 10,
            "simulations": "",
            "depth": 1,
            "move": "m%d" % ply,
            "legal_move_count": 5,
        }

    def test_a_game_id_in_games_implies_its_moves_are_durable(self):
        logger = GameLogger(self.games_path, self.moves_path)
        record = self._play(seed=7)
        logger.write(record)
        logger.close()

        with open(self.moves_path, newline="") as handle:
            moves = [row for row in csv.DictReader(handle)
                     if row["game_id"] == record.game_id]
        self.assertEqual(len(moves), record.plies)
        self.assertEqual({int(row["ply"]) for row in moves}, set(range(record.plies)))

    def test_orphan_moves_are_dropped_on_reopen(self):
        self._write_games_header_only()
        rows = [self._move_row("orphan-game", ply) for ply in range(5)]
        self._write_raw_moves(rows)

        logger = GameLogger(self.games_path, self.moves_path)
        try:
            self.assertEqual(logger.dropped_orphan_moves, 5)
            with open(self.moves_path, newline="") as handle:
                remaining = list(csv.DictReader(handle))
            self.assertEqual(remaining, [])
        finally:
            logger.close()

    def test_orphan_moves_are_dropped_when_games_csv_is_entirely_empty(self):
        # games.csv can be zero bytes (not even a header) on reopen: its
        # tiny header write can still be sitting unflushed in its own file
        # object's buffer when a hard kill lands, even though moves.csv's
        # much bigger buffer already auto-flushed a chunk of orphan rows to
        # disk. This is exactly the shape of the reported reproduction
        # (games.csv rows: 0, moves.csv rows: N), so it must self-heal on
        # the very next open, not just when games.csv already has a header.
        open(self.games_path, "w").close()
        rows = [self._move_row("orphan-game", ply) for ply in range(5)]
        self._write_raw_moves(rows)

        logger = GameLogger(self.games_path, self.moves_path)
        try:
            self.assertEqual(logger.dropped_orphan_moves, 5)
            with open(self.moves_path, newline="") as handle:
                remaining = list(csv.DictReader(handle))
            self.assertEqual(remaining, [])
        finally:
            logger.close()

    def test_a_clean_run_drops_nothing_and_leaves_the_file_untouched(self):
        logger = GameLogger(self.games_path, self.moves_path)
        for seed in (1, 2):
            logger.write(self._play(seed))
        logger.close()

        mtime_before = os.path.getmtime(self.moves_path)
        with open(self.moves_path, "rb") as handle:
            content_before = handle.read()

        logger = GameLogger(self.games_path, self.moves_path)
        try:
            self.assertEqual(logger.dropped_orphan_moves, 0)
        finally:
            logger.close()

        with open(self.moves_path, "rb") as handle:
            content_after = handle.read()
        self.assertEqual(os.path.getmtime(self.moves_path), mtime_before)
        self.assertEqual(content_after, content_before)

    def test_completed_ids_skips_a_truncated_final_line(self):
        logger = GameLogger(self.games_path, self.moves_path)
        record = self._play(seed=3)
        logger.write(record)
        logger.close()

        # Simulate a hard kill mid-write: a partial final line with an
        # empty game_id field and no trailing newline.
        with open(self.games_path, "a", newline="") as handle:
            handle.write("\n,truncated,mid,write")

        logger = GameLogger(self.games_path, self.moves_path)
        try:
            self.assertEqual(logger.completed_ids(), {record.game_id})
        finally:
            logger.close()

    def test_resume_after_a_mid_write_kill_does_not_duplicate_moves(self):
        self._write_games_header_only()
        rows = [self._move_row("resumed-game", ply) for ply in range(5)]
        self._write_raw_moves(rows)

        logger = GameLogger(self.games_path, self.moves_path)
        self.assertEqual(logger.dropped_orphan_moves, 5)

        record = replace(self._play(seed=9), game_id="resumed-game")
        logger.write(record)
        logger.close()

        with open(self.moves_path, newline="") as handle:
            moves = list(csv.DictReader(handle))
        keys = [(row["game_id"], row["ply"]) for row in moves]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(moves), record.plies)



class VersionColumnTest(unittest.TestCase):
    def test_games_csv_carries_the_agent_versions_and_params(self):
        from experiments import logger as logger_module
        for column in ("agent_first_version", "agent_second_version",
                       "agent_first_params", "agent_second_params"):
            self.assertIn(column, logger_module.GAME_COLUMNS)

    def test_the_new_columns_are_appended_not_inserted(self):
        """Existing column positions must not move, or every tool reading the
        v1 CSVs by position breaks on the old files."""
        from experiments import logger as logger_module
        self.assertEqual(logger_module.GAME_COLUMNS[:13], [
            "game_id", "game", "config", "time_budget_s", "max_nodes",
            "max_entries", "agent_first", "agent_second", "winner", "plies",
            "end_reason", "seed", "workers"])

    def test_play_game_defaults_to_v1_with_empty_params(self):
        """An existing caller that passes no version must still work, and must
        produce v1 rows rather than blank ones."""
        from games import isolation
        from agents import random_agent
        record = runner.play_game(
            isolation, (random_agent.choose, random_agent.choose),
            ("random", "random"),
            {"name": "hard", "time_budget_s": 0.02, "max_nodes": 50000,
             "max_entries": 200000}, seed=1, ply_cap=50)
        self.assertEqual(record.agent_first_version, "v1")
        self.assertEqual(record.agent_first_params, "{}")

class EveryColumnIsWrittenTest(unittest.TestCase):
    def test_no_declared_game_column_is_left_blank(self):
        """A column can be declared in GAME_COLUMNS and never populated by
        write(), producing a well-formed CSV with a silently empty column -
        the same shape of defect as D9. Adding a field to GameRecord is not
        enough; the logger maps fields explicitly."""
        import csv
        import os
        import tempfile
        from experiments.logger import GameLogger, GAME_COLUMNS
        from games import isolation
        from agents import random_agent

        record = runner.play_game(
            isolation, (random_agent.choose, random_agent.choose),
            ("random", "random"),
            {"name": "hard", "time_budget_s": 0.02, "max_nodes": 50000,
             "max_entries": 200000}, seed=1, ply_cap=50,
            agent_versions=("v2", "v2"),
            agent_params=({"epsilon": 1.0}, {}))
        directory = tempfile.mkdtemp()
        logger = GameLogger(os.path.join(directory, "games.csv"),
                            os.path.join(directory, "moves.csv"))
        logger.write(record)
        logger.close()
        with open(os.path.join(directory, "games.csv"), newline="") as handle:
            row = list(csv.DictReader(handle))[0]
        blank = sorted(c for c in GAME_COLUMNS if row.get(c) in (None, ""))
        self.assertEqual(blank, [], "declared but never written: %s" % blank)
        self.assertEqual(row["agent_first_version"], "v2")
        self.assertEqual(row["agent_first_params"], '{"epsilon": 1.0}')


if __name__ == "__main__":
    unittest.main()
