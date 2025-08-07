import os
import asyncio
import datetime
import random
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application, MessageHandler, filters


# 🔐 Token і дозвіл тільки для акаунту https://t.me/contact_academy

import os
from dotenv import load_dotenv

load_dotenv()  # Завантажуємо .env

BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID'))  # перетворюємо в int, бо ID число


# Обробник команди start
async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("🙃 Упс! Лише обрані мають силу керувати цим ботом Академії CONTACT 🤖.")
        return

    await update.message.reply_text(
        "👋 Вітаю, зробимо сьогодні нагадування?\nЯкщо так — натискай команду /send"
    )

# Обробник команди getid
async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Перевіряємо, чи це саме ти
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("🙃 Упс! Лише обрані мають силу керувати цим ботом Академії CONTACT 🤖.")
        return

    chat = update.effective_chat
    chat_title = chat.title or chat.full_name or "Без назви"
    chat_id = chat.id

    # Надсилаємо тобі особисто
    await context.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text=f"🔍 Назва чату: {chat_title}\n🆔 Chat ID: {chat_id}"
    )



# 📅 Групи з розкладом
groups = [
    # Вівторок
    {"chat_id": "-1001923361033", "weekday": 6, "lesson_time": "10:00"},  # тестовий
    {"chat_id": "-1002473135036", "weekday": 1, "lesson_time": "16:00"},  # ВТ 16:00
    {"chat_id": "-1002261828597", "weekday": 1, "lesson_time": "17:10"},  # ВТ 17:10
    {"chat_id": "-1002742304131", "weekday": 1, "lesson_time": "17:10"},  # ВТ 17:10 укр мова
    # {"chat_id": "-1002214877213", "weekday": 1, "lesson_time": "17:10"},  # ВТ 17:10 граф диз

    # Четвер
    {"chat_id": "-1002414786164", "weekday": 3, "lesson_time": "16:00"},  # ЧТ 16:00
    {"chat_id": "-1001992761373", "weekday": 3, "lesson_time": "17:10"},  # ЧТ 17:10
    {"chat_id": "-1002858419719", "weekday": 3, "lesson_time": "18:00"},  # ЧТ 18:00
    {"chat_id": "-1002742304131", "weekday": 3, "lesson_time": "17:10"},  # ЧТ 17:10 укр мова

    # Субота
    {"chat_id": "-1001981833432", "weekday": 5, "lesson_time": "10:00"},  # СБ 10:00
    {"chat_id": "-1002170222087", "weekday": 5, "lesson_time": "11:15"},  # СБ 11:15
    {"chat_id": "-1002012663874", "weekday": 5, "lesson_time": "12:30"},  # СБ 12:30
    {"chat_id": "-1002021626621", "weekday": 5, "lesson_time": "15:00"},  # СБ 15:00
    # {"chat_id": "-1002193917570", "weekday": 5, "lesson_time": "15:00"},  # СБ 15:00 (ігри)

    # Неділя
    {"chat_id": "-1002046960642", "weekday": 6, "lesson_time": "10:00"},  # НД 10:00 хш
    # {"chat_id": "-1002193782836", "weekday": 6, "lesson_time": "10:00"},  # НД 10:00 (анімація)
    # {"chat_id": "-1002245783127", "weekday": 6, "lesson_time": "12:30"},  # НД 12:30 (3D-мод)
    {"chat_id": "-1001953194411", "weekday": 6, "lesson_time": "12:30"},  # НД 12:30
    {"chat_id": "-1001722600792", "weekday": 6, "lesson_time": "15:00"},  # НД 15:00
    {"chat_id": "-1001722769204", "weekday": 6, "lesson_time": "17:30"}  # НД 17:30
]

# Шаблон повідомлень
greetings = [
    "Привітики, друзі! 🐼", "Привітики! 👋",
    "Вітання, друзі! 😍", "Салют!✨", "Привіт! Як справи?🙂", "Добридень!☀️", "Усім привіт!🤗"
]
bottoms = [
    "Бажаємо затишного дня!☕️", "Гарного дня та приємних несподіванок! 🎁",
    "Бажаємо вдалого дня 🌟 ", "До зустрічі!💜", "Бажаємо приємного дня!🌻", "Гарного дня!😋", "Вдалого дня!💫"
]
stickers = ["📒", "😎", "👩‍🚀", "📚", "🍀", "🌈", '📌',
            '🌼', '⚡️', '👉', '👀', '🧑‍💻', '🐈', '😺', '🛋', '🎀', '🩵', '📘']


# 📬 Надсилання нагадувань
months_ukr = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}


# Глобальна змінна для контролю над надсиланням
sent_today_date = None

async def send_group_reminders(bot: Bot):
    global sent_today_date

    today = datetime.datetime.now().date()
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow_weekday = tomorrow.weekday()

    day = tomorrow.day
    month = months_ukr[tomorrow.month]
    tomorrow_str = f"{day} {month}"

    sent = False

    for group in groups:
        if group["weekday"] == tomorrow_weekday:
            message = (
                f"{random.choice(greetings)}\n\n"
                f"{random.choice(stickers)} Нагадуємо, що завтра, {tomorrow_str}, о {group['lesson_time']} ми чекаємо вас на занятті\n\n"
                f"{random.choice(bottoms)}"
            )
            await bot.send_message(chat_id=group["chat_id"], text=message)
            print(f"✅ Надіслано в групу {group['chat_id']}")
            sent = True

    if sent:
        sent_today_date = today  # тут оновлюємо дату, якщо хоча б одне повідомлення надіслане

    return sent

async def handle_send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global sent_today_date

    user_id = update.effective_user.id

    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("🙃 Упс! Лише обрані мають силу керувати цим ботом Академії CONTACT 🤖")
        return

    today = datetime.datetime.now().date()

    if sent_today_date == today:
        await update.message.reply_text("ℹ️ Сьогодні нагадування вже були надіслані.")
        return

    sent = await send_group_reminders(context.bot)

    if sent:
        await update.message.reply_text("✅ Нагадування надіслано.")
    else:
        await update.message.reply_text("ℹ️ Сьогодні немає груп із запланованим повідомленням.")



# сам визначає який зараз запуск локальний чи через сервер
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Додаємо хендлери
    app.add_handler(CommandHandler("start", handle_start_command))
    app.add_handler(CommandHandler("send", handle_send_command))
    app.add_handler(CommandHandler("getid", get_chat_id_handler))

    print("""🤖 Бот працює! Напиши /start або /send у Telegram.
    P.S За потреби запусти команду getid в чатах, щоб отримати id чату для додавання його до коду""")

    # Перевіряємо середовище
    # if os.environ.get('RENDER') == 'true':
    #     # Якщо ми на Render — запускаємо через WEBHOOK
    #     PORT = int(os.environ.get('PORT', 8443))
    #     RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
    #     await app.run_webhook(
    #         listen="0.0.0.0",
    #         port=PORT,
    #         webhook_url="https://contact-telegram-bot.onrender.com"
    #     )

    if os.environ.get('PORT'):
        PORT = int(os.environ.get('PORT', 8443))
        webhook_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://contact-telegram-bot.onrender.com')
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url
        )
    else:
        await app.run_polling()

    # else:
    #     # Інакше локально — запускаємо через POLLING
    #     await app.run_polling()

# Запуск з підтримкою активного loop
import nest_asyncio
nest_asyncio.apply()

if __name__ == "__main__":
    asyncio.run(main())



