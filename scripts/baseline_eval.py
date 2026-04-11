"""Deterministic baseline evaluation over all benchmark tasks."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.config import settings
from src.openenv_env import _score_action


def _score_in_open_interval(reward: float) -> float:
    mapped = (reward + 1.0) / 2.0
    return max(1e-6, min(1.0 - 1e-6, mapped))


def _action_for_task(task_id: str) -> dict[str, Any]:
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
                    "description": "Untrusted SQL string interpolation",
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
                    "description": "Mutable default leaks state",
                }
            ],
        }

    return {
        "overall_decision": "request_changes",
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


def _load_tasks(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    if not rows:
        raise ValueError(f"No tasks found in {path}")
    return rows


def evaluate_all(dataset_path: str) -> dict[str, Any]:
    tasks = _load_tasks(dataset_path)
    results: list[dict[str, Any]] = []

    for task in tasks:
        task_id = str(task.get("task_id", "unknown"))
        difficulty = str(task.get("difficulty", "unknown")).lower()
        domain = str(task.get("domain", "unknown")).lower()
        action = _action_for_task(task_id)

        reward, score_info = _score_action(action, task["ground_truth"])
        score_0_1 = _score_in_open_interval(float(reward))

        results.append(
            {
                "task_id": task_id,
                "difficulty": difficulty,
                "domain": domain,
                "reward": float(reward),
                "score_0_1": score_0_1,
                "score": score_info,
            }
        )

    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        by_difficulty[row["difficulty"]].append(row)

    difficulty_summary: dict[str, Any] = {}
    for key, rows in by_difficulty.items():
        count = len(rows)
        difficulty_summary[key] = {
            "count": count,
            "avg_reward": sum(r["reward"] for r in rows) / count,
            "avg_score_0_1": sum(r["score_0_1"] for r in rows) / count,
        }

    count = len(results)
    return {
        "dataset_path": dataset_path,
        "task_count": count,
        "overall": {
            "avg_reward": sum(r["reward"] for r in results) / count,
            "avg_score_0_1": sum(r["score_0_1"] for r in results) / count,
        },
        "difficulty_summary": difficulty_summary,
        "tasks": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic baseline evaluation over all tasks")
    parser.add_argument("--dataset", default=settings.openenv_dataset_path, help="Path to JSONL task dataset")
    parser.add_argument("--json", action="store_true", help="Print full JSON payload")
    args = parser.parse_args()

    output = evaluate_all(args.dataset)

    if args.json:
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return

    print(f"dataset={output['dataset_path']}")
    print(f"tasks={output['task_count']}")
    print(f"overall avg_reward={output['overall']['avg_reward']:.4f} avg_score_0_1={output['overall']['avg_score_0_1']:.4f}")
    for diff in sorted(output["difficulty_summary"].keys()):
        row = output["difficulty_summary"][diff]
        print(
            f"difficulty={diff} count={row['count']} "
            f"avg_reward={row['avg_reward']:.4f} avg_score_0_1={row['avg_score_0_1']:.4f}"
        )


if __name__ == "__main__":
    main()
