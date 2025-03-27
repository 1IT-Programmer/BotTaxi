# src/handlers/common.py
import logging
from telegram import Update, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from src.database import crud
from src.database.database import get_db
from src.config import (logger, ADMIN_IDS, ROLE_ADMIN, ROLE_DRIVER, ROLE_PASSENGER,
                        ASK_PHONE, ASK_FULL_NAME, REGISTRATION_COMPLETE, CHOOSE_ACTION)
from src.keyboards import reply as reply_kb
from src.keyboards import inline as inline_kb
from .passenger import passenger_menu # Импортируем функции меню
from .driver import driver_menu
from .admin import admin_menu

# --- Регистрация ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Обработчик команды /start. Проверяет регистрацию."""
    user_tg = update.effective_user
    logger.info(f"Пользователь {user_tg.id} ({user_tg.username or 'no_username'}) запустил /start")
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user_tg.id)

    if db_user:
        if db_user.is_blocked:
            await update.message.reply_text("❌ Ваш аккаунт заблокирован администратором.")
            return ConversationHandler.END

        # Пользователь найден, показываем меню согласно роли
        logger.info(f"Пользователь {user_tg.id} уже зарегистрирован как {db_user.role}")
        if db_user.telegram_id in ADMIN_IDS:
            # Если ID в списке админов, даем админские права (даже если роль другая)
            if db_user.role != ROLE_ADMIN:
                crud.update_user_role(db, db_user.telegram_id, ROLE_ADMIN)
            await admin_menu(update, context)
        elif db_user.role == ROLE_DRIVER:
            await driver_menu(update, context)
        else: # ROLE_PASSENGER по умолчанию
            await passenger_menu(update, context)
        # Завершаем разговор, если он был активен, или просто выходим
        # Это зависит от того, может ли /start прервать другие диалоги
        # Если start НЕ должен прерывать, то не возвращаем ConversationHandler.END
        # Если может быть вызван во время другого диалога, нужно его завершить
        # Для простоты пока считаем, что /start может быть вызван только вне диалога
        # или он начинает новый диалог регистрации
        # return CHOOSE_ACTION # Переход в состояние ожидания действия (если нужно)
        return ConversationHandler.END # Завершаем, если был диалог

    else:
        # Новый пользователь, начинаем регистрацию
        logger.info(f"Новый пользователь {user_tg.id}. Начинаем регистрацию.")
        await update.message.reply_text(
            " FONT="monospace"> Добро пожаловать в бот междугородних перевозок!\n"
            " FONT="monospace"> Для начала работы, пожалуйста, поделитесь вашим номером телефона.",
            reply_markup=reply_kb.markup_request_contact
        )
        return ASK_PHONE # Переходим к ожиданию номера телефона

async def ask_phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает контакт (номер телефона)."""
    contact = update.message.contact
    user_tg = update.effective_user
    if not contact or contact.user_id != user_tg.id:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопку ниже, чтобы поделиться своим контактом.",
            reply_markup=reply_kb.markup_request_contact
        )
        return ASK_PHONE

    context.user_data['phone_number'] = contact.phone_number
    logger.info(f"Получен номер телефона {contact.phone_number} от {user_tg.id}")

    await update.message.reply_text(
        " FONT="monospace"> Отлично! Теперь введите ваше ФИО (Фамилия Имя Отчество).",
        reply_markup=ReplyKeyboardRemove() # Убираем кнопку запроса контакта
    )
    return ASK_FULL_NAME # Переходим к ожиданию ФИО

async def ask_full_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает ФИО и завершает регистрацию."""
    full_name = update.message.text
    user_tg = update.effective_user
    phone_number = context.user_data.get('phone_number')

    if not full_name or len(full_name) < 5: # Простая проверка
        await update.message.reply_text("Пожалуйста, введите корректное ФИО.")
        return ASK_FULL_NAME

    if not phone_number:
        logger.error(f"Не найден номер телефона в context.user_data для {user_tg.id} на шаге ФИО.")
        await update.message.reply_text("Произошла ошибка. Попробуйте начать сначала /start")
        return ConversationHandler.END

    logger.info(f"Получено ФИО '{full_name}' от {user_tg.id}")

    db = next(get_db())
    try:
        db_user = crud.create_user(db, user_tg.id, full_name.strip(), phone_number)
        logger.info(f"Пользователь {user_tg.id} успешно зарегистрирован.")
        context.user_data.clear() # Очищаем временные данные

        await update.message.reply_text(
            f" FONT="monospace"> Регистрация завершена, {db_user.full_name}!\n"
            " FONT="monospace"> Вы зарегистрированы как пассажир."
        )
        # Показываем меню пассажира
        await passenger_menu(update, context)
        return ConversationHandler.END # Завершаем диалог регистрации

    except Exception as e:
        logger.error(f"Ошибка при создании пользователя {user_tg.id}: {e}")
        await update.message.reply_text("Произошла ошибка при регистрации. Попробуйте позже.")
        context.user_data.clear()
        return ConversationHandler.END

