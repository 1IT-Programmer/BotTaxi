# src/handlers/passenger.py
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters)

from src.database import crud
from src.database.database import get_db
from src.config import (logger, ROLE_PASSENGER, ASK_DEPARTURE_CITY, ASK_ARRIVAL_CITY, ASK_TRIP_DATE)
from src.keyboards import reply as reply_kb
from src.keyboards import inline as inline_kb
from src.utils.helpers import format_trip_details, parse_date, format_booking_details
from .common import cancel # Для fallback

async def passenger_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню пассажира."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    markup = reply_kb.markup_passenger_main
    # Проверяем, есть ли у него профиль водителя, чтобы не показывать кнопку "Стать водителем"
    # Это требует доработки crud и models или отдельной проверки
    # if db_user and crud.get_driver_profile(db, db_user.id):
    #     markup = ... # Клавиатура без кнопки "Стать водителем"

    await update.message.reply_text(" FONT="monospace"> Панель пассажира:", reply_markup=markup)

# --- Поиск поездки ---

async def find_trip_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог поиска поездки: спрашивает город отправления."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    if not db_user or db_user.is_blocked: return ConversationHandler.END

    logger.info(f"Пассажир {user.id} начал поиск поездки.")
    await update.message.reply_text(
        " FONT="monospace"> Введите город отправления:",
        reply_markup=reply_kb.markup_cancel # Добавляем кнопку отмены
    )
    return ASK_DEPARTURE_CITY

