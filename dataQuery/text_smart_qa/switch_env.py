#!/usr/bin/env python
"""
一键切换环境配置。

用法:
    python switch_env.py dev      切换到开发环境 (localhost)
    python switch_env.py prod     切换到生产环境 (192.168.100.160)
    python switch_env.py show     显示当前环境

快捷方式 (Linux/Mac):
    chmod +x switch_env.py && ./switch_env.py dev
"""
import sys
from pathlib import Path

# 确保能找到 src/env_utils
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src.env_utils import switch_env, _get_active_env, _PROJECT_ROOT


def show_env():
    active = _get_active_env()
    env_file = _PROJECT_ROOT / ".env"
    if active:
        env_names = {"dev": "开发环境 (localhost)", "prod": "生产环境 (192.168.100.160)"}
        print(f"当前环境: {env_names.get(active, active)}")
    elif env_file.exists():
        print("当前使用自定义 .env（非标准环境模板）")
    else:
        print("未检测到 .env 文件，请先执行 switch_env.py dev 或 prod")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        show_env()
        sys.exit(0)

    cmd = sys.argv[1].lower().strip()

    if cmd in ("dev", "prod"):
        try:
            name = switch_env(cmd)
            env_names = {"dev": "开发环境 (localhost)", "prod": "生产环境 (192.168.100.160)"}
            print(f"已切换到: {env_names.get(name, name)}")
        except Exception as e:
            print(f"切换失败: {e}")
            sys.exit(1)
    elif cmd == "show":
        show_env()
    elif cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
    else:
        print(f"未知命令: {cmd!r}，可用: dev / prod / show")
        sys.exit(1)


if __name__ == "__main__":
    main()
