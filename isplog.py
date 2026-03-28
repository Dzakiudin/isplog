#!/usr/bin/env python3
"""
ISPLog v2 — Internet Speed & Uptime Monitor
Developer : Ahmad Dzakiudin
Facebook  : https://www.facebook.com/jakijekijuki
Instagram : https://www.instagram.com/jakijekiiii

Usage:
  python isplog.py --run                      Start monitoring loop
  python isplog.py --stats                    Show statistics
  python isplog.py --report [--month YYYY-MM] Generate PDF SLA report
  python isplog.py --export [--month YYYY-MM] Alias for --report
  python isplog.py --history [--days N]       Show recent test history
  python isplog.py --service install          Install Windows Service
  python isplog.py --service uninstall        Uninstall Windows Service
  python isplog.py --service start            Start Windows Service
  python isplog.py --service stop             Stop Windows Service
  python isplog.py --service status           Query Windows Service status
"""
import argparse
import os
import sys
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ensure project root is on path when run as script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _cmd_run():
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
        print(f"REST API started at http://{api_cfg.get('host', '127.0.0.1')}:{api_cfg.get('port', 8080)}")
        print("  /stats | /history | /sla | /downtime | /export | /health")

    monitor.run()


def _cmd_stats():
    from isplog import storage
    from isplog.monitor import SpeedMonitor

    storage.init_database()
    SpeedMonitor().print_stats()


def _cmd_report(month: str):
    from isplog.config import load_config
    from isplog.reporter import generate_pdf

    cfg = load_config()
    print(f"Generating SLA report for {month} ...")
    path = generate_pdf(
        month,
        promised_down=cfg["promised_download_mbps"],
        promised_up=cfg["promised_upload_mbps"],
        threshold_pct=cfg["threshold_percentage"],
    )
    print(f"Report saved: {path}")


def _cmd_history(days: int):
    from isplog import storage

    storage.init_database()
    rows = storage.get_history(days)
    if not rows:
        print(f"No records in the last {days} days.")
        return

    print(f"\n{'#':<5} {'Timestamp':<20} {'Down':>10} {'Up':>10} {'Ping':>8} {'Status'}")
    print("-" * 65)
    for i, r in enumerate(rows, 1):
        status = "BELOW" if r["below_threshold"] else "OK"
        ts = r["timestamp"][:19].replace("T", " ")
        print(f"{i:<5} {ts:<20} {r['download_mbps']:>9.2f}M {r['upload_mbps']:>9.2f}M "
              f"{r['ping_ms']:>7.1f}ms  {status}")
    print(f"\nTotal: {len(rows)} records")


def _cmd_service(action: str):
    from isplog.service import run_service_command
    run_service_command(action)


def _print_banner():
    print("=" * 55)
    print("  ISPLog v2 — Internet Speed & Uptime Monitor")
    print("  Developer : Ahmad Dzakiudin")
    print("  Facebook  : https://www.facebook.com/jakijekijuki")
    print("  Instagram : https://www.instagram.com/jakijekiiii")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(
        prog="isplog",
        description="ISPLog v2 — Internet Speed & Uptime Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true",
                      help="Start continuous monitoring loop")
    mode.add_argument("--stats", action="store_true",
                      help="Show current statistics")
    mode.add_argument("--report", action="store_true",
                      help="Generate PDF SLA report")
    mode.add_argument("--export", action="store_true",
                      help="Alias for --report")
    mode.add_argument("--history", action="store_true",
                      help="Show recent speed test history")
    mode.add_argument("--service", metavar="ACTION",
                      help="Windows Service management (install|uninstall|start|stop|status)")

    parser.add_argument("--month", default=None,
                        help="Month for report (YYYY-MM), default: current month")
    parser.add_argument("--days", type=int, default=7,
                        help="Number of days for --history (default: 7)")

    args = parser.parse_args()
    _print_banner()

    if args.run:
        _cmd_run()
    elif args.stats:
        _cmd_stats()
    elif args.report or args.export:
        month = args.month or datetime.now().strftime("%Y-%m")
        _cmd_report(month)
    elif args.history:
        _cmd_history(args.days)
    elif args.service:
        _cmd_service(args.service)


if __name__ == "__main__":
    main()
