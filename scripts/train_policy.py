"""Minimal RL trainer for the OpenEnv code-review environment.

This script trains a lightweight task-conditioned policy using an epsilon-greedy
bandit-style update over a small discrete action library.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

# Allow running as: python scripts/train_policy.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.openenv_env import CodeReviewOpenEnv


# Discrete action library that the policy can choose from.
ACTION_LIBRARY: list[dict[str, Any]] = [
    {
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
    },
    {
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
    },
    {
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
    },
    {
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
    },
    {
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
    },
]


def _argmax(values: list[float]) -> int:
    best_idx = 0
    best_val = values[0]
    for idx, value in enumerate(values):
        if value > best_val:
            best_idx = idx
            best_val = value
    return best_idx


def _run_training(
    episodes: int,
    alpha: float,
    epsilon: float,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    env = CodeReviewOpenEnv()

    # q_values[task_id][action_idx] -> expected reward in [0, 1]
    q_values: dict[str, list[float]] = {}
    history: list[float] = []

    for episode in range(episodes):
        _, info = env.reset(seed=seed + episode)
        task_id = str(info.get("task_id", "unknown"))

        if task_id not in q_values:
            q_values[task_id] = [0.5 for _ in ACTION_LIBRARY]

        if rng.random() < epsilon:
            action_idx = rng.randrange(len(ACTION_LIBRARY))
        else:
            action_idx = _argmax(q_values[task_id])

        _, reward, _, _, _ = env.step(ACTION_LIBRARY[action_idx])
        reward = float(reward)

        # One-step bandit-style update on expected reward.
        old_q = q_values[task_id][action_idx]
        new_q = old_q + alpha * (reward - old_q)
        q_values[task_id][action_idx] = new_q
        history.append(reward)

    policy: dict[str, Any] = {}
    for task_id, values in q_values.items():
        best_idx = _argmax(values)
        policy[task_id] = {
            "best_action_idx": best_idx,
            "best_action": ACTION_LIBRARY[best_idx],
            "q_values": values,
        }

    avg_reward = sum(history) / len(history) if history else 0.0
    return {
        "episodes": episodes,
        "alpha": alpha,
        "epsilon": epsilon,
        "seed": seed,
        "avg_reward": avg_reward,
        "task_count_seen": len(q_values),
        "policy": policy,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a minimal RL policy for OpenEnv code-review tasks")
    parser.add_argument("--episodes", type=int, default=300, help="Number of training episodes")
    parser.add_argument("--alpha", type=float, default=0.2, help="Learning rate")
    parser.add_argument("--epsilon", type=float, default=0.15, help="Exploration probability")
    parser.add_argument("--seed", type=int, default=123, help="Random seed")
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/policy.json",
        help="Path to save trained policy JSON",
    )
    args = parser.parse_args()

    result = _run_training(
        episodes=args.episodes,
        alpha=args.alpha,
        epsilon=args.epsilon,
        seed=args.seed,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"dataset={settings.openenv_dataset_path}")
    print(f"episodes={result['episodes']} alpha={result['alpha']} epsilon={result['epsilon']}")
    print(f"avg_reward={result['avg_reward']:.4f}")
    print(f"task_count_seen={result['task_count_seen']}")
    print(f"saved_policy={output_path.as_posix()}")


if __name__ == "__main__":
    main()
