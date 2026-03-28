"""Configuration loader with defaults and backward-compatibility."""
import json
import os
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULTS: Dict[str, Any] = {
    "promised_download_mbps": 20,
    "promised_upload_mbps": 20,
    "test_interval_minutes": 30,
    "threshold_percentage": 80,
    "retry_attempts": 3,
    "retry_wait_seconds": 30,
    "uptime_check": {
        "ping_host": "8.8.8.8",
        "custom_host": "",
        "http_url": "https://www.google.com",
        "timeout_seconds": 5,
    },
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    },
    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "to_address": "",
    },
    "desktop_notification": {
        "enabled": True,
    },
    "api": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 8080,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively, preserving unset keys."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> Dict[str, Any]:
    """Load config.json, fill missing keys with defaults, save back."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        config = _deep_merge(DEFAULTS, raw)
    else:
        config = dict(DEFAULTS)

    # Override secrets from environment variables (priority)
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        config["telegram"]["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("TELEGRAM_CHAT_ID"):
        config["telegram"]["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
    if os.getenv("EMAIL_USERNAME"):
        config["email"]["username"] = os.getenv("EMAIL_USERNAME")
    if os.getenv("EMAIL_PASSWORD"):
        config["email"]["password"] = os.getenv("EMAIL_PASSWORD")
    if os.getenv("EMAIL_TO_ADDRESS"):
        config["email"]["to_address"] = os.getenv("EMAIL_TO_ADDRESS")

    save_config(config)
    return config


def save_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
