"""从环境变量（优先）与 config.yaml 加载配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from utils.config_error import ConfigError

DEFAULT_HERO_BASE_URL = "https://hero-sms.com/stubs/handler_api.php"
DEFAULT_PROXY = "http://127.0.0.1:10808"
DEFAULT_SIGNUP_PIN = "123456"
DEFAULT_COUNTRY_CODE = "+62"
DEFAULT_REGISTER_RETRY = 3


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _require(value: str, label: str, env_names: tuple[str, ...]) -> str:
    if value:
        return value
    keys = " / ".join(env_names)
    raise ConfigError(f"未配置 {label}，请设置环境变量: {keys}")


def load_settings(root_dir: Path | None = None) -> dict[str, Any]:
    root = root_dir or Path(__file__).resolve().parents[1]
    config_path = root / "config.yaml"

    cfg: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        cfg = loaded if isinstance(loaded, dict) else {}

    gopay_section = (cfg.get("account_pay") or {}).get("GoPay") or {}
    festival_cfg = gopay_section.get("festival_envelope") or {}
    hero_cfg = cfg.get("hero_sms") or {}
    signup_cfg = gopay_section.get("signup") or {}

    proxy = _env("GOPAY_PROXY", "PROXY") or str(cfg.get("proxy") or DEFAULT_PROXY)
    hero_api_key = _env("HERO_SMS_API_KEY", "GOPAY_HERO_SMS_API_KEY") or str(
        hero_cfg.get("api_key") or ""
    )
    signup_pin = _env("GOPAY_SIGNUP_PIN", "GOPAY_DEFAULT_PIN") or str(
        signup_cfg.get("default_pin") or DEFAULT_SIGNUP_PIN
    )
    country_code = _env("GOPAY_SIGNUP_COUNTRY_CODE", "GOPAY_COUNTRY_CODE") or str(
        signup_cfg.get("country_code") or DEFAULT_COUNTRY_CODE
    )

    proxy = _require(proxy, "代理", ("GOPAY_PROXY", "PROXY"))
    hero_api_key = _require(
        hero_api_key,
        "Hero-SMS API Key",
        ("HERO_SMS_API_KEY", "GOPAY_HERO_SMS_API_KEY"),
    )

    if not country_code.startswith("+"):
        country_code = f"+{country_code}"

    hero_enabled = hero_cfg.get("enabled", True)
    if _env("HERO_SMS_ENABLED", "GOPAY_HERO_SMS_ENABLED").lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        hero_enabled = False
    elif _env("HERO_SMS_ENABLED", "GOPAY_HERO_SMS_ENABLED").lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        hero_enabled = True

    raw_retry = _env("GOPAY_REGISTER_RETRY", "GOPAY_NUMBER_RETRY") or str(
        cfg.get("register_retry") or DEFAULT_REGISTER_RETRY
    )
    try:
        register_retry = max(1, min(20, int(raw_retry)))
    except (TypeError, ValueError):
        register_retry = DEFAULT_REGISTER_RETRY

    return {
        "proxy": proxy,
        "register_retry": register_retry,
        "hero_api_key": hero_api_key,
        "hero_base_url": _env("HERO_SMS_HANDLER_URL", "HERO_SMS_BASE_URL")
        or str(hero_cfg.get("base_url") or DEFAULT_HERO_BASE_URL),
        "hero_enabled": bool(hero_enabled),
        "sms_service": _env("HERO_SMS_SERVICE", "GOPAY_HERO_SMS_SERVICE")
        or str(hero_cfg.get("service") or "ni"),
        "sms_country": int(
            _env("HERO_SMS_COUNTRY", "GOPAY_HERO_SMS_COUNTRY")
            or hero_cfg.get("country")
            or 6
        ),
        "sms_timeout": int(
            _env("HERO_SMS_POLL_TIMEOUT_SEC", "GOPAY_SMS_POLL_TIMEOUT_SEC")
            or hero_cfg.get("poll_timeout_sec")
            or 300
        ),
        "signup_pin": signup_pin,
        "country_code": country_code,
        "festival_cfg": festival_cfg,
        "festival_enabled": bool(festival_cfg.get("enabled"))
        and bool(str(festival_cfg.get("short_link") or "").strip()),
        "config_path": config_path,
    }
