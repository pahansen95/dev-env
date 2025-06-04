"""Tool Documentation Registry

Provides a comprehensive documentation system that captures rich contextual
information about tool purpose, usage patterns, and operational characteristics.

## Architecture

The documentation system builds mental models through structured metadata:

1. **Purpose-driven structure** - Why tools exist and when to use them
2. **Progressive examples** - From basic to advanced usage
3. **Error intelligence** - Diagnosis and recovery strategies
3. **document_tool** - Decorator for registration

This design co-locates documentation with implementation while maintaining
a centralized registry for runtime introspection.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Literal

logger = logging.getLogger(__name__)


@dataclass
class UsageScenario:
  """Specific scenario where tool is appropriate.

  Attributes:
      condition: When to use this tool
      rationale: Why it's the right choice
  """

  condition: str
  rationale: str


@dataclass
class AntiPattern:
  """Scenario where tool should not be used.

  Attributes:
      condition: Scenario to avoid
      reason: Why it's inappropriate
      alternative: What to use instead
  """

  condition: str
  reason: str
  alternative: str


@dataclass
class Example:
  """Progressive usage example.

  Attributes:
      title: Example name
      code: Executable code
      explanation: What this demonstrates
      complexity: 1-3 (basic, intermediate, advanced)
  """

  title: str
  code: str
  explanation: str
  complexity: Literal[1, 2, 3] = 1


@dataclass
class ErrorScenario:
  """Structured error scenario documentation.

  Attributes:
      error_type: Exception class name (e.g., "FileNotFoundError")
      cause: What triggers this error
      diagnosis: How to investigate
      recovery: How to fix
      state_impact: What state changes occurred
  """

  error_type: str
  cause: str
  diagnosis: str
  recovery: str
  state_impact: str = "No changes"


@dataclass
class PerformanceProfile:
  """Tool performance characteristics.

  Attributes:
      time_complexity: Big-O notation
      memory_usage: Memory requirements
      network_impact: Network usage if applicable
      concurrency: Thread/process safety
  """

  time_complexity: str
  memory_usage: str
  network_impact: Optional[str] = None
  concurrency: str = "Thread-safe"


@dataclass
class ToolDocumentation:
  """Comprehensive tool documentation.

  Attributes:
      name: Tool identifier
      purpose: One-line statement of why this tool exists
      category: Functional grouping (e.g., "File Operations")
      operational_model: Brief conceptual explanation
      usage_scenarios: When to use this tool
      anti_patterns: When not to use this tool
      examples: Progressive usage examples
      error_scenarios: Common failures and recovery
      performance: Performance characteristics
      see_also: Related tools with relationships
      composition: Common tool combinations
  """

  name: str
  purpose: str
  category: str
  operational_model: str
  usage_scenarios: List[UsageScenario] = field(default_factory=list)
  anti_patterns: List[AntiPattern] = field(default_factory=list)
  examples: List[Example] = field(default_factory=list)
  error_scenarios: List[ErrorScenario] = field(default_factory=list)
  performance: Optional[PerformanceProfile] = None
  see_also: Dict[str, str] = field(default_factory=dict)
  composition: List[str] = field(default_factory=list)


class ToolRegistry:
  """Centralized registry for tool documentation.

  Maintains a mapping of tool names to their documentation metadata,
  supporting runtime introspection and help generation.
  """

  def __init__(self):
    self._registry: Dict[str, ToolDocumentation] = {}
    self._categories: Dict[str, List[str]] = {}

  def register(self, documentation: ToolDocumentation) -> None:
    """Register tool documentation.

    Args:
        documentation: Tool documentation metadata
    """
    self._registry[documentation.name] = documentation

    # Update category index
    if documentation.category not in self._categories:
      self._categories[documentation.category] = []
    if documentation.name not in self._categories[documentation.category]:
      self._categories[documentation.category].append(documentation.name)

    logger.debug(f"Registered documentation for tool: {documentation.name}")

  def get(self, tool_name: str) -> Optional[ToolDocumentation]:
    """Retrieve documentation for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool documentation or None if not found
    """
    return self._registry.get(tool_name)

  def get_all(self) -> Dict[str, ToolDocumentation]:
    """Get all registered tool documentation.

    Returns:
        Dictionary mapping tool names to documentation
    """
    return self._registry.copy()

  def get_by_category(self, category: str) -> List[ToolDocumentation]:
    """Get all tools in a specific category.

    Args:
        category: Category name

    Returns:
        List of tool documentation in the category
    """
    tool_names = self._categories.get(category, [])
    return [self._registry[name] for name in tool_names if name in self._registry]

  def get_categories(self) -> Dict[str, List[str]]:
    """Get all categories and their tools.

    Returns:
        Dictionary mapping categories to tool names
    """
    return self._categories.copy()


# Global registry instance
_tool_registry = ToolRegistry()


def document_tool(
  name: str,
  purpose: str,
  category: str,
  *,
  operational_model: str,
  usage_scenarios: List[Dict[str, str]],
  examples: List[Dict[str, Any]],
  anti_patterns: Optional[List[Dict[str, str]]] = None,
  error_scenarios: Optional[List[Dict[str, str]]] = None,
  performance: Optional[Dict[str, str]] = None,
  see_also: Optional[Dict[str, str]] = None,
  composition: Optional[List[str]] = None,
) -> Callable:
  """Decorator to register comprehensive tool documentation.

  Captures rich contextual information about tool purpose, usage patterns,
  and operational characteristics.

  Args:
      name: Tool identifier (must match @mcp.tool name)
      purpose: One-line statement of why this tool exists
      category: Functional grouping for organization
      operational_model: Brief conceptual explanation
      usage_scenarios: List with 'condition' and 'rationale'
      examples: Progressive examples with 'title', 'code', 'explanation', 'complexity'
      anti_patterns: List with 'condition', 'reason', 'alternative'
      error_scenarios: List with error details
      performance: Dict with complexity and resource usage
      see_also: Dict mapping tool names to relationships
      composition: List of common tool combination patterns

  Example:
      @document_tool(
          name="file_read",
          purpose="Safely read text files within project boundaries",
          category="File Operations",
          operational_model="Validates path, reads entire file, returns UTF-8 string",
          usage_scenarios=[
              {"condition": "Reading config files", "rationale": "Enforces boundaries"}
          ],
          examples=[
              {"title": "Basic read", "code": "file_read('config.json')",
               "explanation": "Simple file reading", "complexity": 1}
          ]
      )
      @mcp.tool(name="file_read")
      def read_file(path: str) -> str:
          ...
  """

  def decorator(func: Callable) -> Callable:
    # Convert usage scenarios
    scenarios = [UsageScenario(**s) for s in usage_scenarios]

    # Convert anti-patterns
    patterns = []
    if anti_patterns:
      patterns = [AntiPattern(**p) for p in anti_patterns]

    # Convert examples
    exs = []
    for ex in examples:
      complexity = ex.get("complexity", 1)
      exs.append(Example(title=ex["title"], code=ex["code"], explanation=ex["explanation"], complexity=complexity))

    # Convert error scenarios
    errors = []
    if error_scenarios:
      for err in error_scenarios:
        errors.append(
          ErrorScenario(
            error_type=err["error_type"],
            cause=err["cause"],
            diagnosis=err["diagnosis"],
            recovery=err["recovery"],
            state_impact=err.get("state_impact", "No changes"),
          )
        )

    # Convert performance profile
    perf = None
    if performance:
      perf = PerformanceProfile(
        time_complexity=performance["time_complexity"],
        memory_usage=performance["memory_usage"],
        network_impact=performance.get("network_impact"),
        concurrency=performance.get("concurrency", "Thread-safe"),
      )

    # Create documentation object
    documentation = ToolDocumentation(
      name=name,
      purpose=purpose,
      category=category,
      operational_model=operational_model,
      usage_scenarios=scenarios,
      anti_patterns=patterns,
      examples=exs,
      error_scenarios=errors,
      performance=perf,
      see_also=see_also or {},
      composition=composition or [],
    )

    # Register with global registry
    _tool_registry.register(documentation)

    # Return original function unchanged
    return func

  return decorator


def get_tool_registry() -> ToolRegistry:
  """Access the global tool documentation registry.

  Returns:
      The global ToolRegistry instance
  """
  return _tool_registry
