"""grok2api 自动导入"""

from __future__ import annotations

import logging
from typing import Tuple

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

DEFAULT_POOL = "ssoBasic"
DEFAULT_QUOTAS = {
    "ssoBasic": 80,
    "ssoSuper": 140,
}


def _get_config_value(key: str) -> str:
    try:
        from core.config_store import config_store

        return str(config_store.get(key, "") or "")
    except Exception:
        return ""


def _normalize_quota(pool_name: str, quota) -> int:
    if quota not in (None, ""):
        try:
            return int(quota)
        except Exception:
            pass
    return DEFAULT_QUOTAS.get(pool_name, DEFAULT_QUOTAS[DEFAULT_POOL])


def _extract_sso(account) -> str:
    extra = getattr(account, "extra", {}) or {}
    token = (
        extra.get("sso")
        or extra.get("sso_token")
        or extra.get("sso_rw")
        or getattr(account, "token", "")
    )
    token = str(token or "").strip()
    if token.startswith("sso="):
        token = token[4:]
    return token


def build_grok2api_payload(
    account,
    pool_name: str | None = None,
    quota=None,
) -> dict:
    token = _extract_sso(account)
    if not token:
        raise ValueError("账号缺少 sso token")

    pool_name = str(pool_name or _get_config_value("grok2api_pool") or DEFAULT_POOL).strip() or DEFAULT_POOL
    email = getattr(account, "email", "")
    payload = {
        pool_name: [
            {
                "token": token,
                "status": "active",
                "quota": _normalize_quota(pool_name, quota or _get_config_value("grok2api_quota")),
                "tags": [],
                "note": f"auto-import:{email}" if email else "auto-import",
            }
        ]
    }
    return payload


def _request_options() -> dict:
    return {
        "proxies": None,
        "verify": False,
        "timeout": 30,
        "impersonate": "chrome136",
    }


def _build_headers(app_key: str) -> dict:
    return {
        "Authorization": f"Bearer {app_key}",
        "Content-Type": "application/json",
    }


def _build_token_item(account, pool_name: str | None = None, quota=None) -> tuple[str, dict]:
    payload = build_grok2api_payload(account, pool_name=pool_name, quota=quota)
    normalized_pool_name = next(iter(payload.keys()))
    return normalized_pool_name, payload[normalized_pool_name][0]


def _load_existing_tokens(api_url: str, headers: dict) -> dict:
    resp = cffi_requests.get(
        f"{api_url.rstrip('/')}/v1/admin/tokens",
        headers=headers,
        **_request_options(),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"读取现有 tokens 失败: HTTP {resp.status_code} - {resp.text[:200]}")

    data = resp.json()
    tokens = data.get("tokens", {})
    if not isinstance(tokens, dict):
        raise RuntimeError("读取现有 tokens 失败: 响应格式异常")
    return tokens


def _merge_token(existing_tokens: dict, pool_name: str, token_item: dict) -> dict:
    merged: dict = {}
    new_token = str(token_item.get("token", "") or "").strip()

    for existing_pool_name, pool_tokens in existing_tokens.items():
        merged[existing_pool_name] = list(pool_tokens) if isinstance(pool_tokens, list) else []

    pool_list = merged.setdefault(pool_name, [])
    replaced = False

    for index, existing_item in enumerate(pool_list):
        if not isinstance(existing_item, dict):
            continue
        existing_token = str(existing_item.get("token", "") or "").strip()
        if existing_token == new_token:
            updated_item = dict(existing_item)
            updated_item.update(token_item)
            pool_list[index] = updated_item
            replaced = True
            break

    if not replaced:
        pool_list.append(token_item)

    return merged


def upload_to_grok2api(
    account,
    api_url: str | None = None,
    app_key: str | None = None,
    pool_name: str | None = None,
    quota=None,
) -> Tuple[bool, str]:
    """上传 Grok 账号到 grok2api 管理接口。"""
    if not api_url:
        api_url = _get_config_value("grok2api_url")
    if not app_key:
        app_key = _get_config_value("grok2api_app_key")

    api_url = str(api_url or "").strip()
    app_key = str(app_key or "").strip()
    if not api_url:
        return False, "grok2api URL 未配置"
    if not app_key:
        return False, "grok2api App Key 未配置"

    pool_name, token_item = _build_token_item(account, pool_name=pool_name, quota=quota)
    upload_url = f"{api_url.rstrip('/')}/v1/admin/tokens"
    headers = _build_headers(app_key)

    try:
        existing_tokens = _load_existing_tokens(api_url, headers)
        payload = _merge_token(existing_tokens, pool_name, token_item)
        resp = cffi_requests.post(
            upload_url,
            headers=headers,
            json=payload,
            **_request_options(),
        )
        if resp.status_code in (200, 201):
            return True, "导入成功"

        error_msg = f"导入失败: HTTP {resp.status_code}"
        try:
            detail = resp.json()
            if isinstance(detail, dict):
                error_msg = detail.get("message") or detail.get("detail") or error_msg
        except Exception:
            error_msg = f"{error_msg} - {resp.text[:200]}"
        return False, error_msg
    except Exception as e:
        logger.error(f"grok2api 导入异常: {e}")
        return False, f"导入异常: {e}"
