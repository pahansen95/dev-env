"""Search and discovery tools for finding files and content"""

import ast
import logging
import re

from ..server import mcp
from ..core import get_safe_path, find_git_root

logger = logging.getLogger(__name__)


@mcp.tool()
def find(
  query: str,
  match_type: str = "glob",  # "glob", "name", "exact"
  target_type: str = "both",  # "file", "dir", "both"
  directory: str = ".",
) -> list[str]:
  """Find files and directories using various matching strategies

  Args:
      query: Search query (glob pattern, name substring, or exact name)
      match_type: Matching strategy - "glob" (wildcards), "name" (substring), or "exact"
      target_type: What to find - "file", "dir", or "both"
      directory: Starting directory for search (default: project root)

  Returns:
      List of matching paths relative to project root
  """
  logger.info(f"find called with query='{query}', match_type='{match_type}', target_type='{target_type}'")

  if match_type not in ["glob", "name", "exact"]:
    raise ValueError("match_type must be 'glob', 'name', or 'exact'")
  if target_type not in ["file", "dir", "both"]:
    raise ValueError("target_type must be 'file', 'dir', or 'both'")

  # Validate and get search directory
  try:
    search_dir = get_safe_path(directory, must_exist=True)
  except (ValueError, FileNotFoundError) as e:
    logger.error(f"Invalid search directory: {e}")
    return []

  git_root = find_git_root()
  results = []

  # Limit results to prevent memory issues
  MAX_RESULTS = 10000

  try:
    # Glob pattern matching
    if match_type == "glob":
      # Validate glob pattern
      if not query or query.strip() == "":
        return []

      # Use rglob for recursive search if pattern contains '**'
      if "**" in query:
        matches = search_dir.rglob(query.replace("**/", ""))
      else:
        matches = search_dir.glob(query)

      for path in matches:
        if len(results) >= MAX_RESULTS:
          logger.warning(f"Result limit ({MAX_RESULTS}) reached")
          break

        try:
          relative_path = str(path.relative_to(git_root))
          if target_type == "file" and path.is_file():
            results.append(relative_path)
          elif target_type == "dir" and path.is_dir():
            results.append(relative_path + "/")
          elif target_type == "both":
            results.append(relative_path + ("/" if path.is_dir() else ""))
        except (ValueError, OSError) as e:
          logger.debug(f"Skipping inaccessible path {path}: {e}")
          continue

    # Name substring matching
    elif match_type == "name":
      if not query:
        return []

      for path in search_dir.rglob("*"):
        if len(results) >= MAX_RESULTS:
          logger.warning(f"Result limit ({MAX_RESULTS}) reached")
          break

        try:
          if query in path.name:
            relative_path = str(path.relative_to(git_root))
            if target_type == "file" and path.is_file():
              results.append(relative_path)
            elif target_type == "dir" and path.is_dir():
              results.append(relative_path + "/")
            elif target_type == "both":
              results.append(relative_path + ("/" if path.is_dir() else ""))
        except (ValueError, OSError) as e:
          logger.debug(f"Skipping inaccessible path {path}: {e}")
          continue

    # Exact name matching
    elif match_type == "exact":
      if not query:
        return []

      for path in search_dir.rglob("*"):
        if len(results) >= MAX_RESULTS:
          logger.warning(f"Result limit ({MAX_RESULTS}) reached")
          break

        try:
          if path.name == query:
            relative_path = str(path.relative_to(git_root))
            if target_type == "file" and path.is_file():
              results.append(relative_path)
            elif target_type == "dir" and path.is_dir():
              results.append(relative_path + "/")
            elif target_type == "both":
              results.append(relative_path + ("/" if path.is_dir() else ""))
        except (ValueError, OSError) as e:
          logger.debug(f"Skipping inaccessible path {path}: {e}")
          continue

  except Exception as e:
    logger.error(f"Error during find operation: {e}")
    return []

  logger.info(f"Found {len(results)} items matching query '{query}'")
  return sorted(results)


