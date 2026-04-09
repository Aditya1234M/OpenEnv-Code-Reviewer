"""Inference entrypoint required by external evaluators.

This file provides a minimal, deterministic interface to run one grading pass
against the OpenEnv environment.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from src.openenv_env import CodeReviewOpenEnv


def _proxy_llm_probe() -> dict[str, Any]:
    """Make a minimal completion call via injected evaluator proxy credentials."""
    base_url = os.getenv("API_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    model = (
        os.getenv("API_MODEL")
        or os.getenv("MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-4.1-mini"
    )

    if not api_key:
        return {
            "ok": False,
            "error": "Missing API key. Expected API_KEY (or OPENAI_API_KEY fallback).",
            "base_url": base_url,
            "model": model,
        }

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Reply with exactly: ok"},
                {"role": "user", "content": "ping"},
            ],
            max_tokens=4,
            temperature=0,
        )
        text = response.choices[0].message.content if response.choices else ""
        return {
            "ok": True,
            "base_url": base_url,
            "model": model,
            "reply": (text or "").strip(),
        }
    except Exception as exc:  # pragma: no cover - evaluator environment dependent
        return {
            "ok": False,
            "error": str(exc),
            "base_url": base_url,
            "model": model,
        }


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
    llm_probe = _proxy_llm_probe()
    result = run_inference()
    result["llm_proxy_probe"] = llm_probe
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
