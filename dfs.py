"""DataForSEO 客户端（零依赖）。

凭据由词真语 Deploy 统一管理（禁止硬编码）：
  CIZHENYU_AUTH_DIR / SEOGEO_AUTH_DIR 下 dataforseo.json 或 dataforseo_conf.json
  字段：API_login / API_password（或 login / password），可选 Base64_format。
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.request

import cizhenyu_auth

BASE = "https://api.dataforseo.com"
SANDBOX_BASE = "https://sandbox.dataforseo.com"


class DataForSeoError(RuntimeError):
    pass


def base_url() -> str:
    """SEOGEO_DFS_SANDBOX=1 时走官方沙箱（返回模拟数据，用于链路自检，不计费）。"""
    return SANDBOX_BASE if os.environ.get("SEOGEO_DFS_SANDBOX", "").strip().lower() in ("1", "true", "yes") else BASE


def load_auth() -> str:
    try:
        conf = cizhenyu_auth.read_json("dataforseo.json", "dataforseo_conf.json")
    except cizhenyu_auth.AuthError as exc:
        raise DataForSeoError(str(exc)) from exc
    b64 = cizhenyu_auth.first_str(conf, "Base64_format", "base64")
    if b64:
        return b64
    login = cizhenyu_auth.first_str(conf, "API_login", "login", "username")
    password = cizhenyu_auth.first_str(conf, "API_password", "password")
    if not login or not password:
        raise DataForSeoError("dataforseo 配置缺少 API_login / API_password")
    return base64.b64encode(f"{login}:{password}".encode()).decode()


def post(path: str, payload: list[dict], timeout: int = 120, retries: int = 3) -> dict:
    url = f"{base_url()}{path}"
    auth = load_auth()
    body = json.dumps(payload).encode()
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
                data = json.loads(resp.read().decode())
            if data.get("status_code") != 20000:
                raise DataForSeoError(f"{data.get('status_code')}: {data.get('status_message')}")
            tasks = data.get("tasks") or []
            first = tasks[0] if tasks else {}
            if first.get("status_code") not in (20000, None):
                raise DataForSeoError(f"task {first.get('status_code')}: {first.get('status_message')}")
            return data
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            last = DataForSeoError(f"HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503) and attempt < retries:
                time.sleep(4 * attempt)
                continue
            raise last
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(3 * attempt)
    raise last if last else DataForSeoError("unknown error")


def _norm_domain(host: str) -> str:
    """统一域名：去 www、转小写，避免同一站点被算成两个。"""
    host = (host or "").strip().lower()
    return host[4:] if host.startswith("www.") else host


def _result(data: dict):
    tasks = data.get("tasks") or []
    return tasks[0].get("result") if tasks else None


def _first(data: dict):
    result = _result(data)
    return result[0] if isinstance(result, list) and result else {}


def serp_google(keyword: str, location: str = "United States", language: str = "en",
                device: str = "desktop", depth: int = 20) -> dict:
    """Google 自然搜索结果 + SERP 特征，用于判难与 SERP 重叠聚类。"""
    data = post("/v3/serp/google/organic/live/advanced", [{
        "keyword": keyword, "location_name": location, "language_code": language,
        "device": device, "depth": depth,
    }])
    item = _first(data)
    organic, features = [], {}
    for it in item.get("items") or []:
        t = it.get("type")
        if t == "organic":
            organic.append({
                "rank": it.get("rank_group"), "url": it.get("url"),
                "domain": _norm_domain(it.get("domain") or ""),
                "title": it.get("title"), "description": (it.get("description") or "")[:160],
            })
        elif t:
            features[t] = features.get(t, 0) + 1
    return {
        "keyword": keyword, "location": location, "language": language,
        "organic": organic, "serp_features": features,
        "total_results": item.get("se_results_count"), "cost": data.get("cost"),
    }


def bulk_keyword_difficulty(keywords: list[str], location: str = "United States",
                            language: str = "en") -> dict:
    data = post("/v3/dataforseo_labs/google/bulk_keyword_difficulty/live", [{
        "keywords": keywords[:1000], "location_name": location, "language_code": language,
    }])
    rows = [{"keyword": i.get("keyword"), "difficulty": i.get("keyword_difficulty")}
            for i in (_first(data).get("items") or [])]
    return {"location": location, "rows": rows, "cost": data.get("cost")}


def search_intent(keywords: list[str], language: str = "en") -> dict:
    data = post("/v3/dataforseo_labs/google/search_intent/live", [{
        "keywords": keywords[:1000], "language_code": language,
    }])
    rows = [{
        "keyword": i.get("keyword"),
        "intent": (i.get("keyword_intent") or {}).get("label"),
        "probability": (i.get("keyword_intent") or {}).get("probability"),
    } for i in (_first(data).get("items") or [])]
    return {"rows": rows, "cost": data.get("cost")}


def keyword_ideas(keyword: str, location: str = "United States", language: str = "en",
                  limit: int = 200) -> dict:
    data = post("/v3/dataforseo_labs/google/keyword_ideas/live", [{
        "keywords": [keyword], "location_name": location, "language_code": language,
        "limit": min(limit, 1000),
    }])
    rows = []
    for i in (_first(data).get("items") or []):
        info, props = i.get("keyword_info") or {}, i.get("keyword_properties") or {}
        rows.append({
            "keyword": i.get("keyword"), "volume": info.get("search_volume"),
            "competition": info.get("competition_level"), "cpc": info.get("cpc"),
            "difficulty": props.get("keyword_difficulty"),
            "intent": (i.get("search_intent_info") or {}).get("main_intent"),
        })
    return {"seed": keyword, "location": location, "rows": rows, "cost": data.get("cost")}


def bulk_search_volume(keywords: list[str], location: str = "United States",
                       language: str = "en") -> dict:
    data = post("/v3/dataforseo_labs/google/bulk_search_volume/live", [{
        "keywords": keywords[:1000], "location_name": location, "language_code": language,
    }])
    rows = []
    for i in (_first(data).get("items") or []):
        info = i.get("keyword_info") or {}
        rows.append({"keyword": i.get("keyword"), "volume": info.get("search_volume"),
                     "competition": info.get("competition_level"), "cpc": info.get("cpc")})
    return {"location": location, "rows": rows, "cost": data.get("cost")}


def ranked_keywords(domain: str, location: str = "United States", language: str = "en",
                    limit: int = 200) -> dict:
    data = post("/v3/dataforseo_labs/google/ranked_keywords/live", [{
        "target": domain, "location_name": location, "language_code": language,
        "limit": min(limit, 1000),
        "order_by": ["keyword_data.keyword_info.search_volume,desc"],
    }])
    rows = []
    for i in (_first(data).get("items") or []):
        kd = i.get("keyword_data") or {}
        info = kd.get("keyword_info") or {}
        rank = (i.get("ranked_serp_element") or {}).get("serp_item") or {}
        rows.append({"keyword": kd.get("keyword"), "volume": info.get("search_volume"),
                     "competition": info.get("competition_level"),
                     "rank": rank.get("rank_group"), "url": rank.get("url")})
    return {"domain": domain, "location": location, "rows": rows, "cost": data.get("cost")}


def serp_competitors(keywords: list[str], location: str = "United States", language: str = "en",
                     limit: int = 100) -> dict:
    data = post("/v3/dataforseo_labs/google/serp_competitors/live", [{
        "keywords": keywords[:200], "location_name": location, "language_code": language,
        "limit": min(limit, 1000),
    }])
    rows = [{
        "domain": _norm_domain(i.get("domain") or ""), "avg_position": i.get("avg_position"),
        "keywords_count": i.get("keywords_count"), "etv": i.get("etv"),
        "visibility": i.get("visibility"),
    } for i in (_result(data) or [])]
    return {"location": location, "rows": rows, "cost": data.get("cost")}


def get(path: str, timeout: int = 60, retries: int = 2) -> dict:
    """GET 接口（如 appendix/user_data）。"""
    url = f"{base_url()}{path}"
    auth = load_auth()
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
                data = json.loads(resp.read().decode())
            if data.get("status_code") != 20000:
                raise DataForSeoError(f"{data.get('status_code')}: {data.get('status_message')}")
            return data
        except urllib.error.HTTPError as exc:
            last = DataForSeoError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
            if exc.code in (429, 500, 502, 503) and attempt < retries:
                time.sleep(3 * attempt)
                continue
            raise last
    raise last if last else DataForSeoError("unknown error")


def account_status() -> dict:
    data = get("/v3/appendix/user_data")
    item = _first(data)
    money = item.get("money") or {}
    return {"login": item.get("login"), "balance_usd": money.get("balance"),
            "total_usd": money.get("total"),
            "serp_day_limit": ((money.get("limits") or {}).get("day") or {}).get("serp", {}).get("total")}
