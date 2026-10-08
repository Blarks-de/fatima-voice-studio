"""stdio MCP launcher for agents (Claude Code etc.) on Linux. Fatima Voice Studio must be running.

  command: <repo>/linux/.venv/bin/python   args: ["<repo>/linux/mcp_stdio.py"]
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compat  # noqa: E402

compat.apply()
runpy.run_path(str(compat.REPO / "studio_mcp.py"), run_name="__main__")
