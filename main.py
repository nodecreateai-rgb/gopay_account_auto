"""应用入口：仅启动 HTTP API。

Dokploy / Docker 默认执行 `python main.py` 时只拉起服务，
注册流程由 GET /register 触发。手动注册请用: python cli.py
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    from api import DEFAULT_API_PORT

    port = int(os.environ.get("GOPAY_API_PORT", DEFAULT_API_PORT))
    print(f"[gopay-account-auto] 启动 API :{port}（注册请请求 GET /register）")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
