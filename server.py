#!/usr/bin/env python3
"""DataForSEO MCP 服务器 + CLI（零依赖，stdio JSON-RPC）。

MCP 用法（DSH / Claude / Cursor 挂载）：
  command: <python.exe>
  args:    ["C:/scripts/seogeo-dataforseo/server.py"]
  cwd:     C:/scripts/seogeo-dataforseo

CLI 用法（不依赖 MCP 也能调）：
  python server.py list
  python server.py dfs_keyword_ideas --json "{\"keyword\":\"nail lamp\"}"
  python server.py dfs_account

协议自检：
  echo {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}} | python server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dfs  # noqa: E402

SERVER_NAME = "seogeo-dataforseo"
SERVER_VERSION = "1.0.0"

TOOLS = {
    "dfs_account": {
        "fn": dfs.account_status,
        "desc": "DataForSEO 账户状态（余额、登录名）。用于确认凭据可用与余额。",
        "schema": {"type": "object", "properties": {}, "required": []},
    },
    "dfs_serp_google": {
        "fn": dfs.serp_google,
        "desc": "Google 自然搜索 top N（含 SERP 特征）。用于判难、SERP 重叠聚类、看谁在排。",
        "schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
                "device": {"type": "string", "enum": ["desktop", "mobile"], "default": "desktop"},
                "depth": {"type": "integer", "default": 20},
            },
            "required": ["keyword"],
        },
    },
    "dfs_keyword_ideas": {
        "fn": dfs.keyword_ideas,
        "desc": "基于种子词的相关关键词，含月搜索量、竞争度、CPC、难度、意图。",
        "schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["keyword"],
        },
    },
    "dfs_keyword_difficulty": {
        "fn": dfs.bulk_keyword_difficulty,
        "desc": "批量关键词难度（0-100）。替代凭经验猜的 KD。",
        "schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string"}},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
            },
            "required": ["keywords"],
        },
    },
    "dfs_search_intent": {
        "fn": dfs.search_intent,
        "desc": "关键词搜索意图（informational/commercial/transactional/navigational）。",
        "schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string"}},
                "language": {"type": "string", "default": "en"},
            },
            "required": ["keywords"],
        },
    },
    "dfs_bulk_search_volume": {
        "fn": dfs.bulk_search_volume,
        "desc": "批量月搜索量与竞争度（DataForSEO Labs 口径）。",
        "schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string"}},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
            },
            "required": ["keywords"],
        },
    },
    "dfs_ranked_keywords": {
        "fn": dfs.ranked_keywords,
        "desc": "某域名自然搜索排名的关键词（竞品词库反查）。",
        "schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
                "limit": {"type": "integer", "default": 200},
            },
            "required": ["domain"],
        },
    },
    "dfs_serp_competitors": {
        "fn": dfs.serp_competitors,
        "desc": "给定一批关键词，返回抢占这些词的域名（含平均位置、可见度）。",
        "schema": {
            "type": "object",
            "properties": {
                "keywords": {"type": "array", "items": {"type": "string"}},
                "location": {"type": "string", "default": "United States"},
                "language": {"type": "string", "default": "en"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["keywords"],
        },
    },
}


def call_tool(name: str, args: dict) -> dict:
    spec = TOOLS.get(name)
    if not spec:
        return {"error": f"unknown tool: {name}"}
    try:
        result = spec["fn"](**args)
        return {"ok": True, "tool": name, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "tool": name, "error": f"{type(exc).__name__}: {exc}"}


# ------------------------------------------------------------------ MCP stdio

def _reply(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            _reply({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            })
        elif method in ("notifications/initialized", "initialized"):
            continue
        elif method == "tools/list":
            _reply({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": [
                    {"name": n, "description": s["desc"], "inputSchema": s["schema"]}
                    for n, s in TOOLS.items()
                ]},
            })
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            result = call_tool(name, args)
            _reply({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            })
        elif method == "ping":
            _reply({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        elif msg_id is not None:
            _reply({"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"}})


# ------------------------------------------------------------------ CLI

def cli(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "list":
        for name, spec in TOOLS.items():
            print(f"{name:26} {spec['desc']}")
        return 0
    if cmd == "check":
        print(json.dumps(call_tool("dfs_account", {}), ensure_ascii=False, indent=2))
        return 0
    args = {}
    if "--args-file" in argv:
        path = argv[argv.index("--args-file") + 1]
        args = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    elif "--json" in argv:
        idx = argv.index("--json")
        args = json.loads(argv[idx + 1])
    else:
        for i, token in enumerate(argv[1:], start=1):
            if token.startswith("--"):
                key = token[2:].replace("-", "_")
                val = argv[i + 1] if i + 1 < len(argv) else ""
                if key in ("keywords", "domains"):
                    args[key] = [x.strip() for x in val.split(",") if x.strip()]
                elif key in ("depth", "limit"):
                    args[key] = int(val)
                else:
                    args[key] = val
    print(json.dumps(call_tool(cmd, args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(cli(sys.argv[1:]))
    serve()
