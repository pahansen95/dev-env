"""Context resolution logic for finding and managing development contexts."""

from pathlib import Path
from typing import Optional

from dev_env.context import Context
from dev_env.state import StateManager


class ContextResolver:
  """Resolves contexts from filesystem and registry."""

  def __init__(self, state_manager: Optional[StateManager] = None):
    """Initialize the context resolver."""
    self.state_manager = state_manager or StateManager()

  def resolve(self, name: Optional[str] = None) -> Optional[Context]:
    """
    Resolve a context using the following order:
    1. If name provided, check registry
    2. Walk up from cwd looking for .dev-env/
    3. Return None if not found
    """
    if name:
      return self._resolve_by_name(name)

    return self._resolve_by_path()

  def _resolve_by_name(self, name: str) -> Optional[Context]:
    """Resolve context by name from registry."""
    with self.state_manager:
      cursor = self.state_manager.conn.execute(
        "SELECT id, name, path, created_at, last_used, state FROM contexts WHERE name = ?",
        (name,),
      )
      row = cursor.fetchone()

      if row:
        return Context(
          id=row[0],
          name=row[1],
          path=Path(row[2]),
          created_at=row[3],
          last_used=row[4],
          state=row[5],
        )

    return None

  def _resolve_by_path(self) -> Optional[Context]:
    """Resolve context by walking up from current directory."""
    current_path = Path.cwd()

    while current_path != current_path.parent:
      dev_env_path = current_path / ".dev-env"
      if dev_env_path.exists() and dev_env_path.is_dir():
        return self._get_context_by_path(current_path)

      current_path = current_path.parent

    return None

  def _get_context_by_path(self, path: Path) -> Optional[Context]:
    """Get context from registry by path."""
    with self.state_manager:
      cursor = self.state_manager.conn.execute(
        "SELECT id, name, path, created_at, last_used, state FROM contexts WHERE path = ?",
        (str(path.resolve()),),
      )
      row = cursor.fetchone()

      if row:
        return Context(
          id=row[0],
          name=row[1],
          path=Path(row[2]),
          created_at=row[3],
          last_used=row[4],
          state=row[5],
        )

    return None
