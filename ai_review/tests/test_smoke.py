"""Smoke test - 确保包能导入且版本号存在。"""

import src


def test_package_has_version() -> None:
    assert isinstance(src.__version__, str)
    assert src.__version__
