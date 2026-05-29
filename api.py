"""GoPay 自动注册 HTTP API（FastAPI）。"""

from __future__ import annotations

import logging
import os
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from utils.config_error import ConfigError
from utils.runner import run_gopay_register
from utils.serialize import json_safe
from utils.settings import load_settings, settings_preview

DEFAULT_API_PORT = 28000

ROOT_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gopay-api")

app = FastAPI(
    title="GoPay Account Auto API",
    description="GET /register 触发接码（默认 Hero-SMS）并注册 GoPay；启动时不自动注册",
    version="1.0.3",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "gopay-account-auto",
        "health": "/health",
        "config": "/config",
        "register": "/register",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def config_check() -> JSONResponse:
    """检查环境变量是否齐全（不暴露完整密钥）。"""
    try:
        preview = settings_preview(ROOT_DIR)
        status = 200 if preview.get("ready") else 400
        return JSONResponse(content=preview, status_code=status)
    except Exception as e:
        logger.exception("config check failed")
        return JSONResponse(
            content={"ready": False, "error": str(e)},
            status_code=500,
        )


@app.get("/register")
def register_gopay() -> JSONResponse:
    """取号并注册 GoPay（同步执行，可能耗时数分钟）。"""
    try:
        settings = load_settings(ROOT_DIR)
    except ConfigError as e:
        logger.warning("config error: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("load_settings failed")
        return JSONResponse(
            content={
                "ok": False,
                "step": "config",
                "error": str(e),
                "detail": traceback.format_exc(),
            },
            status_code=500,
        )

    if not settings["sms_enabled"]:
        raise HTTPException(status_code=400, detail="接码服务未启用")

    logger.info(
        "register start provider=%s proxy=%s service=%s country=%s",
        settings.get("sms_provider"),
        settings["proxy"],
        settings["sms_service"],
        settings["sms_country"],
    )

    try:
        result = run_gopay_register(settings, log=logger.info)
        body = json_safe(result)
        if result.get("ok"):
            logger.info("register success phone=%s", result.get("phone_display"))
            return JSONResponse(content=body, status_code=200)
        logger.warning("register failed: %s", result.get("error"))
        # 业务失败仍返回 200 + ok:false，便于浏览器/网关看到 JSON 原因
        return JSONResponse(content=body, status_code=200)
    except Exception as e:
        logger.exception("register crashed")
        return JSONResponse(
            content=json_safe(
                {
                    "ok": False,
                    "step": "register",
                    "error": f"{type(e).__name__}: {e}",
                    "detail": traceback.format_exc(),
                }
            ),
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    port = int(
        os.environ.get("PORT")
        or os.environ.get("GOPAY_API_PORT")
        or DEFAULT_API_PORT
    )
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
