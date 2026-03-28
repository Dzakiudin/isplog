"""Windows Service wrapper for ISPLog using pywin32.

Usage (must run as Administrator):
  python isplog.py --service install
  python isplog.py --service start
  python isplog.py --service stop
  python isplog.py --service uninstall
"""
import logging
import os
import sys

logger = logging.getLogger("isplog")

# Guard: pywin32 is Windows-only
try:
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def _require_win32():
    if not WIN32_AVAILABLE:
        print("ERROR: pywin32 is not installed. Run: pip install pywin32")
        sys.exit(1)
    if sys.platform != "win32":
        print("ERROR: Windows Service is only supported on Windows.")
        sys.exit(1)


def run_service_command(action: str) -> None:
    """Dispatch service management commands."""
    _require_win32()
    action = action.lower()
    if action == "install":
        _install()
    elif action == "uninstall":
        _uninstall()
    elif action == "start":
        _start()
    elif action == "stop":
        _stop()
    elif action == "status":
        _status()
    else:
        print(f"Unknown service action: {action}")
        print("Valid actions: install | uninstall | start | stop | status")
        sys.exit(1)


def _install():
    win32serviceutil.InstallService(
        ISPLogService,
        ISPLogService._svc_name_,
        ISPLogService._svc_display_name_,
        startType=win32service.SERVICE_AUTO_START,
        description=ISPLogService._svc_description_,
    )
    print(f"Service '{ISPLogService._svc_display_name_}' installed.")
    print("Run: python isplog.py --service start")


def _uninstall():
    try:
        win32serviceutil.StopService(ISPLogService._svc_name_)
    except Exception:
        pass
    win32serviceutil.RemoveService(ISPLogService._svc_name_)
    print(f"Service '{ISPLogService._svc_display_name_}' uninstalled.")


def _start():
    win32serviceutil.StartService(ISPLogService._svc_name_)
    print(f"Service '{ISPLogService._svc_display_name_}' started.")


def _stop():
    win32serviceutil.StopService(ISPLogService._svc_name_)
    print(f"Service '{ISPLogService._svc_display_name_}' stopped.")


def _status():
    status_map = {
        win32service.SERVICE_STOPPED: "STOPPED",
        win32service.SERVICE_START_PENDING: "START PENDING",
        win32service.SERVICE_STOP_PENDING: "STOP PENDING",
        win32service.SERVICE_RUNNING: "RUNNING",
        win32service.SERVICE_CONTINUE_PENDING: "CONTINUE PENDING",
        win32service.SERVICE_PAUSE_PENDING: "PAUSE PENDING",
        win32service.SERVICE_PAUSED: "PAUSED",
    }
    try:
        status_code = win32serviceutil.QueryServiceStatus(ISPLogService._svc_name_)[1]
        print(f"Service status: {status_map.get(status_code, 'UNKNOWN')}")
    except Exception as exc:
        print(f"Could not query service status: {exc}")


if WIN32_AVAILABLE:
    class ISPLogService(win32serviceutil.ServiceFramework):
        _svc_name_ = "ISPLogMonitor"
        _svc_display_name_ = "ISPLog Network Monitor"
        _svc_description_ = (
            "Monitors internet speed and uptime. Sends alerts via Telegram, "
            "Desktop, and Email. Exposes local REST API on port 8080."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._monitor = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)
            logger.info("ISPLog Windows Service stopping...")

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            self._run()

        def _run(self):
            # Ensure working directory is project root so relative paths work
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            os.chdir(project_dir)

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
                start_api_server(host=api_cfg.get("host", "127.0.0.1"),
                                 port=int(api_cfg.get("port", 8080)))

            import threading
            import time
            interval = cfg["test_interval_minutes"]

            def _loop():
                while True:
                    # Check if service stop was requested
                    if win32event.WaitForSingleObject(self._stop_event, 0) == \
                            win32event.WAIT_OBJECT_0:
                        break
                    monitor._run_cycle()
                    time.sleep(interval * 60)

            t = threading.Thread(target=_loop, daemon=True)
            t.start()

            # Block until stop event
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
            logger.info("ISPLog Windows Service stopped.")
