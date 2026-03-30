"""Outlook/Hotmail 邮箱收件服务

支持协议：
- IMAP (imap.outlook.com / outlook.office365.com)
- Microsoft Graph REST API (需要 client_id + refresh_token)

格式：email----password----client_id----refresh_token
"""

import imaplib
import email
import re
import time
import json
import logging
from typing import Optional, Set
from datetime import datetime, timezone

from .base_mailbox import BaseMailbox, MailboxAccount

logger = logging.getLogger(__name__)

# Outlook IMAP 默认服务器
OUTLOOK_IMAP_SERVERS = {
    "outlook.com": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "live.cn": "outlook.office365.com",
    "outlook.cn": "partner.outlook.cn",
    "msn.com": "outlook.office365.com",
}

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def parse_outlook_entry(raw: str) -> dict:
    """解析 Outlook 邮箱 entry 格式：email----password----client_id----refresh_token

    支持 2-4 个字段：
      - 2 字段：email----password（仅 IMAP）
      - 3 字段：email----password----client_id（不完整）
      - 4 字段：email----password----client_id----refresh_token（完整 Graph API）
    """
    parts = raw.strip().split("----")
    if len(parts) < 2:
        raise ValueError(f"Outlook entry 格式错误，至少需要 email----password，得到: {raw[:50]}...")
    return {
        "email": parts[0].strip(),
        "password": parts[1].strip(),
        "client_id": parts[2].strip() if len(parts) > 2 else "",
        "refresh_token": parts[3].strip() if len(parts) > 3 else "",
    }


def get_imap_server(email_addr: str) -> str:
    """根据邮箱域名返回 IMAP 服务器地址"""
    domain = email_addr.split("@")[-1].lower()
    return OUTLOOK_IMAP_SERVERS.get(domain, "outlook.office365.com")