async def registration_fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает некорректный ввод во время регистрации."""
    current_state = context.user_data.get('state') # Нужно будет сохранять состояние
    logger.warning(f"Некорректный ввод от {update.effective_user.id} в состоянии регистрации {current_state}")
    await update.message.reply_text("Некорректный ввод. Пожалуйста, следуйте инструкциям или нажмите /cancel для отмены.")
    # Возвращаем то же состояние, чтобы пользователь попробовал снова
    # Это требует сохранения текущего состояния в context.user_data или использования ConversationHandler state
    return ASK_PHONE # Или другое релевантное состояние


# --- Общие команды ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с помощью."""
    # Текст помощи нужно будет дополнить
    help_text = (
        " FONT="monospace"> Доступные команды:\n"
        "/start - Начать работу с ботом / Показать главное меню\n"
        "/find_trip - Найти поездку (для пассажиров)\n"
        "/my_bookings - Мои бронирования (для пассажиров)\n"
        "/create_trip - Создать поездку (для водителей)\n"
        "/my_trips - Мои поездки (для водителей)\n"
        "/register_driver - Стать водителем\n"
        "/support - Написать в поддержку\n"
        "/help - Показать это сообщение\n"
        "/cancel - Отменить текущее действие (в диалогах)"
    )
    await update.message.reply_text(help_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог ConversationHandler."""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} отменил диалог.")
    # Очищаем user_data, если там хранились временные данные диалога
    # context.user_data.clear() # Делать осторожно, если там есть и постоянные данные
    await update.message.reply_text(
        "Действие отменено.", reply_markup=ReplyKeyboardRemove() # Убираем спец. клавиатуру, если была
    )
    # Нужно показать основное меню после отмены
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    if db_user:
         if db_user.role == ROLE_ADMIN or db_user.telegram_id in ADMIN_IDS:
              await admin_menu(update, context)
         elif db_user.role == ROLE_DRIVER:
              await driver_menu(update, context)
         else:
              await passenger_menu(update, context)

    return ConversationHandler.END # Завершает диалог

# --- Обработчик регистрации ---
registration_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)], # /start начинает диалог, если юзер не найден
    states={
        ASK_PHONE: [MessageHandler(filters.CONTACT, ask_phone_handler)],
        ASK_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_full_name_handler)],
        # Можно добавить состояния для повторного запроса, если ввод некорректен
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        # Обработчик для любого другого сообщения в процессе регистрации
        MessageHandler(filters.TEXT | filters.COMMAND | filters.VIDEO | filters.PHOTO | filters.Document, registration_fallback_handler)
        ],
    # persistent=True, name="registration_conversation" # Для хранения между перезапусками (требует настройки)
    # allow_reentry=True # Позволяет войти в диалог снова по /start
)
