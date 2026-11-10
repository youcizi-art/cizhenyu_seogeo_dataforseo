"""统一从 Deploy 工作目录 credentials 读取凭据（禁止硬编码、禁止写系统 env）。

优先级：
  1. CIZHENYU_AUTH_DIR
  2. SEOGEO_AUTH_DIR
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class AuthError(RuntimeError):
    pass


def auth_dir() -> Path:
    for key in ("CIZHENYU_AUTH_DIR", "SEOGEO_AUTH_DIR"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw)
    raise AuthError(
        "未设置 CIZHENYU_AUTH_DIR / SEOGEO_AUTH_DIR。"
        "请通过词真语 Deploy 运营台导出 MCP，由软件注入工作目录 credentials。"
    )


def read_json(*relative_names: str) -> dict[str, Any]:
    base = auth_dir()
    tried: list[str] = []
    for name in relative_names:
        path = base / name
        tried.append(str(path))
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    raise AuthError("找不到凭据文件，已尝试：\n- " + "\n- ".join(tried))


def first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None
