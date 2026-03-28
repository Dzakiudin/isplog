"""Multi-channel notification dispatcher.

Channels:
  - Telegram Bot (python-telegram-bot async, run via asyncio.run)
  - Windows Desktop Toast (win10toast)
  - Email via SMTP (smtplib, TLS)

Each channel is optional: if credentials are missing or disabled, it is
silently skipped.  All three channels are dispatched concurrently via
ThreadPoolExecutor so a slow / failing channel does not block others.
"""
import asyncio
import logging
import smtplib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

logger = logging.getLogger("isplog")


# ---------------------------------------------------------------------------
# Individual senders
# ---------------------------------------------------------------------------

def _send_telegram(cfg: Dict[str, Any], title: str, message: str) -> None:
    tg = cfg.get("telegram", {})
    if not tg.get("enabled") or not tg.get("bot_token") or not tg.get("chat_id"):
        return

    try:
        import telegram  # python-telegram-bot

        async def _async_send():
            bot = telegram.Bot(token=tg["bot_token"])
            text = f"*{title}*\n{message}"
            await bot.send_message(
                chat_id=tg["chat_id"],
                text=text,
                parse_mode="Markdown",
            )

        asyncio.run(_async_send())
        logger.debug("Telegram notification sent.")
    except Exception as exc:
        logger.error("Telegram notification failed: %s", exc)


def _send_toast(cfg: Dict[str, Any], title: str, message: str) -> None:
    dn = cfg.get("desktop_notification", {})
    if not dn.get("enabled", True):
        return

    try:
        from win10toast import ToastNotifier

        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=8,
            threaded=True,
        )
        logger.debug("Desktop toast notification sent.")
    except Exception as exc:
        logger.error("Desktop notification failed: %s", exc)


def _send_email(cfg: Dict[str, Any], title: str, message: str) -> None:
    em = cfg.get("email", {})
    if (
        not em.get("enabled")
        or not em.get("username")
        or not em.get("password")
        or not em.get("to_address")
    ):
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[ISPLog] {title}"
        msg["From"] = em["username"]
        msg["To"] = em["to_address"]

        body = MIMEText(message, "plain", "utf-8")
        msg.attach(body)

        with smtplib.SMTP(em.get("smtp_host", "smtp.gmail.com"),
                          int(em.get("smtp_port", 587))) as server:
            server.ehlo()
            server.starttls()
            server.login(em["username"], em["password"])
            server.sendmail(em["username"], em["to_address"], msg.as_string())

        logger.debug("Email notification sent to %s.", em["to_address"])
    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class NotificationManager:
    """Thread-safe notification dispatcher for all channels."""

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="notif")

    def send_all(self, title: str, message: str) -> None:
        """Dispatch notifications to all enabled channels concurrently.

        Non-blocking: submits to thread pool and returns immediately.
        Each channel failure is logged but does not affect others.
        """
        cfg = self.cfg

        def _dispatch():
            futures = {
                self._executor.submit(_send_telegram, cfg, title, message): "Telegram",
                self._executor.submit(_send_toast, cfg, title, message): "Desktop",
                self._executor.submit(_send_email, cfg, title, message): "Email",
            }
            for future in as_completed(futures):
                channel = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.error("[%s] Unhandled notification error: %s", channel, exc)

        # Fire-and-forget in a background thread so `send_all` never blocks
        threading.Thread(target=_dispatch, daemon=True, name="notif-dispatch").start()

    def reload_config(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
