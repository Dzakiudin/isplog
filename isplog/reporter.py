"""SLA compliance calculator and PDF report generator.

PDF is generated using reportlab only (no external binaries / matplotlib).
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from isplog import storage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


# ---------------------------------------------------------------------------
# SLA Calculation
# ---------------------------------------------------------------------------

def calculate_sla(month: str, promised_down: float, promised_up: float,
                  threshold_pct: float) -> Dict[str, Any]:
    """
    month: 'YYYY-MM'
    Returns dict with SLA metrics for the given month.
    """
    rows = storage.get_monthly_data(month)
    total = len(rows)
    if total == 0:
        return {
            "month": month,
            "total_tests": 0,
            "compliant": 0,
            "sla_pct": 0.0,
            "avg_download": 0.0,
            "avg_upload": 0.0,
            "avg_ping": 0.0,
            "min_download": 0.0,
            "min_upload": 0.0,
            "rows": [],
        }

    threshold = threshold_pct / 100
    compliant = sum(
        1 for r in rows
        if r["download_mbps"] >= promised_down * threshold
        and r["upload_mbps"] >= promised_up * threshold
    )

    downloads = [r["download_mbps"] for r in rows]
    uploads = [r["upload_mbps"] for r in rows]
    pings = [r["ping_ms"] for r in rows]

    return {
        "month": month,
        "total_tests": total,
        "compliant": compliant,
        "sla_pct": round(compliant / total * 100, 2),
        "avg_download": round(sum(downloads) / total, 2),
        "avg_upload": round(sum(uploads) / total, 2),
        "avg_ping": round(sum(pings) / total, 2),
        "min_download": round(min(downloads), 2),
        "min_upload": round(min(uploads), 2),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# PDF Generator
# ---------------------------------------------------------------------------

def generate_pdf(month: str, promised_down: float, promised_up: float,
                 threshold_pct: float, output_path: Optional[str] = None) -> str:
    """Generate PDF SLA report. Returns path to created file."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    if output_path is None:
        output_path = os.path.join(REPORTS_DIR, f"sla_report_{month}.pdf")

    sla = calculate_sla(month, promised_down, promised_up, threshold_pct)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    elements = []

    # Title
    elements.append(Paragraph("ISPLog — SLA Compliance Report", styles["Title"]))
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(Paragraph(f"Period: {month}", styles["Heading2"]))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 0.6 * cm))

    # Summary table
    summary_data = [
        ["Metric", "Value"],
        ["Total Tests", str(sla["total_tests"])],
        ["Compliant Tests", f"{sla['compliant']} / {sla['total_tests']}"],
        ["SLA Compliance", f"{sla['sla_pct']}%"],
        ["Promised Download", f"{promised_down} Mbps"],
        ["Promised Upload", f"{promised_up} Mbps"],
        ["Threshold", f"{threshold_pct}%"],
        ["Avg Download", f"{sla['avg_download']} Mbps"],
        ["Avg Upload", f"{sla['avg_upload']} Mbps"],
        ["Avg Ping", f"{sla['avg_ping']} ms"],
        ["Min Download", f"{sla['min_download']} Mbps"],
        ["Min Upload", f"{sla['min_upload']} Mbps"],
    ]

    summary_table = Table(summary_data, colWidths=[8 * cm, 8 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4FF")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.8 * cm))

    # Data table (last 50 rows max for readability)
    if sla["rows"]:
        elements.append(Paragraph("Test Results (latest 50)", styles["Heading3"]))
        elements.append(Spacer(1, 0.3 * cm))

        header = ["#", "Timestamp", "Down (Mbps)", "Up (Mbps)", "Ping (ms)", "Status"]
        data_rows = [header]
        display_rows = sla["rows"][-50:]
        for i, r in enumerate(display_rows, 1):
            status = "BELOW" if r["below_threshold"] else "OK"
            data_rows.append([
                str(i),
                r["timestamp"][:19].replace("T", " "),
                str(r["download_mbps"]),
                str(r["upload_mbps"]),
                str(r["ping_ms"]),
                status,
            ])

        data_table = Table(
            data_rows,
            colWidths=[1 * cm, 4.5 * cm, 3 * cm, 3 * cm, 2.5 * cm, 2 * cm],
        )
        data_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        # Highlight BELOW rows in red
        for i, r in enumerate(display_rows, 1):
            if r["below_threshold"]:
                data_table.setStyle(TableStyle([
                    ("TEXTCOLOR", (5, i), (5, i), colors.red),
                    ("FONTNAME", (5, i), (5, i), "Helvetica-Bold"),
                ]))

        elements.append(data_table)

    # Footer
    elements.append(Spacer(1, 1.0 * cm))
    footer_style = styles["Normal"]
    elements.append(Paragraph(
        "<para align='center'>"
        "ISPLog v2 &mdash; Internet Speed &amp; Uptime Monitor<br/>"
        "Developer: <b>Ahmad Dzakiudin</b><br/>"
        "Facebook: https://www.facebook.com/jakijekijuki &nbsp;|&nbsp; "
        "Instagram: https://www.instagram.com/jakijekiiii"
        "</para>",
        footer_style,
    ))

    doc.build(elements)
    return output_path