@mcp.tool()
def search(
  pattern: str,
  search_type: str = "string",  # "string", "regex", "ast"
  file_pattern: str = "**/*",
  max_files: int = 100,
  context_lines: int = 0,
  definition_type: str = None,  # For AST searches: "function", "class", or "any"
) -> list[dict]:
  """Universal search tool for finding patterns in project files

  Args:
      pattern: Search pattern (string, regex, or function/class name)
      search_type: Type of search - "string", "regex", or "ast" (for Python definitions)
      file_pattern: Glob pattern for files to search (default: all files)
      max_files: Maximum number of files to search
      context_lines: Number of context lines before/after match (for string/regex)
      definition_type: For AST search - "function", "class", or "any" (default: "any")

  Returns:
      List of matches with file path, line number, and match details
  """
  logger.info(f"search called with pattern='{pattern}', search_type='{search_type}', file_pattern='{file_pattern}'")

  if search_type not in ["string", "regex", "ast"]:
    raise ValueError("search_type must be 'string', 'regex', or 'ast'")

  # Validate inputs
  if not pattern:
    return [{"error": "Search pattern cannot be empty"}]

  if max_files < 1:
    max_files = 1
  elif max_files > 1000:
    max_files = 1000

  if context_lines < 0:
    context_lines = 0
  elif context_lines > 10:
    context_lines = 10

  git_root = find_git_root()
  results = []
  files_searched = 0

  # AST-based search for Python code definitions
  if search_type == "ast":
    if definition_type is None:
      definition_type = "any"
    elif definition_type not in ["function", "class", "any"]:
      return [{"error": "definition_type must be 'function', 'class', or 'any'"}]

    # Only search Python files for AST
    if not file_pattern.endswith(".py"):
      file_pattern = "**/*.py"

    try:
      for file_path in git_root.rglob(file_pattern.replace("**/", "")):
        if files_searched >= max_files:
          break

        if not file_path.is_file() or not file_path.suffix == ".py":
          continue

        files_searched += 1

        try:
          content = file_path.read_text(encoding="utf-8")
          tree = ast.parse(content, filename=str(file_path))

          # Walk AST to find definitions
          for node in ast.walk(tree):
            match = False
            node_type = None

            if definition_type in ("function", "any") and isinstance(node, ast.FunctionDef):
              if node.name == pattern:
                match = True
                node_type = "function"

            elif definition_type in ("class", "any") and isinstance(node, ast.ClassDef):
              if node.name == pattern:
                match = True
                node_type = "class"

            if match and hasattr(node, "lineno"):
              # Get preview lines
              lines = content.splitlines()
              start = max(0, node.lineno - 1)
              end = min(len(lines), node.lineno + 4)
              preview = lines[start:end]

              results.append(
                {
                  "file": str(file_path.relative_to(git_root)),
                  "line": node.lineno,
                  "type": node_type,
                  "name": node.name,
                  "preview": "\n".join(preview),
                }
              )

        except (SyntaxError, UnicodeDecodeError) as e:
          logger.debug(f"Error parsing {file_path}: {e}")
          continue
        except Exception as e:
          logger.error(f"Unexpected error parsing {file_path}: {e}")
          continue
    except Exception as e:
      logger.error(f"Error during AST search: {e}")
      return [{"error": f"Search failed: {str(e)}"}]

  # String and regex searches
  else:
    # Compile regex if needed
    regex = None
    if search_type == "regex":
      try:
        regex = re.compile(pattern)
      except re.error as e:
        logger.error(f"Invalid regex pattern: {e}")
        return [{"error": f"Invalid regex pattern: {str(e)}"}]

    try:
      # Exclude common binary file extensions
      BINARY_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".bin",
        ".o",
        ".a",
        ".lib",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".ico",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".db",
        ".sqlite",
        ".sqlite3",
      }

      for file_path in git_root.rglob(file_pattern.replace("**/", "")):
        if files_searched >= max_files:
          if not results:  # Only add warning if we haven't found anything yet
            results.append({"warning": f"Stopped after searching {max_files} files"})
          break

        if not file_path.is_file():
          continue

        # Skip binary files
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
          continue

        files_searched += 1

        try:
          content = file_path.read_text(encoding="utf-8")
          lines = content.splitlines()

          for line_num, line in enumerate(lines, 1):
            match_found = False
            match_text = None

            if search_type == "string":
              if pattern in line:
                match_found = True
                match_text = pattern
            else:  # regex
              match = regex.search(line)
              if match:
                match_found = True
                match_text = match.group(0)

            if match_found:
              result = {
                "file": str(file_path.relative_to(git_root)),
                "line": line_num,
                "match": match_text,
                "full_line": line.strip(),
              }

              # Add context if requested
              if context_lines > 0:
                start = max(0, line_num - context_lines - 1)
                end = min(len(lines), line_num + context_lines)
                context = lines[start:end]
                result["context"] = "\n".join(f"{start + i + 1}: {ctx_line}" for i, ctx_line in enumerate(context))

              results.append(result)

        except (UnicodeDecodeError, PermissionError) as e:
          # Skip binary files or files we can't read
          logger.debug(f"Skipping file {file_path}: {e}")
          continue
        except Exception as e:
          logger.error(f"Error reading file {file_path}: {e}")
          continue
    except Exception as e:
      logger.error(f"Error during search: {e}")
      return [{"error": f"Search failed: {str(e)}"}]

  logger.info(f"Searched {files_searched} files, found {len(results)} matches")
  return results
