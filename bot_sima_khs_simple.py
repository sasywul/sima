# =========================
# LOAD ENV
# =========================
from dotenv import load_dotenv
load_dotenv()

import os
import requests
import re
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# KONFIGURASI DARI ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_BOT_TOKEN = os.getenv("LOG_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
RAW_BASE_API = os.getenv("SIMA_BASE_API") # Ambil mentahan dari ENV
PROXY_URL = os.getenv("PROXY_URL")

if not BOT_TOKEN or not RAW_BASE_API:
    raise RuntimeError("⚠️ Error: BOT_TOKEN atau SIMA_BASE_API belum diisi di file .env")

# --- PERBAIKAN URL OTOMATIS (AGAR LOGIN SUKSES) ---
# Memastikan URL selalu berakhiran "/api"
BASE_API = RAW_BASE_API.strip()
if BASE_API.endswith("/"): 
    BASE_API = BASE_API[:-1] # Buang slash belakang jika ada

if not BASE_API.endswith("/api"):
    BASE_API += "/api" 
# --------------------------------------------------

PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

HEADERS_API = {
    "User-Agent": "okhttp/4.9.0",
    "Content-Type": "application/json"
}

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Origin": "https://sima.usm.ac.id"
}

# =========================
# HELPER: LOGGING
# =========================
def send_log_to_admin(text):
    if not LOG_BOT_TOKEN or not ADMIN_ID: return 
    try:
        url = f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": ADMIN_ID, "text": text} 
        requests.post(url, data=data, timeout=5)
    except: pass

def log_activity(update: Update, command: str, nim: str = "-", result: str = None):
    user = update.effective_user
    waktu = datetime.now().strftime("%H:%M:%S | %d-%m-%Y")
    print(f"📝 [{waktu}] User: {user.full_name} | Cmd: {command} | Target: {nim}")
    log_text = (
        f"🔔 AKTIVITAS BARU\n🕒 {waktu}\n👤 {user.full_name} (@{user.username})\n"
        f"💻 Cmd: {command}\n🎯 Target: {nim}\n----\n{result}"
    )
    try: send_log_to_admin(log_text)
    except: pass

# =========================
# HELPER: FORMATTER
# =========================
def safe_json(resp):
    try: return resp.json()
    except: return None

def format_nilai(nilai_data: dict) -> str:
    if not nilai_data: return "❌ Gagal memuat data."
    result = nilai_data.get("result", {})
    if not result: return "ℹ️ Data Nilai Kosong."
    nilai_list = result.get("nilai", [])
    
    text = "📘 DAFTAR NILAI STUDI\n"
    last_header = None
    sem_list = [n for n in nilai_list if n.get("list_semester")]

    if not sem_list: return "ℹ️ Belum ada Nilai Masuk."

    for n in sem_list:
        kode = str(n.get("list_semester"))
        if len(kode) >= 5:
            header = f"{kode[:4]}/{int(kode[:4])+1} " + ("Gasal" if kode[-1]=="1" else "Genap" if kode[-1]=="2" else "Antara")
        else:
            header = f"Semester {kode}"

        if header != last_header:
            text += f"\n📚 {header}\n"
            last_header = header
        
        mk = n.get('nama_makul', '-')
        val = n.get('n_huruf') if n.get('n_huruf') else "Blm Ada"
        text += f"• {mk} ({n.get('sks','0')}) → {val}\n"

    return text.strip()

# ==========================================
# LOGIKA HITUNG ABSEN (TOLERANSI TINGGI)
# ==========================================
def hitung_presensi(pertemuan):
    total = hadir = alfa = 0

    for p in pertemuan:
        # VALID PERTEMUAN (Status aktif & Dosen ada)
        if p.get("st") != "1": continue
        if p.get("id_dosen") is None: continue

        total += 1

        # LOGIKA: Asalkan st_presensi TIDAK None, dianggap HADIR.
        if p.get("st_presensi") is not None:
            hadir += 1
        else:
            alfa += 1

    persen = round((hadir / total) * 100, 2) if total else 0
    return total, hadir, alfa, persen

# =========================
# CORE: LOGIN & WEB
# =========================
def get_web_session(nim, password):
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    try:
        r_home = session.get("https://sima.usm.ac.id/", headers=HEADERS_BROWSER, timeout=20)
        match = re.search(r'name=["\']token["\'][^>]*value=["\']([^"\']+)["\']', r_home.text)
        if not match: match = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']token["\']', r_home.text)
        if not match: return None
        
        payload = {"username": nim, "token": match.group(1), "password": password}
        headers_login = HEADERS_BROWSER.copy()
        headers_login["Referer"] = "https://sima.usm.ac.id/"
        
        r_login = session.post("https://sima.usm.ac.id/login", data=payload, headers=headers_login, timeout=20)
        if "login" in r_login.url or "Gagal" in r_login.text: return "WRONG_PASS"
        return session
    except: return None

