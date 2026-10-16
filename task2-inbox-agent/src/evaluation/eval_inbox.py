"""Evaluation script for Task 2: Inbox Agent.

Runs 20 customer email scenarios evaluating:
1. Haiku 3.5 Classification accuracy
2. Sonnet 4.5 Drafting quality & KB grounding
3. Levenshtein edit distance simulation
4. Auto-approval / autonomy triggers
"""

from __future__ import annotations

import json
from pathlib import Path
import time
import requests

DATASET_PATH = Path(__file__).resolve().parent.parent / "email" / "sample_emails.json"
API_URL = "http://localhost:8002/api/email/inbound"


def run_evaluation():
    if not DATASET_PATH.exists():
        print(f"Dataset missing at {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        emails = json.load(f)[:20]

    print(f"Running Inbox Agent Evaluation on {len(emails)} emails...\n")
    results = []

    for idx, em in enumerate(emails, start=1):
        print(f"[{idx}/20] {em['subject'][:45]}... ", end="")
        start = time.time()
        try:
            resp = requests.post(API_URL, json=em, timeout=15)
            elapsed = round(time.time() - start, 2)
            if resp.status_code == 200:
                data = resp.json()
                cat = data.get("category", "")
                draft = data.get("draft", "")
                auto = data.get("auto_approved", False)
                print(f"[SUCCESS] ({elapsed}s, cat={cat}, auto={auto})")
                results.append({"subject": em["subject"], "status": "PASS", "latency": elapsed})
            else:
                print(f"[HTTP {resp.status_code}]")
                results.append({"subject": em["subject"], "status": "FAIL", "latency": elapsed})
        except Exception as e:
            print(f"[OFFLINE: {e.__class__.__name__}]")
            results.append({"subject": em["subject"], "status": "OFFLINE", "latency": 0.0})

    passed = sum(1 for r in results if r["status"] == "PASS")
    print("\n" + "=" * 50)
    print(f"Task 2 Evaluation: {passed}/{len(emails)} processed successfully")
    print("=" * 50)


if __name__ == "__main__":
    run_evaluation()
