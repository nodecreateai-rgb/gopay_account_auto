# GoPay Account Auto - GoPay 钱包自动注册与红包领取

---

## ⚠️ 免责声明

**本项目仅供学习研究和技术交流使用，请勿用于任何商业用途或非法用途。**

- 本项目代码仅用于学习 HTTP 协议、API 签名算法等技术知识
- 使用本工具产生的任何后果由使用者自行承担，与开发者无关
- 请遵守相关法律法规和服务条款，尊重服务提供商的权益
- 请勿利用本工具进行大规模自动化操作，避免对服务造成影响
- 使用前请确保已获得相关服务的授权和许可
- 开发者不对因使用本工具导致的账号封禁、法律纠纷等问题负责

**如果您不同意以上声明，请立即停止使用本项目。**

---

## 功能特性

- ✅ 自动接码注册 GoPay 钱包
- ✅ 自动设置账号 PIN
- ✅ 自动领取节日红包
- ✅ 支持代理配置（绕过 WAF）
- ✅ 完整的 SMS OTP 自动化

## 流程说明

1. **SMS 取号**：通过 hero-sms 接码平台获取印尼手机号
2. **注册/登录**：使用手机号注册新钱包或登录已有账号
3. **领取红包**：自动解析短链并领取节日红包

## 环境要求

- Python 3.8+
- hero-sms 接码平台账号（需充值）
- 印尼 IP 代理（用于注册和 API 调用）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

**敏感项与注册参数优先从环境变量读取**（与 `gpt_plus` 的 `HERO_SMS_*` / `PROXY` 命名兼容），`config.yaml` 仅作非敏感项补充。

```bash
cp config.example.yaml config.yaml
cp .env.example .env
# 编辑 .env 填入密钥，勿提交 .env
```

### 环境变量（推荐）

| 变量 | 必填 | 说明 |
|------|------|------|
| `HERO_SMS_API_KEY` | 是 | Hero-SMS API Key（别名：`GOPAY_HERO_SMS_API_KEY`） |
| `GOPAY_PROXY` | 是 | HTTP 代理，须为**印尼 IP**（别名：`PROXY`） |
| `GOPAY_SIGNUP_PIN` | 否 | 注册/登录 PIN，默认 `123456`（别名：`GOPAY_DEFAULT_PIN`） |
| `GOPAY_SIGNUP_COUNTRY_CODE` | 否 | 国家码，默认 `+62`（别名：`GOPAY_COUNTRY_CODE`） |
| `HERO_SMS_SERVICE` | 否 | 接码服务码，默认 `ni` |
| `HERO_SMS_COUNTRY` | 否 | 接码国家 ID，默认 `6`（印尼） |
| `HERO_SMS_POLL_TIMEOUT_SEC` | 否 | 等码超时（秒），默认 `300` |
| `HERO_SMS_ENABLED` | 否 | `true` / `false`，默认 `true` |
| `GOPAY_REGISTER_RETRY` | 否 | 取号失败、号码已注册、限流等时换号重试次数，默认 `3`（别名 `GOPAY_NUMBER_RETRY`） |
| `GOPAY_API_PORT` | 否 | API 端口，默认 `28000` |

一次性加载（zsh/bash）：

```bash
set -a
source .env
set +a
```

或逐条 export：

```bash
export HERO_SMS_API_KEY="你的key"
export GOPAY_PROXY="http://127.0.0.1:10808"
export GOPAY_SIGNUP_PIN="123456"
export GOPAY_SIGNUP_COUNTRY_CODE="+62"
```

### config.yaml（可选）

用于红包开关、`hero_sms` 的 `service` / `country` 等非敏感项。未设置环境变量时，仍可从 yaml 回退读取 `api_key`、`proxy`、`signup`（不推荐把密钥写在文件里）。

### 红包配置（仅 yaml）

```yaml
account_pay:
  GoPay:
    festival_envelope:
      enabled: true
      short_link: "https://gopay.co.id/xxx"
```

## 使用方法

### CLI

```bash
python main.py
```

### HTTP API（FastAPI）

先加载环境变量（见上文），再启动服务。**启动后不会自动注册**，仅访问接口时执行：

```bash
python api.py
# 或: uvicorn api:app --host 0.0.0.0 --port 28000
```

Docker 请使用 `python api.py` 或本仓库 `Dockerfile`，**不要用 `python main.py` 作为容器入口**（`main.py` 会立即跑一轮 CLI 注册）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/register` | 同步执行取号 + GoPay 注册/登录（可能 5–10 分钟，客户端需加大超时） |

示例：

```bash
curl --max-time 900 "http://127.0.0.1:28000/register"
```

## 输出示例

```
使用代理: http://127.0.0.1:7890
红包配置: enabled=True

============================================================
Step 1: hero-sms 取号
============================================================
[1/5] hero-sms 取号 (service=ni, country=6)...
[ok] 取到号码: +628123456789 (activation_id=12345)

============================================================
Step 2: 注册/登录 GoPay 钱包
============================================================
[2/5] 注册/登录 +628123456789 (PIN=123456)...
[gopay-signup] 触发注册 SMS OTP
[gopay-signup] 等待注册 SMS OTP...
  [signup-otp] 等待第 1 次 SMS 验证码 (timeout=300s)...
  [signup-otp] 收到验证码: 123456
[gopay-signup] 注册 OTP 验证成功
[gopay-signup] 设置 PIN: 123456
[gopay-signup] 等待 PIN 设置 SMS OTP (尝试 1/3)...
  [pin-setup-otp] 等待第 1 次 SMS 验证码 (timeout=300s)...
  [pin-setup-otp] 收到验证码: 654321
[gopay-signup] PIN 设置成功
[3/5] 注册成功!
       phone: +628123456789
       pin: 123456
       access_token: eyJhbGciOiJSUzI1NiIsInR5cCI6...

============================================================
Step 4: 领取红包
============================================================
       envelope_request_id: abc123def456

[4/5] 领取红包...

结果: {
  "ok": true,
  "remaining": 99,
  "total": 100
}
[ok] 红包领取成功! 剩余: 99/100
```

## 注意事项

### 安全提醒

- ⚠️ **不要泄露 API Key**：`config.yaml` 包含敏感信息，请勿提交到公开仓库
- ⚠️ **代理质量**：使用低质量代理可能触发 WAF 封禁
- ⚠️ **接码成本**：hero-sms 按次收费，建议充值后使用

### 常见问题

**Q: 注册失败提示 "WAF 拦截"？**  
A: 代理 IP 被标记，切换到其他印尼代理重试。

**Q: SMS 验证码超时？**  
A: 增加 `poll_timeout_sec` 或检查 hero-sms 余额。

**Q: 红包领取失败？**  
A: 检查短链是否有效，或红包是否已领完。

## 技术细节

### GoPay API 签名

使用 HMAC-SHA256 签名算法，需要：
- `x-e1`: 请求体签名
- `x-device-id`: 设备指纹
- `x-request-id`: 请求唯一标识

### SMS OTP 管理

- 自动排除已使用的验证码
- 支持请求重发（reactivate）
- 超时自动取消激活

## 免责声明

本项目仅供学习研究使用，请遵守相关法律法规和服务条款。使用本工具产生的任何后果由使用者自行承担。

**请勿用于任何商业用途或非法用途。**

## License

MIT License
