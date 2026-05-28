"""GoPay 自动注册（及可选红包）流程。"""

from __future__ import annotations

import random
import time
from typing import Any, Callable

import requests

from utils.gopay.account import GoPayAccountError, auto_signup
from utils.gopay.charger import GoPayCharger, GoPayError
from utils.grizzly_sms import (
    SmsActivation,
    get_number,
    set_status,
    STATUS_READY,
    STATUS_RESEND,
)

_RETRY_KEYWORDS = (
    "已注册",
    "探测异常",
    "ratelimit",
    "init_verification",
    "otp_token",
    "429",
    "unable to verify",
    "unable to continue",
)


def _normalize_phone(phone_raw: str) -> str:
    phone = phone_raw.lstrip("+")
    if phone.startswith("62"):
        phone = phone[2:]
    return phone


def _is_retryable_error(message: str) -> bool:
    text = (message or "").lower()
    return any(k.lower() in text for k in _RETRY_KEYWORDS)


def _attempt_signup_with_number(
    settings: dict[str, Any],
    log: Callable[[str], None],
) -> dict[str, Any]:
    """单次：取号并尝试注册新账号（不走登录兜底）。"""
    proxy = settings["proxy"]
    sms_api_key = settings["sms_api_key"]
    sms_base_url = settings["sms_base_url"]
    signup_pin = settings["signup_pin"]
    country_code = settings["country_code"]
    sms_timeout = settings["sms_timeout"]

    activation_id, phone_raw, err = get_number(
        service_code=settings["sms_service"],
        country_id=settings["sms_country"],
        base_url=sms_base_url,
        api_key=sms_api_key,
        max_price=settings["sms_max_price"],
        log=log,
    )
    if not activation_id:
        return {
            "ok": False,
            "retryable": True,
            "step": "get_number",
            "error": err or "取号失败",
        }

    phone = _normalize_phone(phone_raw)
    log(f"取到号码: +62{phone} (activation_id={activation_id})")

    set_status(sms_base_url, sms_api_key, activation_id, STATUS_READY)
    log("[grizzly-sms] 已标记就绪 (status=1)")

    sms_activation = SmsActivation(
        activation_id=activation_id,
        phone=phone_raw,
        country_id=settings["sms_country"],
        base_url=sms_base_url,
        api_key=sms_api_key,
        log=log,
    )

    otp_call_count = [0]

    def auto_otp_provider(label: str) -> str:
        otp_call_count[0] += 1
        call_n = otp_call_count[0]
        log(f"  [{label}] 等待第 {call_n} 次 SMS 验证码 (timeout={sms_timeout}s)...")
        code = sms_activation.wait_code(timeout_sec=sms_timeout, label=f"{label}#{call_n}")
        if code:
            log(f"  [{label}] 收到验证码: {code}")
            return code
        log(f"  [{label}] 等码超时")
        return ""

    shared_gopay_cfg: dict[str, Any] = {}

    def reactivate_before_pin() -> None:
        set_status(sms_base_url, sms_api_key, activation_id, STATUS_RESEND)
        log("  [pre-pin] reactivate SMS (status=3)")

    try:
        signup_result = auto_signup(
            phone=phone,
            country_code=country_code,
            pin=signup_pin,
            otp_provider=auto_otp_provider,
            gopay_cfg=shared_gopay_cfg,
            proxy=proxy,
            log=log,
            pre_pin_otp_hook=reactivate_before_pin,
        )
    except GoPayAccountError as e:
        sms_activation.cancel_activation()
        msg = str(e)
        log(f"[失败] 注册异常，已取消号码 {activation_id}: {msg}")
        return {
            "ok": False,
            "retryable": _is_retryable_error(msg),
            "step": "signup",
            "error": msg,
            "phone": phone,
            "activation_id": activation_id,
        }
    except Exception as e:
        sms_activation.cancel_activation()
        msg = f"{type(e).__name__}: {e}"
        log(f"[失败] 未知异常，已取消号码 {activation_id}: {msg}")
        return {
            "ok": False,
            "retryable": True,
            "step": "signup",
            "error": msg,
            "phone": phone,
            "activation_id": activation_id,
        }

    if not signup_result.access_token:
        sms_activation.cancel_activation()
        return {
            "ok": False,
            "retryable": True,
            "step": "signup",
            "error": "未获取到 access_token",
            "phone": phone,
            "activation_id": activation_id,
        }

    sms_activation.release()
    return {
        "ok": True,
        "mode": "signup",
        "phone": signup_result.phone,
        "phone_display": f"+62{signup_result.phone}",
        "pin": signup_result.pin,
        "access_token": signup_result.access_token,
        "activation_id": activation_id,
        "gopay_session": signup_result.session,
        "shared_gopay_cfg": shared_gopay_cfg,
    }


