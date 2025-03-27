# src/database/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, date

# Импортируем модели и роли
from . import models
from src.config import ROLE_DRIVER, ROLE_PASSENGER, logger

# --- User Operations ---

def get_user_by_telegram_id(db: Session, telegram_id: int) -> models.User | None:
    return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()

def create_user(db: Session, telegram_id: int, full_name: str, phone_number: str) -> models.User:
    db_user = models.User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone_number=phone_number,
        role=ROLE_PASSENGER # По умолчанию - пассажир
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(f"Создан новый пользователь: {db_user}")
    return db_user

def update_user_role(db: Session, telegram_id: int, new_role: str) -> models.User | None:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.role = new_role
        db.commit()
        db.refresh(db_user)
        logger.info(f"Роль пользователя {telegram_id} обновлена на '{new_role}'")
    return db_user

def block_user(db: Session, telegram_id: int, block_status: bool = True) -> models.User | None:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.is_blocked = block_status
        db.commit()
        db.refresh(db_user)
        status_str = "заблокирован" if block_status else "разблокирован"
        logger.info(f"Пользователь {telegram_id} {status_str}")
    return db_user

def get_all_drivers(db: Session) -> list[models.User]:
    return db.query(models.User).filter(models.User.role == ROLE_DRIVER).all()

# --- Driver Profile Operations ---

def create_driver_profile(db: Session, user_id: int, car_make: str, car_model: str, car_color: str, car_plate: str) -> models.DriverProfile:
    # Убедимся, что профиль для этого user_id еще не создан
    existing_profile = db.query(models.DriverProfile).filter(models.DriverProfile.user_id == user_id).first()
    if existing_profile:
        logger.warning(f"Попытка создать дублирующийся профиль водителя для user_id={user_id}")
        # Можно обновить существующий или вернуть ошибку
        existing_profile.car_make = car_make
        existing_profile.car_model = car_model
        existing_profile.car_color = car_color
        existing_profile.car_plate = car_plate
        db.commit()
        db.refresh(existing_profile)
        return existing_profile
    else:
        db_profile = models.DriverProfile(
            user_id=user_id,
            car_make=car_make,
            car_model=car_model,
            car_color=car_color,
            car_plate=car_plate
        )
        db.add(db_profile)
        # Обновляем роль пользователя на 'driver'
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.role = ROLE_DRIVER
            logger.info(f"Роль пользователя {user.telegram_id} обновлена на driver при создании профиля")
        else:
             logger.error(f"Не найден пользователь с id={user_id} при создании профиля водителя")
             db.rollback() # Откатываем создание профиля, если юзера нет
             raise ValueError(f"User with id {user_id} not found")

        db.commit()
        db.refresh(db_profile)
        logger.info(f"Создан профиль водителя для user_id={user_id}: {db_profile}")
        return db_profile

def get_driver_profile(db: Session, user_id: int) -> models.DriverProfile | None:
    return db.query(models.DriverProfile).filter(models.DriverProfile.user_id == user_id).first()

# --- Trip Operations ---

def create_trip(db: Session, driver_id: int, departure_city: str, arrival_city: str,
                departure_datetime: datetime, estimated_arrival_datetime: datetime, total_seats: int) -> models.Trip:
    if total_seats <= 0:
         raise ValueError("Количество мест должно быть положительным")
    db_trip = models.Trip(
        driver_id=driver_id,
        departure_city=departure_city,
        arrival_city=arrival_city,
        departure_datetime=departure_datetime,
        estimated_arrival_datetime=estimated_arrival_datetime,
        total_seats=total_seats,
        available_seats=total_seats # Изначально все места свободны
    )
    db.add(db_trip)
    db.commit()
    db.refresh(db_trip)
    logger.info(f"Создана новая поездка: {db_trip}")
    return db_trip

def get_trip_by_id(db: Session, trip_id: int) -> models.Trip | None:
    return db.query(models.Trip).filter(models.Trip.id == trip_id).first()

def find_trips(db: Session, departure_city: str, arrival_city: str, trip_date: date) -> list[models.Trip]:
    """Находит поездки на конкретную дату"""
    start_of_day = datetime.combine(trip_date, datetime.min.time())
    end_of_day = datetime.combine(trip_date, datetime.max.time())

    return db.query(models.Trip).join(models.User).filter(
        models.Trip.departure_city.ilike(f"%{departure_city}%"), # ilike для регистронезависимого поиска
        models.Trip.arrival_city.ilike(f"%{arrival_city}%"),
        models.Trip.departure_datetime >= start_of_day,
        models.Trip.departure_datetime <= end_of_day,
        models.Trip.available_seats > 0, # Только поездки со свободными местами
        models.Trip.status == 'scheduled', # Только запланированные
        models.User.is_blocked == False # Водитель не заблокирован
    ).order_by(models.Trip.departure_datetime).all()

