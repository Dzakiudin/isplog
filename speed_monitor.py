#!/usr/bin/env python3
"""
Backward-compatibility shim.
This file is kept so existing shortcuts/scripts pointing to speed_monitor.py
continue to work. All logic has moved to isplog.py + isplog/ package.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("[speed_monitor.py] Redirecting to isplog.py --run ...")
    print("Tip: Use 'python isplog.py --help' for all options.\n")
    from isplog.config import load_config
    from isplog.monitor import SpeedMonitor
    from isplog.notifier import NotificationManager
    from isplog.api import start_api_server
    from isplog import storage

    storage.setup_logger()
    cfg = load_config()
    storage.init_database()

    notifier = NotificationManager(cfg)
    monitor = SpeedMonitor()
    monitor.set_notifier(notifier)

    if cfg.get("api", {}).get("enabled", True):
        api_cfg = cfg["api"]
        start_api_server(
            host=api_cfg.get("host", "127.0.0.1"),
            port=int(api_cfg.get("port", 8080)),
        )

    monitor.run()
