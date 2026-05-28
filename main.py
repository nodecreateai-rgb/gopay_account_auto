"""应用入口：仅启动 HTTP API。

Dokploy / Docker 默认执行 `python main.py` 时只拉起服务，
注册流程由 GET /register 触发。手动注册请用: python cli.py
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    from api import DEFAULT_API_PORT

    port = int(
        os.environ.get("PORT")
        or os.environ.get("GOPAY_API_PORT")
        or DEFAULT_API_PORT
    )
    print(
        f"[gopay-account-auto] 监听 0.0.0.0:{port} | "
        f"健康检查 GET /health | 注册 GET /register"
    )
    print(
        "[提示] Dokploy 请在 Domains 里绑定域名并填容器端口 "
        f"{port}；或用 Advanced→Ports 映射 宿主机端口→{port}"
    )
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
