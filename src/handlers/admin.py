# src/handlers/admin.py
import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
                           filters)

from src.database import crud
from src.database.database import get_db
from src.config import logger, ADMIN_IDS, ROLE_DRIVER
from src.keyboards import reply as reply_kb
from .common import cancel

# Определим состояния для диалогов админа (если нужны)
ASK_DRIVER_ID_TO_ADD, ASK_DRIVER_ID_TO_BLOCK, ASK_DRIVER_ID_TO_UNBLOCK = range(20, 23)

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню администратора."""
    user = update.effective_user
    # Дополнительная проверка, что пользователь действительно админ
    if user.id not in ADMIN_IDS:
        logger.warning(f"Попытка доступа к админ-панели пользователем {user.id}")
        return # Ничего не делаем

    await update.message.reply_text(" FONT="monospace"> Панель администратора:", reply_markup=reply_kb.markup_admin_main)

# --- Управление водителями ---

async def list_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит список водителей."""
    user = update.effective_user
    if user.id not in ADMIN_IDS: return

    db = next(get_db())
    drivers = crud.get_all_drivers(db)

    if not drivers:
        await update.message.reply_text("В системе нет зарегистрированных водителей.")
        return

    message = " FONT="monospace"> Список водителей:\n\n"
    for i, driver in enumerate(drivers, 1):
        profile = driver.driver_profile
        car_info = f"{profile.car_make} {profile.car_model} ({profile.car_plate})" if profile else "Нет данных об авто"
        status = " FONT="monospace"> [Заблокирован]" if driver.is_blocked else ""
        message += (f"{i}. {driver.full_name} (ID: {driver.telegram_id})\n"
                    f"    FONT="monospace"> Телефон: {driver.phone_number}\n"
                    f"    FONT="monospace"> Авто: {car_info}{status}\n\n")

    # Отправка может быть слишком длинной, надо разбивать
    # Пока отправляем как есть
    if len(message) > 4000: # Примерный лимит Telegram
         await update.message.reply_text("Слишком много водителей для отображения одним сообщением.")
         # Здесь нужна логика разбивки сообщения
    else:
         await update.message.reply_text(message)


async def add_driver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог добавления водителя: спрашивает ID."""
    user = update.effective_user
    if user.id not in ADMIN_IDS: return ConversationHandler.END

    await update.message.reply_text(
        "Введите Telegram ID пользователя, которого хотите назначить водителем:",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_DRIVER_ID_TO_ADD

async def add_driver_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает ID и назначает роль водителя."""
    admin = update.effective_user
    if admin.id not in ADMIN_IDS: return ConversationHandler.END

    try:
        target_user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный ID. Введите числовой Telegram ID.")
        return ASK_DRIVER_ID_TO_ADD

    db = next(get_db())
    target_user = crud.get_user_by_telegram_id(db, target_user_id)

    if not target_user:
        await update.message.reply_text(f"Пользователь с ID {target_user_id} не найден в базе бота.")
        # return ASK_DRIVER_ID_TO_ADD # Дать шанс ввести снова? Или завершить?
        return ConversationHandler.END
    if target_user.role == ROLE_DRIVER:
        await update.message.reply_text(f"Пользователь {target_user.full_name} (ID: {target_user_id}) уже является водителем.")
        return ConversationHandler.END

    # Меняем роль
    updated_user = crud.update_user_role(db, target_user_id, ROLE_DRIVER)
    if updated_user:
        logger.info(f"Администратор {admin.id} назначил {target_user_id} водителем.")
        await update.message.reply_text(f"✅ Пользователь {updated_user.full_name} (ID: {target_user_id}) назначен водителем.")
        # Уведомить пользователя?
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=" FONT="monospace"> Администратор назначил вас водителем!\n"
                     " FONT="monospace"> Теперь вам доступны функции водителя. Если вы еще не добавили данные об авто, используйте /register_driver."
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {target_user_id} о назначении водителем: {e}")
    else:
        await update.message.reply_text(f"Не удалось обновить роль для пользователя {target_user_id}.")

    await admin_menu(update, context) # Возврат в админ меню
    return ConversationHandler.END


