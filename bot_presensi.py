import time
import requests
import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# =========================
# KONFIGURASI
# =========================
BOT_TOKEN = "8127285199:AAE9-WJSrPLxSRhJQN848RknKKskD6ofv0M"
BASE_URL = "https://sima.usm.ac.id/index.php/api"
SESSION_EXPIRE = 7200 

HEADERS_ANDROID = {
    "User-Agent": "okhttp/4.9.0",
    "Content-Type": "application/json; charset=UTF-8"
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# =========================
# HELPER API
# =========================
def api_login(nim, password):
    try:
        r = requests.patch(
            f"{BASE_URL}/login/sia",
            json={"username": nim, "password": password},
            headers=HEADERS_ANDROID,
            timeout=15
        )
        data = r.json()
        if data.get("result", {}).get("st") == "1":
            return data["result"]
    except: pass
    return None

def api_get_biodata(token):
    try:
        r = requests.put(
            f"{BASE_URL}/mhs/biodata",
            headers={"Authorization": token, **HEADERS_ANDROID},
            timeout=15
        )
        return r.json().get("result", {}).get("get_mhs", {}).get("kode_khusus")
    except: return None

def api_get_jadwal(token, kode_khusus):
    try:
        r = requests.put(
            f"{BASE_URL}/presensi/hari_ini/get",
            headers={"Authorization": token, **HEADERS_ANDROID},
            json={"kode_khusus": kode_khusus},
            timeout=15
        )
        return r.json().get("result", [])
    except: return []

def api_log_press(token, kode_khusus):
    try:
        ip_resp = requests.get("https://api64.ipify.org/?format=json", timeout=5)
        my_ip = ip_resp.json().get("ip", "127.0.0.1")
        
        requests.patch(
            f"{BASE_URL}/presensi/hari_ini/log",
            headers={"Authorization": token, **HEADERS_ANDROID},
            json={
                "ip": my_ip,
                "keterangan": "Android 23049PCD8G (OS 15)", 
                "kode_khusus": kode_khusus
            },
            timeout=10
        )
    except: pass

# =========================
# UI BUILDER (Tampilan Bersih)
# =========================
def generate_jadwal_view(token, nama_mhs, kode_khusus):
    """Membuat Tampilan Jadwal tanpa tombol sampah"""
    
    # Ambil Data Terbaru
    jadwal = api_get_jadwal(token, kode_khusus)
    
    tgl_skrg = datetime.now().strftime("%A, %d %B %Y")
    # Hapus detik agar lebih bersih, atau biarkan jika suka
    jam_update = datetime.now().strftime("%H:%M") 

    text = (
        f"📅 <b>JADWAL HARI INI</b>\n"
        f"👤 {nama_mhs}\n"
        f"🗓️ {tgl_skrg}\n"
        f"─────────────────\n\n"
    )
    
    if not jadwal:
        text += "<i>ℹ️ Tidak ada jadwal kuliah hari ini.</i>"
        return text, None

    keyboard = []
    
    for j in jadwal:
        matkul = j['nm_makul']
        jam = j['jam']
        ruang = j['ruang']
        
        raw_st = j.get("st_presensi")
        status_buka = str(j.get("status_presensi")) == "1"
        sudah_hadir = False
        ket_status = "-"

        # Logika Deteksi Kehadiran
        if isinstance(raw_st, dict):
            ket_status = raw_st.get("st_presensi", "Hadir")
            sudah_hadir = True 
        elif isinstance(raw_st, str):
            ket_status = raw_st
            if raw_st in ["Hadir", "Terlambat", "On Time", "Ijin", "Sakit"]:
                sudah_hadir = True
        
        # Penentuan Ikon & Teks
        if sudah_hadir:
            icon = "✅"
            info_text = f"Sudah Absen ({ket_status})"
        elif status_buka:
            icon = "📘"
            info_text = "Silahkan Klik Presensi"
        else:
            icon = "🔴"
            info_text = "Tutup"

        text += (
            f"{icon} <b>{matkul}</b>\n"
            f"   ├ 🕒 {jam} | 🏫 {ruang}\n"
            f"   └ ℹ️ {info_text}\n\n"
        )

        # FILTER STRICT: Tombol HANYA muncul jika BUKA dan BELUM HADIR
        # Tombol Refresh dan Ulang DIBUANG.
        if status_buka and not sudah_hadir:
            keyboard.append([
                InlineKeyboardButton(
                    f"👆 KLIK HADIR: {matkul}", 
                    callback_data=f"presensi|{j['id_jadwal']}"
                )
            ])
            
    return text, InlineKeyboardMarkup(keyboard) if keyboard else None

# =========================
# HANDLER COMMAND
# =========================
async def presensi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hapus pesan user (Privacy)
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except: pass

    if len(context.args) != 2:
        msg = await update.message.reply_text("❌ <b>Format Salah</b>\nGunakan: <code>/presensi NIM PASSWORD</code>", parse_mode="HTML")
        return

    nim, password = context.args
    msg = await update.message.reply_text("🔐 <i>Login & Mengambil Data...</i>", parse_mode="HTML")

    # 1. Login
    login_data = api_login(nim, password)
    if not login_data:
        await msg.edit_text("❌ <b>Login Gagal</b>\nNIM atau Password salah.")
        return

    token = login_data["token"]
    nama_mhs = login_data.get("nama", "Mahasiswa")
    kode_khusus = api_get_biodata(token)

    # 2. Simpan Sesi
    context.user_data.update({
        "token": token,
        "kode_khusus": kode_khusus,
        "nama": nama_mhs,
        "login_at": time.time()
    })

    # 3. Tampilkan Hasil (Hapus loading dulu)
    await msg.delete()
    
    text, markup = generate_jadwal_view(token, nama_mhs, kode_khusus)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML", reply_markup=markup)


# =========================
# HANDLER TOMBOL (Callback)
# =========================
async def presensi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Cek Sesi
    sess = context.user_data
    if "token" not in sess or (time.time() - sess.get("login_at", 0) > SESSION_EXPIRE):
        await query.answer("⚠️ Sesi habis. Login ulang.", show_alert=True)
        return

    # Proses Presensi
    _, id_jadwal_target = data.split("|")
    await query.answer("🚀 Mengirim request...")
    
    try:
        # 1. Log IP
        api_log_press(sess["token"], sess["kode_khusus"])

        # 2. Request
        url = f"{BASE_URL}/presensi/hari_ini/press"
        payload = {
            "id_presensi": "", 
            "kode_khusus": sess["kode_khusus"]
        }
        
        # Cari ID Presensi terbaru (Fetch data baru untuk memastikan ID benar)
        current_jadwal = api_get_jadwal(sess["token"], sess["kode_khusus"])
        target_mk = next((x for x in current_jadwal if str(x['id_jadwal']) == id_jadwal_target), None)
        
        if target_mk:
            payload["id_presensi"] = target_mk["id_presensi"]
            
            # Eksekusi API
            r = requests.patch(
                url, json=payload, 
                headers={"Authorization": sess["token"], **HEADERS_ANDROID}, 
                timeout=20
            )
            res = r.json()
            
            # Cek Sukses (Status 200)
            if str(res.get("status")) == "200":
                await query.answer("✅ Sukses!", show_alert=True)
                
                # --- UPDATE TAMPILAN ---
                # 1. Hapus Pesan Lama (yang ada tombolnya)
                try: await query.message.delete()
                except: pass
                
                # 2. Ambil data terbaru (Status sekarang sudah pasti 'Done')
                new_text, new_markup = generate_jadwal_view(sess["token"], sess["nama"], sess["kode_khusus"])
                
                # 3. Kirim sebagai Pesan Baru yang bersih
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=new_text, 
                    parse_mode="HTML", 
                    reply_markup=new_markup
                )
                
            else:
                msg = res.get("message", "Gagal")
                await query.answer(f"❌ {msg}", show_alert=True)
        else:
             await query.answer("❌ Jadwal tidak valid/ditemukan.", show_alert=True)

    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Error: {e}")

# =========================
# MAIN
# =========================
def main():
    print("🤖 Bot Presensi (Clean Mode) Berjalan...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("presensi", presensi_cmd))
    app.add_handler(CallbackQueryHandler(presensi_callback))
    app.run_polling()

if __name__ == "__main__":
    main()