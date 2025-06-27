# from telegram import Update
# from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
#
# BOT_TOKEN = '8035806550:AAE-guU0462nmrlzaG5pHD1DxlUY0cUhOAQ'
#
#
# # Обробка повідомлень
# async def get_chat_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     chat = update.effective_chat
#     chat_id = chat.id
#     chat_title = chat.title or chat.full_name or "Без назви"
#
#     print(f"🔍 Назва чату: {chat_title}")
#     print(f"🆔 Chat ID: {chat_id}")
#     print("-" * 40)
#
#     # Нічого не надсилаємо назад у групу (без спаму)
#
#
# app = ApplicationBuilder().token(BOT_TOKEN).build()
# app.add_handler(MessageHandler(filters.ALL, get_chat_info))
#
# print("🤖 Надішли будь-яке повідомлення у групи з ботом — виведемо chat_id у консоль.")
# app.run_polling()



from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = '8035806550:AAE-guU0462nmrlzaG5pHD1DxlUY0cUhOAQ'
ALLOWED_USER_ID = 5117974777  # тільки ти отримуєш chat_id

# 💬 Команда /getid
async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Перевіряємо, чи це саме ти
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ У вас немає прав для цієї дії.")
        return

    chat = update.effective_chat
    chat_title = chat.title or chat.full_name or "Без назви"
    chat_id = chat.id

    # Надсилаємо тобі особисто
    await context.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text=f"🔍 Назва чату: {chat_title}\n🆔 Chat ID: {chat_id}"
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("getid", get_chat_id_handler))

print("🤖 Бот запущено! Напиши /getid у групі, і бот надішле тобі назву чату та chat_id.")
app.run_polling()

