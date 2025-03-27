# src/bot.py
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    PicklePersistence, # Для сохранения состояний между перезапусками (опционально)
    Defaults,
    filters
)
from telegram.constants import ParseMode

# Конфигурация и логгер
from src.config import BOT_TOKEN, logger, ADMIN_IDS

# База данных
from src.database import database, crud

# Клавиатуры
from src.keyboards import reply as reply_kb
from src.keyboards import inline as inline_kb

# Обработчики
from src.handlers import common, passenger, driver, admin, support

# --- Основная функция ---
async def post_init(application: Application) -> None:
    """Действия после инициализации приложения (например, установка команд)."""
    await application.bot.set_my_commands([
        ('start', ' FONT="monospace"> Запустить бота / Главное меню'),
        ('find_trip', ' FONT="monospace"> Найти поездку'),
        ('my_bookings', ' FONT="monospace"> Мои бронирования'),
        ('create_trip', ' FONT="monospace"> Создать поездку (для водителей)'),
        ('my_trips', ' FONT="monospace"> Мои поездки (для водителей)'),
        ('register_driver', ' FONT="monospace"> Стать водителем'),
        ('support', ' FONT="monospace"> Связь с поддержкой'),
        ('help', ' FONT="monospace"> Помощь'),
        ('cancel', ' FONT="monospace"> Отменить текущее действие'),
        # Добавить админские команды?
        # ('admin', 'Админ-панель'),
    ])
    logger.info("Команды бота установлены.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибки, вызванные Updates."""
    logger.error(f"Исключение при обработке апдейта {update}:", exc_info=context.error)
    # Можно добавить отправку сообщения об ошибке админам
    # if isinstance(update, Update) and update.effective_user:
    #     user_info = f"User: {update.effective_user.id} (@{update.effective_user.username})"
    # else:
    #     user_info = "N/A"
    # error_message = f"Произошла ошибка:\n{context.error}\nUpdate: {update}\nUser: {user_info}"
    # for admin_id in ADMIN_IDS:
    #     try:
    #         await context.bot.send_message(chat_id=admin_id, text=error_message[:4000])
    #     except Exception as e:
    #         logger.error(f"Не удалось отправить сообщение об ошибке админу {admin_id}: {e}")


def main() -> None:
    """Запуск бота."""
    logger.info("Инициализация базы данных...")
    database.init_db() # Создаем таблицы, если их нет

    # Настройка persistence (опционально, для сохранения user_data/chat_data)
    # persistence = PicklePersistence(filepath="bot_persistence")

    # Установка настроек по умолчанию для парсинга HTML
    defaults = Defaults(parse_mode=ParseMode.HTML)

    logger.info("Сборка приложения бота...")
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        # .persistence(persistence) # Раскомментировать для persistence
        .defaults(defaults)
        .post_init(post_init) # Установка команд после инициализации
        .build()
    )

    # --- Регистрация обработчиков ---
    logger.info("Регистрация обработчиков...")

    # 0. Обработчик ошибок (должен быть первым)
    application.add_error_handler(error_handler)

    # 1. Conversation Handler для регистрации (из common.py)
    # Он включает /start и должен идти перед другими CommandHandler('start')
    application.add_handler(common.registration_conv_handler)

    # 2. Conversation Handler для поддержки (из support.py)
    application.add_handler(support.support_conv_handler)

    # 3. Обработчики администратора (из admin.py)
    # Включают Conversation Handlers для add/block/unblock
    for handler in admin.admin_handlers:
        application.add_handler(handler)

    # 4. Обработчики водителя (из driver.py)
    # Включают Conversation Handlers для регистрации и создания поездки
    for handler in driver.driver_handlers:
        application.add_handler(handler)

    # 5. Обработчики пассажира (из passenger.py)
    # Включают Conversation Handler для поиска и колбэки
    for handler in passenger.passenger_handlers:
        application.add_handler(handler)

    # 6. Общие команды (help, cancel вне диалогов)
    application.add_handler(CommandHandler("help", common.help_command))
    # Отдельный cancel для случаев, когда нет активного диалога
    application.add_handler(CommandHandler("cancel", common.cancel))

    # 7. Обработчик неизвестных команд (должен быть последним среди CommandHandler)
    # async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     await update.message.reply_text(" FONT="monospace"> Неизвестная команда.")
    # application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # 8. Обработчик текстовых сообщений вне команд и диалогов (если нужно)
    # async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #     # Пример: если пользователь просто пишет текст, показываем меню
    #     user_tg_id = update.effective_user.id
    #     db = next(get_db())
    #     db_user = crud.get_user_by_telegram_id(db, user_tg_id)
    #     if db_user:
    #         if db_user.role == ROLE_ADMIN or user_tg_id in ADMIN_IDS: await admin.admin_menu(update, context)
    #         elif db_user.role == ROLE_DRIVER: await driver.driver_menu(update, context)
    #         else: await passenger.passenger_menu(update, context)
    #     else:
    #         # Если не зарегистрирован, может быть стоит снова предложить /start
    #         await update.message.reply_text("Пожалуйста, используйте /start для начала работы.")
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


    # --- Запуск бота ---
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске или работе бота: {e}", exc_info=True)
