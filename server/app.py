"""Server entrypoint shim for multi-mode deployment validators."""

from __future__ import annotations

import uvicorn

from src.server import app


def main() -> None:
    """Run the FastAPI server."""
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
