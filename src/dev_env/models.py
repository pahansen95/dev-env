"""Data models for API responses."""

from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class EnvironmentStatus:
  """Standardized environment status response."""

  state: Literal["running", "stopped", "notfound", "error"]
  context_name: Optional[str] = None
  container_id: Optional[str] = None
  container_name: Optional[str] = None
  context_id: Optional[str] = None
  context_state: Optional[str] = None
  created_at: Optional[str] = None
  updated_at: Optional[str] = None
  error_message: Optional[str] = None
  error_code: Optional[str] = None

  def to_dict(self) -> dict:
    """Convert to dictionary format for JSON serialization."""
    result = {"state": self.state}

    if self.context_name:
      result["context_name"] = self.context_name
    if self.container_id:
      result["container_id"] = self.container_id
    if self.container_name:
      result["container_name"] = self.container_name
    if self.context_id:
      result["context_id"] = self.context_id
    if self.context_state:
      result["context_state"] = self.context_state
    if self.created_at:
      result["created_at"] = self.created_at
    if self.updated_at:
      result["updated_at"] = self.updated_at
    if self.error_message:
      result["error"] = self.error_message
    if self.error_code:
      result["code"] = self.error_code

    return result
