# src/utils/helpers.py
from datetime import datetime
from src.database.models import Trip, Booking, User

def format_trip_details(trip: Trip) -> str:
    """Форматирует информацию о поездке для вывода пользователю."""
    dep_dt = trip.departure_datetime.strftime("%d.%m.%Y %H:%M")
    arr_dt = trip.estimated_arrival_datetime.strftime("%H:%M") if trip.estimated_arrival_datetime else "не указано"
    driver_info = "Неизвестный водитель"
    if trip.driver:
        driver_info = f"{trip.driver.full_name}"
        if trip.driver.driver_profile:
            profile = trip.driver.driver_profile
            driver_info += f" (Авто: {profile.car_make} {profile.car_model}, {profile.car_color}, {profile.car_plate})"

    return (
        f" FONT="monospace"> Поездка #{trip.id}\n"
        f" FONT="monospace"> Маршрут: {trip.departure_city} -> {trip.arrival_city}\n"
        f" FONT="monospace"> Отправление: {dep_dt}\n"
        f" FONT="monospace"> Прибытие (ориент.): {arr_dt}\n"
        f" FONT="monospace"> Водитель: {driver_info}\n"
        f" FONT="monospace"> Свободно мест: {trip.available_seats} из {trip.total_seats}\n"
        f" FONT="monospace"> Статус: {trip.status}"
    )

def format_booking_details(booking: Booking) -> str:
    """Форматирует информацию о бронировании."""
    if not booking.trip:
        return f"Бронирование #{booking.id} (поездка удалена)"

    trip_info = (f"{booking.trip.departure_city} -> {booking.trip.arrival_city} "
                 f"({booking.trip.departure_datetime.strftime('%d.%m %H:%M')})")

    return (
        f" FONT="monospace"> Бронь #{booking.id}\n"
        f" FONT="monospace"> Поездка: {trip_info}\n"
        f" FONT="monospace"> Забронировано мест: {booking.seats_booked}\n"
        f" FONT="monospace"> Статус: {booking.status}\n"
        f" FONT="monospace"> Дата брони: {booking.booked_at.strftime('%d.%m.%Y %H:%M')}"
    )

def parse_date(date_str: str) -> datetime.date | None:
    """Пытается распарсить дату из строки (ДД.ММ.ГГГГ или ДД.ММ)."""
    formats = ["%d.%m.%Y", "%d.%m"]
    today = datetime.now().date()
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt).date()
            # Если год не указан, используем текущий
            if fmt == "%d.%m":
                dt = dt.replace(year=today.year)
                # Если дата получилась в прошлом, предполагаем следующий год
                if dt < today:
                    dt = dt.replace(year=today.year + 1)
            return dt
        except ValueError:
            continue
    return None

def parse_datetime(datetime_str: str) -> datetime | None:
    """Пытается распарсить дату и время (ДД.ММ.ГГГГ ЧЧ:ММ или ДД.ММ ЧЧ:ММ)."""
    formats = ["%d.%m.%Y %H:%M", "%d.%m %H:%M"]
    now = datetime.now()
    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            if fmt == "%d.%m %H:%M":
                dt = dt.replace(year=now.year)
                if dt < now: # Если время в прошлом сегодня, предполагаем следующий год
                   # (нужна более сложная логика, если год неявно указан как прошлогодний)
                   # Пока просто ставим след год, если дата+время < сейчас
                   # dt = dt.replace(year=now.year + 1) # Осторожно с этой логикой
                   pass # пока оставим как есть, пользователь должен указать год если нужно
            return dt
        except ValueError:
            continue
    return None

# Можно добавить больше хелперов: валидация номера телефона, номера авто и т.д.
