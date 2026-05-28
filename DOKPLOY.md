# Dokploy 部署说明

应用在容器内监听 **`0.0.0.0:28000`**（可用环境变量 `PORT` / `GOPAY_API_PORT` 修改）。

日志里出现 `Uvicorn running` **只表示容器内已启动**，外网能否访问取决于 Dokploy 的 **域名** 或 **端口映射**。

## 方式一：域名访问（推荐）

1. Dokploy → 你的 Application → **Domains**
2. 添加域名（或自动生成的 `xxx.dokploy.app`）
3. **Container Port / Target Port 填 `28000`**
4. 保存并 Redeploy

访问：

```text
https://你的域名/health
https://你的域名/config    # 检查环境变量是否配齐
https://你的域名/register
```

若 `/register` 失败，响应体 JSON 里会有 `error` 字段（业务失败也返回 200 + `ok:false`，不再是空 500）。

## 方式二：IP + 端口访问

1. Dokploy → Application → **Advanced** → **Ports**
2. 添加映射：
   - **Published Port（宿主机）**: `28000`
   - **Target Port（容器内）**: `28000`
   - **Protocol**: TCP
3. 服务器防火墙 / 云安全组 **放行 28000**
4. Redeploy

访问：

```text
http://服务器公网IP:28000/health
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `PORT` | 监听端口（部分平台注入，优先于 `GOPAY_API_PORT`） |
| `GOPAY_API_PORT` | 默认 `28000` |
| `GRIZZLY_SMS_API_KEY` | 必填 |
| `GOPAY_PROXY` | 必填，印尼 IP |

## 启动命令

```text
python main.py
```

**不要**使用 `python cli.py`（会立刻跑注册，不会常驻 API）。

## 自检

容器内（Dokploy Terminal / Exec）：

```bash
curl -s http://127.0.0.1:28000/health
```

若容器内通、外网不通 → 一定是 **Domains 端口** 或 **Ports 映射 / 防火墙** 未配置。