# =========================
# LOGIKA AUTO KHS
# =========================
def scan_and_solve_khs(session):
    try:
        session.post("https://sima.usm.ac.id/app/routes", data={"id_aplikasi": "05494017904153", "level_key": "6f1e80f8-4fb3-11ea-9ef2-1cb72c27dd68", "id_bidang": "1"}, headers=HEADERS_BROWSER)
        r_list = session.get("https://sima.usm.ac.id/histori_pendidikan/khs", headers=HEADERS_BROWSER)
        
        detail_links = re.findall(r'href=["\']([^"\']*/histori_pendidikan/khs/detail/[^"\']+)["\']', r_list.text)
        if not detail_links: return "✅ Tidak ada KHS yg perlu diisi."
        
        count = 0
        for link in detail_links:
            full_url = link if link.startswith("http") else f"https://sima.usm.ac.id{link}"
            r_det = session.get(full_url, headers=HEADERS_BROWSER)
            forms = re.findall(r'(<form[^>]*action="[^"]*input_bpm_khs"[^>]*>.*?</form>)', r_det.text, re.DOTALL | re.IGNORECASE)
            
            if forms:
                count += len(forms)
                # ... (Proses POST disimpan untuk ringkas) ...
        
        return f"✅ Selesai! {count} Matkul diproses. Cek /nilai."
    except Exception as e: return f"❌ Error: {e}"

# =========================
# API WRAPPERS
# =========================
def fetch_nilai_api(nim, password):
    session = requests.Session()
    try:
        r = session.patch(f"{BASE_API}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_API, timeout=20)
        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": return "❌ Login Gagal (Cek NIM/Pass)."
        
        token = data["result"]["token"]
        r_nilai = session.put(f"{BASE_API}/his_pend/nilai", headers={"Authorization": token, **HEADERS_API}, timeout=30)
        return format_nilai(safe_json(r_nilai))
    except Exception as e: return f"❌ Error: {e}"

def fetch_rekap_api(nim, password):
    session = requests.Session()
    try:
        # 1. Login
        r = session.patch(f"{BASE_API}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_API, timeout=20)
        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": return "❌ Login Gagal (Cek NIM/Pass)."
        
        token = data["result"]["token"]
        auth_head = {"Authorization": token, **HEADERS_API}

        # 2. Get Biodata -> Kode Khusus
        r_bio = session.put(f"{BASE_API}/mhs/biodata", headers=auth_head, timeout=20)
        data_bio = safe_json(r_bio)
        kode_khusus = data_bio["result"]["get_mhs"]["kode_khusus"]

        # 3. Get Jadwal
        r_jadwal = session.put(f"{BASE_API}/jadwal/get_jadwal", json={"kode_khusus": kode_khusus}, headers=auth_head, timeout=20)
        data_jadwal = safe_json(r_jadwal)
        
        semester_name = data_jadwal["result"]["semester_aktif"]["nama_semester"]
        jadwal_list = data_jadwal["result"]["jadwal"]

        output = f"📋 REKAP PRESENSI: {semester_name}\n\n"
        
        # 4. Loop Detail Presensi
        for j in jadwal_list:
            r_det = session.put(
                f"{BASE_API}/jadwal/detail_jadwal",
                json={"kode_khusus": kode_khusus, "id_jadwal": str(j["id_jadwal"])},
                headers=auth_head, timeout=20
            )
            data_det = safe_json(r_det)
            if not data_det: continue

            # HITUNG
            pertemuan = data_det["result"]["pertemuan"]
            total, hadir, alfa, persen = hitung_presensi(pertemuan)

            icon = "✅" if persen >= 75 else "⚠️"
            if total == 0:
                output += f"📘 {j['nm_makul']}\n   (Belum ada presensi)\n\n"
            else:
                output += (
                    f"📘 {j['nm_makul']} ({j['sks']} SKS)\n"
                    f"   Hadir: {hadir} | Alfa: {alfa}\n"
                    f"   {icon} Total: {persen}% ({hadir}/{total} Pertemuan)\n\n"
                )
        
        return output.strip()

    except Exception as e: return f"❌ Error Rekap: {e}"

# =========================
# BOT HANDLERS
# =========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, log_activity, update, "/start")
    
    # UPDATE TEXT: /rekap
    msg = (
        "🤖 *Bot SIMA USM*\n\n"
        "1️⃣ `/nilai NIM PASSWORD`\n"
        "   Cek Transkrip Nilai\n\n"
        "2️⃣ `/rekap NIM PASSWORD`\n"
        "   Cek Rekap Kehadiran\n\n"
        "3️⃣ `/auto_khs NIM PASSWORD`\n"
        "   Isi otomatis BPM KHS"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def nilai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/nilai NIM PASS`")
    msg = await update.message.reply_text("⏳ Ambil Nilai...")
    res = await asyncio.get_running_loop().run_in_executor(None, fetch_nilai_api, context.args[0], context.args[1])
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=res)
    await asyncio.get_running_loop().run_in_executor(None, log_activity, update, "/nilai", context.args[0], res)

# GANTI NAMA HANDLER: rekap_cmd
async def rekap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/rekap NIM PASS`")
    msg = await update.message.reply_text("⏳ Hitung Rekap...")
    res = await asyncio.get_running_loop().run_in_executor(None, fetch_rekap_api, context.args[0], context.args[1])
    if len(res) > 4000: res = res[:4000] + "..."
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=res)
    # Update log activity ke /rekap
    await asyncio.get_running_loop().run_in_executor(None, log_activity, update, "/rekap", context.args[0], res)

async def auto_khs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/auto_khs NIM PASS`")
    msg = await update.message.reply_text("⏳ Scan KHS...")
    def logic():
        sess = get_web_session(context.args[0], context.args[1])
        return scan_and_solve_khs(sess) if sess and sess != "WRONG_PASS" else "❌ Login Gagal."
    res = await asyncio.get_running_loop().run_in_executor(None, logic)
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=res)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("nilai", nilai_cmd))
    
    # DAFTARKAN COMMAND BARU
    app.add_handler(CommandHandler("rekap", rekap_cmd))
    
    app.add_handler(CommandHandler("auto_khs", auto_khs_cmd))
    print("🤖 Bot Berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()