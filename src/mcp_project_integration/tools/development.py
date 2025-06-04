"""Development tools for code modifications and syntax validation"""

import ast
import difflib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from ..server import mcp
from ..core import get_safe_path, find_git_root

logger = logging.getLogger(__name__)

TOOL_PREFIX = "patch"


def validate_syntax(file_path: Path) -> dict:
  """Validate file syntax based on extension

  Returns dict with:
      - valid: bool (True if syntax is valid)
      - status: 'valid', 'invalid', or 'skipped'
      - message: Description of validation result
      - errors: List of syntax errors if any
  """
  extension = file_path.suffix.lower()

  # Python files
  if extension == ".py":
    try:
      content = file_path.read_text()
      ast.parse(content, filename=str(file_path))
      return {"valid": True, "status": "valid", "message": "Python syntax is valid"}
    except SyntaxError as e:
      return {
        "valid": False,
        "status": "invalid",
        "message": f"Python syntax error at line {e.lineno}",
        "errors": [f"Line {e.lineno}: {e.msg}"],
      }

  # JSON files
  elif extension == ".json":
    try:
      content = file_path.read_text()
      json.loads(content)
      return {"valid": True, "status": "valid", "message": "JSON syntax is valid"}
    except json.JSONDecodeError as e:
      return {
        "valid": False,
        "status": "invalid",
        "message": f"JSON syntax error at line {e.lineno}",
        "errors": [f"Line {e.lineno}, Column {e.colno}: {e.msg}"],
      }

  # Unsupported file types
  else:
    return {
      "valid": True,  # Assume valid since we can't check
      "status": "skipped",
      "message": f"Syntax validation not supported for {extension} files",
    }


class PatchHunk:
  """Represents a single hunk in a patch"""

  def __init__(self, old_start: int, old_count: int, new_start: int, new_count: int):
    self.old_start = old_start
    self.old_count = old_count
    self.new_start = new_start
    self.new_count = new_count
    self.raw_lines = []  # All lines in order with their types

  def get_expected_content(self) -> list[str]:
    """Get the content we expect to find in the file"""
    return [line for line_type, line in self.raw_lines if line_type in (" ", "-")]

  def get_replacement_content(self) -> list[str]:
    """Get the content to replace with"""
    return [line for line_type, line in self.raw_lines if line_type in (" ", "+")]


class ImprovedPatchParser:
  """Improved patch parser with better error handling"""

  def __init__(self, patch_content: str):
    self.patch_lines = patch_content.splitlines(keepends=True)
    self.hunks: list[PatchHunk] = []
    self._parse()

  def _parse(self):
    """Parse the patch into hunks"""
    hunk_header_re = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    current_hunk = None

    for line in self.patch_lines:
      # Skip file headers
      if line.startswith("---") or line.startswith("+++"):
        continue

      # Check for hunk header
      match = hunk_header_re.match(line)
      if match:
        # Save previous hunk
        if current_hunk:
          self.hunks.append(current_hunk)

        # Create new hunk
        old_start = int(match.group(1))
        old_count = int(match.group(2) or 1)
        new_start = int(match.group(3))
        new_count = int(match.group(4) or 1)

        current_hunk = PatchHunk(old_start, old_count, new_start, new_count)

      elif current_hunk and line:
        # Process hunk content
        if line.startswith("-") and len(line) > 1:
          current_hunk.raw_lines.append(("-", line[1:]))
        elif line.startswith("+") and len(line) > 1:
          current_hunk.raw_lines.append(("+", line[1:]))
        elif line.startswith(" "):
          current_hunk.raw_lines.append((" ", line[1:]))

    # Don't forget the last hunk
    if current_hunk:
      self.hunks.append(current_hunk)


