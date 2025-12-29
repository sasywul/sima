import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# CONFIG DARI ENV (AMAN)
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # token bot Telegram
BASE_API = os.getenv("SIMA_BASE_API")       # contoh: https://sima.usm.ac.id/index.php

if not BOT_TOKEN or not BASE_API:
    raise RuntimeError("ENV BOT_TOKEN / SIMA_BASE_API belum diset")

# =========================
# HEADER MENIRU OKHTTP
# =========================
OKHTTP_HEADERS = {
    "User-Agent": "okhttp/4.9.0",
    "Accept-Encoding": "gzip",
    "Connection": "Keep-Alive",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# =========================
# FUNGSI AMBIL KHS
# =========================
def fetch_khs(nim: str, password: str) -> str:
    session = requests.Session()

    # 1️⃣ LOGIN API
    login_resp = session.patch(
        f"{BASE_API}/api/login/sia",
        json={"username": nim, "password": password},
        headers=OKHTTP_HEADERS,
        timeout=20
    )

    try:
        login_data = login_resp.json()
    except Exception:
        return "❌ Login gagal (response tidak valid)"

    if not isinstance(login_data, dict) or not login_data.get("result"):
        return "❌ Login gagal. Periksa NIM / PASSWORD."

    token = login_data["result"].get("token")
    if not token:
        return "❌ Token tidak ditemukan."

    # 2️⃣ AMBIL KHS
    headers = OKHTTP_HEADERS.copy()
    headers["Authorization"] = token  # TANPA 'Bearer'

    khs_resp = session.put(
        f"{BASE_API}/api/his_pend/khs",
        headers=headers,
        timeout=20
    )

    try:
        khs_data = khs_resp.json()
    except Exception:
        return "❌ Gagal membaca data KHS"

    result = khs_data.get("result")
    if not isinstance(result, dict):
        return "❌ Data KHS tidak tersedia"

    mhs = result.get("mhs", {})
    prodi = result.get("prodi", {})
    histori = result.get("histori_khs", [])

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

    try:
        result = fetch_khs(nim, password)
        await update.message.reply_text(result, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ Terjadi kesalahan sistem")

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
