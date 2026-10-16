"""Alias wrapper for knowledge-client directory to allow standard Python imports."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_client_path = Path(__file__).resolve().parent / "knowledge-client" / "client.py"
_spec = importlib.util.spec_from_file_location("knowledge_client_module", _client_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

KnowledgeClient = _mod.KnowledgeClient
knowledge_client = _mod.knowledge_client
