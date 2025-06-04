"""Usage and documentation tool for dev-env MCP integration"""

import logging
from typing import Optional, Dict, Any, List
import inspect

from ..server import mcp
from ..core import document_tool, get_tool_registry, UsageScenario, AntiPattern, ErrorScenario, PerformanceProfile

logger = logging.getLogger(__name__)

TOOL_PREFIX = "tool"


def _format_usage_scenarios(scenarios: List[UsageScenario]) -> List[Dict[str, str]]:
  """Format usage scenarios for display."""
  return [{"when": scenario.condition, "because": scenario.rationale} for scenario in scenarios]


def _format_anti_patterns(patterns: List[AntiPattern]) -> List[Dict[str, str]]:
  """Format anti-patterns for display."""
  return [
    {"avoid": pattern.condition, "reason": pattern.reason, "use_instead": pattern.alternative} for pattern in patterns
  ]


def _format_examples(examples) -> List[Dict[str, str]]:
  """Format progressive examples for display."""
  # Sort by complexity
  sorted_examples = sorted(examples, key=lambda x: x.complexity)

  complexity_labels = {1: "Basic", 2: "Intermediate", 3: "Advanced"}

  return [
    {
      "level": complexity_labels.get(ex.complexity, "Basic"),
      "title": ex.title,
      "code": ex.code,
      "explanation": ex.explanation,
    }
    for ex in sorted_examples
  ]


def _format_error_scenarios(errors: List[ErrorScenario]) -> List[Dict[str, str]]:
  """Format error scenarios with diagnosis and recovery."""
  return [
    {
      "error": err.error_type,
      "cause": err.cause,
      "diagnosis": err.diagnosis,
      "recovery": err.recovery,
      "state_impact": err.state_impact,
    }
    for err in errors
  ]


def _format_performance(perf: Optional[PerformanceProfile]) -> Optional[Dict[str, str]]:
  """Format performance characteristics."""
  if not perf:
    return None

  result = {"time_complexity": perf.time_complexity, "memory_usage": perf.memory_usage, "concurrency": perf.concurrency}

  if perf.network_impact:
    result["network_impact"] = perf.network_impact

  return result


@document_tool(
  name="tool_usage",
  purpose="Discover and understand available dev-env tools",
  category="Documentation",
  operational_model="""
    Queries the global tool registry to provide categorized listings or
    detailed documentation for specific tools including examples and error scenarios.
    """,
  usage_scenarios=[
    {"condition": "Starting work with dev-env", "rationale": "Discover available tools and their purposes"},
    {"condition": "Before using an unfamiliar tool", "rationale": "Understand parameters, errors, and best practices"},
  ],
  examples=[
    {
      "title": "List all tools",
      "code": "tool_usage()",
      "explanation": "Shows all tools organized by functional category",
      "complexity": 1,
    },
    {
      "title": "Get specific help",
      "code": "tool_usage('file_read')",
      "explanation": "Shows comprehensive documentation for file_read",
      "complexity": 1,
    },
    {
      "title": "Discover file tools",
      "code": "result = tool_usage()\nfile_tools = result['categories']['File Operations']",
      "explanation": "Extract tools for a specific category",
      "complexity": 2,
    },
  ],
  see_also={"project_status": "Check project state before using tools"},
  performance={"time_complexity": "O(1) - registry lookup", "memory_usage": "Minimal - returns documentation only"},
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_usage",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def tool_usage(tool_name: Optional[str] = None) -> Dict[str, Any]:
  """Get usage information for dev-env tools.

  Args:
      tool_name: Specific tool name to get help for (optional).
                If omitted, lists all available tools.

  Returns:
      Dictionary containing tool documentation
  """
  logger.info(f"tool_usage called with tool_name='{tool_name}'")

  registry = get_tool_registry()

  try:
    if tool_name:
      # Get specific tool details
      doc = registry.get(tool_name)

      if not doc:
        all_tools = sorted(registry.get_all().keys())
        return {
          "error": f"Tool '{tool_name}' not found",
          "available_tools": all_tools,
          "hint": "Use tool_usage() without arguments to see all tools",
        }

      # Core information
      result = {
        "name": doc.name,
        "purpose": doc.purpose,
        "category": doc.category,
        "conceptual_model": doc.operational_model,
      }

      # Usage guidance
      if doc.usage_scenarios:
        result["when_to_use"] = _format_usage_scenarios(doc.usage_scenarios)

      if doc.anti_patterns:
        result["when_not_to_use"] = _format_anti_patterns(doc.anti_patterns)

      # Examples
      if doc.examples:
        result["examples"] = _format_examples(doc.examples)

      # Error handling
      if doc.error_scenarios:
        result["common_errors"] = _format_error_scenarios(doc.error_scenarios)

      # Performance
      perf = _format_performance(doc.performance)
      if perf:
        result["performance"] = perf

      # Relationships
      if doc.see_also:
        result["see_also"] = doc.see_also

      if doc.composition:
        result["commonly_used_with"] = doc.composition

      # Try to get function signature if tool is registered
      if hasattr(mcp, "_handlers") and hasattr(mcp._handlers, "tools"):
        if tool_name in mcp._handlers.tools:
          handler = mcp._handlers.tools[tool_name]
          func = handler.fn
          result["signature"] = str(inspect.signature(func))

      return result

    else:
      # List all tools by category
      categories = registry.get_categories()

      if not categories:
        return {"message": "No tools have been documented yet", "hint": "Tools need to use @document_tool decorator"}

      result = {
        "total_tools": len(registry.get_all()),
        "usage_hint": "Call tool_usage('tool_name') for detailed documentation",
        "categories": {},
      }

      # Build categorized listing
      for category, tool_names in sorted(categories.items()):
        category_tools = []
        for tool_name in sorted(tool_names):
          doc = registry.get(tool_name)
          if doc:
            category_tools.append({"name": tool_name, "purpose": doc.purpose})

        if category_tools:
          result["categories"][category] = category_tools

      return result

  except Exception as e:
    logger.error(f"Error in tool_usage: {e}", exc_info=True)
    return {"error": f"Failed to retrieve tool information: {str(e)}", "type": type(e).__name__}
