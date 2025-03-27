# src/handlers/support.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from src.database import crud
from src.database.database import get_db
from src.config import logger, ADMIN_IDS, SUPPORT_MESSAGE
from .common import cancel # Импорт cancel для fallback

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог поддержки."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)

    if not db_user:
        await update.message.reply_text("Пожалуйста, сначала зарегистрируйтесь с помощью /start.")
        return ConversationHandler.END
    if db_user.is_blocked:
        await update.message.reply_text("Ваш аккаунт заблокирован.")
        return ConversationHandler.END

    logger.info(f"Пользователь {user.id} ({db_user.full_name}) инициировал обращение в поддержку.")
    await update.message.reply_text(
        " FONT="monospace"> Напишите ваше сообщение для администратора. Мы передадим его вместе с вашими контактами.\n"
        " FONT="monospace"> Для отмены введите /cancel.",
        reply_markup=ReplyKeyboardRemove() # Или можно добавить кнопку Cancel
    )
    return SUPPORT_MESSAGE # Переходим в состояние ожидания сообщения

async def support_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает сообщение пользователя и пересылает админам."""
    user = update.effective_user
    message_text = update.message.text
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)

    if not db_user: # Доп. проверка
        return ConversationHandler.END
    if not message_text:
         await update.message.reply_text("Пожалуйста, введите текстовое сообщение.")
         return SUPPORT_MESSAGE # Остаемся в том же состоянии

    logger.info(f"Получено сообщение поддержки от {user.id}: {message_text[:50]}...")

    support_header = (
        f" FONT="monospace"> === Обращение в поддержку ===\n"
        f" FONT="monospace"> От: {db_user.full_name} (ID: {user.id})\n"
        f" FONT="monospace"> Телефон: {db_user.phone_number}\n"
        f" FONT="monospace"> Telegram: @{user.username or 'нет'}\n"
        f" FONT="monospace"> ==========================="
    )
    full_support_message = f"{support_header}\n\n{message_text}"

    if not ADMIN_IDS:
        logger.warning("Нет ADMIN_IDS для отправки сообщения поддержки.")
        await update.message.reply_text(
            "К сожалению, в данный момент нет доступных администраторов для обработки вашего запроса."
        )
        return ConversationHandler.END

    message_sent_to_admin = False
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=full_support_message
            )
            message_sent_to_admin = True
            logger.info(f"Сообщение поддержки от {user.id} отправлено администратору {admin_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение поддержки админу {admin_id}: {e}")

    if message_sent_to_admin:
        await update.message.reply_text(
            "✅ Ваше сообщение передано администратору. Ожидайте ответа (если он потребуется)."
        )
    else:
        await update.message.reply_text(
             "Произошла ошибка при передаче вашего сообщения. Пожалуйста, попробуйте позже."
        )

    # Возвращаем пользователя в основное меню после отправки
    if db_user.role == ROLE_DRIVER:
        from .driver import driver_menu
        await driver_menu(update, context)
    else:
        from .passenger import passenger_menu
        await passenger_menu(update, context)

    return ConversationHandler.END # Завершаем диалог поддержки


# --- Conversation Handler для поддержки ---
support_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('support', support_start)],
    states={
        SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_message_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
