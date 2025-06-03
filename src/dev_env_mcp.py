#!/usr/bin/env python3
"""
Legacy wrapper for backwards compatibility.
This script redirects to the refactored package structure.
"""

import sys
from pathlib import Path

# Add src to path to import the package
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main entry point
from mcp_project_integration.cli import main

if __name__ == "__main__":
  sys.exit(main())
