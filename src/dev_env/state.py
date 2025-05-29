"""State management using SQLite"""

import sqlite3
import json
import contextlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class StateManager:
  """Manage environment state using SQLite"""

  def __init__(self, state_dir: Path):
    self.state_dir = state_dir
    self.state_dir.mkdir(parents=True, exist_ok=True)
    self.db_path = self.state_dir / "environments.db"
    self._init_db()

  def _init_db(self):
    """Initialize database schema"""
    with self._get_conn() as conn:
      conn.execute("""
                CREATE TABLE IF NOT EXISTS environments (
                    name TEXT PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    container_name TEXT NOT NULL,
                    config TEXT NOT NULL,
                    volumes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
      conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

  @contextlib.contextmanager
  def _get_conn(self):
    """Get database connection with automatic commit/rollback"""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    try:
      yield conn
      conn.commit()
    except Exception:
      conn.rollback()
      raise
    finally:
      conn.close()

  def save_environment(self, name: str, state: Dict[str, Any]) -> None:
    """Save environment state"""
    now = datetime.utcnow().isoformat()

    with self._get_conn() as conn:
      conn.execute(
        """
                INSERT OR REPLACE INTO environments
                (name, container_id, container_name, config, volumes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM environments WHERE name = ?), ?),
                    ?)
            """,
        (
          name,
          state["container_id"],
          state["container_name"],
          json.dumps(state.get("config", {})),
          json.dumps(state.get("volumes", [])),
          name,  # For the COALESCE subquery
          now,  # For new records
          now,  # updated_at
        ),
      )

  def get_environment(self, name: str) -> Optional[Dict[str, Any]]:
    """Get environment state by name"""
    with self._get_conn() as conn:
      row = conn.execute("SELECT * FROM environments WHERE name = ?", (name,)).fetchone()

      if not row:
        return None

      return {
        "name": row["name"],
        "container_id": row["container_id"],
        "container_name": row["container_name"],
        "config": json.loads(row["config"]),
        "volumes": json.loads(row["volumes"]) if row["volumes"] else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
      }

  def list_environments(self) -> Dict[str, Dict[str, Any]]:
    """List all environments"""
    with self._get_conn() as conn:
      rows = conn.execute("SELECT * FROM environments ORDER BY name").fetchall()

      return {
        row["name"]: {
          "container_id": row["container_id"],
          "container_name": row["container_name"],
          "config": json.loads(row["config"]),
          "volumes": json.loads(row["volumes"]) if row["volumes"] else [],
          "created_at": row["created_at"],
          "updated_at": row["updated_at"],
        }
        for row in rows
      }

  def remove_environment(self, name: str) -> None:
    """Remove environment state"""
    with self._get_conn() as conn:
      conn.execute("DELETE FROM environments WHERE name = ?", (name,))

  def set_metadata(self, key: str, value: str) -> None:
    """Set metadata value"""
    with self._get_conn() as conn:
      conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))

  def get_metadata(self, key: str) -> Optional[str]:
    """Get metadata value"""
    with self._get_conn() as conn:
      row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()

      return row["value"] if row else None

  def cleanup_orphaned(self, existing_containers: List[str]) -> int:
    """Remove state for containers that no longer exist"""
    with self._get_conn() as conn:
      # Get all tracked containers
      rows = conn.execute("SELECT name, container_id FROM environments").fetchall()

      removed = 0
      for row in rows:
        if row["container_id"] not in existing_containers:
          conn.execute("DELETE FROM environments WHERE name = ?", (row["name"],))
          removed += 1

      return removed
