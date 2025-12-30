# =========================
# LOAD ENV (untuk lokal)
# =========================
from dotenv import load_dotenv
load_dotenv()

import os
import requests
import json

# =========================
# ENV
# =========================
BASE_API = os.getenv("SIMA_BASE_API")
PROXY_URL = os.getenv("PROXY_URL")  # opsional

if not BASE_API:
    raise RuntimeError("ENV SIMA_BASE_API belum diset")

# =========================
# PROXY (opsional)
# =========================
PROXIES = None
if PROXY_URL:
    PROXIES = {
        "http": PROXY_URL,
        "https": PROXY_URL,
    }

# =========================
# HEADER MENIRU OKHTTP
# =========================
HEADERS = {
    "User-Agent": "okhttp/4.9.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Encoding": "identity",
    "Connection": "close"
}

# =========================
# INPUT LOGIN (MANUAL)
# =========================
NIM = input("Masukkan NIM: ").strip()
PASSWORD = input("Masukkan PASSWORD: ").strip()

session = requests.Session()

# =========================
# LOGIN
# =========================
print("\n[LOGIN] Mengirim request login...")
login_resp = session.patch(
    f"{BASE_API}/api/login/sia",
    json={"username": NIM, "password": PASSWORD},
    headers=HEADERS,
    timeout=30,
    allow_redirects=False,
    proxies=PROXIES
)

print("[LOGIN] Status:", login_resp.status_code)
print("[LOGIN] Raw response:")
print(login_resp.text)

try:
    login_data = login_resp.json()
except Exception:
    print("\n❌ Response login bukan JSON, berhenti.")
    exit()

result = login_data.get("result", {})
if result.get("st") == "0" or not result.get("token"):
    print("\n❌ Login gagal (NIM / password salah).")
    exit()

token = result["token"]
print("\n✅ Login berhasil, token didapat.")

# =========================
# AMBIL NILAI
# =========================
print("\n[NILAI] Mengambil data nilai...")

headers_nilai = HEADERS.copy()
headers_nilai["Authorization"] = token  # TANPA Bearer

nilai_resp = session.put(
    f"{BASE_API}/api/his_pend/nilai",
    headers=headers_nilai,
    timeout=30,
    allow_redirects=False,
    proxies=PROXIES
)

print("[NILAI] Status:", nilai_resp.status_code)
print("[NILAI] Raw response:")
print(nilai_resp.text)

# =========================
# SIMPAN KE FILE (OPSIONAL)
# =========================
try:
    nilai_json = nilai_resp.json()
    with open("nilai_response.json", "w", encoding="utf-8") as f:
        json.dump(nilai_json, f, indent=2, ensure_ascii=False)
    print("\n✅ JSON nilai disimpan ke file: nilai_response.json")
except Exception:
    print("\n⚠️ Response nilai bukan JSON, tidak disimpan.")
