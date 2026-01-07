import asyncio
import time
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import SESSION_EXPIRE, LOG_BOT_TOKEN, ADMIN_ID
import api_service as api

# ==========================================
# 1. HELPER: LOGGING KE ADMIN
# ==========================================
def send_log_to_admin(text):
    if not LOG_BOT_TOKEN or not ADMIN_ID: return 
    try:
        url = f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
        data = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
    except: pass

def log_activity(user, command, nim="-", result="-"):
    waktu = datetime.now().strftime("%H:%M:%S | %d-%m-%Y")
    print(f"📝 [{waktu}] {user.full_name} -> {command}")
    
    msg = (
        f"🔔 <b>AKTIVITAS BOT</b>\n"
        f"🕒 {waktu}\n"
        f"👤 <b>{user.full_name}</b> (@{user.username or '-'})\n"
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
        text += "<i>ℹ️ Tidak ada jadwal kuliah hari ini. Santai dulu! ☕</i>"
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
            status_txt = f"Sudah Absen ({ket_status})"
        elif status_buka:
            icon = "📢"
            status_txt = "Silahkan Absen Sekarang!"
        else:
            icon = "🔒"
            status_txt = "Belum Buka / Tutup"

        text += f"{icon} <b>{matkul}</b>\n   ├ 🕒 {waktu} | 🏫 {ruang}\n   └ ℹ️ {status_txt}\n\n"

        if status_buka and not sudah_hadir:
            keyboard.append([InlineKeyboardButton(f"👆 ABSEN: {matkul}", callback_data=f"presensi|{j['id_jadwal']}")])

    return text, InlineKeyboardMarkup(keyboard) if keyboard else None

# ==========================================
# 3. COMMAND HANDLERS
# ==========================================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/start"))
    msg = (
        "👋 <b>Halo! Bot Akademik USM siap bantu.</b>\n\n"
        "1️⃣ <code>/presensi NIM PASS</code> - Cek Jadwal & Absen\n"
        "2️⃣ <code>/nilai NIM PASS</code> - Cek Transkrip Nilai\n"
        "3️⃣ <code>/rekap NIM PASS</code> - Cek Persentase Kehadiran\n"
        "4️⃣ <code>/auto_khs NIM PASS</code> - Isi Kuesioner Otomatis\n"
        "5️⃣ <code>/skpi NIM PASS</code> - Cek Poin SKPI \n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def presensi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: await context.bot.delete_message(update.message.chat_id, update.message.message_id)
    except: pass
    
    if len(context.args) != 2: 
        return await update.message.reply_text("⚠️ **Format Salah**\nKetik: `/presensi NIM PASSWORD`", parse_mode="Markdown")
    
    msg = await update.message.reply_text("👋 _Sebentar, sedang login..._", parse_mode="Markdown")
    
    login_res = await asyncio.to_thread(api.api_login_android, context.args[0], context.args[1])
    
    if isinstance(login_res, str):
        asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/presensi", context.args[0], "Gagal Login"))
        return await msg.edit_text(login_res, parse_mode="Markdown")

    if not login_res: 
        return await msg.edit_text("😵 **Gagal Login** (Server tidak merespon)", parse_mode="Markdown")

    token = login_res["token"]
    nama = login_res.get("nama", "Mahasiswa")
    kode_khusus = await asyncio.to_thread(api.api_get_biodata, token)

    context.user_data.update({"token": token, "kode_khusus": kode_khusus, "nama": nama, "login_at": time.time()})
    
    text, markup = await asyncio.to_thread(generate_jadwal_view, token, nama, kode_khusus)
    
    await msg.delete()
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="HTML", reply_markup=markup)
    
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/presensi", context.args[0], "Sukses Load Jadwal"))

async def presensi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sess = context.user_data
    
    if "token" not in sess: 
        return await query.answer("⌛ Sesi habis. Login lagi ya.", show_alert=True)

    _, id_jadwal_target = query.data.split("|")
    await query.answer("🚀 Mengirim data absen...")

    jadwal = await asyncio.to_thread(api.api_get_jadwal, sess["token"], sess["kode_khusus"])
    target = next((x for x in jadwal if str(x['id_jadwal']) == id_jadwal_target), None)

    if target:
        res = await asyncio.to_thread(api.api_execute_presensi, sess["token"], sess["kode_khusus"], target["id_presensi"])
        status = str(res.get("status", "error"))
        
        if status == "200" or status == "1":
            await query.answer("✅ Absen Berhasil!", show_alert=True)
            try: await query.message.delete()
            except: pass
            
            text, markup = await asyncio.to_thread(generate_jadwal_view, sess["token"], sess["nama"], sess["kode_khusus"])
            await context.bot.send_message(query.message.chat_id, text, parse_mode="HTML", reply_markup=markup)
            
            asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "TEKAN ABSEN", sess.get("nama"), f"ID: {id_jadwal_target}"))
        else:
            pesan_error = res.get("message", "Gagal Unknown")
            await query.answer(f"❌ Gagal Absen:\n{pesan_error}", show_alert=True)
    else:
        await query.answer("❌ Jadwal tidak ditemukan.", show_alert=True)

async def nilai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("⚠️ **Format Salah**\nKetik: `/nilai NIM PASSWORD`", parse_mode="Markdown")
    msg = await update.message.reply_text("🔍 _Sedang mengecek transkrip..._", parse_mode="Markdown")
    
    res = await asyncio.to_thread(api.fetch_nilai_api, context.args[0], context.args[1])
    await msg.edit_text(res, parse_mode="Markdown")
    
    log_status = "Sukses" if "TRANSKRIP" in res else "Gagal"
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/nilai", context.args[0], log_status))

async def rekap_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("⚠️ **Format Salah**\nKetik: `/rekap NIM PASSWORD`", parse_mode="Markdown")
    msg = await update.message.reply_text("📊 _Sedang menghitung persentase..._", parse_mode="Markdown")
    
    res = await asyncio.to_thread(api.fetch_rekap_api, context.args[0], context.args[1])
    if len(res) > 4000: res = res[:4000] + "\n...(terpotong)"
    await msg.edit_text(res, parse_mode="Markdown")
    
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/rekap", context.args[0], "Cek Rekap"))

async def skpi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("⚠️ **Format Salah**\nKetik: `/skpi NIM PASSWORD`", parse_mode="Markdown")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    msg_loading = await update.message.reply_text("📜 _Sedang mengambil data SKPI..._", parse_mode="Markdown")

    hasil = await asyncio.to_thread(api.fetch_skpi_web, context.args[0], context.args[1])
    
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_loading.message_id)
    await update.message.reply_text(hasil, parse_mode='Markdown', disable_web_page_preview=True)
    
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/skpi", context.args[0], "Cek SKPI"))

async def auto_khs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2: return await update.message.reply_text("⚠️ **Format Salah**\nKetik: `/auto_khs NIM PASSWORD`", parse_mode="Markdown")
    msg = await update.message.reply_text("🤖 _Bot sedang bekerja, mohon tunggu..._", parse_mode="Markdown")
    
    def process():
        sess_or_error = api.get_web_session(context.args[0], context.args[1])
        return api.scan_and_solve_khs(sess_or_error)

    res = await asyncio.to_thread(process)
    await msg.edit_text(res, parse_mode="Markdown")
    
    asyncio.create_task(asyncio.to_thread(log_activity, update.effective_user, "/auto_khs", context.args[0], res[:50] + "..."))