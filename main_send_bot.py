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
from openai import OpenAI

# nest_asyncio потрібен тільки для локального запуску (polling) на Python 3.10+
# На Render (webhook) він не використовується
if not os.environ.get("PORT"):
    import nest_asyncio
    nest_asyncio.apply()

# 🔐 Token і дозвіл тільки для акаунту https://t.me/contact_academy

load_dotenv()  # Завантажуємо .env

BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID'))  # перетворюємо в int, бо ID число
ADMIN_CHAT_ID = ALLOWED_USER_ID  # для нових команд

# Нові змінні для LLM-функцій (тільки тестові групи)
TEST_GROUP_IDS = {int(x) for x in os.getenv("TEST_GROUP_IDS", "").split(",") if x.strip()}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ліміт викликів LLM на користувача (в пам’яті, скидається при рестарті)
user_llm_calls = {}  # user_id -> count today
MAX_LLM_CALLS_PER_USER = 3

waiting_for_send_all_message = False

# OpenAI клієнт (створюємо тільки якщо ключ є)
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)


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


# ==================== LLM FEATURES (тільки тестові групи) ====================

def get_diverse_it_fact():
    """Генерує випадковий цікавий факт про IT українською для дітей."""
    if not openai_client:
        return "⚠️ OpenAI ключ не налаштовано."

    topics = [
        "cybersecurity and staying safe online",
        "robotics and how robots work",
        "game development and how video games are made",
        "artificial intelligence and future tech",
        "how the internet actually works (cables, servers, etc.)",
        "3d-visualizations or modeling",
        "3d animation",
        "graphic design"
    ]
    styles = [
        "a fun and educational fact",
        "a short and funny story",
        "an amazing 'did you know' fact",
        "a simple explanation of a complex concept",
        "interesting facts for children on IT topic"
    ]

    topic = random.choice(topics)
    style = random.choice(styles)

    prompt = f"Tell {style} about {topic} for children aged 10–14. Your response MUST be in Ukrainian language. Add emoji. Start with a new sentence, do not answer the prompt directly."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ти — дружній IT-помічник, який пояснює складні технології дітям простою та цікавою українською мовою."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "❌ Не вдалося згенерувати факт. Спробуй пізніше."


def get_coding_game():
    """Генерує просту логічну задачу / гру з кодом для дітей."""
    if not openai_client:
        return "⚠️ OpenAI ключ не налаштовано.", None

    prompt = """Create a simple and fun coding or logic puzzle for children aged 10-14 about programming.
Make it interactive: give a short problem, then ask a question.
At the end, on a new line, write the correct answer in the format: ANSWER: <correct answer>
The whole response MUST be in Ukrainian. Add some emoji. Keep it short and engaging."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ти — веселий учитель програмування для дітей. Створюй прості, цікаві задачі українською."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        full = response.choices[0].message.content
        # Спроба відокремити відповідь
        if "ANSWER:" in full:
            parts = full.split("ANSWER:")
            question = parts[0].strip()
            answer = parts[1].strip()
            return question, answer
        return full, None
    except Exception as e:
        print(f"OpenAI game error: {e}")
        return "❌ Не вдалося згенерувати гру. Спробуй пізніше.", None


# Просте сховище очікуваних відповідей на гру (user_id -> correct_answer)
pending_game_answers = {}


async def check_llm_access(update: Update) -> bool:
    """Перевірка: чи це тестова група + ліміт викликів."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in TEST_GROUP_IDS:
        await update.message.reply_text("🚫 Ця команда доступна тільки в тестових групах.")
        return False

    # Ліміт
    today = datetime.date.today()
    key = (user_id, today)
    count = user_llm_calls.get(key, 0)
    if count >= MAX_LLM_CALLS_PER_USER:
        await update.message.reply_text(f"⏳ Ліміт {MAX_LLM_CALLS_PER_USER} викликів на сьогодні вичерпано. Спробуй завтра!")
        return False

    user_llm_calls[key] = count + 1
    return True


async def handle_interest_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_llm_access(update):
        return

    await update.message.reply_text("🤔 Генерую цікавий факт...")
    fact = get_diverse_it_fact()
    await update.message.reply_text(fact)


async def handle_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_llm_access(update):
        return

    await update.message.reply_text("🎮 Генерую гру...")
    question, answer = get_coding_game()
    if answer:
        pending_game_answers[update.effective_user.id] = answer
        await update.message.reply_text(question + "\n\n✍️ Напиши свою відповідь командою /game_answer <відповідь>")
    else:
        await update.message.reply_text(question)


async def handle_game_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_llm_access(update):
        return

    user_id = update.effective_user.id
    if user_id not in pending_game_answers:
        await update.message.reply_text("Спочатку згенеруй гру командою /game")
        return

    user_answer = " ".join(context.args).strip().lower() if context.args else ""
    correct = pending_game_answers[user_id].lower()

    if user_answer and user_answer in correct or correct in user_answer:
        await update.message.reply_text("✅ Правильно! Молодець! 🎉")
    else:
        await update.message.reply_text(f"❌ Не зовсім. Правильна відповідь: {pending_game_answers[user_id]}")

    del pending_game_answers[user_id]


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Старі хендлери (не чіпаємо)
    app.add_handler(CommandHandler("start", handle_start_command))
    app.add_handler(CommandHandler("send", handle_send_command))
    app.add_handler(CommandHandler("send_today_reminders", handle_send_today))
    app.add_handler(CommandHandler("getid", get_chat_id_handler))
    app.add_handler(CommandHandler("send_all", handle_send_all))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_send_all_message)
    )

    # Нові LLM-хендлери (тільки тестові групи)
    app.add_handler(CommandHandler("interest_fact", handle_interest_fact))
    app.add_handler(CommandHandler("game", handle_game))
    app.add_handler(CommandHandler("game_answer", handle_game_answer))

    print("""🤖 Бот працює! Напиши /start або /send у Telegram.
    P.S За потреби запусти команду getid в чатах, щоб отримати id чату для додавання його до коду""")


    if os.environ.get('PORT'):
        PORT = int(os.environ.get('PORT', 8443))
        webhook_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://contact-telegram-bot.onrender.com')
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=webhook_url
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
