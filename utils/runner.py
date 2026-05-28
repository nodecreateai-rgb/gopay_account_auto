"""GoPay 自动注册/登录（及可选红包）流程。"""

from __future__ import annotations

import time
from typing import Any, Callable

import requests

from utils.gopay.account import GoPayAccountError, auto_login, auto_signup
from utils.gopay.charger import GoPayCharger, GoPayError
from utils.hero_sms import SmsActivation, get_number, set_status, STATUS_RESEND


def _normalize_phone(phone_raw: str) -> str:
    phone = phone_raw.lstrip("+")
    if phone.startswith("62"):
        phone = phone[2:]
    return phone


def run_gopay_register(
    settings: dict[str, Any],
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """执行完整注册流程，返回结构化结果。"""

    def _log(msg: str) -> None:
        if log:
            log(msg)

    if not settings.get("hero_enabled"):
        return {"ok": False, "error": "hero-sms 未启用"}

    proxy = settings["proxy"]
    hero_api_key = settings["hero_api_key"]
    hero_base_url = settings["hero_base_url"]
    festival_cfg = settings["festival_cfg"]
    festival_enabled = settings["festival_enabled"]
    signup_pin = settings["signup_pin"]
    country_code = settings["country_code"]
    sms_timeout = settings["sms_timeout"]

    _log(f"使用代理: {proxy}")
    _log(f"红包配置: enabled={festival_enabled}")

    _log("Step 1: hero-sms 取号")
    activation_id, phone_raw, err = get_number(
        service_code=settings["sms_service"],
        country_id=settings["sms_country"],
        base_url=hero_base_url,
        api_key=hero_api_key,
        log=_log,
    )
    if not activation_id:
        return {"ok": False, "step": "get_number", "error": err or "取号失败"}

    phone = _normalize_phone(phone_raw)
    _log(f"取到号码: +62{phone} (activation_id={activation_id})")

    sms_activation = SmsActivation(
        activation_id=activation_id,
        phone=phone_raw,
        country_id=settings["sms_country"],
        base_url=hero_base_url,
        api_key=hero_api_key,
        log=_log,
    )

    otp_call_count = [0]

    def auto_otp_provider(label: str) -> str:
        otp_call_count[0] += 1
        call_n = otp_call_count[0]
        _log(f"  [{label}] 等待第 {call_n} 次 SMS 验证码 (timeout={sms_timeout}s)...")
        code = sms_activation.wait_code(timeout_sec=sms_timeout, label=f"{label}#{call_n}")
        if code:
            _log(f"  [{label}] 收到验证码: {code}")
            return code
        _log(f"  [{label}] 等码超时")
        return ""

    shared_gopay_cfg: dict[str, Any] = {}
    mode = ""
    access_token = ""
    result_phone = ""
    result_pin = ""
    gopay_session = None

    def reactivate_before_pin() -> None:
        set_status(hero_base_url, hero_api_key, activation_id, STATUS_RESEND)
        _log("  [pre-pin] reactivate SMS (status=3)")

    _log(f"Step 2: 注册/登录 +62{phone}")
    try:
        signup_result = auto_signup(
            phone=phone,
            country_code=country_code,
            pin=signup_pin,
            otp_provider=auto_otp_provider,
            gopay_cfg=shared_gopay_cfg,
            proxy=proxy,
            log=_log,
            pre_pin_otp_hook=reactivate_before_pin,
        )
        mode = "signup"
        access_token = signup_result.access_token
        result_phone = signup_result.phone
        result_pin = signup_result.pin
        gopay_session = signup_result.session
        _log("注册成功")

    except GoPayAccountError as e:
        if "已注册" in str(e) or "探测异常" in str(e):
            _log("号码已注册，切换登录...")
            time.sleep(2)
            login_result = auto_login(
                phone=phone,
                country_code=country_code,
                pin=signup_pin,
                otp_provider=auto_otp_provider,
                gopay_cfg=shared_gopay_cfg,
                proxy=proxy,
                log=_log,
            )
            mode = "login"
            access_token = login_result.access_token
            result_phone = login_result.phone
            result_pin = login_result.pin
            gopay_session = login_result.session
            _log("登录成功")
        else:
            sms_activation.cancel_activation()
            return {
                "ok": False,
                "step": "signup",
                "error": str(e),
                "phone": phone,
                "activation_id": activation_id,
            }

    except Exception as e:
        sms_activation.cancel_activation()
        return {
            "ok": False,
            "step": "signup",
            "error": f"{type(e).__name__}: {e}",
            "phone": phone,
            "activation_id": activation_id,
        }

    if not access_token:
        sms_activation.cancel_activation()
        return {
            "ok": False,
            "step": "signup",
            "error": "未获取到 access_token",
            "phone": phone,
            "activation_id": activation_id,
        }

    sms_activation.release()

    result: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "phone": result_phone,
        "phone_display": f"+62{result_phone}",
        "pin": result_pin,
        "access_token": access_token,
        "activation_id": activation_id,
        "festival": None,
    }

    if not festival_enabled:
        _log("红包未启用，流程结束")
        return result

    _log("Step 3: 领取红包")
    gopay_cfg_for_charger = {
        "country_code": "62",
        "phone_number": result_phone,
        "pin": result_pin,
        "gopay_access_token": access_token,
        "festival_envelope": festival_cfg,
    }
    for k, v in shared_gopay_cfg.items():
        if k.startswith("_fp_") or k == "_device_fingerprint_initialized":
            gopay_cfg_for_charger[k] = v

    session = gopay_session or requests.Session()
    if not gopay_session:
        session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2_1) AppleWebKit/537.36"
        )

    charger = GoPayCharger(
        chatgpt_session=session,
        gopay_cfg=gopay_cfg_for_charger,
        otp_provider=lambda: "",
        log=_log,
        proxy=proxy,
    )

    cfg_envelope = charger._festival_envelope_cfg()
    try:
        envelope_id = charger._festival_resolve_envelope_request_id(cfg_envelope)
    except GoPayError as e:
        result["festival"] = {"ok": False, "error": str(e)}
        return result

    if not envelope_id:
        result["festival"] = {"ok": False, "error": "envelope_id 为空"}
        return result

    try:
        festival_result = charger._run_link_festival_envelope()
        result["festival"] = festival_result
    except (GoPayError, Exception) as e:
        result["festival"] = {"ok": False, "error": str(e)}

    return result
