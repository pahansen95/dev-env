"""Context management for isolated development workspaces."""

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Context:
  """Represents an isolated development workspace."""

  id: str  # SHA-256 hash of name + path
  name: str  # Human-readable identifier
  path: Path  # Filesystem location
  created_at: str  # ISO timestamp
  last_used: str  # ISO timestamp
  state: str  # active|suspended|archived

  @classmethod
  def generate_id(cls, name: str, path: Path) -> str:
    """Generate a unique ID from name and path."""
    content = f"{name}:{path.resolve()}"
    return hashlib.sha256(content.encode()).hexdigest()

  def to_dict(self) -> dict:
    """Convert context to dictionary for serialization."""
    return {
      "id": self.id,
      "name": self.name,
      "path": str(self.path),
      "created_at": self.created_at,
      "last_used": self.last_used,
      "state": self.state,
    }

  @classmethod
  def from_dict(cls, data: dict) -> "Context":
    """Create Context from dictionary."""
    return cls(
      id=data["id"],
      name=data["name"],
      path=Path(data["path"]),
      created_at=data["created_at"],
      last_used=data["last_used"],
      state=data["state"],
    )
