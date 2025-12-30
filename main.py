from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import BOT_TOKEN
import bot_handlers as h

def main():
    print("🤖 Bot USM Integrated (Final Mantap) Running...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", h.start_cmd))
    app.add_handler(CommandHandler("presensi", h.presensi_cmd))
    app.add_handler(CommandHandler("nilai", h.nilai_cmd))
    app.add_handler(CommandHandler("rekap", h.rekap_cmd))
    app.add_handler(CommandHandler("auto_khs", h.auto_khs_cmd))
    
    app.add_handler(CallbackQueryHandler(h.presensi_callback))

    app.run_polling()

if __name__ == "__main__":
    main()