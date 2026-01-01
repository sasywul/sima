import asyncio
import time
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import SESSION_EXPIRE, LOG_BOT_TOKEN, ADMIN_ID
import api_service as api
import os   
import base64
# --- FUNGSI TRAWANG (POLLINATIONS VIA BASE64) ---
async def trawang_foto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. Kasih status "sedang mengetik"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    msg_loading = await update.message.reply_text(f"👁️ Sedang menerawang aura Kak {user.first_name}...")

    try:
        # 2. Download Foto dari Telegram ke Memori (RAM)
        # Kita tidak perlu simpan ke file, langsung olah di RAM biar cepat
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # 3. Ubah Foto jadi Kode Base64
        # Ini triknya! Foto diubah jadi teks panjang biar bisa dibaca AI
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        url_gambar_base64 = f"data:image/jpeg;base64,{base64_image}"

        # 4. Tembak API Pollinations (Format OpenAI)
        url_api = "https://text.pollinations.ai/openai"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Mantra Dukun
        prompt_text = "Lihat foto ini. Kamu adalah dukun gaul yang lucu dan sarkas. Ramal kepribadian, percintaan, dan keuangannya minggu ini. Pakai bahasa Indonesia gaul."

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url", 
                            "image_url": {"url": url_gambar_base64} # Kirim kode fotonya langsung!
                        }
                    ]
                }
            ],
            "model": "openai-large", # Model besar biar tajam mata batinnya
            "json": False
        }

        # Kirim Request (POST)
        response = requests.post(url_api, json=payload, headers=headers)
        
        # 5. Cek Hasil
        if response.status_code == 200:
            # Pollinations kadang balikin teks langsung, kadang JSON. Kita amanin dua-duanya.
            try:
                hasil_teks = response.choices[0].message.content # Kalau format OpenAI
            except:
                hasil_teks = response.text # Kalau format teks biasa
            
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_loading.message_id)
            await update.message.reply_text(f"🔮 **RAMALAN DUKUN AI** 🔮\n\n{hasil_teks}", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Dukunnya pusing (Error {response.status_code}). Coba lagi nanti.")

    except Exception as e:
        print(f"Error System: {e}")
        await update.message.reply_text("😵 Ada gangguan teknis saat menerawang.")
# ==========================================
# 1. HELPER: LOGGING KE ADMIN
# ==========================================
def send_log_to_admin(text):
    """Kirim pesan notifikasi ke ID Admin"""
    if not LOG_BOT_TOKEN or not ADMIN_ID: return 
    try:
        url = f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
    except: pass

def log_activity(user, command, nim="-", result="-"):
    """Format pesan log"""
    waktu = datetime.now().strftime("%H:%M:%S | %d-%m-%Y")
    
    # Print di Terminal Railway/Laptop
    print(f"📝 [{waktu}] {user.full_name} (@{user.username}) -> {command} ({nim})")
    
    # Kirim ke Telegram Admin
    msg = (
        f"🔔 <b>AKTIVITAS BOT</b>\n"
        f"🕒 {waktu}\n"
        f"👤 <b>{user.full_name}</b> (@{user.username or '-'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💻 Cmd: <code>{command}</code>\n"
        f"🎯 Target: <code>{nim}</code>\n"
        f"📝 Hasil: {result}"
    )
    send_log_to_admin(msg)

# ==========================================
# 2. UI GENERATOR (PRESENSI)
# ==========================================
def generate_jadwal_view(token, nama, kode_khusus):
    jadwal = api.api_get_jadwal(token, kode_khusus)
    tgl = datetime.now().strftime("%A, %d %B %Y")
    jam = datetime.now().strftime("%H:%M")
    
    text = f"📅 <b>JADWAL HARI INI</b>\n👤 {nama}\n🗓️ {tgl} (Upd: {jam})\n─────────────────\n\n"
    keyboard = []

    if not jadwal:
        text += "<i>ℹ️ Tidak ada jadwal kuliah hari ini.</i>"
        return text, None

    for j in jadwal:
        matkul = j['nm_makul']
        waktu = j['jam']
        ruang = j['ruang']
        
        raw_st = j.get("st_presensi")
        status_buka = str(j.get("status_presensi")) == "1"
        sudah_hadir = False
        ket_status = "-"

        if isinstance(raw_st, dict):
            ket_status = raw_st.get("st_presensi", "Hadir")
            sudah_hadir = True
        elif isinstance(raw_st, str):
            ket_status = raw_st
            if raw_st in ["Hadir", "Terlambat", "On Time", "Ijin", "Sakit"]:
                sudah_hadir = True
        
        if sudah_hadir:
            icon = "✅"
            status_txt = f"Done ({ket_status})"
        elif status_buka:
            icon = "📘"
            status_txt = "Silahkan Klik Presensi"
        else:
            icon = "🔴"
            status_txt = "Tutup / Belum Buka"

        text += f"{icon} <b>{matkul}</b>\n   ├ 🕒 {waktu} | 🏫 {ruang}\n   └ ℹ️ {status_txt}\n\n"

        if status_buka and not sudah_hadir:
            keyboard.append([InlineKeyboardButton(f"👆 KLIK HADIR: {matkul}", callback_data=f"presensi|{j['id_jadwal']}")])

    return text, InlineKeyboardMarkup(keyboard) if keyboard else None

# ==========================================
# 3. HANDLERS
# ==========================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Log Start
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/start"))
    
    msg = (
        "🤖 <b>Bot Akademik USM (Integrated)</b>\n\n"
        "1️⃣ <code>/presensi NIM PASS</code> - Cek & Absen\n"
        "2️⃣ <code>/nilai NIM PASS</code> - Cek Transkrip\n"
        "3️⃣ <code>/rekap NIM PASS</code> - Cek Rekap Absensi\n"
        "4️⃣ <code>/auto_khs NIM PASS</code> - Isi Otomatis BPM\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def presensi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(update.message.chat_id, update.message.message_id)
    except: pass
    
    if len(context.args) != 2: return await update.message.reply_text("Format: `/presensi NIM PASS`")
    
    msg = await update.message.reply_text("🔐 <i>Login...</i>", parse_mode="HTML")
    
    login_res = await asyncio.to_thread(api.api_login_android, context.args[0], context.args[1])
    if not login_res: 
        # Log Gagal
        asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/presensi", context.args[0], "Gagal Login"))
        return await msg.edit_text("❌ <b>Login Gagal</b>", parse_mode="HTML")

    token = login_res["token"]
    nama = login_res.get("nama", "Mhs")
    kode_khusus = await asyncio.to_thread(api.api_get_biodata, token)

    context.user_data.update({"token": token, "kode_khusus": kode_khusus, "nama": nama, "login_at": time.time()})
    
    text, markup = await asyncio.to_thread(generate_jadwal_view, token, nama, kode_khusus)
    await msg.delete()
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="HTML", reply_markup=markup)
    
    # Log Sukses
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/presensi", context.args[0], "Sukses Cek Jadwal"))

async def presensi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sess = context.user_data
    if "token" not in sess: return await query.answer("⚠️ Sesi habis.", show_alert=True)

    _, id_jadwal_target = query.data.split("|")
    await query.answer("🚀 Memproses...")

    jadwal = await asyncio.to_thread(api.api_get_jadwal, sess["token"], sess["kode_khusus"])
    target = next((x for x in jadwal if str(x['id_jadwal']) == id_jadwal_target), None)

    if target:
        res = await asyncio.to_thread(api.api_execute_presensi, sess["token"], sess["kode_khusus"], target["id_presensi"])
        if str(res.get("status")) == "200":
            await query.answer("✅ Berhasil!", show_alert=True)
            try: await query.message.delete()
            except: pass
            text, markup = await asyncio.to_thread(generate_jadwal_view, sess["token"], sess["nama"], sess["kode_khusus"])
            await context.bot.send_message(query.message.chat_id, text, parse_mode="HTML", reply_markup=markup)
            
            # Log Klik Absen
            asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "KLIK ABSEN", sess.get("nama"), f"Matkul ID: {id_jadwal_target}"))
        else:
            await query.answer(f"❌ {res.get('message')}", show_alert=True)

