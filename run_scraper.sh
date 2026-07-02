#!/bin/bash
# Wrapper script for cron execution.
# Sets up the correct environment before running the scraper.

# Set HOME explicitly (cron often has wrong or missing HOME)
export HOME=/home/l1nkit360

# Required by Chrome for temp socket/lock files; cron often skips this
export XDG_RUNTIME_DIR=/tmp/runtime-l1nkit360
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Prevent Chrome from trying to connect to D-Bus session bus.
# Cron tidak punya D-Bus session — tanpa ini Chrome bisa hang 60+ detik
# mencoba connect ke D-Bus sebelum akhirnya crash.
export DBUS_SESSION_BUS_ADDRESS=/dev/null

# Pastikan file descriptor limit cukup.
# Cron default bisa se-rendah 1024; Chrome butuh ribuan fd untuk proses-prosesnya.
ulimit -n 65536 2>/dev/null || true

# PATH: include common binary locations for Chrome and system tools
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Project root
PROJECT_DIR=/home/l1nkit360/vending-machine

# Masuk ke venv supaya semua environment variable ter-set dengan benar
# (PYTHONPATH, PATH, dll untuk dependencies yang ada di venv)
source "$PROJECT_DIR/venv/bin/activate"

# Sekarang gunakan python dari PATH (sudah di-set oleh activate)
PYTHON=python3

# Jalankan dengan xvfb-run jika tersedia (virtual display untuk UC compatibility).
# Install: sudo apt-get install -y xvfb
if command -v xvfb-run &>/dev/null; then
    exec xvfb-run -a --server-args="-screen 0 1920x1080x24" "$PYTHON" "$PROJECT_DIR/main.py" "$@"
else
    exec "$PYTHON" "$PROJECT_DIR/main.py" "$@"
fi
