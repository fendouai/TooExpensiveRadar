from __future__ import annotations

import json
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx


@dataclass
class NotificationResult:
    success: bool
    channel: str
    message: str
    details: Optional[dict] = None


class TelegramSender:
    def __init__(self, bot_token: str, proxy_url: Optional[str] = None, max_retries: int = 3):
        self.bot_token = bot_token
        self.proxy_url = proxy_url
        self.max_retries = max_retries

    def send(self, chat_id: str, text: str, parse_mode: str = "HTML") -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            for attempt in range(self.max_retries):
                try:
                    async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                        response = await client.post(url, json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": parse_mode,
                        })
                        result = response.json()
                        if result.get("ok"):
                            return NotificationResult(
                                success=True,
                                channel="telegram",
                                message="Message sent successfully",
                                details={"message_id": result.get("result", {}).get("message_id")},
                            )
                        return NotificationResult(success=False, channel="telegram", message=result.get("description", "Failed"))
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        return NotificationResult(success=False, channel="telegram", message=str(e))

        return asyncio.run(_send())


class EmailSender:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, to_email: str, subject: str, html_content: str, plain_content: str = "") -> NotificationResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.username
            msg["To"] = to_email

            if plain_content:
                msg.attach(MIMEText(plain_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            return NotificationResult(success=True, channel="email", message="Email sent successfully")
        except Exception as e:
            return NotificationResult(success=False, channel="email", message=str(e))


class DingTalkSender:
    def __init__(self, webhook_url: str, proxy_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.proxy_url = proxy_url

    def send(self, content: str, at_mobiles: Optional[list[str]] = None) -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None
            payload = {"msgtype": "markdown", "markdown": {"title": "Too Expensive Alert", "text": content}}
            if at_mobiles:
                payload["at"] = {"atMobiles": at_mobiles, "isAtAll": False}

            try:
                async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                    response = await client.post(self.webhook_url, json=payload)
                    result = response.json()
                    if result.get("errcode") == 0:
                        return NotificationResult(success=True, channel="dingtalk", message="Message sent")
                    return NotificationResult(success=False, channel="dingtalk", message=result.get("errmsg", "Failed"))
            except Exception as e:
                return NotificationResult(success=False, channel="dingtalk", message=str(e))

        return asyncio.run(_send())


class WeComSender:
    def __init__(self, webhook_url: str, proxy_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.proxy_url = proxy_url

    def send(self, content: str) -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None
            payload = {"msgtype": "markdown", "markdown": {"content": content}}

            try:
                async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                    response = await client.post(self.webhook_url, json=payload)
                    result = response.json()
                    if result.get("errcode") == 0:
                        return NotificationResult(success=True, channel="wecom", message="Message sent")
                    return NotificationResult(success=False, channel="wecom", message=result.get("errmsg", "Failed"))
            except Exception as e:
                return NotificationResult(success=False, channel="wecom", message=str(e))

        return asyncio.run(_send())


class FeishuSender:
    def __init__(self, webhook_url: str, proxy_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.proxy_url = proxy_url

    def send(self, content: str) -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None
            payload = {"msg_type": "interactive", "card": {"header": {"title": {"tag": "plain_text", "content": "Too Expensive Alert"}}, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}]}}

            try:
                async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                    response = await client.post(self.webhook_url, json=payload)
                    result = response.json()
                    if result.get("code") == 0 or result.get("StatusCode") == 0:
                        return NotificationResult(success=True, channel="feishu", message="Message sent")
                    return NotificationResult(success=False, channel="feishu", message=result.get("msg", "Failed"))
            except Exception as e:
                return NotificationResult(success=False, channel="feishu", message=str(e))

        return asyncio.run(_send())


class NtfySender:
    def __init__(self, topic: str, server_url: str = "https://ntfy.sh", auth_token: Optional[str] = None):
        self.topic = topic
        self.server_url = server_url
        self.auth_token = auth_token

    def send(self, title: str, message: str, priority: int = 3, tags: str = "warning") -> NotificationResult:
        import asyncio

        async def _send():
            headers = {"Title": title, "Priority": str(priority), "Tags": tags}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.server_url}/{self.topic}",
                        data=message.encode("utf-8"),
                        headers=headers,
                    )
                    if response.status_code == 200:
                        return NotificationResult(success=True, channel="ntfy", message="Notification sent")
                    return NotificationResult(success=False, channel="ntfy", message=f"HTTP {response.status_code}")
            except Exception as e:
                return NotificationResult(success=False, channel="ntfy", message=str(e))

        return asyncio.run(_send())


class BarkSender:
    def __init__(self, push_token: str, server_url: str = "https://api.day.app", proxy_url: Optional[str] = None):
        self.push_token = push_token
        self.server_url = server_url
        self.proxy_url = proxy_url

    def send(self, title: str, content: str, sound: str = "alarm") -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None
            url = f"{self.server_url}/{self.push_token}/{title}/{content}?sound={sound}"

            try:
                async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return NotificationResult(success=True, channel="bark", message="Push sent")
                    return NotificationResult(success=False, channel="bark", message=f"HTTP {response.status_code}")
            except Exception as e:
                return NotificationResult(success=False, channel="bark", message=str(e))

        return asyncio.run(_send())


class GenericWebhookSender:
    def __init__(self, webhook_url: str, proxy_url: Optional[str] = None, headers: Optional[dict] = None):
        self.webhook_url = webhook_url
        self.proxy_url = proxy_url
        self.headers = headers or {}

    def send(self, payload: dict) -> NotificationResult:
        import asyncio

        async def _send():
            proxies = {"http://": self.proxy_url, "https://": self.proxy_url} if self.proxy_url else None

            try:
                async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                    all_headers = {"Content-Type": "application/json"}
                    all_headers.update(self.headers)
                    response = await client.post(self.webhook_url, json=payload, headers=all_headers)
                    if response.status_code < 400:
                        return NotificationResult(success=True, channel="webhook", message="Webhook sent", details={"status": response.status_code})
                    return NotificationResult(success=False, channel="webhook", message=f"HTTP {response.status_code}")
            except Exception as e:
                return NotificationResult(success=False, channel="webhook", message=str(e))

        return asyncio.run(_send())


def create_notification_sender(channel: str, config: dict) -> Optional[object]:
    channel = channel.lower()
    if channel == "telegram":
        return TelegramSender(config.get("bot_token", ""), config.get("proxy_url"))
    elif channel == "email":
        return EmailSender(
            smtp_host=config.get("smtp_host", "localhost"),
            smtp_port=config.get("smtp_port", 587),
            username=config.get("username", ""),
            password=config.get("password", ""),
            use_tls=config.get("use_tls", True),
        )
    elif channel == "dingtalk":
        return DingTalkSender(config.get("webhook_url", ""), config.get("proxy_url"))
    elif channel == "wecom":
        return WeComSender(config.get("webhook_url", ""), config.get("proxy_url"))
    elif channel == "feishu":
        return FeishuSender(config.get("webhook_url", ""), config.get("proxy_url"))
    elif channel == "ntfy":
        return NtfySender(config.get("topic", ""), config.get("server_url", "https://ntfy.sh"), config.get("auth_token"))
    elif channel == "bark":
        return BarkSender(config.get("push_token", ""), config.get("server_url", "https://api.day.app"), config.get("proxy_url"))
    elif channel == "webhook":
        return GenericWebhookSender(config.get("webhook_url", ""), config.get("proxy_url"), config.get("headers"))
    return None


def markdown_to_telegram(text: str) -> str:
    text = text.replace("**", "*")
    text = text.replace("__", "_")
    return text


def markdown_to_dingtalk(text: str) -> str:
    text = text.replace("**", "#### ")
    lines = text.split("\n")
    return "\n".join(f"- {l}" if not l.startswith("#") else l.replace("# ", "") for l in lines if l.strip())


def format_notification_content(title: str, items: list[dict], max_items: int = 10) -> str:
    lines = [f"**{title}**\n"]
    for i, item in enumerate(items[:max_items]):
        software = item.get("software", "Unknown")
        score = item.get("disruption_score", 0)
        summary = item.get("complaint_summary", item.get("content", "")[:100])
        lines.append(f"{i+1}. **{software}** (score: {score:.1f})\n   {summary}")
    if len(items) > max_items:
        lines.append(f"\n_...and {len(items) - max_items} more_")
    return "\n".join(lines)


def split_content(content: str, max_length: int = 4000, overlap: int = 100) -> list[str]:
    if len(content) <= max_length:
        return [content]

    chunks = []
    start = 0
    while start < len(content):
        end = start + max_length
        chunk = content[start:end]
        if start > 0 and overlap > 0:
            chunk = content[start - overlap:start] + chunk
        chunks.append(chunk)
        start = end
    return chunks