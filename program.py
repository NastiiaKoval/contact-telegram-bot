import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import random
import pytz

# Тут можна налаштувати посилання на заняття та матеріали для кожної групи
GROUPS_INFO = {
    'група_1': {
        'day': 'СБ',
        'zoom_link': 'https://us02web.zoom.us/j/7341839862?pwd=WFprdWdhbXZKME9IZ0ZtUlNTWjh2UT09',
        'materials_link': 'https://drive.google.com/drive/folders/1S8UPhpbO_m1tCKNfVCtjPfcrcgKzcoTu?usp=drive_link'
    },
    'група_2': {
        'day': 'НД',
        'zoom_link': 'https://us02web.zoom.us/j/8123749823?pwd=WFprdWdhbXZKME9IZ0ZtUlNTWjh2UT10',
        'materials_link': 'https://drive.google.com/drive/folders/2B8JQypQH_m1tEKNdFCvjPfrdgKyzgoRu?usp=drive_link'
    },
    # Додайте інші групи за потреби
}

# Заготовки повідомлень
REMINDER_MESSAGES = [
    "Друзі, привіт! 🐸\n\nНагадуємо, що завтра о 10:00 зустрічаємось на занятті!\n\n✏️  Посилання для підключення: {zoom_link}\n👀  Матеріали занять: {materials_link}\n\nВсім гарного настрою! ↗️",
    # Додайте інші шаблони
]


def start(update: Update, context: CallbackContext) -> None:
    """Вітальне повідомлення при запуску бота."""
    update.message.reply_text(
        'Привіт! Я нагадуватиму про заняття в групах. Використовуйте команду /set для налаштування нагадувань.')


def send_reminders(context: CallbackContext) -> None:
    """Відправляє нагадування в усі групи за день до заняття."""
    now = datetime.datetime.now(pytz.timezone('Europe/Kiev'))
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_day = tomorrow.strftime('%a').upper()  # Отримуємо наступний день

    for group, info in GROUPS_INFO.items():
        if info['day'] == tomorrow_day:
            # Вибираємо випадкове повідомлення
            message = random.choice(REMINDER_MESSAGES).format(
                zoom_link=info['zoom_link'],
                materials_link=info['materials_link']
            )
            context.bot.send_message(chat_id=group, text=message)


def set_reminders(update: Update, context: CallbackContext) -> None:
    """Команда для запуску нагадувань о заданій годині щодня."""
    # Встановлює відправку нагадувань кожного дня о 18:00
    time = datetime.time(hour=18, minute=0, tzinfo=pytz.timezone('Europe/Kiev'))
    context.job_queue.run_daily(send_reminders, time)
    update.message.reply_text('Нагадування встановлені на щоденне відправлення о 18:00!')


def main() -> None:
    """Запускає бота."""
    updater = Updater("YOUR_BOT_TOKEN")
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("set", set_reminders))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
