"""Streaming CSV logging.

Rows are flushed per game, so an interrupted overnight run keeps everything it
had already produced.
"""
import csv
import os
import tempfile
from typing import Set

GAME_COLUMNS = [
    "game_id", "game", "config", "time_budget_s", "max_nodes", "max_entries",
    "agent_first", "agent_second", "winner", "plies", "end_reason",
    "seed", "workers",
]

# nodes and simulations are deliberately separate: an Alpha-Beta node is a
# static evaluation at a horizon and an MCTS simulation is a rollout, so they
# are not the same unit of work and must never share an axis.
MOVE_COLUMNS = [
    "game_id", "ply", "agent", "side", "tag", "elapsed_s",
    "nodes", "simulations", "depth", "move", "legal_move_count",
]


class GameLogger:
    def __init__(self, games_path, moves_path):
        self._games_path = games_path
        self._moves_path = moves_path
        for path in (games_path, moves_path):
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

        self.dropped_orphan_moves = self._drop_orphan_moves()

        games_is_new = not os.path.exists(games_path) or os.path.getsize(games_path) == 0
        moves_is_new = not os.path.exists(moves_path) or os.path.getsize(moves_path) == 0

        self._games_file = open(games_path, "a", newline="")
        self._moves_file = open(moves_path, "a", newline="")
        self._games = csv.DictWriter(self._games_file, fieldnames=GAME_COLUMNS)
        self._moves = csv.DictWriter(self._moves_file, fieldnames=MOVE_COLUMNS)
        if games_is_new:
            self._games.writeheader()
        if moves_is_new:
            self._moves.writeheader()

    def _drop_orphan_moves(self):
        # type: () -> int
        """Rewrite moves.csv to drop rows whose game_id has no matching row
        in games.csv, plus any row missing a game_id entirely (what a
        truncated final line looks like after a hard kill mid-write).

        Must run before the append handles are opened, since it replaces
        moves.csv outright rather than appending to it.

        Only "moves.csv missing or empty" short-circuits, because there is
        nothing to drop. games.csv missing or empty is NOT treated as
        "nothing to check": on the very first game of a fresh run, a kill
        during write() can auto-flush a chunk of moves.csv (its buffer
        fills after ~110 rows) while games.csv's own tiny header is still
        sitting unflushed in its own file object's buffer, so games.csv
        reads back as 0 bytes even though moves.csv already holds durable
        orphan rows. Treating "games.csv empty" as "skip" would leave
        those orphans in place, and a replay of that same game_id would
        then duplicate them - the exact bug this method exists to prevent.
        So an empty/missing games.csv means zero durable game_ids, not an
        early return.
        """
        if not os.path.exists(self._moves_path) or os.path.getsize(self._moves_path) == 0:
            return 0

        if not os.path.exists(self._games_path) or os.path.getsize(self._games_path) == 0:
            game_ids = set()
        else:
            with open(self._games_path, newline="") as handle:
                game_ids = {row["game_id"] for row in csv.DictReader(handle) if row.get("game_id")}

        with open(self._moves_path, newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            rows = list(reader)

        kept = [row for row in rows if row.get("game_id") in game_ids]
        dropped = len(rows) - len(kept)
        if dropped == 0:
            return 0

        directory = os.path.dirname(self._moves_path) or "."
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".moves.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", newline="") as tmp_file:
                writer = csv.DictWriter(tmp_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(kept)
            os.replace(tmp_path, self._moves_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        return dropped

    def write(self, record):
        # Move rows are written and flushed before the games row, and the
        # games row is written and flushed last. That makes the games row
        # the commit marker: once a game_id is durably in games.csv, every
        # one of its move rows is already durable too. The old order wrote
        # the games row first, but a games row (~120 B) never fills Python's
        # 8192-byte text buffer on its own, while a full game's move rows
        # (tens of KB) do auto-flush partway through - so a kill mid-write
        # could land moves.csv ahead of games.csv with no way to tell, from
        # games.csv alone, whether those moves were really complete.
        for move in record.moves:
            self._moves.writerow({
                "game_id": record.game_id,
                "ply": move.ply,
                "agent": move.agent,
                "side": move.side,
                "tag": move.tag,
                "elapsed_s": "%.6f" % move.elapsed_s,
                "nodes": "" if move.nodes is None else move.nodes,
                "simulations": "" if move.simulations is None else move.simulations,
                "depth": "" if move.depth is None else move.depth,
                "move": move.move,
                "legal_move_count": move.legal_move_count,
            })
        self._moves_file.flush()
        self._games.writerow({
            "game_id": record.game_id,
            "game": record.game,
            "config": record.config,
            "time_budget_s": record.time_budget_s,
            "max_nodes": record.max_nodes,
            "max_entries": record.max_entries,
            "agent_first": record.agent_first,
            "agent_second": record.agent_second,
            "winner": record.winner,
            "plies": record.plies,
            "end_reason": record.end_reason,
            "seed": record.seed,
            "workers": record.workers,
        })
        self._games_file.flush()

    def completed_ids(self):
        # type: () -> Set[str]
        """Game ids already present, so an interrupted run can resume."""
        if not os.path.exists(self._games_path):
            return set()
        with open(self._games_path, newline="") as handle:
            return {row["game_id"] for row in csv.DictReader(handle) if row.get("game_id")}

    def close(self):
        self._games_file.close()
        self._moves_file.close()
