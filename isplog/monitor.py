"""Core monitoring loop: uptime check, speedtest with retry, scheduling."""
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests
import speedtest
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from isplog import storage
from isplog.config import load_config

logger = storage.setup_logger()


# ---------------------------------------------------------------------------
# Uptime / Connectivity Checks
# ---------------------------------------------------------------------------

def _ping(host: str, timeout: int = 5) -> bool:
    """Return True if ping succeeds."""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout * 1000), host],
            capture_output=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except Exception:
        return False


def _http_check(url: str, timeout: int = 5) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def check_connectivity(cfg: Dict[str, Any]) -> bool:
    """
    Returns True if internet is reachable.
    Uses all three methods; any one passing = online.
    """
    uc = cfg.get("uptime_check", {})
    timeout = int(uc.get("timeout_seconds", 5))

    # 1) Ping to 8.8.8.8
    if _ping(uc.get("ping_host", "8.8.8.8"), timeout):
        return True

    # 2) Ping to custom host (if set)
    custom = uc.get("custom_host", "")
    if custom and _ping(custom, timeout):
        return True

    # 3) HTTP check
    http_url = uc.get("http_url", "https://www.google.com")
    if http_url and _http_check(http_url, timeout):
        return True

    return False


# ---------------------------------------------------------------------------
# Speed Test with Retry
# ---------------------------------------------------------------------------

def _build_retry(cfg: Dict[str, Any]):
    attempts = int(cfg.get("retry_attempts", 3))
    wait_s = int(cfg.get("retry_wait_seconds", 30))
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_fixed(wait_s),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )


def run_speedtest(cfg: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Run speedtest with configured retry. Returns dict or None on failure."""
    decorator = _build_retry(cfg)

    @decorator
    def _test():
        st = speedtest.Speedtest()
        st.get_best_server()
        down = st.download() / 1_000_000
        up = st.upload() / 1_000_000
        ping = st.results.ping
        return {
            "download": round(down, 2),
            "upload": round(up, 2),
            "ping": round(ping, 2),
        }

    try:
        result = _test()
        logger.info(
            "Speed test OK — Download: %.2f Mbps | Upload: %.2f Mbps | Ping: %.2f ms",
            result["download"], result["upload"], result["ping"],
        )
        return result
    except Exception as exc:
        logger.error("Speed test failed after retries: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main Monitor Loop
# ---------------------------------------------------------------------------

class SpeedMonitor:
    def __init__(self):
        self.cfg = load_config()
        storage.init_database()
        self._downtime_id: Optional[int] = None
        self._downtime_start: Optional[datetime] = None
        self._notifier = None  # injected after import to avoid circular deps

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    def _notify(self, message: str, title: str = "ISPLog Alert") -> None:
        if self._notifier:
            self._notifier.send_all(title=title, message=message)

    def _record_online(self) -> None:
        """Called when internet comes back online."""
        if self._downtime_id is not None:
            end = datetime.now()
            duration = (end - self._downtime_start).total_seconds()
            storage.update_downtime(
                self._downtime_id,
                end_time=end.isoformat(),
                duration_s=round(duration, 1),
            )
            msg = (
                f"Internet RESTORED after {round(duration/60, 1)} min downtime."
            )
            logger.warning(msg)
            self._notify(msg, title="ISPLog: Internet Restored")
            self._downtime_id = None
            self._downtime_start = None

    def _record_offline(self) -> None:
        """Called when internet is detected as down."""
        if self._downtime_id is None:
            now = datetime.now()
            self._downtime_start = now
            self._downtime_id = storage.insert_downtime(
                start_time=now.isoformat(),
                reason="No response to ping/HTTP checks",
            )
            msg = "Internet is DOWN! No response to connectivity checks."
            logger.warning(msg)
            self._notify(msg, title="ISPLog: Internet DOWN")

    def _run_cycle(self) -> None:
        self.cfg = load_config()  # reload config on each cycle

        logger.info("Starting connectivity check...")
        online = check_connectivity(self.cfg)

        if not online:
            self._record_offline()
            return

        self._record_online()
        logger.info("Connectivity OK. Running speed test...")
        result = run_speedtest(self.cfg)

        if result is None:
            return

        # Threshold check
        threshold = self.cfg["threshold_percentage"] / 100
        promised_down = self.cfg["promised_download_mbps"]
        promised_up = self.cfg["promised_upload_mbps"]
        below = int(
            result["download"] < promised_down * threshold
            or result["upload"] < promised_up * threshold
        )

        storage.insert_speed_test(
            timestamp=datetime.now().isoformat(),
            download=result["download"],
            upload=result["upload"],
            ping=result["ping"],
            below=below,
        )

        if below:
            msg = (
                f"Speed BELOW {self.cfg['threshold_percentage']}% threshold!\n"
                f"Download: {result['download']} Mbps (promised: {promised_down} Mbps)\n"
                f"Upload:   {result['upload']} Mbps (promised: {promised_up} Mbps)\n"
                f"Ping:     {result['ping']} ms"
            )
            logger.warning(msg)
            self._notify(msg, title="ISPLog: Speed Alert")

    def run(self) -> None:
        """Blocking monitor loop (for direct CLI / service use)."""
        interval = self.cfg["test_interval_minutes"]
        logger.info("=" * 55)
        logger.info("ISPLog v2 — Network Speed & Uptime Monitor")
        logger.info("Developer : Ahmad Dzakiudin")
        logger.info("Facebook  : https://www.facebook.com/jakijekijuki")
        logger.info("Instagram : https://www.instagram.com/jakijekiiii")
        logger.info("=" * 55)
        logger.info("Promised: %s Mbps down / %s Mbps up",
                    self.cfg["promised_download_mbps"], self.cfg["promised_upload_mbps"])
        logger.info("Threshold: %s%% | Interval: %s min",
                    self.cfg["threshold_percentage"], interval)
        logger.info("=" * 55)

        try:
            while True:
                self._run_cycle()
                logger.info("Next test in %s minutes...", interval)
                time.sleep(interval * 60)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user.")
            self.print_stats()

    def print_stats(self) -> None:
        stats = storage.get_stats()
        print("\n" + "=" * 55)
        print("STATISTICS")
        print("=" * 55)
        print(f"Total tests       : {stats['total_tests']}")
        print(f"Below threshold   : {stats['below_threshold']} ({stats['below_pct']}%)")
        print(f"Avg Download      : {stats['avg_download']} Mbps")
        print(f"Avg Upload        : {stats['avg_upload']} Mbps")
        print(f"Avg Ping          : {stats['avg_ping']} ms")
        print(f"Downtime events   : {stats['downtime_events']}")
        print("=" * 55)
        print("ISPLog v2 | Developer: Ahmad Dzakiudin")
        print("FB: https://www.facebook.com/jakijekijuki")
        print("IG: https://www.instagram.com/jakijekiiii")
        print("=" * 55)