def _run_festival_if_enabled(
    settings: dict[str, Any],
    base: dict[str, Any],
    log: Callable[[str], None],
) -> dict[str, Any] | None:
    festival_cfg = settings["festival_cfg"]

    gopay_cfg_for_charger = {
        "country_code": "62",
        "phone_number": base["phone"],
        "pin": base["pin"],
        "gopay_access_token": base["access_token"],
        "festival_envelope": festival_cfg,
    }
    shared = base.get("shared_gopay_cfg") or {}
    for k, v in shared.items():
        if k.startswith("_fp_") or k == "_device_fingerprint_initialized":
            gopay_cfg_for_charger[k] = v

    session = base.get("gopay_session") or requests.Session()
    if not base.get("gopay_session"):
        session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2_1) AppleWebKit/537.36"
        )

    charger = GoPayCharger(
        chatgpt_session=session,
        gopay_cfg=gopay_cfg_for_charger,
        otp_provider=lambda: "",
        log=log,
        proxy=settings["proxy"],
    )

    try:
        envelope_id = charger._festival_resolve_envelope_request_id(
            charger._festival_envelope_cfg()
        )
    except GoPayError as e:
        return {"ok": False, "error": str(e)}

    if not envelope_id:
        return {"ok": False, "error": "envelope_id 为空"}

    try:
        return charger._run_link_festival_envelope()
    except (GoPayError, Exception) as e:
        return {"ok": False, "error": str(e)}


def run_gopay_register(
    settings: dict[str, Any],
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """执行完整注册流程；可重试取号（见 GOPAY_REGISTER_RETRY）。"""

    def _log(msg: str) -> None:
        if log:
            log(msg)

    if not settings.get("sms_enabled"):
        return {"ok": False, "error": "GrizzlySMS 未启用"}

    max_attempts = int(settings.get("register_retry") or 3)
    _log(f"使用代理: {settings['proxy']}")
    _log(f"红包配置: enabled={settings['festival_enabled']}")
    _log(f"取号重试上限: {max_attempts}")

    last_fail: dict[str, Any] = {"ok": False, "error": "未知错误"}
    tried_phones: list[str] = []

    for attempt in range(1, max_attempts + 1):
        _log(f"\n--- 第 {attempt}/{max_attempts} 次取号注册 ---")
        _log("Step 1: GrizzlySMS 取号")

        outcome = _attempt_signup_with_number(settings, _log)
        if outcome.get("ok"):
            result: dict[str, Any] = {
                "ok": True,
                "mode": outcome["mode"],
                "phone": outcome["phone"],
                "phone_display": outcome["phone_display"],
                "pin": outcome["pin"],
                "access_token": outcome["access_token"],
                "activation_id": outcome["activation_id"],
                "attempts": attempt,
                "festival": None,
            }
            if not settings["festival_enabled"]:
                _log("红包未启用，流程结束")
                return result
            _log("Step 3: 领取红包")
            result["festival"] = _run_festival_if_enabled(settings, outcome, _log)
            return result

        last_fail = outcome
        phone = outcome.get("phone")
        if phone:
            tried_phones.append(str(phone))

        if not outcome.get("retryable"):
            break

        if attempt < max_attempts:
            wait = random.uniform(2.0, 5.0)
            _log(f"将换新号重试，等待 {wait:.1f}s ...")
            time.sleep(wait)

    last_fail["attempts"] = max_attempts
    last_fail["tried_phones"] = tried_phones
    return last_fail