class OutlookMailbox(BaseMailbox):
    """Outlook/Hotmail 邮箱服务

    优先使用 Microsoft Graph API（需要 client_id + refresh_token），
    回退到 IMAP（需要密码）。
    """

    def __init__(
        self,
        email_addr: str,
        password: str = "",
        client_id: str = "",
        refresh_token: str = "",
        protocol: str = "auto",  # auto | graph | imap
        proxy: str = None,
    ):
        self._email = email_addr
        self._password = password
        self._client_id = client_id
        self._refresh_token = refresh_token
        self._protocol = protocol
        self._proxy = proxy
        self._access_token = None
        self._token_expiry = 0

        # 自动选择协议
        if protocol == "auto":
            if client_id and refresh_token:
                self._protocol = "graph"
            elif password:
                self._protocol = "imap"
            else:
                raise RuntimeError(
                    "Outlook 邮箱需要密码（IMAP）或 client_id + refresh_token（Graph API）"
                )

        self._log(f"Outlook 邮箱初始化: {email_addr}, 协议: {self._protocol}")

    def _log(self, msg):
        logger.info(f"[Outlook] {msg}")

    # ─── Graph API ───────────────────────────────────────────

    def _refresh_access_token(self):
        """使用 refresh_token 获取新的 access_token"""
        from curl_cffi import requests as curl_requests

        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "client_id": self._client_id,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": "https://graph.microsoft.com/Mail.Read offline_access",
        }
        proxies = {"http": self._proxy, "https": self._proxy} if self._proxy else None
        resp = curl_requests.post(
            token_url,
            data=data,
            proxies=proxies,
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Graph API token 刷新失败: HTTP {resp.status_code} - {resp.text[:200]}"
            )
        token_data = resp.json()
        self._access_token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600) - 60
        self._log("Graph API access_token 刷新成功")

    def _ensure_graph_token(self):
        """确保 access_token 有效"""
        if not self._access_token or time.time() >= self._token_expiry:
            self._refresh_access_token()

    def _graph_get_messages(self, top: int = 20, filter_str: str = "") -> list:
        """通过 Graph API 获取邮件"""
        from curl_cffi import requests as curl_requests

        self._ensure_graph_token()
        url = f"{GRAPH_API_BASE}/me/messages"
        params = {
            "$top": top,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,body,isRead",
        }
        if filter_str:
            params["$filter"] = filter_str

        headers = {"Authorization": f"Bearer {self._access_token}"}
        proxies = {"http": self._proxy, "https": self._proxy} if self._proxy else None

        resp = curl_requests.get(
            url,
            params=params,
            headers=headers,
            proxies=proxies,
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Graph API 获取邮件失败: HTTP {resp.status_code}")
        return resp.json().get("value", [])

    # ─── IMAP ────────────────────────────────────────────────

    def _imap_connect(self) -> imaplib.IMAP4_SSL:
        """连接 Outlook IMAP 服务器"""
        server = get_imap_server(self._email)
        self._log(f"连接 IMAP: {server}:993")
        conn = imaplib.IMAP4_SSL(server, 993, timeout=30)
        conn.login(self._email, self._password)
        conn.select("INBOX")
        return conn

    def _imap_search(self, conn, since_minutes: int = 30) -> list:
        """搜索最近的邮件"""
        since_date = (datetime.now(timezone.utc)).strftime("%d-%b-%Y")
        _, msg_ids = conn.search(None, f'(SINCE "{since_date}")')
        return msg_ids[0].split() if msg_ids[0] else []

    def _imap_fetch(self, conn, msg_id: bytes) -> dict:
        """获取单封邮件内容"""
        _, msg_data = conn.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                elif ct == "text/html" and not body:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        return {
            "id": msg_id.decode(),
            "subject": str(email.header.make_header(email.header.decode_header(msg.get("Subject", "")))),
            "from": msg.get("From", ""),
            "body": body,
            "date": msg.get("Date", ""),
        }

    # ─── BaseMailbox 接口 ───────────────────────────────────

    def get_email(self) -> MailboxAccount:
        """返回邮箱地址"""
        if not self._email:
            raise RuntimeError("Outlook 邮箱地址未配置")
        return MailboxAccount(
            email=self._email,
            account_id=self._email,
            extra={
                "protocol": self._protocol,
                "has_graph": bool(self._client_id and self._refresh_token),
            },
        )

    def get_current_ids(self, account: MailboxAccount) -> Set[str]:
        """返回当前邮件 ID 集合"""
        try:
            if self._protocol == "graph":
                messages = self._graph_get_messages(top=50)
                return {m["id"] for m in messages}
            else:
                conn = self._imap_connect()
                try:
                    ids = self._imap_search(conn)
                    return {i.decode() for i in ids}
                finally:
                    try:
                        conn.logout()
                    except Exception:
                        pass
        except Exception as e:
            self._log(f"获取邮件 ID 失败: {e}")
            return set()

    def wait_for_code(
        self,
        account: MailboxAccount,
        keyword: str = "",
        timeout: int = 120,
        before_ids: Set[str] = None,
        code_pattern: str = None,
        **kwargs,
    ) -> Optional[str]:
        """等待并提取验证码"""
        before_ids = before_ids or set()
        keyword = keyword or "verification"
        start = time.time()
        check_interval = 5

        self._log(f"等待验证码 ({timeout}s, 关键词: {keyword})...")

        while time.time() - start < timeout:
            try:
                emails = self._fetch_recent_emails(since_minutes=5)
                for mail in emails:
                    mail_id = mail.get("id", "")
                    if mail_id in before_ids:
                        continue
                    subject = mail.get("subject", "")
                    body = mail.get("body", "")
                    combined = f"{subject}\n{body}"

                    if keyword.lower() not in combined.lower():
                        continue

                    code = self._safe_extract(combined, code_pattern)
                    if code:
                        self._log(f"验证码提取成功: {code}")
                        return code
            except Exception as e:
                self._log(f"检查邮件异常: {e}")

            time.sleep(check_interval)

        self._log("等待验证码超时")
        return None

    def _fetch_recent_emails(self, since_minutes: int = 30) -> list:
        """获取最近的邮件（统一接口）"""
        if self._protocol == "graph":
            # Graph API: 过滤最近 N 分钟的邮件
            since_time = (
                datetime.now(timezone.utc)
                .replace(minute=0, second=0, microsecond=0)
                .isoformat()
            )
            filter_str = f"receivedDateTime ge {since_time}"
            return self._graph_get_messages(top=20, filter_str=filter_str)
        else:
            conn = self._imap_connect()
            try:
                msg_ids = self._imap_search(conn, since_minutes=since_minutes)
                # 只取最近 20 封
                results = []
                for mid in msg_ids[-20:]:
                    try:
                        results.append(self._imap_fetch(conn, mid))
                    except Exception:
                        pass
                return results
            finally:
                try:
                    conn.logout()
                except Exception:
                    pass

    def get_messages(self, limit: int = 20) -> list:
        """获取邮件列表（供外部调用）"""
        if self._protocol == "graph":
            return self._graph_get_messages(top=limit)
        else:
            conn = self._imap_connect()
            try:
                msg_ids = self._imap_search(conn)
                results = []
                for mid in msg_ids[-limit:]:
                    try:
                        results.append(self._imap_fetch(conn, mid))
                    except Exception:
                        pass
                return results
            finally:
                try:
                    conn.logout()
                except Exception:
                    pass
