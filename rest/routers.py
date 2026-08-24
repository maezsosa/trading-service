from __future__ import annotations

from fastapi import FastAPI

from rest import backtests


def setup_routers(app: FastAPI) -> None:
    app.include_router(backtests.router, prefix="/backtests", tags=["Backtests"])
