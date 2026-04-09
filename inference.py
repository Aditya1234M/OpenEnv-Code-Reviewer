"""Inference entrypoint required by external evaluators.

This file provides a minimal, deterministic interface to run one grading pass
against the OpenEnv environment.
"""

from __future__ import annotations

import json
from typing import Any

from src.openenv_env import CodeReviewOpenEnv


def run_inference(action: dict[str, Any] | None = None, seed: int = 123) -> dict[str, Any]:
    """Run a single reset/step cycle and return evaluation JSON."""
    env = CodeReviewOpenEnv()
    obs, info = env.reset(seed=seed)

    if action is None:
        action = {
            "overall_decision": "request_changes",
            "issues": [
                {
                    "file": "auth.py",
                    "line": 5,
                    "category": "security",
                    "severity": "critical",
                    "description": "Empty token bypass",
                }
            ],
        }

    obs2, reward, terminated, truncated, step_info = env.step(action)
    return {
        "task_id": info.get("task_id"),
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "score": step_info.get("score", {}),
        "observation": obs2,
    }


def main() -> None:
    """CLI entrypoint: prints parser-friendly logs and JSON result to stdout."""
    result = run_inference()
    task_id = str(result.get("task_id") or "unknown")
    reward = float(result.get("reward", 0.0))
    score_block = result.get("score", {})
    score = float(score_block.get("final", 0.0)) if isinstance(score_block, dict) else 0.0

    # Required by external evaluator: structured stdout markers.
    print(f"[START] task={task_id}", flush=True)
    print(f"[STEP] step=1 reward={reward:.6f}", flush=True)
    print(f"[END] task={task_id} score={score:.6f} steps=1", flush=True)

    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
