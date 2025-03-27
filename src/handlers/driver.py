# src/handlers/driver.py
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (ContextTypes, ConversationHandler, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters)

from src.database import crud
from src.database.database import get_db
from src.database.models import User
from src.config import (logger, ROLE_DRIVER, ASK_CAR_MAKE, ASK_CAR_MODEL, ASK_CAR_COLOR, ASK_CAR_PLATE,
                        ASK_TRIP_DEPARTURE_CITY, ASK_TRIP_ARRIVAL_CITY, ASK_TRIP_DEPARTURE_DATETIME,
                        ASK_TRIP_ARRIVAL_DATETIME, ASK_TRIP_SEATS)
from src.keyboards import reply as reply_kb
from src.keyboards import inline as inline_kb
from src.utils.helpers import format_trip_details, parse_datetime
from .common import cancel

async def driver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню водителя."""
    await update.message.reply_text(" FONT="monospace"> Панель водителя:", reply_markup=reply_kb.markup_driver_main)

def is_driver(db_user: User | None) -> bool:
    """Проверяет, является ли пользователь водителем."""
    return db_user and db_user.role == ROLE_DRIVER and db_user.driver_profile is not None

# --- Регистрация водителя ---

async def register_driver_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог регистрации водителя (спрашивает марку авто)."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)

    if not db_user or db_user.is_blocked: return ConversationHandler.END
    if is_driver(db_user):
        await update.message.reply_text("Вы уже зарегистрированы как водитель.")
        return ConversationHandler.END

    logger.info(f"Пользователь {user.id} ({db_user.full_name}) начал регистрацию как водитель.")
    await update.message.reply_text(
        " FONT="monospace"> Регистрация водителя.\n"
        " FONT="monospace"> Пожалуйста, введите марку вашего автомобиля (например, Toyota, ВАЗ):",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_CAR_MAKE

async def ask_car_make_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает марку, спрашивает модель."""
    car_make = update.message.text
    if not car_make or len(car_make) < 2:
        await update.message.reply_text("Введите корректную марку автомобиля.")
        return ASK_CAR_MAKE
    context.user_data['car_make'] = car_make.strip()
    await update.message.reply_text(" FONT="monospace"> Введите модель автомобиля (например, Camry, 2109):", reply_markup=reply_kb.markup_cancel)
    return ASK_CAR_MODEL

async def ask_car_model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает модель, спрашивает цвет."""
    car_model = update.message.text
    if not car_model:
        await update.message.reply_text("Введите корректную модель автомобиля.")
        return ASK_CAR_MODEL
    context.user_data['car_model'] = car_model.strip()
    await update.message.reply_text(" FONT="monospace"> Введите цвет автомобиля:", reply_markup=reply_kb.markup_cancel)
    return ASK_CAR_COLOR

async def ask_car_color_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает цвет, спрашивает номер."""
    car_color = update.message.text
    if not car_color or len(car_color) < 3:
        await update.message.reply_text("Введите корректный цвет автомобиля.")
        return ASK_CAR_COLOR
    context.user_data['car_color'] = car_color.strip()
    await update.message.reply_text(" FONT="monospace"> Введите государственный номер автомобиля (например, А123ВС77):", reply_markup=reply_kb.markup_cancel)
    return ASK_CAR_PLATE

