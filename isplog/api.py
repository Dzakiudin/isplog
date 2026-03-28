"""REST API server (FastAPI) running on localhost only.

Endpoints:
  GET /stats                  - overall statistics
  GET /history?days=7         - speed test history
  GET /sla?month=YYYY-MM      - SLA report for a month
  GET /export?month=YYYY-MM   - download PDF report
  GET /downtime?days=30       - downtime events
  GET /health                 - health check

The server is started in a daemon thread so it never blocks the main loop.
"""
import os
import threading
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from isplog import storage
from isplog.config import load_config
from isplog.reporter import calculate_sla, generate_pdf, REPORTS_DIR

app = FastAPI(
    title="ISPLog API",
    description="Local REST API for ISPLog network monitor",
    version="2.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/stats")
def get_stats():
    return storage.get_stats()


@app.get("/history")
def get_history(days: int = 7):
    if days < 1 or days > 365:
        raise HTTPException(400, "days must be between 1 and 365")
    return storage.get_history(days)


@app.get("/sla")
def get_sla(month: Optional[str] = None):
    if month is None:
        month = datetime.now().strftime("%Y-%m")
    cfg = load_config()
    data = calculate_sla(
        month,
        promised_down=cfg["promised_download_mbps"],
        promised_up=cfg["promised_upload_mbps"],
        threshold_pct=cfg["threshold_percentage"],
    )
    # Omit raw rows for lightweight JSON response
    data.pop("rows", None)
    return data


@app.get("/downtime")
def get_downtime(days: int = 30):
    if days < 1 or days > 365:
        raise HTTPException(400, "days must be between 1 and 365")
    return storage.get_downtime_events(days)


@app.get("/export")
def export_pdf(month: Optional[str] = None):
    if month is None:
        month = datetime.now().strftime("%Y-%m")
    cfg = load_config()
    try:
        path = generate_pdf(
            month,
            promised_down=cfg["promised_download_mbps"],
            promised_up=cfg["promised_upload_mbps"],
            threshold_pct=cfg["threshold_percentage"],
        )
    except Exception as exc:
        raise HTTPException(500, f"PDF generation failed: {exc}")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=os.path.basename(path),
    )


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

_server_thread: Optional[threading.Thread] = None


def start_api_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start FastAPI in a daemon thread. Call once from main process."""
    global _server_thread

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",  # keep uvicorn quiet; use isplog logger
        access_log=False,
    )
    server = uvicorn.Server(config)

    _server_thread = threading.Thread(
        target=server.run,
        daemon=True,
        name="api-server",
    )
    _server_thread.start()
