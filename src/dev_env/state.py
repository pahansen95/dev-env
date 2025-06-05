"""State management using SQLite"""

import sqlite3
import json
import contextlib
from pathlib import Path
from typing import Any, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
  from dev_env.context import Context


class StateManager:
  """Manage environment state using SQLite"""

  def __init__(self, state_dir: Optional[Path] = None):
    if state_dir is None:
      state_dir = Path.home() / ".dev-env"
    self.state_dir = state_dir
    self.state_dir.mkdir(parents=True, exist_ok=True)
    self.db_path = self.state_dir / "environments.db"
    self._init_db()
    self.conn = None

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
                    network TEXT,
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

      # Add network column if it doesn't exist (migration)
      try:
        conn.execute("ALTER TABLE environments ADD COLUMN network TEXT")
      except sqlite3.OperationalError:
        # Column already exists
        pass

      # Create contexts table for context management
      conn.execute("""
                CREATE TABLE IF NOT EXISTS contexts (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used TEXT NOT NULL,
                    state TEXT NOT NULL,
                    UNIQUE(name, path)
                )
            """)
      conn.execute("CREATE INDEX IF NOT EXISTS idx_contexts_name ON contexts(name)")
      conn.execute("CREATE INDEX IF NOT EXISTS idx_contexts_path ON contexts(path)")

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

  def save_environment(self, name: str, state: dict[str, Any]) -> None:
    """Save environment state"""
    now = datetime.utcnow().isoformat()

    with self._get_conn() as conn:
      conn.execute(
        """
                INSERT OR REPLACE INTO environments
                (name, container_id, container_name, config, volumes, network, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM environments WHERE name = ?), ?),
                    ?)
            """,
        (
          name,
          state["container_id"],
          state["container_name"],
          json.dumps(state.get("config", {})),
          json.dumps(state.get("volumes", [])),
          state.get("network"),
          name,  # For the COALESCE subquery
          now,  # For new records
          now,  # updated_at
        ),
      )

  def get_environment(self, name: str) -> dict[str, Any] | None:
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
        "network": row["network"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
      }

  def list_environments(self) -> dict[str, dict[str, Any]]:
    """List all environments"""
    with self._get_conn() as conn:
      rows = conn.execute("SELECT * FROM environments ORDER BY name").fetchall()

      return {
        row["name"]: {
          "container_id": row["container_id"],
          "container_name": row["container_name"],
          "config": json.loads(row["config"]),
          "volumes": json.loads(row["volumes"]) if row["volumes"] else [],
          "network": row["network"],
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

  def get_metadata(self, key: str) -> str | None:
    """Get metadata value"""
    with self._get_conn() as conn:
      row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()

      return row["value"] if row else None

  def cleanup_orphaned(self, existing_containers: list[str]) -> int:
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

  def __enter__(self):
    """Context manager entry for transactional operations."""
    self.conn = sqlite3.connect(self.db_path)
    self.conn.row_factory = sqlite3.Row
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    """Context manager exit with automatic commit/rollback."""
    if exc_type is None:
      self.conn.commit()
    else:
      self.conn.rollback()
    self.conn.close()
    self.conn = None


class ContextManager(StateManager):
  """Manage context state for isolated development workspaces."""

  def create_context(self, name: str, path: Path) -> "Context":
    """Create a new context."""
    from dev_env.context import Context

    now = datetime.utcnow().isoformat()
    context_id = Context.generate_id(name, path)

    context = Context(
      id=context_id,
      name=name,
      path=path,
      created_at=now,
      last_used=now,
      state="active",
    )

    with self._get_conn() as conn:
      conn.execute(
        """
                INSERT INTO contexts (id, name, path, created_at, last_used, state)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
        (context.id, context.name, str(context.path.resolve()), context.created_at, context.last_used, context.state),
      )

    return context

  def get_context(self, context_id: str) -> Optional["Context"]:
    """Get context by ID."""
    from dev_env.context import Context

    with self._get_conn() as conn:
      row = conn.execute("SELECT * FROM contexts WHERE id = ?", (context_id,)).fetchone()

      if not row:
        return None

      return Context(
        id=row["id"],
        name=row["name"],
        path=Path(row["path"]),
        created_at=row["created_at"],
        last_used=row["last_used"],
        state=row["state"],
      )

  def list_contexts(self) -> List["Context"]:
    """List all contexts."""
    from dev_env.context import Context

    with self._get_conn() as conn:
      rows = conn.execute("SELECT * FROM contexts ORDER BY last_used DESC").fetchall()

      return [
        Context(
          id=row["id"],
          name=row["name"],
          path=Path(row["path"]),
          created_at=row["created_at"],
          last_used=row["last_used"],
          state=row["state"],
        )
        for row in rows
      ]

  def update_context(self, context: "Context") -> None:
    """Update an existing context."""
    with self._get_conn() as conn:
      conn.execute(
        """
                UPDATE contexts
                SET name = ?, path = ?, last_used = ?, state = ?
                WHERE id = ?
            """,
        (context.name, str(context.path.resolve()), context.last_used, context.state, context.id),
      )