async def ask_car_plate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает номер, завершает регистрацию водителя."""
    car_plate = update.message.text
    user = update.effective_user
    # TODO: Добавить валидацию номера авто (например, регулярным выражением)
    if not car_plate or len(car_plate) < 6:
        await update.message.reply_text("Введите корректный номер автомобиля.")
        return ASK_CAR_PLATE

    car_plate_processed = car_plate.strip().upper().replace(" ", "")
    context.user_data['car_plate'] = car_plate_processed

    # Собираем все данные
    car_make = context.user_data.get('car_make')
    car_model = context.user_data.get('car_model')
    car_color = context.user_data.get('car_color')

    if not all([car_make, car_model, car_color]):
        logger.error(f"Отсутствуют данные об авто в context.user_data при регистрации водителя {user.id}")
        await update.message.reply_text("Произошла ошибка сбора данных. Попробуйте /register_driver снова.")
        context.user_data.clear()
        return ConversationHandler.END

    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    if not db_user: return ConversationHandler.END # Не должно произойти, но на всякий случай

    try:
        # Проверяем уникальность номера авто перед созданием профиля
        existing_profile_plate = db.query(crud.models.DriverProfile).filter(crud.models.DriverProfile.car_plate == car_plate_processed).first()
        if existing_profile_plate:
             await update.message.reply_text(f"Автомобиль с номером {car_plate_processed} уже зарегистрирован в системе.")
             # Не завершаем диалог, даем шанс ввести другой номер? Или отмена?
             return ASK_CAR_PLATE # Возвращаемся к вводу номера

        profile = crud.create_driver_profile(
            db,
            user_id=db_user.id,
            car_make=car_make,
            car_model=car_model,
            car_color=car_color,
            car_plate=car_plate_processed
        )
        # crud.create_driver_profile также меняет роль пользователя на ROLE_DRIVER
        logger.info(f"Пользователь {user.id} успешно зарегистрирован как водитель. Профиль: {profile}")
        context.user_data.clear() # Очищаем временные данные

        await update.message.reply_text(
            "✅ Вы успешно зарегистрированы как водитель!\n"
            f" FONT="monospace"> Авто: {profile.car_make} {profile.car_model}, {profile.car_color}, {profile.car_plate}"
        )
        await driver_menu(update, context) # Показываем меню водителя
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при создании профиля водителя для {user.id}: {e}")
        await update.message.reply_text("Произошла ошибка при регистрации водителя. Попробуйте позже.")
        context.user_data.clear()
        return ConversationHandler.END

# --- Создание поездки ---

async def create_trip_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог создания поездки: город отправления."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    if not is_driver(db_user) or db_user.is_blocked:
        await update.message.reply_text("Доступ запрещен.")
        return ConversationHandler.END

    logger.info(f"Водитель {user.id} начал создание поездки.")
    await update.message.reply_text(" FONT="monospace"> Введите город отправления:", reply_markup=reply_kb.markup_cancel)
    return ASK_TRIP_DEPARTURE_CITY

async def ask_trip_departure_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает город отправления, спрашивает город прибытия."""
    city = update.message.text
    if not city or len(city) < 2: return ASK_TRIP_DEPARTURE_CITY # Повторный запрос
    context.user_data['trip_departure_city'] = city.strip()
    await update.message.reply_text(" FONT="monospace"> Введите город прибытия:", reply_markup=reply_kb.markup_cancel)
    return ASK_TRIP_ARRIVAL_CITY

async def ask_trip_arrival_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает город прибытия, спрашивает дату/время отправления."""
    city = update.message.text
    if not city or len(city) < 2: return ASK_TRIP_ARRIVAL_CITY
    context.user_data['trip_arrival_city'] = city.strip()
    await update.message.reply_text(
        " FONT="monospace"> Введите дату и время отправления (ДД.ММ ЧЧ:ММ или ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_TRIP_DEPARTURE_DATETIME

async def ask_trip_departure_datetime_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает дату/время отправления, спрашивает время прибытия."""
    dt_str = update.message.text
    dep_dt = parse_datetime(dt_str)
    if not dep_dt or dep_dt <= datetime.now(): # Проверка, что дата/время в будущем
        await update.message.reply_text(
            "Некорректный формат или дата/время в прошлом.\n"
            "Введите как ДД.ММ ЧЧ:ММ или ДД.ММ.ГГГГ ЧЧ:ММ (например, 25.12 15:30):",
             reply_markup=reply_kb.markup_cancel
        )
        return ASK_TRIP_DEPARTURE_DATETIME
    context.user_data['trip_departure_datetime'] = dep_dt
    await update.message.reply_text(
        " FONT="monospace"> Введите примерное время прибытия (ДД.ММ ЧЧ:ММ или ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=reply_kb.markup_cancel
    )
    return ASK_TRIP_ARRIVAL_DATETIME

