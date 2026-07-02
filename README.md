# Web Scraper - SMS Gateway Sales Statistic

Automated Python web scraper untuk mengekstrak data Sales Statistic dari SMS gateway platform.

## Project Structure

```
web-scraper/
├── config/config.py           # Load settings dari .env
├── scrapers/
│   ├── auth_handler.py        # Login handler (update selectors!)
│   └── parser.py              # Data extraction (TODO: implement)
├── models/sales_data.py       # Pydantic data schemas
├── storage/json_storage.py    # JSON storage + auto-backup
├── scheduler/jobs.py          # Scheduled job definitions
├── utils/
│   ├── session_manager.py     # Selenium WebDriver lifecycle
│   ├── logging_setup.py       # Logging (console + file rotation)
│   └── exceptions.py          # Custom exception types
├── main.py                    # Entry point (CLI)
├── .env                       # Credentials — JANGAN di-commit!
├── .env.example               # Template (tidak ada real value)
└── requirements.txt
```

## Setup (Sudah Dilakukan)

```bash
source venv/bin/activate
```

Setup ulang dari awal:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env dan isi credentials Anda
```

## Konfigurasi (.env)

Edit file `.env` (file ini git-ignored, aman untuk diisi credentials):

```ini
WEBSITE_MSISDN=isi_nomor_anda
WEBSITE_PASSWORD=isi_password_anda
BASE_URL=https://target-website.com
LOG_LEVEL=INFO
BROWSER_TYPE=chrome
HEADLESS_MODE=true
SCHEDULE_TIME=02:00
```

## Cara Menggunakan (Step-by-Step)

### Langkah 1 — Identifikasi HTML selectors website

Sebelum scraper bisa berjalan, Anda perlu mengetahui struktur HTML website:

1. Buka website target di browser
2. Login secara manual dengan credentials Anda
3. Tekan **F12** untuk membuka DevTools
4. Klik icon **"Select Element"** (ikon panah/cursor di pojok kiri atas DevTools)
5. Klik pada field username/MSISDN di halaman → lihat HTML yang ter-highlight di panel kanan
6. Catat nilai atribut `name`, `id`, atau `class` dari element tersebut. Contoh:
   ```html
   <input type="text" name="msisdn" id="username-field" />
   ```
   → selectornya adalah `input[name='msisdn']` atau `#username-field`
7. Ulangi untuk field password dan tombol login
8. Navigasi ke menu **Sales Statistic** → inspect tabel data → catat selector tabel dan kolom

### Langkah 2 — Update selectors di kode

Buka `scrapers/auth_handler.py`, bagian `login()`. Selectors sudah di-update dengan:
```python
msisdn_field_selector = "#username"      # HTML: <input id="username" name="username" ...>
password_field_selector = "#password"    # HTML: <input id="password" name="password" ...>
login_button_selector = "#sub"           # HTML: <input type="button" name="sub" id="sub" ...>
```

Jika website Anda memiliki struktur berbeda, edit selectors sesuai hasil inspeksi F12 pada Langkah 1.

### Langkah 3 — Setup ChromeDriver

Selenium membutuhkan ChromeDriver. Cara paling mudah:

```bash
pip install webdriver-manager
```

Kemudian update `utils/session_manager.py` bagian inisialisasi Chrome:
```python
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

self.driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
```

### Langkah 4 — Test sekali (mode debugging)

```bash
source venv/bin/activate
python main.py --run-once
```

Output akan ada di:
- Terminal (live logs)
- `logs/scraper.log` (file log lengkap)
- `data/sales_data_YYYY-MM-DD_HH-MM-SS.json` (hasil data)

### Langkah 5 — Implement parser

Setelah login berhasil, Anda perlu mengimplementasikan `scrapers/parser.py` untuk mengekstrak data dari tabel. Gunakan selector yang ditemukan di Langkah 1.

### Langkah 6 — Production (jadwal harian)

```bash
source venv/bin/activate
python main.py --schedule
```

Berjalan otomatis sesuai `SCHEDULE_TIME` di `.env`. Tekan `Ctrl+C` untuk berhenti.

---

## Output Data

Data tersimpan di `data/` sebagai JSON:
```json
{
  "metadata": { "saved_at": "2026-05-04T08:30:00" },
  "data": {
    "status": "success",
    "total_records_scraped": 1500,
    "data_by_submenu": {
      "Sales Overview": { "records": [], "record_count": 500 }
    },
    "execution_time_seconds": 45.5
  }
}
```

Monitor log: `tail -f logs/scraper.log`

---

## Troubleshooting

| Error | Solusi |
|-------|--------|
| `WEBSITE_MSISDN is not set` | Buat `.env` dari `.env.example` dan isi nilai |
| `chromedriver not found` | Install via `pip install webdriver-manager`, update `session_manager.py` |
| `Element not found` saat login | Selector di `auth_handler.py` salah, inspect ulang website |
| Data kosong setelah login | Selector tabel di `parser.py` salah, inspect tabel website |
| Timeout | Naikkan `REQUEST_TIMEOUT` di `.env` |

---

## Status

| Komponen | Status | Catatan |
|----------|--------|---------|
| Project structure, config, logging | ✅ Done | |
| Session manager, exceptions, models | ✅ Done | |
| JSON storage, scheduler | ✅ Done | |
| Auth handler selectors | ✅ Done | Updated: #username, #password, #sub |
| Data parser (scrapers/parser.py) | ✅ Created | Template ready, needs table selector customization |
| Scheduler job workflow | ✅ Implemented | Full scraping pipeline with error handling |
| Unit tests | ⏳ Pending | |