async def block_driver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог блокировки: спрашивает ID."""
    user = update.effective_user
    if user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("Введите Telegram ID водителя для блокировки:", reply_markup=reply_kb.markup_cancel)
    return ASK_DRIVER_ID_TO_BLOCK

async def block_driver_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает ID и блокирует пользователя."""
    admin = update.effective_user
    if admin.id not in ADMIN_IDS: return ConversationHandler.END

    try:
        target_user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный ID.")
        return ASK_DRIVER_ID_TO_BLOCK

    db = next(get_db())
    user_to_block = crud.block_user(db, target_user_id, block_status=True)

    if user_to_block:
        logger.info(f"Администратор {admin.id} заблокировал пользователя {target_user_id}")
        await update.message.reply_text(f"✅ Пользователь {user_to_block.full_name} (ID: {target_user_id}) заблокирован.")
        # Уведомить пользователя о блокировке?
        try:
            await context.bot.send_message(chat_id=target_user_id, text="❌ Ваш аккаунт был заблокирован администратором.")
        except Exception as e:
             logger.error(f"Не удалось уведомить пользователя {target_user_id} о блокировке: {e}")
    else:
        await update.message.reply_text(f"Пользователь с ID {target_user_id} не найден или произошла ошибка.")

    await admin_menu(update, context)
    return ConversationHandler.END


async def unblock_driver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог разблокировки: спрашивает ID."""
    user = update.effective_user
    if user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("Введите Telegram ID пользователя для разблокировки:", reply_markup=reply_kb.markup_cancel)
    return ASK_DRIVER_ID_TO_UNBLOCK

async def unblock_driver_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает ID и разблокирует пользователя."""
    admin = update.effective_user
    if admin.id not in ADMIN_IDS: return ConversationHandler.END

    try:
        target_user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Некорректный ID.")
        return ASK_DRIVER_ID_TO_UNBLOCK

    db = next(get_db())
    user_to_unblock = crud.block_user(db, target_user_id, block_status=False)

    if user_to_unblock:
        logger.info(f"Администратор {admin.id} разблокировал пользователя {target_user_id}")
        await update.message.reply_text(f"✅ Пользователь {user_to_unblock.full_name} (ID: {target_user_id}) разблокирован.")
        # Уведомить пользователя о разблокировке?
        try:
            await context.bot.send_message(chat_id=target_user_id, text="✅ Ваш аккаунт был разблокирован администратором.")
        except Exception as e:
             logger.error(f"Не удалось уведомить пользователя {target_user_id} о разблокировке: {e}")
    else:
        await update.message.reply_text(f"Пользователь с ID {target_user_id} не найден или произошла ошибка.")

    await admin_menu(update, context)
    return ConversationHandler.END

# --- Conversation Handlers для админских действий ---
add_driver_conv = ConversationHandler(
    entry_points=[CommandHandler('add_driver', add_driver_start, filters=filters.User(ADMIN_IDS))],
    states={
        ASK_DRIVER_ID_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_driver_id_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
block_driver_conv = ConversationHandler(
    entry_points=[CommandHandler('block_driver', block_driver_start, filters=filters.User(ADMIN_IDS))],
    states={
        ASK_DRIVER_ID_TO_BLOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_driver_id_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)
unblock_driver_conv = ConversationHandler(
    entry_points=[CommandHandler('unblock_driver', unblock_driver_start, filters=filters.User(ADMIN_IDS))],
    states={
        ASK_DRIVER_ID_TO_UNBLOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, unblock_driver_id_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# --- Список хендлеров администратора ---
admin_handlers = [
    CommandHandler('admin', admin_menu, filters=filters.User(ADMIN_IDS)),
    CommandHandler('list_drivers', list_drivers, filters=filters.User(ADMIN_IDS)),
    add_driver_conv,
    block_driver_conv,
    unblock_driver_conv,
    # Обработчики для кнопок ReplyKeyboard
    MessageHandler(filters.Regex('^/list_drivers$') & filters.User(ADMIN_IDS), list_drivers),
    MessageHandler(filters.Regex('^/add_driver$') & filters.User(ADMIN_IDS), add_driver_start),
    MessageHandler(filters.Regex('^/block_driver$') & filters.User(ADMIN_IDS), block_driver_start),
    MessageHandler(filters.Regex('^/unblock_driver$') & filters.User(ADMIN_IDS), unblock_driver_start),
]
