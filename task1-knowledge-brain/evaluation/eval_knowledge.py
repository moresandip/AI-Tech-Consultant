"""Evaluator for Task 1: Knowledge Brain.

Loads the 20 benchmark test cases from test_cases.json, runs them against the
Task 1 API (or directly against the retrieval pipeline), and computes accuracy,
keyword recall, and escalation rates.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
import requests

EVAL_PATH = Path(__file__).resolve().parent / "test_cases.json"
API_URL = "http://localhost:8001/api/query"
API_KEY = "dev-secret-task1"


def run_evaluation():
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} test cases for Task 1 Evaluation.\n")
    results = []

    for c in cases:
        print(f"Running [{c['id']}] {c['question'][:50]}... ", end="")
        start = time.time()
        try:
            resp = requests.post(
                API_URL,
                headers={"X-API-Key": API_KEY},
                json={"question": c["question"], "top_k": 3, "include_images": True},
                timeout=10,
            )
            elapsed = round(time.time() - start, 2)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "").lower()
                escalated = data.get("escalated", False)

                # Check if expected keywords are present
                hits = [kw for kw in c["expected_keywords"] if kw.lower() in answer]
                recall = len(hits) / len(c["expected_keywords"]) if c["expected_keywords"] else 1.0
                passed = recall >= 0.5 or (c["category"] in ["Out of Domain", "Unknown Info"] and escalated)

                results.append({
                    "id": c["id"],
                    "status": "PASS" if passed else "FAIL",
                    "latency": elapsed,
                    "confidence": data.get("confidence", 0.0),
                    "escalated": escalated,
                })
                print(f"[{'PASS' if passed else 'FAIL'}] ({elapsed}s, conf={data.get('confidence')})")
            else:
                print(f"[HTTP {resp.status_code}]")
                results.append({"id": c["id"], "status": "ERROR", "latency": elapsed})
        except Exception as e:
            print(f"[OFFLINE: {e.__class__.__name__}]")
            results.append({"id": c["id"], "status": "OFFLINE", "latency": 0.0})

    passed_count = sum(1 for r in results if r["status"] == "PASS")
    print("\n" + "=" * 50)
    print(f"Task 1 Evaluation Summary: {passed_count}/{len(cases)} Passed")
    print("=" * 50)


if __name__ == "__main__":
    run_evaluation()
