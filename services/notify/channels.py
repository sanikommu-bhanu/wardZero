"""Free alert channels: Telegram bot and ntfy.sh push, with guaranteed in-app fallback.

Secrets come from environment variables (see .env.example) and are never logged or returned. Every send is
attempted independently; a failure on one channel never blocks another, and the in-app channel always succeeds
(the alert is already stored and broadcast over the WebSocket), so a dead internet link degrades gracefully."""
from __future__ import annotations

import json
import os
import urllib.request

TIMEOUT_S = 5


def _default_transport(req: urllib.request.Request):
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:   # noqa: S310 - fixed https hosts
        return r.status


class InAppChannel:
    name = "in_app"
    configured = True

    def __init__(self, sink=None):
        self.sink = sink or (lambda payload: None)   # e.g. websocket broadcast

    def send(self, title: str, body: str, severity: str, alert_id=None) -> bool:
        self.sink({"type": "notification", "title": title, "body": body, "severity": severity, "alert_id": alert_id})
        return True


class TelegramChannel:
    name = "telegram"

    def __init__(self, token: str | None = None, chat_id: str | None = None, transport=None):
        self.token = token or os.environ.get("WZ_TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("WZ_TELEGRAM_CHAT_ID")
        self.transport = transport or _default_transport

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, title, body, severity, alert_id=None) -> bool:
        data = json.dumps({"chat_id": self.chat_id, "text": f"[{severity.upper()}] {title}\n{body}"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/sendMessage", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        return 200 <= self.transport(req) < 300


class NtfyChannel:
    name = "ntfy"
    PRIORITY = {"critical": "5", "high_risk": "4", "warning": "3", "informational": "2"}

    def __init__(self, topic: str | None = None, server: str | None = None, transport=None):
        self.topic = topic or os.environ.get("WZ_NTFY_TOPIC")
        self.server = (server or os.environ.get("WZ_NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
        self.transport = transport or _default_transport

    @property
    def configured(self) -> bool:
        return bool(self.topic)

    def send(self, title, body, severity, alert_id=None) -> bool:
        req = urllib.request.Request(f"{self.server}/{self.topic}", data=body.encode(), method="POST",
                                     headers={"Title": title.encode("ascii", "ignore").decode() or "WardZero alert",
                                              "Priority": self.PRIORITY.get(severity, "3"), "Tags": "warning"})
        return 200 <= self.transport(req) < 300


class Dispatcher:
    """Sends to every configured channel; records each outcome (repo.log_notification if provided)."""

    def __init__(self, channels: list, repo=None):
        self.channels, self.repo = channels, repo

    def send(self, title: str, body: str, severity: str, alert_id=None) -> dict:
        outcome = {}
        for ch in self.channels:
            if not ch.configured:
                continue
            try:
                ok = bool(ch.send(title, body, severity, alert_id))
                detail = ""
            except Exception as e:  # network down, bad token, timeout...
                ok, detail = False, type(e).__name__          # class name only: never leak URLs/tokens
            outcome[ch.name] = ok
            if self.repo:
                self.repo.log_notification(ch.name, ok, alert_id, detail)
        return outcome

    @staticmethod
    def from_env(repo=None, in_app_sink=None) -> "Dispatcher":
        return Dispatcher([InAppChannel(in_app_sink), TelegramChannel(), NtfyChannel()], repo)
