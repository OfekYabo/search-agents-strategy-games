"""Streaming CSV logging.

Rows are flushed per game, so an interrupted overnight run keeps everything it
had already produced.
"""
import csv
import os
from typing import Set

GAME_COLUMNS = [
    "game_id", "game", "config", "time_budget_s", "max_nodes",
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
        for path in (games_path, moves_path):
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

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

    def write(self, record):
        self._games.writerow({
            "game_id": record.game_id,
            "game": record.game,
            "config": record.config,
            "time_budget_s": record.time_budget_s,
            "max_nodes": record.max_nodes,
            "agent_first": record.agent_first,
            "agent_second": record.agent_second,
            "winner": record.winner,
            "plies": record.plies,
            "end_reason": record.end_reason,
            "seed": record.seed,
            "workers": record.workers,
        })
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
        self._games_file.flush()
        self._moves_file.flush()

    def completed_ids(self):
        # type: () -> Set[str]
        """Game ids already present, so an interrupted run can resume."""
        if not os.path.exists(self._games_path):
            return set()
        with open(self._games_path, newline="") as handle:
            return {row["game_id"] for row in csv.DictReader(handle)}

    def close(self):
        self._games_file.close()
        self._moves_file.close()
