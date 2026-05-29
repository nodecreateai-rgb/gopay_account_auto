"""从环境变量（优先）与 config.yaml 加载配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from utils.config_error import ConfigError

DEFAULT_HERO_HANDLER_URL = "https://hero-sms.com/stubs/handler_api.php"
DEFAULT_GRIZZLY_HANDLER_URL = "https://api.grizzlysms.com/stubs/handler_api.php"
DEFAULT_PROXY = "http://127.0.0.1:10808"
DEFAULT_SIGNUP_PIN = "123456"
DEFAULT_COUNTRY_CODE = "+62"
DEFAULT_REGISTER_RETRY = 3
DEFAULT_SMS_SERVICE = "ni"
DEFAULT_SMS_COUNTRY = 6
DEFAULT_SMS_MAX_PRICE = "0.06"
DEFAULT_SMS_PROVIDER = "hero_sms"


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _mask_secret(value: str, show: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= show * 2:
        return "*" * len(text)
    return f"{text[:show]}...{text[-show:]}"


def _require(value: str, label: str, env_names: tuple[str, ...]) -> str:
    if value:
        return value
    keys = " / ".join(env_names)
    raise ConfigError(f"未配置 {label}，请设置环境变量: {keys}")


def _normalize_provider(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text in ("grizzly", "grizzly_sms", "grizzlysms"):
        return "grizzly_sms"
    if text in ("hero", "hero_sms", "herosms"):
        return "hero_sms"
    if text == "grizzly_sms":
        return "grizzly_sms"
    return "hero_sms"


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
    signup_cfg = gopay_section.get("signup") or {}

    provider_raw = _env("SMS_PROVIDER", "GOPAY_SMS_PROVIDER") or str(cfg.get("sms_provider") or "")
    sms_provider = _normalize_provider(provider_raw) if provider_raw else _normalize_provider(
        str(cfg.get("sms_provider") or DEFAULT_SMS_PROVIDER)
    )

    hero_cfg = cfg.get("hero_sms") or {}
    grizzly_cfg = cfg.get("grizzly_sms") or {}

    proxy = _env("GOPAY_PROXY", "PROXY") or str(cfg.get("proxy") or DEFAULT_PROXY)
    signup_pin = _env("GOPAY_SIGNUP_PIN", "GOPAY_DEFAULT_PIN") or str(
        signup_cfg.get("default_pin") or DEFAULT_SIGNUP_PIN
    )
    country_code = _env("GOPAY_SIGNUP_COUNTRY_CODE", "GOPAY_COUNTRY_CODE") or str(
        signup_cfg.get("country_code") or DEFAULT_COUNTRY_CODE
    )

    proxy = _require(proxy, "代理", ("GOPAY_PROXY", "PROXY"))

    if sms_provider == "grizzly_sms":
        sms_cfg = grizzly_cfg
        sms_api_key = _env("GRIZZLY_SMS_API_KEY", "CPA_GRIZZLY_SMS_API_KEY") or str(
            grizzly_cfg.get("api_key") or ""
        )
        sms_api_key = _require(
            sms_api_key,
            "GrizzlySMS API Key",
            ("GRIZZLY_SMS_API_KEY", "CPA_GRIZZLY_SMS_API_KEY"),
        )
        sms_base_url = _env("GRIZZLY_SMS_HANDLER_URL", "GRIZZLY_SMS_BASE_URL") or str(
            grizzly_cfg.get("base_url") or DEFAULT_GRIZZLY_HANDLER_URL
        )
        sms_enabled = grizzly_cfg.get("enabled", True)
        enabled_env = _env("GRIZZLY_SMS_ENABLED", "GOPAY_SMS_ENABLED")
        service_env = ("GRIZZLY_SMS_SERVICE", "GOPAY_SMS_SERVICE")
        country_env = ("GRIZZLY_SMS_COUNTRY", "GOPAY_SMS_COUNTRY")
        timeout_env = (
            "GRIZZLY_SMS_POLL_TIMEOUT_SEC",
            "GRIZZLY_SMS_WAIT_SECONDS",
            "GOPAY_SMS_POLL_TIMEOUT_SEC",
        )
        max_price_env = ("GRIZZLY_SMS_MAX_PRICE", "CPA_GRIZZLY_SMS_MAX_PRICE", "GOPAY_SMS_MAX_PRICE")
    else:
        sms_cfg = hero_cfg
        sms_api_key = _env("HERO_SMS_API_KEY", "GOPAY_HERO_SMS_API_KEY", "CPA_HERO_SMS_API_KEY") or str(
            hero_cfg.get("api_key") or ""
        )
        sms_api_key = _require(
            sms_api_key,
            "Hero-SMS API Key",
            ("HERO_SMS_API_KEY", "GOPAY_HERO_SMS_API_KEY"),
        )
        sms_base_url = _env("HERO_SMS_HANDLER_URL", "HERO_SMS_BASE_URL") or str(
            hero_cfg.get("base_url") or DEFAULT_HERO_HANDLER_URL
        )
        sms_enabled = hero_cfg.get("enabled", True)
        enabled_env = _env("HERO_SMS_ENABLED", "GOPAY_HERO_SMS_ENABLED", "GOPAY_SMS_ENABLED")
        service_env = ("HERO_SMS_SERVICE", "GOPAY_HERO_SMS_SERVICE", "GOPAY_SMS_SERVICE")
        country_env = ("HERO_SMS_COUNTRY", "GOPAY_HERO_SMS_COUNTRY", "GOPAY_SMS_COUNTRY")
        timeout_env = ("HERO_SMS_POLL_TIMEOUT_SEC", "GOPAY_SMS_POLL_TIMEOUT_SEC")
        max_price_env = ("HERO_SMS_MAX_PRICE", "GOPAY_SMS_MAX_PRICE")

    if not country_code.startswith("+"):
        country_code = f"+{country_code}"

    if enabled_env.lower() in ("0", "false", "no", "off"):
        sms_enabled = False
    elif enabled_env.lower() in ("1", "true", "yes", "on"):
        sms_enabled = True

    raw_retry = _env("GOPAY_REGISTER_RETRY", "GOPAY_NUMBER_RETRY") or str(
        cfg.get("register_retry") or DEFAULT_REGISTER_RETRY
    )
    try:
        register_retry = max(1, min(20, int(raw_retry)))
    except (TypeError, ValueError):
        register_retry = DEFAULT_REGISTER_RETRY

    sms_max_price = _env(*max_price_env) or str(sms_cfg.get("max_price") or DEFAULT_SMS_MAX_PRICE)

    return {
        "proxy": proxy,
        "register_retry": register_retry,
        "sms_provider": sms_provider,
        "sms_api_key": sms_api_key,
        "sms_base_url": sms_base_url,
        "sms_enabled": bool(sms_enabled),
        "sms_service": _env(*service_env) or str(sms_cfg.get("service") or DEFAULT_SMS_SERVICE),
        "sms_country": _safe_int(_env(*country_env) or sms_cfg.get("country"), DEFAULT_SMS_COUNTRY),
        "sms_max_price": sms_max_price,
        "sms_timeout": _safe_int(_env(*timeout_env) or sms_cfg.get("poll_timeout_sec"), 300),
        "signup_pin": signup_pin,
        "country_code": country_code,
        "festival_cfg": festival_cfg,
        "festival_enabled": bool(festival_cfg.get("enabled"))
        and bool(str(festival_cfg.get("short_link") or "").strip()),
        "config_path": str(config_path),
    }


def settings_preview(root_dir: Path | None = None) -> dict[str, Any]:
    root = root_dir or Path(__file__).resolve().parents[1]
    config_path = root / "config.yaml"

    loaded: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        loaded = raw if isinstance(raw, dict) else {}

    provider_raw = _env("SMS_PROVIDER", "GOPAY_SMS_PROVIDER") or str(loaded.get("sms_provider") or "")
    sms_provider = _normalize_provider(provider_raw) if provider_raw else _normalize_provider(
        str(loaded.get("sms_provider") or DEFAULT_SMS_PROVIDER)
    )
    if not provider_raw and not loaded.get("sms_provider"):
        sms_provider = DEFAULT_SMS_PROVIDER

    hero_cfg = loaded.get("hero_sms") or {}
    grizzly_cfg = loaded.get("grizzly_sms") or {}
    yaml_proxy = str(loaded.get("proxy") or "").strip()

    missing: list[str] = []
    if sms_provider == "grizzly_sms":
        gk = _env("GRIZZLY_SMS_API_KEY", "CPA_GRIZZLY_SMS_API_KEY")
        yk = str(grizzly_cfg.get("api_key") or "").strip()
        if not gk and not yk:
            missing.append("GRIZZLY_SMS_API_KEY")
        key_mask = _mask_secret(gk or yk)
    else:
        hk = _env("HERO_SMS_API_KEY", "GOPAY_HERO_SMS_API_KEY")
        yk = str(hero_cfg.get("api_key") or "").strip()
        if not hk and not yk:
            missing.append("HERO_SMS_API_KEY")
        key_mask = _mask_secret(hk or yk)

    if not _env("GOPAY_PROXY", "PROXY") and not yaml_proxy:
        missing.append("GOPAY_PROXY")

    settings: dict[str, Any] = {}
    try:
        settings = load_settings(root)
    except ConfigError as e:
        missing.append(str(e))

    return {
        "ready": not missing,
        "missing": list(dict.fromkeys(missing)),
        "sms_provider": settings.get("sms_provider", sms_provider),
        "sms_api_key": key_mask,
        "proxy": settings.get("proxy") or _env("GOPAY_PROXY", "PROXY") or yaml_proxy or "(未设置)",
        "sms_service": settings.get("sms_service", DEFAULT_SMS_SERVICE),
        "sms_country": settings.get("sms_country", DEFAULT_SMS_COUNTRY),
        "sms_max_price": settings.get("sms_max_price", DEFAULT_SMS_MAX_PRICE),
        "sms_enabled": settings.get("sms_enabled", True),
        "register_retry": settings.get("register_retry", DEFAULT_REGISTER_RETRY),
        "config_yaml": str(config_path) if config_path.exists() else None,
    }