async def ask_departure_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает город отправления, спрашивает город прибытия."""
    departure_city = update.message.text
    if not departure_city or len(departure_city) < 2:
        await update.message.reply_text("Введите корректное название города отправления.")
        return ASK_DEPARTURE_CITY

    context.user_data['departure_city'] = departure_city.strip()
    logger.info(f"Поиск поездки: город отправления '{departure_city}' от {update.effective_user.id}")
    await update.message.reply_text(
        " FONT="monospace"> Введите город прибытия:",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_ARRIVAL_CITY

async def ask_arrival_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает город прибытия, спрашивает дату."""
    arrival_city = update.message.text
    if not arrival_city or len(arrival_city) < 2:
        await update.message.reply_text("Введите корректное название города прибытия.")
        return ASK_ARRIVAL_CITY

    context.user_data['arrival_city'] = arrival_city.strip()
    logger.info(f"Поиск поездки: город прибытия '{arrival_city}' от {update.effective_user.id}")
    await update.message.reply_text(
        " FONT="monospace"> Введите дату поездки (например, 25.12 или 25.12.2024):",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_TRIP_DATE

async def ask_trip_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает дату, ищет поездки и выводит результат."""
    date_str = update.message.text
    trip_date = parse_date(date_str)

    if not trip_date:
        await update.message.reply_text(
            "Некорректный формат даты. Введите дату как ДД.ММ или ДД.ММ.ГГГГ (например, 25.12 или 25.12.2024).",
            reply_markup=reply_kb.markup_cancel
        )
        return ASK_TRIP_DATE

    departure_city = context.user_data.get('departure_city')
    arrival_city = context.user_data.get('arrival_city')

    if not departure_city or not arrival_city:
        logger.error(f"Отсутствуют города в context.user_data для поиска у {update.effective_user.id}")
        await update.message.reply_text("Произошла ошибка. Попробуйте начать поиск сначала /find_trip")
        context.user_data.pop('departure_city', None)
        context.user_data.pop('arrival_city', None)
        return ConversationHandler.END

    logger.info(f"Ищем поездки: {departure_city} -> {arrival_city} на {trip_date.strftime('%d.%m.%Y')}")

    db = next(get_db())
    trips = crud.find_trips(db, departure_city, arrival_city, trip_date)

    if not trips:
        await update.message.reply_text(
            f" FONT="monospace"> На {trip_date.strftime('%d.%m.%Y')} поездок по маршруту\n"
            f" FONT="monospace"> {departure_city} -> {arrival_city}\n"
            f" FONT="monospace"> не найдено.",
            reply_markup=reply_kb.markup_passenger_main # Возвращаем основную клавиатуру
        )
    else:
        await update.message.reply_text(
            f" FONT="monospace"> Найденные поездки на {trip_date.strftime('%d.%m.%Y')}\n"
            f" FONT="monospace"> {departure_city} -> {arrival_city}:",
            reply_markup=inline_kb.trips_keyboard(trips)
        )

    # Очищаем данные поиска из user_data
    context.user_data.pop('departure_city', None)
    context.user_data.pop('arrival_city', None)
    return ConversationHandler.END # Завершаем диалог поиска

# --- Бронирование поездки ---

async def book_trip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие кнопки 'Забронировать'."""
    query = update.callback_query
    await query.answer() # Отвечаем на колбэк, чтобы убрать "часики"

    callback_data = query.data
    if not callback_data.startswith("book_"):
        return

    try:
        trip_id = int(callback_data.split("_")[1])
    except (IndexError, ValueError):
        logger.error(f"Некорректный callback_data для бронирования: {callback_data}")
        await query.edit_message_text("Произошла ошибка.")
        return

    user_tg_id = query.from_user.id
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user_tg_id)

    if not db_user or db_user.is_blocked:
        await query.edit_message_text("Не удалось выполнить бронирование (ошибка пользователя).")
        return

    # Попытка создать бронирование
    booking = crud.create_booking(db, passenger_id=db_user.id, trip_id=trip_id, seats=1) # Бронируем 1 место

    if booking:
        logger.info(f"Пассажир {user_tg_id} успешно забронировал место на поездку {trip_id}")
        trip = booking.trip # Получаем обновленную поездку из бронирования
        await query.edit_message_text(
            f"✅ Вы успешно забронировали место!\n\n{format_trip_details(trip)}"
            # Можно добавить клавиатуру для управления бронью
        )
        # Уведомляем водителя (если нужно)
        try:
            driver_tg_id = trip.driver.telegram_id
            await context.bot.send_message(
                chat_id=driver_tg_id,
                text=(f" FONT="monospace"> Новое бронирование!\n"
                      f" FONT="monospace"> Пассажир: {db_user.full_name}\n"
                      f" FONT="monospace"> Поездка: {trip.departure_city} -> {trip.arrival_city} ({trip.departure_datetime.strftime('%d.%m %H:%M')})\n"
                      f" FONT="monospace"> Свободно мест: {trip.available_seats}")
            )
            logger.info(f"Уведомление о бронировании отправлено водителю {driver_tg_id}")
        except Exception as e:
            logger.error(f"Не удалось уведомить водителя {trip.driver_id} о бронировании: {e}")
    else:
        # Обработка ошибок бронирования (мест нет, поездка отменена и т.д.)
        # crud.create_booking вернет None в случае неудачи
        db_trip = crud.get_trip_by_id(db, trip_id) # Проверим причину
        error_message = "Не удалось забронировать место."
        if db_trip and db_trip.available_seats <= 0:
            error_message = " FONT="monospace"> К сожалению, все места на эту поездку уже заняты."
        elif db_trip and db_trip.status != 'scheduled':
             error_message = f" FONT="monospace"> Бронирование на эту поездку больше недоступно (статус: {db_trip.status})."
        elif crud.get_user_bookings(db, db_user.id, active_only=False): # Проверим, не бронировал ли уже
            if any(b.trip_id == trip_id and b.status=='confirmed' for b in crud.get_user_bookings(db, db_user.id, active_only=False)):
                 error_message = " FONT="monospace"> Вы уже забронировали место на эту поездку."

        logger.warning(f"Неудачная попытка бронирования поездки {trip_id} пассажиром {user_tg_id}")
        await query.edit_message_text(error_message)

# --- Мои бронирования ---

