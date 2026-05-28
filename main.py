"""GoPay Account Auto - CLI 入口"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from utils.config_error import ConfigError
from utils.runner import run_gopay_register
from utils.settings import load_settings


def main() -> None:
    try:
        settings = load_settings(ROOT_DIR)
    except ConfigError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    print(f"使用代理: {settings['proxy']}")
    print(f"红包配置: enabled={settings['festival_enabled']}")
    print(f"GrizzlySMS: enabled={settings['sms_enabled']}")
    print(
        f"sms: service={settings['sms_service']} country={settings['sms_country']} "
        f"maxPrice={settings['sms_max_price']}"
    )
    print(f"signup: pin=****** country={settings['country_code']}")

    if not settings["sms_enabled"]:
        print("\n[跳过] GrizzlySMS 未启用，无法自动取号")
        sys.exit(0)

    result = run_gopay_register(settings, log=print)
    if not result.get("ok"):
        print(f"\n[失败] {result.get('error')}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("流程完成")
    print(f"mode: {result.get('mode')}")
    print(f"phone: {result.get('phone_display')}")
    print(f"pin: {result.get('pin')}")
    print(f"access_token: {str(result.get('access_token', ''))[:30]}...")
    if result.get("festival"):
        print(f"festival: {result['festival']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
