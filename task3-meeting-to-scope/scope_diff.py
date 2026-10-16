"""Python alias wrapper for scope-diff directory."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_diff_path = Path(__file__).resolve().parent / "scope-diff" / "diff_agent.py"
_spec = importlib.util.spec_from_file_location("diff_agent_module", _diff_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compute_diff = _mod.compute_diff