async def my_bookings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает активные бронирования пользователя."""
    user_tg = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user_tg.id)

    if not db_user or db_user.is_blocked:
        await update.message.reply_text("Ошибка доступа.")
        return

    bookings = crud.get_user_bookings(db, db_user.id, active_only=True)

    if not bookings:
        await update.message.reply_text("У вас нет активных бронирований.")
    else:
        await update.message.reply_text("Ваши активные бронирования:")
        for booking in bookings:
            # Отправляем каждое бронирование отдельным сообщением с кнопкой отмены
            await update.message.reply_text(
                format_booking_details(booking),
                reply_markup=inline_kb.booking_management_keyboard(booking.id)
            )

async def cancel_booking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие кнопки 'Отменить бронирование'."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("cancel_booking_"):
        return

    try:
        booking_id = int(callback_data.split("_")[-1])
    except (IndexError, ValueError):
        logger.error(f"Некорректный callback_data для отмены бронирования: {callback_data}")
        await query.edit_message_text("Произошла ошибка.")
        return

    user_tg_id = query.from_user.id
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user_tg_id)

    # Проверяем, что пользователь отменяет свою бронь
    booking_to_cancel = db.query(crud.models.Booking).filter(
        crud.models.Booking.id == booking_id,
        crud.models.Booking.passenger_id == db_user.id
    ).first()

    if not booking_to_cancel:
        await query.edit_message_text("Не удалось найти это бронирование или оно принадлежит не вам.")
        return
    if booking_to_cancel.status != 'confirmed':
         await query.edit_message_text("Это бронирование уже неактивно.")
         return

    cancelled_booking = crud.cancel_booking(db, booking_id=booking_id, cancelled_by="passenger")

    if cancelled_booking:
        logger.info(f"Пассажир {user_tg_id} отменил бронирование {booking_id}")
        await query.edit_message_text("✅ Бронирование успешно отменено.")
        # Уведомить водителя об отмене? (опционально)
        try:
             driver_tg_id = cancelled_booking.trip.driver.telegram_id
             await context.bot.send_message(
                  chat_id=driver_tg_id,
                  text=(f" FONT="monospace"> Отмена бронирования!\n"
                      f" FONT="monospace"> Пассажир: {db_user.full_name}\n"
                      f" FONT="monospace"> Поездка: {cancelled_booking.trip.departure_city} -> {cancelled_booking.trip.arrival_city} ({cancelled_booking.trip.departure_datetime.strftime('%d.%m %H:%M')})\n"
                      f" FONT="monospace"> Места возвращены. Свободно: {cancelled_booking.trip.available_seats}")
             )
        except Exception as e:
             logger.error(f"Не удалось уведомить водителя об отмене брони {booking_id}: {e}")
    else:
        logger.error(f"Ошибка при отмене бронирования {booking_id} пассажиром {user_tg_id}")
        await query.edit_message_text("Не удалось отменить бронирование. Попробуйте позже.")


# --- Conversation Handler для поиска поездки ---
find_trip_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('find_trip', find_trip_start),
        MessageHandler(filters.Regex('^🔍 Найти поездку$'), find_trip_start), # Обработка кнопки
    ],
    states={
        ASK_DEPARTURE_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_departure_city_handler)],
        ASK_ARRIVAL_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_arrival_city_handler)],
        ASK_TRIP_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_date_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# --- Обработчики для команд и колбэков пассажира ---
passenger_handlers = [
    find_trip_conv_handler, # Добавляем ConversationHandler поиска
    CommandHandler('my_bookings', my_bookings_command),
    MessageHandler(filters.Regex('^🎫 Мои бронирования$'), my_bookings_command),
    CallbackQueryHandler(book_trip_callback, pattern='^book_'),
    CallbackQueryHandler(cancel_booking_callback, pattern='^cancel_booking_'),
    # Обработчик для кнопки главного меню (если она не запускает ConversationHandler)
    # MessageHandler(filters.Regex('^Что-то еще$'), some_other_passenger_action),
]
