"""Monitor Plugin v3 - 代码质量验证脚本

用途: 快速检查项目结构、语法、核心模块导入与关键文件
用法: python validate.py
"""

import sys
from pathlib import Path


def _ensure_astrbot_available() -> None:
    """无 AstrBot 环境时注入 tests/fake_astrbot 最小 API 桩。"""
    try:
        import astrbot  # noqa: F401
        return
    except ImportError:
        pass
    fake = Path(__file__).parent / "tests" / "fake_astrbot"
    if fake.is_dir():
        sys.path.insert(0, str(fake))
        print(f"(注：未检测到 astrbot，已注入测试桩 {fake})")


def check_directory_structure():
    """检查目录结构是否完整。"""
    print("=" * 60)
    print("1. 检查目录结构...")
    print("=" * 60)

    required_dirs = [
        "commands",
        "core/crawler",
        "core/detector",
        "core/models",
        "db",
        "notifier",
        "scheduler",
        "templates",
        "translate",
        "tests",
    ]

    base_path = Path(__file__).parent
    all_ok = True

    for dir_name in required_dirs:
        dir_path = base_path / dir_name
        if dir_path.exists():
            print(f"OK {dir_name}/")
        else:
            print(f"MISSING {dir_name}/")
            all_ok = False

    return all_ok


def check_required_files():
    """检查必需文件是否存在。"""
    print("\n" + "=" * 60)
    print("2. 检查必需文件...")
    print("=" * 60)

    required_files = [
        "metadata.yaml",
        "requirements.txt",
        "_conf_schema.json",
        "main.py",
        "README.md",
        "templates/change_report.html",
        "templates/compare_report.html",
        "templates/account_list.html",
        "translate/translation_map.json",
    ]

    base_path = Path(__file__).parent
    all_ok = True

    for file_name in required_files:
        file_path = base_path / file_name
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"OK {file_name} ({size} bytes)")
        else:
            print(f"MISSING {file_name}")
            all_ok = False

    return all_ok


def check_python_syntax():
    """检查 Python 文件语法是否正确。"""
    print("\n" + "=" * 60)
    print("3. 检查 Python 语法...")
    print("=" * 60)

    import py_compile

    py_files = list(Path(__file__).parent.rglob("*.py"))

    all_ok = True
    errors = []

    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
            rel_path = py_file.relative_to(Path(__file__).parent)
            print(f"OK {rel_path}")
        except py_compile.PyCompileError as e:
            rel_path = py_file.relative_to(Path(__file__).parent)
            print(f"FAIL {rel_path}: {e}")
            errors.append(str(e))
            all_ok = False

    if errors:
        print(f"\n发现 {len(errors)} 个语法错误")

    return all_ok and len(errors) == 0


def check_imports():
    """检查核心模块导入是否成功。"""
    print("\n" + "=" * 60)
    print("4. 检查核心模块导入...")
    print("=" * 60)

    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    # 以 metadata name（monitor_plugin3）注册插件根为包（同 tests/conftest.py），
    # 使插件内部相对导入（from ..core.xxx）在验证中成立
    import types
    _pkg = types.ModuleType("monitor_plugin3")
    _pkg.__path__ = [str(project_root)]
    sys.modules["monitor_plugin3"] = _pkg

    test_imports = [
        ("monitor_plugin3.commands.validators", "validate_steam_id"),
        ("monitor_plugin3.commands.add_account", "add_account"),
        ("monitor_plugin3.commands.list_accounts", "list_accounts"),
        ("monitor_plugin3.commands.edit_gap", "edit_gap"),
        ("monitor_plugin3.commands.stop_message", "stop_message"),
        ("monitor_plugin3.commands.stop_all", "stop_all"),
        ("monitor_plugin3.commands.stop_all", "start_all"),
        ("monitor_plugin3.commands.compare", "compare"),
        ("monitor_plugin3.commands.message_gap", "message_gap"),
        ("monitor_plugin3.commands.nickname", "nickname"),
        ("monitor_plugin3.commands.crawl_now", "crawl_now"),
        ("monitor_plugin3.commands.proxy_test", "proxy_test"),
        ("monitor_plugin3.commands.del_account", "del_account"),
        ("monitor_plugin3.commands.restore_account", "restore_account"),
        ("monitor_plugin3.commands.export_import", "mon_export"),
        ("monitor_plugin3.commands.export_import", "mon_import"),
        ("monitor_plugin3.scheduler.monitor", "MonitorController"),
        ("monitor_plugin3.scheduler.message_queue", "MessageQueue"),
        ("monitor_plugin3.notifier.formatter", "build_report"),
        ("monitor_plugin3.notifier.dispatcher", "MessageDispatcher"),
        ("monitor_plugin3.notifier.dispatcher", "notify_admin"),
        ("monitor_plugin3.db.repository", "export_all_data"),
        ("monitor_plugin3.db.repository", "import_all_data"),
        ("monitor_plugin3.db.models", "MonitoredUser"),
        ("monitor_plugin3.core.config", "PluginSettings"),
        ("monitor_plugin3.core.crawler.fetcher", "fetch_inventory_paginated"),
        ("monitor_plugin3.core.crawler.localize", "translate_name"),
        ("monitor_plugin3.core.detector.diff", "detect_changes"),
        ("monitor_plugin3.main", "MonitorPlugin"),
    ]

    all_ok = True
    failed = []

    for module_name, symbol_name in test_imports:
        try:
            module = __import__(module_name, fromlist=[symbol_name])
            if hasattr(module, symbol_name):
                print(f"OK {module_name}.{symbol_name}")
            else:
                print(f"WARN {module_name} (缺少 {symbol_name})")
                all_ok = False
        except ImportError as e:
            print(f"FAIL {module_name}: {e}")
            failed.append((module_name, str(e)))
            all_ok = False
        except Exception as e:
            print(f"FAIL {module_name}: {type(e).__name__}: {e}")
            failed.append((module_name, str(e)))
            all_ok = False

    if failed:
        print(f"\n导入失败：{len(failed)} 个模块")

    return all_ok and len(failed) == 0


def main():
    """主验证流程。"""
    print("\n" + "=" * 60)
    print("Monitor Plugin v3 - 代码质量验证")
    print("=" * 60 + "\n")

    _ensure_astrbot_available()

    results = []

    results.append(("目录结构", check_directory_structure()))
    results.append(("必需文件", check_required_files()))
    results.append(("Python 语法", check_python_syntax()))
    results.append(("模块导入", check_imports()))

    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status}: {name}")

    print(f"\n总计：{passed}/{total} 项通过")

    if passed == total:
        print("\n全部检查通过！")
        return 0
    else:
        print(f"\n发现 {total - passed} 个问题，请修复后重新验证")
        return 1


if __name__ == "__main__":
    sys.exit(main())
