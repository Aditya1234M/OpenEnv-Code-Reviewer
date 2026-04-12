"""Evaluate trained policy against baseline on full OpenEnv dataset."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Allow running as: python scripts/eval_policy.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.openenv_env import _score_action


def _score_in_open_interval(reward: float) -> float:
    if 0.0 <= reward <= 1.0:
        mapped = reward
    else:
        mapped = (reward + 1.0) / 2.0
    return max(0.01, min(0.99, mapped))


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    if not rows:
        raise ValueError(f"No tasks found in {path}")
    return rows


def _load_policy(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _baseline_action_for_task(task_id: str) -> dict[str, Any]:
    if task_id == "task-python-auth-001":
        return {
            "overall_decision": "request_changes",
            "issues": [
                {
                    "file": "auth.py",
                    "line": 5,
                    "category": "security",
                    "severity": "high",
                    "description": "Empty token bypass",
                }
            ],
        }
    if task_id == "task-python-quality-002":
        return {
            "overall_decision": "request_changes",
            "issues": [
                {
                    "file": "utils.py",
                    "line": 2,
                    "category": "bug",
                    "severity": "medium",
                    "description": "Possible division by zero on empty list",
                }
            ],
        }
    if task_id == "task-python-api-003":
        return {
            "overall_decision": "request_changes",
            "issues": [
                {
                    "file": "api.py",
                    "line": 18,
                    "category": "security",
                    "severity": "high",
                    "description": "Potential SQL injection",
                }
            ],
        }
    if task_id == "task-python-cache-004":
        return {
            "overall_decision": "request_changes",
            "issues": [
                {
                    "file": "cache.py",
                    "line": 9,
                    "category": "bug",
                    "severity": "low",
                    "description": "Mutable default list can leak state",
                }
            ],
        }

    return {
        "overall_decision": "comment",
        "issues": [
            {
                "file": "unknown.py",
                "line": 1,
                "category": "bug",
                "severity": "medium",
                "description": "Potential issue requires review",
            }
        ],
    }


def _evaluate_rows(tasks: list[dict[str, Any]], action_getter) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("task_id", "unknown"))
        difficulty = str(task.get("difficulty", "unknown")).lower()
        domain = str(task.get("domain", "unknown")).lower()
        action = action_getter(task_id)
        reward, info = _score_action(action, task["ground_truth"])
        score = _score_in_open_interval(float(reward))
        rows.append(
            {
                "task_id": task_id,
                "difficulty": difficulty,
                "domain": domain,
                "score": score,
                "reward": score,
                "metrics": info,
            }
        )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_difficulty[row["difficulty"]].append(row)

    difficulty_summary: dict[str, Any] = {}
    for difficulty, grp in by_difficulty.items():
        difficulty_summary[difficulty] = {
            "count": len(grp),
            "avg_score": sum(r["score"] for r in grp) / len(grp),
        }

    return {
        "task_count": len(rows),
        "avg_score": sum(r["score"] for r in rows) / len(rows),
        "by_difficulty": difficulty_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare trained policy against baseline")
    parser.add_argument("--dataset", default="data/pr_tasks.jsonl", help="Path to dataset JSONL")
    parser.add_argument("--policy", default="artifacts/policy.json", help="Path to trained policy JSON")
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    tasks = _load_jsonl(args.dataset)
    policy_blob = _load_policy(args.policy)
    policy_map = policy_blob.get("policy", {})

    baseline_rows = _evaluate_rows(tasks, _baseline_action_for_task)

    def trained_action(task_id: str) -> dict[str, Any]:
        row = policy_map.get(task_id, {})
        action = row.get("best_action")
        if isinstance(action, dict):
            return action
        return _baseline_action_for_task(task_id)

    trained_rows = _evaluate_rows(tasks, trained_action)

    baseline_summary = _summary(baseline_rows)
    trained_summary = _summary(trained_rows)

    output = {
        "dataset": args.dataset,
        "policy": args.policy,
        "baseline": baseline_summary,
        "trained": trained_summary,
        "improvement": {
            "avg_score_delta": trained_summary["avg_score"] - baseline_summary["avg_score"],
        },
        "baseline_tasks": baseline_rows,
        "trained_tasks": trained_rows,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return

    print(f"dataset={args.dataset}")
    print(f"policy={args.policy}")
    print(f"baseline_avg_score={baseline_summary['avg_score']:.4f}")
    print(f"trained_avg_score={trained_summary['avg_score']:.4f}")
    print(f"delta={output['improvement']['avg_score_delta']:.4f}")

    all_diffs = sorted(set(baseline_summary["by_difficulty"].keys()) | set(trained_summary["by_difficulty"].keys()))
    for diff in all_diffs:
        b = baseline_summary["by_difficulty"].get(diff, {"count": 0, "avg_score": 0.0})
        t = trained_summary["by_difficulty"].get(diff, {"count": 0, "avg_score": 0.0})
        print(
            f"difficulty={diff} count={max(b['count'], t['count'])} "
            f"baseline={b['avg_score']:.4f} trained={t['avg_score']:.4f} "
            f"delta={(t['avg_score'] - b['avg_score']):.4f}"
        )


if __name__ == "__main__":
    main()