def get_driver_trips(db: Session, driver_id: int, active_only: bool = True) -> list[models.Trip]:
    query = db.query(models.Trip).filter(models.Trip.driver_id == driver_id)
    if active_only:
        # Показываем запланированные и активные
        query = query.filter(models.Trip.status.in_(['scheduled', 'active']))
    return query.order_by(models.Trip.departure_datetime).all()

def update_trip_status(db: Session, trip_id: int, new_status: str) -> models.Trip | None:
    db_trip = get_trip_by_id(db, trip_id)
    if db_trip:
        db_trip.status = new_status
        db.commit()
        db.refresh(db_trip)
        logger.info(f"Статус поездки {trip_id} обновлен на '{new_status}'")
    return db_trip

# --- Booking Operations ---

def create_booking(db: Session, passenger_id: int, trip_id: int, seats: int = 1) -> models.Booking | None:
    db_trip = get_trip_by_id(db, trip_id)
    if not db_trip:
        logger.error(f"Попытка бронирования несуществующей поездки {trip_id}")
        return None # Поездка не найдена

    if db_trip.status != 'scheduled':
        logger.warning(f"Попытка бронирования поездки {trip_id} со статусом {db_trip.status}")
        return None # Поездка не активна для бронирования

    if db_trip.available_seats < seats:
        logger.warning(f"Недостаточно мест в поездке {trip_id} ({db_trip.available_seats} доступно, запрошено {seats})")
        return None # Недостаточно мест

    # Проверяем, не бронировал ли этот пассажир уже эту поездку
    existing_booking = db.query(models.Booking).filter(
        models.Booking.passenger_id == passenger_id,
        models.Booking.trip_id == trip_id
    ).first()
    if existing_booking and existing_booking.status == 'confirmed':
        logger.warning(f"Пассажир {passenger_id} уже забронировал поездку {trip_id}")
        return None # Уже забронировано

    # Уменьшаем количество доступных мест и создаем бронь (в транзакции)
    try:
        db_trip.available_seats -= seats
        db_booking = models.Booking(
            passenger_id=passenger_id,
            trip_id=trip_id,
            seats_booked=seats,
            status='confirmed'
        )
        db.add(db_booking)
        db.commit()
        db.refresh(db_booking)
        db.refresh(db_trip) # Обновляем и поездку тоже
        logger.info(f"Создано бронирование: {db_booking}")
        return db_booking
    except Exception as e:
        db.rollback() # Откатываем изменения в случае ошибки
        logger.error(f"Ошибка при создании бронирования для поездки {trip_id}: {e}")
        return None

def get_user_bookings(db: Session, passenger_id: int, active_only: bool = True) -> list[models.Booking]:
    query = db.query(models.Booking).filter(models.Booking.passenger_id == passenger_id)
    if active_only:
        # Показываем только подтвержденные бронирования на запланированные поездки
        query = query.join(models.Trip).filter(
            models.Booking.status == 'confirmed',
            models.Trip.status.in_(['scheduled', 'active']) # Можно уточнить до 'scheduled'
        )
    return query.order_by(models.Booking.booked_at.desc()).all()

def cancel_booking(db: Session, booking_id: int, cancelled_by: str = "passenger") -> models.Booking | None:
    """ Отменяет бронирование и возвращает места """
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking or db_booking.status != 'confirmed':
        logger.warning(f"Попытка отменить неактивное или несуществующее бронирование {booking_id}")
        return None # Бронь не найдена или уже отменена

    db_trip = db_booking.trip # Получаем связанную поездку
    if not db_trip:
         logger.error(f"Не найдена поездка для бронирования {booking_id}")
         return None # Ошибка данных

    # Возвращаем места и меняем статус брони (в транзакции)
    try:
        db_trip.available_seats += db_booking.seats_booked
        if cancelled_by == "driver":
            db_booking.status = 'cancelled_by_driver'
        else:
            db_booking.status = 'cancelled_by_passenger'
        db.commit()
        db.refresh(db_booking)
        db.refresh(db_trip)
        logger.info(f"Бронирование {booking_id} отменено ({cancelled_by}). Места возвращены в поездку {db_trip.id}.")
        return db_booking
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при отмене бронирования {booking_id}: {e}")
        return None
