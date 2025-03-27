# src/keyboards/inline.py
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import Trip

# Пример клавиатуры для найденных поездок
def trips_keyboard(trips: list[Trip]) -> InlineKeyboardMarkup:
    buttons = []
    for trip in trips:
        # Форматируем время для отображения
        dep_time = trip.departure_datetime.strftime("%H:%M")
        driver_name = trip.driver.full_name.split()[0] if trip.driver and trip.driver.full_name else "Водитель"
        # Текст кнопки: Время - Имя водителя - Места
        button_text = f"{dep_time} - {driver_name} ({trip.available_seats} мест)"
        # callback_data должен содержать уникальный идентификатор поездки
        callback_data = f"book_{trip.id}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if not buttons:
         buttons.append([InlineKeyboardButton("Нет доступных поездок", callback_data="no_trips")])

    return InlineKeyboardMarkup(buttons)

# Клавиатура подтверждения (да/нет)
def confirmation_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton("✅ Да", callback_data=yes_callback),
        InlineKeyboardButton("❌ Нет", callback_data=no_callback),
    ]
    return InlineKeyboardMarkup([buttons])

# Клавиатура для управления бронированием
def booking_management_keyboard(booking_id: int) -> InlineKeyboardMarkup:
     buttons = [
          InlineKeyboardButton("❌ Отменить бронирование", callback_data=f"cancel_booking_{booking_id}")
     ]
     return InlineKeyboardMarkup([buttons])

# Клавиатура для управления поездкой водителя
def trip_management_keyboard(trip_id: int) -> InlineKeyboardMarkup:
     buttons = [
          InlineKeyboardButton("✏️ Редактировать (не реализовано)", callback_data=f"edit_trip_{trip_id}"),
          InlineKeyboardButton("❌ Отменить поездку", callback_data=f"cancel_trip_{trip_id}")
     ]
     return InlineKeyboardMarkup([buttons])
