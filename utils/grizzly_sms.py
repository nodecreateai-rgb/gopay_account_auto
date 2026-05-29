"""GrizzlySMS 接码客户端（API 与 Hero-SMS 同族 handler 协议）。"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable, Optional

try:
    from curl_cffi import requests as _requests
    _CurlCffiAvailable = True
except ImportError:
    import requests as _requests
    _CurlCffiAvailable = False

logger = logging.getLogger(__name__)

DEFAULT_HANDLER_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
DEFAULT_OPERATOR = "any"
DEFAULT_MAX_PRICE = "0.06"

STATUS_READY = 1
STATUS_CANCEL = 8
STATUS_RESEND = 3
STATUS_FINISH = 6

POLL_INTERVAL_SEC = 3.0

_FATAL_ERRORS = frozenset(
    {
        "BAD_KEY",
        "BAD_ACTION",
        "BAD_SERVICE",
        "WRONG_SERVICE",
        "WRONG_COUNTRY",
        "NO_BALANCE",
        "NO_NUMBERS",
        "ERROR_SQL",
    }
)

_GOPAY_OTP_RE = re.compile(r"\b(\d{6})\b")


def _extract_otp(value: str) -> str:
    """从 Grizzly STATUS_OK 或短信正文中提取 GoPay 6 位验证码。"""
    text = str(value or "").strip()
    if text.upper().startswith("STATUS_OK:"):
        text = text.split(":", 1)[1].strip()

    matches = _GOPAY_OTP_RE.findall(text)
    if matches:
        return matches[-1]

    digits = re.sub(r"\D", "", text)
    if len(digits) >= 6:
        return digits[-6:]
    return ""


def _request(
    base_url: str,
    api_key: str,
    action: str,
    params: Optional[dict] = None,
    timeout: int = 25,
) -> tuple[bool, str, Any]:
    if not api_key:
        return False, "NO_KEY", None

    query = {"action": action, "api_key": api_key}
    if params:
        for k, v in params.items():
            if v is not None and str(v).strip():
                query[k] = v

    try:
        kwargs: dict[str, Any] = {"params": query, "timeout": timeout}
        if _CurlCffiAvailable:
            kwargs["impersonate"] = "chrome131"
        resp = _requests.get(base_url, **kwargs)
    except Exception as e:
        return False, f"REQUEST_ERROR:{e}", None

    text = resp.text.strip()
    try:
        data = resp.json()
    except Exception:
        data = None

    if not (200 <= resp.status_code < 300):
        return False, text or f"HTTP {resp.status_code}", data
    if text.upper() in _FATAL_ERRORS:
        return False, text, data
    return True, text, data


def set_status(base_url: str, api_key: str, activation_id: str, status: int) -> str:
    if not activation_id:
        return ""
    _, text, _ = _request(
        base_url,
        api_key,
        "setStatus",
        {"id": activation_id, "status": status},
        timeout=20,
    )
    return str(text or "")


def get_number(
    service_code: str,
    country_id: int,
    base_url: str,
    api_key: str,
    max_price: str = DEFAULT_MAX_PRICE,
    operator: str = DEFAULT_OPERATOR,
    log: Callable[[str], None] = logger.info,
) -> tuple[str, str, str]:
    """购买号码，返回 (activation_id, phone, error)。"""
    log(
        f"[grizzly-sms] getNumber service={service_code} country={country_id} "
        f"operator={operator} maxPrice={max_price}"
    )
    ok, text, data = _request(
        base_url,
        api_key,
        "getNumber",
        {
            "service": service_code,
            "country": country_id,
            "operator": operator,
            "maxPrice": max_price,
        },
        timeout=30,
    )

    if not ok:
        return "", "", str(text or "getNumber failed")

    line = str(text or "").strip()
    if line.upper().startswith("ACCESS_NUMBER:"):
        parts = line.split(":", 2)
        if len(parts) >= 3:
            return parts[1].strip(), parts[2].strip(), ""

    if isinstance(data, dict):
        activation_id = str(data.get("activationId") or data.get("id") or "")
        phone = str(data.get("phoneNumber") or data.get("phone") or "")
        if activation_id and phone:
            return activation_id, phone, ""

    return "", "", line or "无法解析号码"


class SmsActivation:
    """验证码生命周期管理。"""

    def __init__(
        self,
        activation_id: str,
        phone: str,
        country_id: int,
        base_url: str,
        api_key: str,
        log: Callable[[str], None] = logger.info,
    ):
        self.activation_id = activation_id
        self.phone = phone
        self.country_id = country_id
        self.base_url = base_url
        self.api_key = api_key
        self.log = log
        self.used_codes: set[str] = set()

    def wait_code(self, timeout_sec: int = 300, label: str = "", max_resends: int = 3) -> str:
        start = time.time()
        last_resend = start
        resend_count = 0
        resend_intervals = [30, 60, 120]

        while time.time() - start < timeout_sec:
            ok, text, data = _request(
                self.base_url,
                self.api_key,
                "getStatus",
                {"id": self.activation_id},
                timeout=20,
            )

            if not ok:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            line = str(text or "").strip()
            upper = line.upper()
            code = ""
            if upper.startswith("STATUS_OK:"):
                code = _extract_otp(line)
            elif isinstance(data, dict):
                raw = str(data.get("code") or data.get("sms") or "")
                code = _extract_otp(raw) or raw.strip()

            if upper.startswith("STATUS_WAIT") or upper == "STATUS_WAIT_CODE":
                time.sleep(POLL_INTERVAL_SEC)
                continue

            if code and code not in self.used_codes:
                self.log(f"[{label}] Grizzly 收到验证码: {code}")
                self.used_codes.add(code)
                return code

            elapsed = time.time() - last_resend
            if resend_count < max_resends:
                wait_time = (
                    resend_intervals[resend_count]
                    if resend_count < len(resend_intervals)
                    else resend_intervals[-1]
                )
                if elapsed > wait_time:
                    resend_count += 1
                    self.log(f"[{label}] 超过 {wait_time}s 未收到新码，请求第 {resend_count} 次重发")
                    set_status(self.base_url, self.api_key, self.activation_id, STATUS_RESEND)
                    last_resend = time.time()

            time.sleep(POLL_INTERVAL_SEC)

        return ""

    def cancel_activation(self) -> None:
        if self.activation_id:
            set_status(self.base_url, self.api_key, self.activation_id, STATUS_CANCEL)
            self.log(f"[grizzly-sms] 取消激活 {self.activation_id}")

    def release(self) -> None:
        if self.activation_id:
            set_status(self.base_url, self.api_key, self.activation_id, STATUS_FINISH)
            self.log(f"[grizzly-sms] 完成激活 {self.activation_id}")