async def ask_trip_arrival_datetime_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает время прибытия, спрашивает количество мест."""
    dt_str = update.message.text
    arr_dt = parse_datetime(dt_str)
    dep_dt = context.user_data.get('trip_departure_datetime')
    if not arr_dt or not dep_dt or arr_dt <= dep_dt: # Прибытие должно быть после отправления
        await update.message.reply_text(
            "Некорректный формат или время прибытия раньше/равно времени отправления.\n"
            "Введите как ДД.ММ ЧЧ:ММ или ДД.ММ.ГГГГ ЧЧ:ММ:",
             reply_markup=reply_kb.markup_cancel
        )
        return ASK_TRIP_ARRIVAL_DATETIME
    context.user_data['trip_arrival_datetime'] = arr_dt
    await update.message.reply_text(" FONT="monospace"> Введите количество доступных мест для пассажиров:", reply_markup=reply_kb.markup_cancel)
    return ASK_TRIP_SEATS

async def ask_trip_seats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает кол-во мест и создает поездку."""
    seats_str = update.message.text
    user = update.effective_user
    try:
        seats = int(seats_str)
        if seats <= 0 or seats > 10: # Ограничение на кол-во мест
            raise ValueError("Некорректное количество мест")
    except ValueError:
        await update.message.reply_text("Введите корректное число мест (от 1 до 10).")
        return ASK_TRIP_SEATS

    # Собираем все данные
    dep_city = context.user_data.get('trip_departure_city')
    arr_city = context.user_data.get('trip_arrival_city')
    dep_dt = context.user_data.get('trip_departure_datetime')
    arr_dt = context.user_data.get('trip_arrival_datetime')

    if not all([dep_city, arr_city, dep_dt, arr_dt]):
        logger.error(f"Отсутствуют данные о поездке в context.user_data у водителя {user.id}")
        await update.message.reply_text("Произошла ошибка сбора данных. Попробуйте /create_trip снова.")
        context.user_data.clear()
        return ConversationHandler.END

    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)
    if not db_user: return ConversationHandler.END

    try:
        trip = crud.create_trip(
            db,
            driver_id=db_user.id,
            departure_city=dep_city,
            arrival_city=arr_city,
            departure_datetime=dep_dt,
            estimated_arrival_datetime=arr_dt,
            total_seats=seats
        )
        logger.info(f"Водитель {user.id} создал поездку: {trip}")
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Поездка успешно создана!\n\n{format_trip_details(trip)}"
        )
        await driver_menu(update, context) # Показываем меню водителя
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при создании поездки водителем {user.id}: {e}")
        await update.message.reply_text("Произошла ошибка при создании поездки. Попробуйте позже.")
        context.user_data.clear()
        return ConversationHandler.END


# --- Мои поездки (водителя) ---

