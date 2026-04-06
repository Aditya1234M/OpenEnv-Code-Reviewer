"""FastAPI server exposing OpenEnv-compatible reset/state/step APIs."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.config import settings
from src.pipeline import current_state, reset_environment, step_environment

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenEnv Code Review Environment")


class ResetRequest(BaseModel):
    seed: int | None = None


class StepRequest(BaseModel):
    action: dict[str, Any] | str


@app.post("/reset")
async def reset(payload: ResetRequest):
    """Start a new episode and return initial observation."""
    obs, info = reset_environment(seed=payload.seed)
    return {"observation": obs, "info": info}


@app.get("/state")
async def state():
    """Return current environment observation without stepping."""
    return {"observation": current_state()}


@app.post("/step")
async def step(payload: StepRequest):
    """Apply an action and return OpenEnv transition tuple."""
    try:
        obs, reward, terminated, truncated, info = step_environment(payload.action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid action payload: {exc}") from exc

    return {
        "observation": obs,
        "reward": reward,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "openenv-code-review"}
