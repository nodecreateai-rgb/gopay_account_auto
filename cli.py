"""命令行手动触发注册（本地调试用，勿作为容器启动命令）。"""

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
    print(f"接码: {settings.get('sms_provider', 'hero_sms')} enabled={settings['sms_enabled']}")

    if not settings["sms_enabled"]:
        print("\n[跳过] 接码未启用")
        sys.exit(0)

    result = run_gopay_register(settings, log=print)
    if not result.get("ok"):
        print(f"\n[失败] {result.get('error')}")
        sys.exit(1)

    print("\n流程完成")
    print(f"phone: {result.get('phone_display')}")
    print(f"pin: {result.get('pin')}")


if __name__ == "__main__":
    main()
