import asyncio
import datetime
import random
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Application, MessageHandler, filters
import gspread
import os, json
from oauth2client.service_account import ServiceAccountCredentials
import re


# 🔐 Token і дозвіл тільки для акаунту https://t.me/contact_academy

import os
from dotenv import load_dotenv

load_dotenv()  # Завантажуємо .env

BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID'))  # перетворюємо в int, бо ID число

waiting_for_send_all_message = False

# Підключення до клієнта
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not set")

    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    return gspread.authorize(creds)

# Зчитування потрібної таблиці
def read_schedule_from_sheet():
    client = get_gspread_client()
    sheet = client.open("groups_schedule").sheet1
    return sheet.get_all_records()


async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("🙃 Упс! Лише обрані мають силу керувати цим ботом Академії CONTACT 🤖.")
        return

    await update.message.reply_text(
        "👋 Вітаю, зробимо сьогодні нагадування?\nЯкщо так — натискай команду /send"
    )

    # 👉 Виводимо в термінал список груп, яким буде надіслано нагадування
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow_weekday = tomorrow.weekday()
    day = tomorrow.day
    month = months_ukr[tomorrow.month]
    tomorrow_str = f"{day} {month}"

    print("\n🔍 Групи, яким буде надіслано нагадування завтра:")
    for group in groups:
        if int(group["weekday"]) == tomorrow_weekday:
            print(f"🟢 Chat ID: {group['chat_id']}, час: {group['lesson_time']}")
        else:
            pass

    print("------")

# Парсер для дня тижня в текстовому форматі (укр)
weekday_map = {
    "ПН": 0, "ВТ": 1, "СР": 2, "ЧТ": 3, "ПТ": 4, "СБ": 5, "НД": 6
}

# Додає новий рядок у таблицю груп, якщо ще немає
def append_new_group_if_not_exists(chat_id, group_name):
    client = get_gspread_client()
    sheet = client.open("groups_schedule").sheet1

    existing_records = sheet.get_all_records()
    existing_chat_ids = {str(row["chat_id"]) for row in existing_records}

    if str(chat_id) in existing_chat_ids:
        print(f"ℹ️ Chat ID {chat_id} вже є в таблиці.")
        return

    # --- парсинг ---
    try:
        match = re.search(r"\((.*?)\)", group_name)
        if not match:
            raise ValueError("Немає дужок")

        content = match.group(1).strip()

        if "," in content:
            day_part, time_part = map(str.strip, content.split(","))
        else:
            parts = content.split()
            if len(parts) != 2:
                raise ValueError("Невідомий формат")
            day_part, time_part = parts

        weekday = weekday_map.get(day_part.upper())
        lesson_time = time_part

        if weekday is None:
            raise ValueError("Невідомий день тижня")

    except Exception as e:
        print(f"⚠️ Не вдалося розпарсити '{group_name}': {e}")
        return

    new_row = [
        group_name,
        str(chat_id),
        weekday,
        lesson_time,
        "",  # zoom_link
        ""   # materials_link
    ]

    sheet.append_row(new_row)
    print(f"✅ Додано нову групу: {group_name}")


# Обробник команди getid
async def get_chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

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
    # Спроба додати в таблицю
    append_new_group_if_not_exists(chat_id, chat_title)

# Шаблони ддя повідомлень
greetings = [
    "Привітики, друзі! 🐼", "Привітики! 👋", "Хеей!😋",
    "Вітання, друзі! 😍", "Салют!✨", "Привіт! Як справи?🙂", "Добридень!☀️", "Усім привіт!🤗"
]
endings = [
    "Бажаємо затишного дня!☕️", "Гарного дня та приємних несподіванок! 🎁",
    "Бажаємо вдалого дня 🌟 ", "До зустрічі!💜", "Бажаємо приємного дня!🌻", "Гарного дня!😋", "Вдалого дня!💫"
]
stickers = ["📒", "😎", "👩‍🚀", "📚", "🍀", "🌈", '📌',
            '🌼', '⚡️', '👉', '👀', '🧑‍💻', '🐈', '😺', '🛋', '🎀', '🩵', '📘']

months_ukr = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}

# Глобальна змінна для контролю над надсиланням
sent_today_date = None

