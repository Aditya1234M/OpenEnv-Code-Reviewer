"""OpenEnv pipeline helpers for reset/state/step interaction."""

import logging
from typing import Any

from src.openenv_env import CodeReviewOpenEnv

logger = logging.getLogger(__name__)

_ENV = CodeReviewOpenEnv()

def reset_environment(seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset environment and return initial observation + info."""
    obs, info = _ENV.reset(seed=seed)
    logger.info("Environment reset with task_id=%s", info.get("task_id"))
    return obs, info


def current_state() -> dict[str, Any]:
    """Return current observation without mutating environment state."""
    return _ENV.state()


def step_environment(action: dict[str, Any] | str) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
    """Apply an action (review JSON) and return OpenEnv step tuple."""
    obs, reward, terminated, truncated, info = _ENV.step(action)
    logger.info(
        "Environment step complete task_id=%s reward=%.4f terminated=%s truncated=%s",
        info.get("task_id"),
        reward,
        terminated,
        truncated,
    )
    return obs, reward, terminated, truncated, info
