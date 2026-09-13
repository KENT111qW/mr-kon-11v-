import os
import logging
from dotenv import load_dotenv

import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Убираем шум от httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Токены берутся только из окружения (.env)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Системный промпт для учителя информатики
SYSTEM_INSTRUCTION = (
    "Ты — Мистер Кон Ча Янь, дружелюбный учитель информатики для школы 11В в Казахстане. "
    "Отвечаешь на русском языке, просто и понятно для школьников с 4 по 11 класс. "
    "Объясняешь на примерах из жизни, даешь примеры кода на Scratch/Python если просят. "
    "Тематика: компьютер, алгоритмы, программирование, интернет, безопасность, Office, логика. "
    "Если вопрос не по информатике — мягко возвращай к информатике."
)

# Инициализация модели Gemini (ленивая, при первом запросе)
_gemini_model = None


def get_gemini_model():
    """Получить или создать модель Gemini с системным промптом."""
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    if not GEMINI_API_KEY:
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    _gemini_model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        system_instruction=SYSTEM_INSTRUCTION,
    )
    return _gemini_model


# Команда /start - приветствие
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    text = (
        "Привет! Я — Мистер Кон Ча Янь, твой учитель информатики из 11В.\n\n"
        "Помогаю разобраться с информатикой для 4-11 классов: "
        "алгоритмы, программирование (Scratch / Python), устройство компьютера, "
        "интернет, безопасность, Office и логика.\n\n"
        "Просто напиши свой вопрос — например: \"Что такое алгоритм?\" или \"Как сделать цикл в Python?\"\n\n"
        "Команды:\n"
        "/start — это приветствие\n"
        "/help — как спрашивать\n"
        "/about — о боте"
    )
    await update.message.reply_text(text)


# Команда /help - как пользоваться
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    text = (
        "Как спрашивать у Мистера Кон Ча Янь:\n\n"
        "1. Просто напиши вопрос текстом, например:\n"
        "   — Что такое двоичная система?\n"
        "   — Объясни, что такое переменная в Python\n"
        "   — Как безопасно пользоваться интернетом?\n\n"
        "2. Я отвечаю просто и с примерами из жизни.\n"
        "3. Если хочешь пример кода — скажи \"покажи пример на Python\" или \"покажи в Scratch\".\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/help — эта подсказка\n"
        "/about — о боте\n\n"
        "Совет: формулируй вопрос конкретно, и я объясню пошагово."
    )
    await update.message.reply_text(text)


# Команда /about - о боте
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /about."""
    text = (
        "О боте «11В. Мистер Кон Ча Янь»\n\n"
        "Это учебный помощник по информатике для школы 11В (Казахстан).\n"
        "Подходит для учеников с 4 по 11 класс.\n"
        "Работает на бесплатной модели Google Gemini (gemini-1.5-flash).\n"
        "Язык общения — русский.\n\n"
        "Автор идеи — учитель информатики 11В.\n"
        "Бот отвечает на вопросы по информатике и мягко возвращает к теме, "
        "если вопрос не по предмету."
    )
    await update.message.reply_text(text)


# Обработка текстовых вопросов - обращение к Gemini
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений - отправляет вопрос в Gemini."""
    # Проверяем наличие ключа
    if not GEMINI_API_KEY:
        await update.message.reply_text(
            "Ключ GEMINI_API_KEY не настроен. Попроси учителя проверить настройки бота."
        )
        return

    user_text = update.message.text.strip() if update.message.text else ""
    if not user_text:
        await update.message.reply_text("Напиши вопрос текстом, и я постараюсь помочь!")
        return

    # Очень длинные сообщения обрезаем, чтобы не превысить лимиты
    if len(user_text) > 4000:
        user_text = user_text[:4000]
        await update.message.reply_text("Вопрос был длинный — взял первые 4000 символов.")

    model = get_gemini_model()
    if model is None:
        await update.message.reply_text("Ошибка настройки модели. Обратись к учителю.")
        return

    # Показываем индикатор набора
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Генерация ответа
        response = await model.generate_content_async(user_text)
        answer = response.text.strip() if response.text else ""

        if not answer:
            answer = "Не получилось сформировать ответ. Попробуй переформулировать вопрос."

        # Ограничение Telegram ~4096 символов, режем аккуратно
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n[Ответ сокращен — был слишком длинный]"

        await update.message.reply_text(answer)

    except Exception as e:
        logger.exception("Ошибка при обращении к Gemini: %s", e)
        # Дружелюбное сообщение без технических деталей
        await update.message.reply_text(
            "Что-то пошло не так при обращении к нейросети. "
            "Попробуй еще раз через минуту. Если повторится — скажи учителю."
        )


# Обработка неподдерживаемых типов сообщений
async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сообщает, что поддерживается только текст."""
    await update.message.reply_text(
        "Я пока понимаю только текстовые вопросы. Напиши вопрос словами!"
    )


def main() -> None:
    """Запуск бота."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан! Заполни .env файл. Смотри .env.example")
        raise SystemExit("TELEGRAM_TOKEN не задан. Заполни .env")

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY не задан — бот запустится, но не сможет отвечать на вопросы.")

    # Создаем приложение
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))

    # Текстовые сообщения (не команды)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Все остальное (фото, стикеры, голосовые и т.д.)
    app.add_handler(MessageHandler(~filters.TEXT, handle_unsupported))

    logger.info("Бот Мистер Кон Ча Янь запущен. Ожидаю сообщения...")
    # Запуск в режиме polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