# 📬 Надсилання нагадувань
groups = read_schedule_from_sheet()
async def send_group_reminders(bot: Bot):
    global sent_today_date
    groups = read_schedule_from_sheet()

    today = datetime.datetime.now().date()
    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
    tomorrow_weekday = tomorrow.weekday()

    day = tomorrow.day
    month = months_ukr[tomorrow.month]
    tomorrow_str = f"{day} {month}"

    sent = False

    for group in groups:
        # Розпакування
        chat_id = group["chat_id"]
        weekday = int(group["weekday"])
        lesson_time = group["lesson_time"]
        zoom = group.get("zoom_link")
        gdrive = group.get("materials_link")

        # Вітання і завершення (рандомно)
        greeting = random.choice(greetings)
        ending = random.choice(endings)
        stiker = random.choice(stickers)

        if group["weekday"] == tomorrow_weekday:
            # Формування повідомлення
            message = f"{greeting}\n\n" \
                      f"{stiker}Нагадуємо, що завтра, {tomorrow_str}, о {lesson_time} ми чекаємо вас на занятті"

            if zoom:
                message += f"\n\n🔗 Посилання для підключення – {zoom}"
            if gdrive:
                message += f"\n\n🔹 Матеріали занять – {gdrive}"

            message += f"\n\n{ending}"

            try:
                await bot.send_message(chat_id=chat_id, text=message)
                print(f"✅ Надіслано в групу {chat_id}")
                sent = True
            except Exception as e:
                print(f"❌ Не вдалося надіслати в {chat_id}: {e}")
                continue

    if sent:
        sent_today_date = today  # тут оновлюємо дату, якщо хоча б одне повідомлення надіслане

    return sent

async def handle_send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global sent_today_date
    groups = read_schedule_from_sheet()

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


# команда для розсилки всім наявним чатам в groups
async def handle_send_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_for_send_all_message
    groups = read_schedule_from_sheet()

    user_id = update.effective_user.id

    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text(
            "🙃 Упс! Лише обрані мають силу керувати цим ботом Академії CONTACT 🤖"
        )
        return

    waiting_for_send_all_message = True

    await update.message.reply_text(
        "✍️ Напиши повідомлення, яке хочеш розіслати в усі групи 📩"
    )

async def handle_send_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global waiting_for_send_all_message
    groups = read_schedule_from_sheet()

    if not waiting_for_send_all_message:
        return

    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return

    waiting_for_send_all_message = False

    source_message = update.message

    # ⏱️ Даємо Telegram стабілізувати custom emoji
    await asyncio.sleep(1)

    sent_count = 0

    for group in groups:
        try:
            await context.bot.copy_message(
                chat_id=group["chat_id"],
                from_chat_id=source_message.chat.id,
                message_id=source_message.message_id
            )
            sent_count += 1
        except Exception as e:
            print(f"❌ Не вдалося надіслати в {group['chat_id']}: {e}")

    await update.message.reply_text(
        f"✅ Повідомлення надіслано в {sent_count} груп(и)."
    )

async def send_today_reminders(bot: Bot):
    groups = read_schedule_from_sheet()
    today_datetime = datetime.datetime.now()
    today = today_datetime.date()
    today_weekday = today_datetime.weekday()

    day = today_datetime.day
    month = months_ukr[today_datetime.month]
    today_str = f"{day} {month}"

    sent = False

    for group in groups:
        chat_id = group["chat_id"]
        weekday = int(group["weekday"])
        lesson_time = group["lesson_time"]
        zoom = group.get("zoom_link")
        gdrive = group.get("materials_link")

        greeting = random.choice(greetings)
        ending = random.choice(endings)
        stiker = random.choice(stickers)

        if weekday == today_weekday:
            message = (
                f"{greeting}\n\n"
                f"{stiker}Нагадуємо, що сьогодні, {today_str}, о {lesson_time} ми чекаємо вас на занятті"
            )

            if zoom:
                message += f"\n\n🔗 Посилання для підключення – {zoom}"
            if gdrive:
                message += f"\n\n🔹 Матеріали занять – {gdrive}"

            message += f"\n\n{ending}"

            await bot.send_message(chat_id=chat_id, text=message)
            print(f"✅ Надіслано сьогодні в групу {chat_id}")
            sent = True

    return sent

async def handle_send_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("🙃 Доступ заборонено")
        return

    sent = await send_today_reminders(context.bot)

    if sent:
        await update.message.reply_text("✅ Нагадування на сьогодні надіслано.")
    else:
        await update.message.reply_text("ℹ️ Сьогодні немає груп.")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Додаємо хендлери
    app.add_handler(CommandHandler("start", handle_start_command))
    app.add_handler(CommandHandler("send", handle_send_command))
    app.add_handler(CommandHandler("send_today_reminders", handle_send_today))
    app.add_handler(CommandHandler("getid", get_chat_id_handler))
    app.add_handler(CommandHandler("send_all", handle_send_all))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_send_all_message)
    )

    print("""🤖 Бот працює! Напиши /start або /send у Telegram.
    P.S За потреби запусти команду getid в чатах, щоб отримати id чату для додавання його до коду""")


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


import nest_asyncio
import asyncio

nest_asyncio.apply()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

