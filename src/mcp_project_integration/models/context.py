"""Context management for Claude Code sessions

Maintains accumulated knowledge and state across task executions using
Python configuration files for human-readable persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

from ..core import PythonConfigSerializer

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
  """Discovered code pattern or convention"""

  name: str
  description: str
  examples: List[str] = field(default_factory=list)
  discovered_at: datetime = field(default_factory=datetime.now)


@dataclass
class Decision:
  """Architectural or implementation decision"""

  description: str
  rationale: str
  timestamp: datetime = field(default_factory=datetime.now)
  related_files: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
  """Task verification outcome"""

  task_id: str
  success: bool
  tests_passed: int = 0
  tests_failed: int = 0
  errors: List[str] = field(default_factory=list)
  timestamp: datetime = field(default_factory=datetime.now)


class SessionContext:
  """Accumulated context across task executions

  Tracks discovered patterns, architectural decisions, and verification
  results throughout a coding session. Persists state using Python
  configuration files for easy inspection and debugging.
  """

  def __init__(self, session_id: str):
    self.session_id = session_id
    self.discovered_patterns: List[Pattern] = []
    self.architectural_decisions: List[Decision] = []
    self.verification_results: Dict[str, VerificationResult] = {}
    self.claude_memories: List[str] = []

  def add_pattern(self, name: str, description: str, examples: Optional[List[str]] = None):
    """Record a discovered pattern"""
    pattern = Pattern(name=name, description=description, examples=examples or [])
    self.discovered_patterns.append(pattern)
    logger.info(f"Added pattern: {name}")

  def add_decision(self, description: str, rationale: str, files: Optional[List[str]] = None):
    """Record an architectural decision"""
    decision = Decision(description=description, rationale=rationale, related_files=files or [])
    self.architectural_decisions.append(decision)
    logger.info(f"Added decision: {description}")

  def add_verification(self, result: VerificationResult):
    """Record task verification outcome"""
    self.verification_results[result.task_id] = result
    logger.info(f"Added verification for task {result.task_id}: {'success' if result.success else 'failure'}")

  def add_memory(self, memory: str):
    """Add Claude conversation context"""
    self.claude_memories.append(memory)

  def to_dict(self) -> Dict:
    """Convert context to dictionary for persistence"""
    return {
      "session_id": self.session_id,
      "discovered_patterns": [
        {"name": p.name, "description": p.description, "examples": p.examples, "discovered_at": p.discovered_at}
        for p in self.discovered_patterns
      ],
      "architectural_decisions": [
        {
          "description": d.description,
          "rationale": d.rationale,
          "timestamp": d.timestamp,
          "related_files": d.related_files,
        }
        for d in self.architectural_decisions
      ],
      "verification_results": {
        task_id: {
          "success": r.success,
          "tests_passed": r.tests_passed,
          "tests_failed": r.tests_failed,
          "errors": r.errors,
          "timestamp": r.timestamp,
        }
        for task_id, r in self.verification_results.items()
      },
      "claude_memories": self.claude_memories,
    }

  def save(self, path: Path):
    """Save context to Python file"""
    data = self.to_dict()

    imports = {
      "datetime": "from datetime import datetime",
    }

    PythonConfigSerializer.write_config(
      path=path, config_name="CONTEXT", data=data, imports=imports, header="Auto-generated session context"
    )

  @classmethod
  def load(cls, path: Path, session_id: str) -> "SessionContext":
    """Load context from Python file"""
    if not path.exists():
      return cls(session_id)

    try:
      context_data = PythonConfigSerializer.read_config(path, "CONTEXT")
    except Exception as e:
      logger.warning(f"Failed to load context from {path}: {e}")
      return cls(session_id)

    context = cls(session_id)

    # Restore patterns
    for p in context_data.get("discovered_patterns", []):
      context.discovered_patterns.append(
        Pattern(name=p["name"], description=p["description"], examples=p["examples"], discovered_at=p["discovered_at"])
      )

    # Restore decisions
    for d in context_data.get("architectural_decisions", []):
      context.architectural_decisions.append(
        Decision(
          description=d["description"],
          rationale=d["rationale"],
          timestamp=d["timestamp"],
          related_files=d["related_files"],
        )
      )

    # Restore verification results
    for task_id, r in context_data.get("verification_results", {}).items():
      context.verification_results[task_id] = VerificationResult(
        task_id=task_id,
        success=r["success"],
        tests_passed=r["tests_passed"],
        tests_failed=r["tests_failed"],
        errors=r["errors"],
        timestamp=r["timestamp"],
      )

    # Restore memories
    context.claude_memories = context_data.get("claude_memories", [])

    return context

  def get_relevant_context(self, intent: str, scope: List[str]) -> str:
    """Generate context summary relevant to task intent"""
    context_parts = []

    # Add relevant patterns
    if self.discovered_patterns:
      context_parts.append("Known patterns:")
      for pattern in self.discovered_patterns:
        context_parts.append(f"  - {pattern.name}: {pattern.description}")

    # Add recent decisions
    if self.architectural_decisions:
      context_parts.append("\nArchitectural decisions:")
      for decision in self.architectural_decisions[-5:]:  # Last 5 decisions
        context_parts.append(f"  - {decision.description}")

    # Add relevant file history
    relevant_files = set(scope) if scope else set()
    for decision in self.architectural_decisions:
      if any(f in relevant_files for f in decision.related_files):
        context_parts.append(f"  - Related: {decision.rationale}")

    return "\n".join(context_parts) if context_parts else "No relevant context found."