async def my_trips_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает активные/запланированные поездки водителя."""
    user = update.effective_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)

    if not is_driver(db_user) or db_user.is_blocked:
        await update.message.reply_text("Доступ запрещен.")
        return

    trips = crud.get_driver_trips(db, db_user.id, active_only=True)

    if not trips:
        await update.message.reply_text("У вас нет запланированных или активных поездок.")
    else:
        await update.message.reply_text("Ваши поездки:")
        for trip in trips:
            # Отправляем каждую поездку с кнопками управления
            await update.message.reply_text(
                format_trip_details(trip),
                reply_markup=inline_kb.trip_management_keyboard(trip.id)
            )

async def cancel_trip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие 'Отменить поездку'."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    if not callback_data.startswith("cancel_trip_"): return

    try:
        trip_id = int(callback_data.split("_")[-1])
    except (IndexError, ValueError):
        logger.error(f"Некорректный callback_data для отмены поездки: {callback_data}")
        await query.edit_message_text("Произошла ошибка.")
        return

    user = query.from_user
    db = next(get_db())
    db_user = crud.get_user_by_telegram_id(db, user.id)

    trip_to_cancel = db.query(crud.models.Trip).filter(
        crud.models.Trip.id == trip_id,
        crud.models.Trip.driver_id == db_user.id # Убеждаемся, что водитель отменяет свою поездку
    ).first()

    if not trip_to_cancel:
        await query.edit_message_text("Не удалось найти эту поездку или она вам не принадлежит.")
        return
    if trip_to_cancel.status not in ['scheduled', 'active']: # Отменять можно только запланированные или активные
        await query.edit_message_text(f"Эту поездку нельзя отменить (статус: {trip_to_cancel.status}).")
        return

    # Получаем список пассажиров до отмены
    passenger_bookings = db.query(crud.models.Booking).filter(
        crud.models.Booking.trip_id == trip_id,
        crud.models.Booking.status == 'confirmed'
    ).all()

    # Меняем статус поездки
    updated_trip = crud.update_trip_status(db, trip_id, 'cancelled')

    if updated_trip:
        logger.info(f"Водитель {user.id} отменил поездку {trip_id}")
        await query.edit_message_text("✅ Поездка успешно отменена.")

        # Отменяем брони и уведомляем пассажиров
        for booking in passenger_bookings:
            cancelled_booking = crud.cancel_booking(db, booking.id, cancelled_by="driver")
            if cancelled_booking and cancelled_booking.passenger:
                try:
                    passenger_tg_id = cancelled_booking.passenger.telegram_id
                    await context.bot.send_message(
                        chat_id=passenger_tg_id,
                        text=(f" FONT="monospace"> Внимание! Поездка отменена водителем.\n"
                              f" FONT="monospace"> Маршрут: {trip_to_cancel.departure_city} -> {trip_to_cancel.arrival_city}\n"
                              f" FONT="monospace"> Отправление: {trip_to_cancel.departure_datetime.strftime('%d.%m %H:%M')}\n"
                              f" FONT="monospace"> Ваше бронирование #{booking.id} было отменено.")
                    )
                    logger.info(f"Уведомление об отмене поездки {trip_id} отправлено пассажиру {passenger_tg_id}")
                except Exception as e:
                    logger.error(f"Не удалось уведомить пассажира {cancelled_booking.passenger_id} об отмене поездки {trip_id}: {e}")
    else:
        logger.error(f"Ошибка при отмене поездки {trip_id} водителем {user.id}")
        await query.edit_message_text("Не удалось отменить поездку. Попробуйте позже.")


# --- Conversation Handlers ---
register_driver_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('register_driver', register_driver_start),
        MessageHandler(filters.Regex('^🚗 Стать водителем$'), register_driver_start),
    ],
    states={
        ASK_CAR_MAKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_car_make_handler)],
        ASK_CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_car_model_handler)],
        ASK_CAR_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_car_color_handler)],
        ASK_CAR_PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_car_plate_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

create_trip_conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('create_trip', create_trip_start),
        MessageHandler(filters.Regex('^➕ Создать поездку$'), create_trip_start),
    ],
    states={
        ASK_TRIP_DEPARTURE_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_departure_city_handler)],
        ASK_TRIP_ARRIVAL_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_arrival_city_handler)],
        ASK_TRIP_DEPARTURE_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_departure_datetime_handler)],
        ASK_TRIP_ARRIVAL_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_arrival_datetime_handler)],
        ASK_TRIP_SEATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_trip_seats_handler)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

# --- Общий список хендлеров водителя ---
driver_handlers = [
    register_driver_conv_handler,
    create_trip_conv_handler,
    CommandHandler('my_trips', my_trips_command),
    MessageHandler(filters.Regex('^ FONT="monospace"> Мои поездки$'), my_trips_command),
    CallbackQueryHandler(cancel_trip_callback, pattern='^cancel_trip_'),
    # Добавить обработчики для других кнопок/действий водителя
]
