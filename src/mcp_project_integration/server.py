"""MCP Server instance and configuration"""

import logging
import subprocess
import sys
from mcp.server.fastmcp import FastMCP
from .utils import get_git_project_name

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Create MCP server instance
try:
  git_project_name = get_git_project_name()
  server_display_name = f"Project: {git_project_name}"
except subprocess.CalledProcessError:
  # Not in a git repo yet, use generic name
  server_display_name = "Project Integration"

mcp = FastMCP(server_display_name)

# Import and register all tools - this happens when server module is imported
from . import tools  # noqa: F401 E402
