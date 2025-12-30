import os
import logging
from dotenv import load_dotenv

load_dotenv()

# --- KONFIGURASI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN belum diisi di .env")

BASE_URL = os.getenv("SIMA_BASE_API", "https://sima.usm.ac.id/index.php/api")
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PROXY_URL = os.getenv("PROXY_URL")
SESSION_EXPIRE = 7200 

PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

# --- HEADERS ---
HEADERS_ANDROID = {
    "User-Agent": "okhttp/4.9.0",
    "Content-Type": "application/json; charset=UTF-8"
}

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Origin": "https://sima.usm.ac.id"
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)