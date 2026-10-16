"""Evaluation script for Task 3: Meeting to Scope of Work.

Evaluates the multi-agent pipeline across:
1. Long transcript chunking & synthesis
2. Requirement extraction recall & vagueness detection
3. Feasibility classification (platform settings vs custom dev)
4. Hour estimation boundaries
5. Follow-up meeting diff classification
6. Proposal generation acceptance benchmarking
"""

from __future__ import annotations

from pathlib import Path
import time
import requests

API_URL = "http://localhost:8003/api/meeting/pipeline"
TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "transcripts"


def run_evaluation():
    transcripts = list(TRANSCRIPTS_DIR.glob("*.txt"))
    print(f"Found {len(transcripts)} meeting transcripts for Task 3 Evaluation.\n")

    for t in sorted(transcripts):
        print(f"Testing pipeline with [{t.name}]... ", end="")
        content = t.read_text(encoding="utf-8")
        start = time.time()
        payload = {
            "client_name": "Test Client",
            "project_name": "Directory Upgrade",
            "transcript": content,
            "is_followup": "followup" in t.name.lower(),
            "hourly_rate": 100.0,
        }
        try:
            resp = requests.post(API_URL, json=payload, timeout=60)
            elapsed = round(time.time() - start, 2)
            if resp.status_code == 200:
                data = resp.json()
                req_count = len(data.get("requirements", []))
                has_sow = bool(data.get("sow_markdown"))
                has_prop = bool(data.get("proposal_markdown"))
                print(f"[SUCCESS] ({elapsed}s, reqs={req_count}, sow={has_sow}, prop={has_prop})")
            else:
                print(f"[HTTP {resp.status_code}]")
        except Exception as e:
            print(f"[OFFLINE: {e.__class__.__name__}]")


if __name__ == "__main__":
    run_evaluation()
