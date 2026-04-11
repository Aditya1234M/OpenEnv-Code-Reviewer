"""OpenEnv-compatible code review environment.

This module exposes a deterministic environment with reset()/step()/state()
for training and evaluating code-review agents.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from src.config import settings


def _load_tasks(dataset_path: str) -> list[dict[str, Any]]:
    """Load task episodes from a JSONL file."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(
            f"OpenEnv dataset not found at '{dataset_path}'. "
            "Create data/pr_tasks.jsonl or set OPENENV_DATASET_PATH."
        )

    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                task = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {idx}: {exc}") from exc
            _validate_task_schema(task, idx)
            tasks.append(task)

    if not tasks:
        raise ValueError(f"No tasks found in dataset: {dataset_path}")

    return tasks


def _validate_task_schema(task: dict[str, Any], idx: int) -> None:
    required = {"task_id", "title", "description", "diff", "ground_truth"}
    missing = required.difference(task.keys())
    if missing:
        raise ValueError(f"Task #{idx} missing required keys: {sorted(missing)}")

    gt = task["ground_truth"]
    if not isinstance(gt, dict) or "issues" not in gt:
        raise ValueError(f"Task #{idx} has invalid ground_truth format")


def _parse_action(action: Any) -> dict[str, Any]:
    """Accept dict or JSON string action payload."""
    if isinstance(action, dict):
        return action
    if isinstance(action, str):
        return json.loads(action)
    raise TypeError("Action must be a dict or a JSON string")


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": str(issue.get("file", "")).strip(),
        "line": int(issue.get("line", 0) or 0),
        "category": str(issue.get("category", "")).strip().lower(),
        "severity": str(issue.get("severity", "")).strip().lower(),
        "description": str(issue.get("description", "")).strip(),
    }


def _score_action(action: dict[str, Any], ground_truth: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Compute deterministic reward against planted ground truth labels."""
    predicted = [_normalize_issue(i) for i in action.get("issues", [])]
    expected = [_normalize_issue(i) for i in ground_truth.get("issues", [])]

    matched_expected: set[int] = set()
    tp = 0
    fp = 0
    missed = 0
    severity_hits = 0

    for pred in predicted:
        hit_idx = None
        for idx, exp in enumerate(expected):
            if idx in matched_expected:
                continue
            same_file = pred["file"] == exp["file"]
            close_line = abs(pred["line"] - exp["line"]) <= 2
            same_category = not exp["category"] or pred["category"] == exp["category"]
            if same_file and close_line and same_category:
                hit_idx = idx
                break

        if hit_idx is None:
            fp += 1
            continue

        matched_expected.add(hit_idx)
        tp += 1
        if predicted and pred["severity"] == expected[hit_idx]["severity"]:
            severity_hits += 1

    missed = len(expected) - len(matched_expected)

    critical_missed = sum(
        1
        for idx, exp in enumerate(expected)
        if idx not in matched_expected and exp.get("severity") == "critical"
    )

    decision_bonus = 0.0
    expected_decision = str(ground_truth.get("expected_decision", "")).strip().lower()
    submitted_decision = str(action.get("overall_decision", "")).strip().lower()
    if expected_decision and submitted_decision == expected_decision:
        decision_bonus = 0.5

    # Reward weights tuned for stable one-step episodes.
    raw_score = (
        tp * 1.0
        + severity_hits * 0.25
        + decision_bonus
        - fp * 0.5
        - missed * 1.0
        - critical_missed * 1.0
    )

    max_score = max(len(expected) * 1.25 + 0.5, 1.0)
    signed_reward = max(-1.0, min(1.0, raw_score / max_score))
    # External validators require task scores strictly inside (0, 1).
    reward = max(0.01, min(0.99, (signed_reward + 1.0) / 2.0))

    info = {
        "true_positives": tp,
        "false_positives": fp,
        "missed": missed,
        "severity_hits": severity_hits,
        "critical_missed": critical_missed,
        "expected_issues": len(expected),
        "predicted_issues": len(predicted),
        "decision_match": bool(decision_bonus),
        "raw_score": raw_score,
        "max_score": max_score,
        "signed_reward": signed_reward,
    }
    return reward, info


class CodeReviewOpenEnv:
    """Single-step OpenEnv environment for code review tasks."""

    def __init__(self, dataset_path: str | None = None, max_steps: int | None = None):
        self.dataset_path = dataset_path or settings.openenv_dataset_path
        self.max_steps = max_steps or settings.openenv_max_steps
        self._tasks = _load_tasks(self.dataset_path)

        self._rng = random.Random()
        self._step_count = 0
        self._done = False
        self._current_task: dict[str, Any] | None = None
        self._last_reward = 0.0
        self._last_info: dict[str, Any] = {}

    def reset(self, seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if seed is not None:
            self._rng.seed(seed)

        self._step_count = 0
        self._done = False
        self._last_reward = 0.0
        self._last_info = {}
        self._current_task = self._rng.choice(self._tasks)

        return self.state(), {"task_id": self._current_task["task_id"]}

    def state(self) -> dict[str, Any]:
        if self._current_task is None:
            return {
                "ready": False,
                "message": "Call reset() before state() or step().",
            }

        task = self._current_task
        return {
            "ready": True,
            "task_id": task["task_id"],
            "title": task["title"],
            "description": task["description"],
            "difficulty": task.get("difficulty", "unknown"),
            "domain": task.get("domain", "unknown"),
            "diff": task["diff"],
            "context_files": task.get("context_files", []),
            "step_count": self._step_count,
            "max_steps": self.max_steps,
            "done": self._done,
            "last_reward": self._last_reward,
            "last_info": self._last_info,
        }

    def step(self, action: dict[str, Any] | str) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self._current_task is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        if self._done:
            raise RuntimeError("Episode already finished. Call reset() for next task.")

        payload = _parse_action(action)
        reward, score_info = _score_action(payload, self._current_task["ground_truth"])

        self._step_count += 1
        terminated = True
        truncated = self._step_count >= self.max_steps and not terminated
        self._done = terminated or truncated

        self._last_reward = reward
        self._last_info = score_info

        info = {
            "task_id": self._current_task["task_id"],
            "score": score_info,
        }
        return self.state(), reward, terminated, truncated, info
