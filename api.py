"""GoPay 自动注册 HTTP API（FastAPI）。"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_API_PORT = 28000

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from utils.config_error import ConfigError
from utils.runner import run_gopay_register
from utils.settings import load_settings

ROOT_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="GoPay Account Auto API",
    description="GET /register 触发 GrizzlySMS 取号并注册 GoPay；启动时不自动注册",
    version="1.0.1",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/register")
def register_gopay() -> JSONResponse:
    """取号并注册 GoPay（同步执行，可能耗时数分钟）。"""
    try:
        settings = load_settings(ROOT_DIR)
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not settings["sms_enabled"]:
        raise HTTPException(status_code=400, detail="GrizzlySMS 未启用")

    result = run_gopay_register(settings)
    status = 200 if result.get("ok") else 500
    return JSONResponse(content=result, status_code=status)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("GOPAY_API_PORT", DEFAULT_API_PORT))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