class ContextMatcher:
  """Sophisticated context matching with fuzzy logic"""

  def __init__(self, tolerance: float = 0.85):
    self.tolerance = tolerance

  def find_best_match(self, expected_lines: list[str], file_lines: list[str], start_hint: int) -> int | None:
    """Find the best matching position for expected content"""
    # First try exact match at expected position
    if self._try_exact_match(expected_lines, file_lines, start_hint):
      return start_hint

    # Try searching nearby (± 10 lines)
    search_range = 10
    for offset in range(1, search_range + 1):
      # Try forward
      if start_hint + offset < len(file_lines):
        if self._try_exact_match(expected_lines, file_lines, start_hint + offset):
          logger.info(f"Found exact match {offset} lines forward")
          return start_hint + offset

      # Try backward
      if start_hint - offset >= 0:
        if self._try_exact_match(expected_lines, file_lines, start_hint - offset):
          logger.info(f"Found exact match {offset} lines backward")
          return start_hint - offset

    # Fall back to fuzzy matching
    best_pos, best_score = self._fuzzy_search(expected_lines, file_lines, start_hint)
    if best_score >= self.tolerance:
      logger.info(f"Found fuzzy match at line {best_pos + 1} with score {best_score:.2f}")
      return best_pos

    return None

  def _try_exact_match(self, expected: list[str], file_lines: list[str], start: int) -> bool:
    """Check if expected lines exactly match at given position"""
    if start < 0 or start + len(expected) > len(file_lines):
      return False

    for i, expected_line in enumerate(expected):
      if self._normalize_line(expected_line) != self._normalize_line(file_lines[start + i]):
        return False

    return True

  def _fuzzy_search(self, expected: list[str], file_lines: list[str], hint: int) -> tuple[int, float]:
    """Search for best fuzzy match near hint position"""
    best_pos = hint - 1
    best_score = 0.0

    # Search window based on file size
    window = min(50, len(file_lines) // 10)
    start = max(0, hint - window)
    end = min(len(file_lines) - len(expected) + 1, hint + window)

    for pos in range(start, end):
      score = self._calculate_similarity(expected, file_lines[pos : pos + len(expected)])
      if score > best_score:
        best_score = score
        best_pos = pos

    return best_pos, best_score

  def _calculate_similarity(self, expected: list[str], actual: list[str]) -> float:
    """Calculate similarity score between line sequences"""
    if len(expected) != len(actual):
      return 0.0

    scores = []
    for exp_line, act_line in zip(expected, actual):
      # Normalize and compare
      exp_norm = self._normalize_line(exp_line)
      act_norm = self._normalize_line(act_line)

      matcher = difflib.SequenceMatcher(None, exp_norm, act_norm)
      scores.append(matcher.ratio())

    return sum(scores) / len(scores) if scores else 0.0

  def _normalize_line(self, line: str) -> str:
    """Normalize line for comparison"""
    # Strip trailing whitespace but preserve indentation
    return line.rstrip()


@mcp.tool(
  name=f"{TOOL_PREFIX}_apply",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # Creates backup first
    "idempotentHint": False,
    "openWorldHint": False,
  },
)
def apply_patch(file_path: str, patch: str) -> dict:
  """Apply a unified diff patch to a file using difflib

  Args:
      file_path: Path to file to patch
      patch: Unified diff format patch string

  Returns:
      dict with status, backup_path, and any errors

  Use when:
  - Applying code review suggestions
  - Implementing incremental changes
  - Testing modifications safely
  - Programmatically editing files

  Patch format:
  Standard unified diff format with:
  - --- original/file.py
  - +++ modified/file.py
  - @@ -start,count +start,count @@ headers
  - Lines starting with - (removed)
  - Lines starting with + (added)
  - Lines starting with space (context)

  Features:
  - Sophisticated fuzzy matching (85% similarity threshold)
  - Automatic backup creation before modification
  - Python/JSON syntax validation after patching
  - Multi-hunk support with independent matching
  - Searches ±10 lines for displaced content

  Return format:
  Success:
  {
    "status": "success",
    "backup_path": "relative/path/to/backup",
    "lines_changed": 42,
    "hunks_applied": 3,
    "syntax_validation": {"valid": true, "status": "valid"}
  }

  Error:
  {
    "status": "error",
    "error": "Failed to find context...",
    "failed_hunk": 23  # Line number of failed hunk
  }

  Safety features:
  - Always creates timestamped backup
  - Validates file exists before patching
  - Restores original on any error
  - Reports syntax errors after patching

  Example patch:
  ```
  --- a/config.py
  +++ b/config.py
  @@ -10,3 +10,3 @@
  -DEBUG = False
  +DEBUG = True
  ```
  """
  logger.info(f"apply_patch called for {file_path}")

  try:
    # Parse the patch
    parser = ImprovedPatchParser(patch)
    if not parser.hunks:
      return {"status": "error", "error": "No valid hunks found in patch"}

    # Validate and resolve path
    target_path = get_safe_path(file_path, must_exist=True)

    # Create backup first
    backup_name = f".{target_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    backup_path = target_path.parent / backup_name
    backup_path.write_bytes(target_path.read_bytes())

    # Read current content
    original_content = target_path.read_text()
    working_lines = original_content.splitlines(keepends=True)

    # Apply hunks with sophisticated matching
    matcher = ContextMatcher()
    applied_hunks = 0
    offset = 0  # Track cumulative line offset

    # Sort hunks by line number to apply in order
    sorted_hunks = sorted(parser.hunks, key=lambda h: h.old_start)

    for hunk in sorted_hunks:
      # Adjust for previous modifications
      adjusted_start = hunk.old_start - 1 + offset

      # Get expected content
      expected_lines = hunk.get_expected_content()

      # Find best match position
      match_pos = matcher.find_best_match(expected_lines, working_lines, adjusted_start)

      if match_pos is None:
        error_msg = f"Failed to find context for hunk starting at line {hunk.old_start}"
        logger.error(error_msg)

        # Restore from backup
        if backup_path and backup_path.exists():
          target_path.write_text(original_content)
          logger.info("Restored from backup after error")

        return {"status": "error", "error": error_msg, "failed_hunk": hunk.old_start}

      # Apply the hunk
      replacement = hunk.get_replacement_content()

      # Ensure proper line endings
      if working_lines and replacement and not replacement[-1].endswith("\n"):
        replacement[-1] += "\n"

      # Perform replacement
      end_pos = match_pos + len(expected_lines)
      working_lines[match_pos:end_pos] = replacement

      # Update offset for next hunk
      offset += len(replacement) - len(expected_lines)
      applied_hunks += 1

      logger.info(f"Applied hunk {applied_hunks}/{len(parser.hunks)} at line {match_pos + 1}")

    # Write result
    result_content = "".join(working_lines)
    target_path.write_text(result_content)

    # Validate syntax after patching
    validation = validate_syntax(target_path)

    # Calculate total lines changed
    lines_changed = sum(
      len([line for t, line in h.raw_lines if t == "-"]) + len([line for t, line in h.raw_lines if t == "+"])
      for h in parser.hunks
    )

    return {
      "status": "success",
      "backup_path": str(backup_path.relative_to(find_git_root())),
      "lines_changed": lines_changed,
      "hunks_applied": applied_hunks,
      "syntax_validation": validation,
    }

  except Exception as e:
    logger.error(f"Failed to apply patch: {e}")
    # Restore from backup on error
    if "backup_path" in locals() and backup_path.exists():
      try:
        target_path.write_bytes(backup_path.read_bytes())
        logger.info("Restored file from backup")
      except Exception as restore_error:
        logger.error(f"Failed to restore backup: {restore_error}")
    return {"status": "error", "error": str(e)}