async def nilai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/nilai NIM PASS`")
    msg = await update.message.reply_text("⏳ Ambil Nilai...")
    
    res = await asyncio.to_thread(api.fetch_nilai_api, context.args[0], context.args[1])
    await msg.edit_text(res, parse_mode="Markdown")
    
    # Log Nilai
    log_status = "Sukses" if "DAFTAR NILAI" in res else "Gagal/Error"
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/nilai", context.args[0], log_status))

async def rekap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/rekap NIM PASS`")
    msg = await update.message.reply_text("⏳ Hitung Rekap...")
    
    res = await asyncio.to_thread(api.fetch_rekap_api, context.args[0], context.args[1])
    if len(res) > 4000: res = res[:4000] + "\n...(terpotong)"
    await msg.edit_text(res, parse_mode="Markdown")
    
    # Log Rekap
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/rekap", context.args[0], "Cek Rekap"))

async def auto_khs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("Format: `/auto_khs NIM PASS`")
    msg = await update.message.reply_text("⏳ *Sedang Cek Tagihan & Scan BPM...*", parse_mode="Markdown")
    
    def process():
        sess = api.get_web_session(context.args[0], context.args[1])
        if sess == "WRONG_PASS": return "❌ *Password Salah!*"
        if not sess: return "❌ Gagal Login Web."
        return api.scan_and_solve_khs(sess)

    res = await asyncio.to_thread(process)
    await msg.edit_text(res, parse_mode="Markdown")
    
    # Log Auto KHS
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/auto_khs", context.args[0], res[:50] + "..."))