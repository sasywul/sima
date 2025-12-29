# =========================
# LOAD ENV (untuk lokal)
# =========================
from dotenv import load_dotenv
load_dotenv()

import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ENV CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_API = os.getenv("SIMA_BASE_API")
PROXY_URL = os.getenv("PROXY_URL")  # opsional

if not BOT_TOKEN or not BASE_API:
    raise RuntimeError("ENV BOT_TOKEN / SIMA_BASE_API belum diset")

# =========================
# PROXY CONFIG
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
OKHTTP_HEADERS = {
    "User-Agent": "okhttp/4.9.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Encoding": "identity",
    "Connection": "close"
}

# =========================
# HELPER
# =========================
def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def is_blocked(resp):
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct.lower():
        return True
    if resp.status_code in (403, 429):
        return True
    return False

# =========================
# FETCH KHS
# =========================
def fetch_khs(nim: str, password: str) -> str:
    session = requests.Session()

    # === LOGIN ===
    login_resp = session.patch(
        f"{BASE_API}/api/login/sia",
        json={"username": nim, "password": password},
        headers=OKHTTP_HEADERS,
        timeout=30,
        allow_redirects=False,
        proxies=PROXIES
    )

    if is_blocked(login_resp):
        return (
            "🚫 *Akses dibatasi oleh server kampus*\n\n"
            "Permintaan dari bot ditolak oleh sistem kampus.\n"
            "Silakan coba lagi nanti."
        )

    login_data = safe_json(login_resp)
    if not login_data or not isinstance(login_data, dict):
        return "❌ Login gagal (response tidak valid dari server)"

    result = login_data.get("result", {})
    message = login_data.get("message", "")

    # === LOGIN GAGAL (PASSWORD SALAH) ===
    if result.get("st") == "0" or not result.get("token"):
        return (
            "❌ *Login gagal*\n\n"
            "NIM atau password yang kamu masukkan salah.\n"
            "Silakan periksa kembali dan coba lagi."
        )

    token = result.get("token")

    # === AMBIL KHS ===
    headers = OKHTTP_HEADERS.copy()
    headers["Authorization"] = token  # TANPA Bearer

    khs_resp = session.put(
        f"{BASE_API}/api/his_pend/khs",
        headers=headers,
        timeout=30,
        allow_redirects=False,
        proxies=PROXIES
    )

    if is_blocked(khs_resp):
        return (
            "🚫 *Tidak bisa mengambil KHS*\n\n"
            "Server kampus menolak koneksi bot.\n"
            "Silakan coba lagi nanti."
        )

    khs_data = safe_json(khs_resp)
    if not khs_data or not isinstance(khs_data.get("result"), dict):
        return "❌ Data KHS tidak tersedia"

    result = khs_data["result"]
    histori = result.get("histori_khs", [])

    mhs = result.get("mhs", {})
    prodi = result.get("prodi", {})

    nama = mhs.get("nama_mahasiswa", "-")
    nim_val = mhs.get("nim", "-")
    prodi_nama = prodi.get("programstudi", "-").strip()
    fakultas = prodi.get("fakultas", "-")

    text = (
        f"🎓 *KARTU HASIL STUDI*\n"
        f"👤 {nama}\n"
        f"🆔 {nim_val}\n"
        f"🏫 {prodi_nama}\n"
        f"🏢 {fakultas}\n\n"
    )

    if not histori:
        return text + "_Belum ada data KHS_"

    for h in histori:
        ips = h.get("ips")
        ips_text = ips if ips is not None else "Belum ada nilai"

        text += (
            f"📚 *{h.get('nama_semester','-')}*\n"
            f"• IPS : {ips_text}\n"
            f"• SKS : {h.get('jm_sks','-')}\n"
            f"• MK  : {h.get('jm_mk','-')}\n"
            f"• Status : {h.get('status_kuliah','-')}\n\n"
        )

    return text.strip()

# =========================
# COMMAND /khs
# =========================
async def khs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Format:\n/khs NIM PASSWORD")
        return

    nim, password = context.args
    await update.message.reply_text("⏳ Mengambil data KHS...")

    result = fetch_khs(nim, password)
    await update.message.reply_text(result, parse_mode="Markdown")

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("khs", khs_cmd))
    print("🤖 Bot SIMA Telegram berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
