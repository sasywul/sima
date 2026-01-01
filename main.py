import os
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
import bot_handlers as h

def main():
    print("🚀 Memulai Bot USM...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- DAFTAR HANDLERS ---
    app.add_handler(CommandHandler("start", h.start_cmd))
    app.add_handler(CommandHandler("presensi", h.presensi_cmd))
    app.add_handler(CommandHandler("nilai", h.nilai_cmd))
    app.add_handler(CommandHandler("rekap", h.rekap_cmd))
    app.add_handler(CommandHandler("auto_khs", h.auto_khs_cmd))
    
    app.add_handler(CallbackQueryHandler(h.presensi_callback))
    app.add_handler(MessageHandler(filters.PHOTO, h.trawang_foto_handler))

    # --- LOGIKA AUTO-SWITCH (POLLING vs WEBHOOK) ---
    # Railway otomatis memberikan variable 'PORT' dan kita akan set 'WEBHOOK_URL' nanti
    PORT = int(os.environ.get('PORT', '8080'))
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL') 

    if WEBHOOK_URL:
        # MODE: RAILWAY (PRODUCTION)
        print(f"🌐 Berjalan di Mode WEBHOOK pada Port {PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # MODE: LAPTOP (LOCAL)
        print("💻 Berjalan di Mode POLLING (Lokal)")
        app.run_polling()

if __name__ == "__main__":
    main()