# ISPLog v2 — Network Speed & Uptime Monitor

CLI daemon untuk monitoring kecepatan internet dan uptime, dengan notifikasi real-time, laporan PDF, dan REST API lokal. Berjalan di background sebagai Windows Service.

## Fitur

- **Monitor otomatis** — test kecepatan setiap N menit, rekam ke SQLite
- **Uptime Monitor** — deteksi internet mati via ping (8.8.8.8 + custom host) & HTTP check
- **Retry otomatis** — speedtest gagal → retry hingga 3x sebelum di-skip
- **Notifikasi multi-channel** — Telegram Bot, Windows Desktop Toast, Email SMTP (paralel)
- **Threshold alert** — warning saat kecepatan di bawah % yang dikonfigurasi
- **SLA Report** — laporan kepatuhan ISP per bulan dalam format PDF
- **REST API lokal** — akses data via `http://127.0.0.1:8080`
- **Rotating log** — file log di `logs/isplog.log` (max 5 MB × 3 backup)
- **Windows Service** — install sebagai service, jalan otomatis saat startup

## Instalasi

```bash
pip install -r requirements.txt
```

> **Catatan**: `pywin32` membutuhkan Windows. Di Linux/Mac, fitur Windows Service tidak tersedia.

## Penggunaan CLI

```bash
# Mulai monitoring (foreground)
python isplog.py --run

# Lihat statistik
python isplog.py --stats

# Lihat riwayat 14 hari terakhir
python isplog.py --history --days 14

# Generate PDF SLA report bulan ini
python isplog.py --report

# Generate PDF SLA report bulan tertentu
python isplog.py --report --month 2025-03

# Windows Service (jalankan sebagai Administrator)
python isplog.py --service install
python isplog.py --service start
python isplog.py --service stop
python isplog.py --service uninstall
python isplog.py --service status
```

## Konfigurasi (`config.json`)

```json
{
  "promised_download_mbps": 20,
  "promised_upload_mbps": 20,
  "test_interval_minutes": 30,
  "threshold_percentage": 80,
  "retry_attempts": 3,
  "retry_wait_seconds": 30,
  "uptime_check": {
    "ping_host": "8.8.8.8",
    "custom_host": "router.local",
    "http_url": "https://www.google.com",
    "timeout_seconds": 5
  },
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "you@gmail.com",
    "password": "app_password",
    "to_address": "alert@example.com"
  },
  "desktop_notification": {
    "enabled": true
  },
  "api": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080
  }
}
```

## REST API Endpoints

Saat `--run` aktif, API tersedia di `http://127.0.0.1:8080`:

| Endpoint | Deskripsi |
|---|---|
| `GET /health` | Health check |
| `GET /stats` | Statistik keseluruhan |
| `GET /history?days=7` | Riwayat test N hari terakhir |
| `GET /sla?month=2025-03` | Kalkulasi SLA per bulan |
| `GET /downtime?days=30` | Daftar event internet mati |
| `GET /export?month=2025-03` | Download PDF report |

Dokumentasi interaktif (Swagger UI): `http://127.0.0.1:8080/docs`

## Struktur Project

```
isplog/
├── isplog.py           # CLI entry point utama
├── speed_monitor.py    # Backward-compat shim
├── config.json         # Konfigurasi
├── speed_logs.db       # Database SQLite
├── requirements.txt
├── isplog/
│   ├── config.py       # Config loader
│   ├── storage.py      # Database + logging
│   ├── monitor.py      # Core monitoring loop
│   ├── notifier.py     # Telegram + Toast + Email
│   ├── reporter.py     # SLA calc + PDF generator
│   ├── api.py          # FastAPI REST API
│   └── service.py      # Windows Service
├── logs/
│   └── isplog.log      # Rotating log file
└── reports/
    └── sla_report_YYYY-MM.pdf
```

## Setup Notifikasi Telegram

1. Buat bot via [@BotFather](https://t.me/BotFather), dapatkan `bot_token`
2. Kirim pesan ke bot, lalu cek `chat_id` via `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Isi `telegram.bot_token` dan `telegram.chat_id` di `config.json`, set `enabled: true`

## Setup Email (Gmail)

1. Aktifkan 2FA di akun Gmail
2. Buat **App Password** di Google Account → Security → App passwords
3. Isi `email.username`, `email.password` (app password), `email.to_address` di `config.json`

## Data

- Database: `speed_logs.db` (SQLite) — tabel `speed_tests` & `downtime_events`
- Logs: `logs/isplog.log` (rotating, max 5 MB × 3 file)
- Reports: `reports/sla_report_YYYY-MM.pdf`

## License

MIT
