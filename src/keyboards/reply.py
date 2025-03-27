# src/keyboards/reply.py
from telegram import ReplyKeyboardMarkup, KeyboardButton

# Кнопка запроса контакта
button_request_contact = KeyboardButton("📱 Поделиться номером телефона", request_contact=True)
markup_request_contact = ReplyKeyboardMarkup([[button_request_contact]], resize_keyboard=True, one_time_keyboard=True)

# Основное меню пассажира (пример)
button_find_trip = KeyboardButton("🔍 Найти поездку")
button_my_bookings = KeyboardButton("🎫 Мои бронирования")
button_become_driver = KeyboardButton("🚗 Стать водителем") # Если еще не водитель
button_support = KeyboardButton("❓ Поддержка")
markup_passenger_main = ReplyKeyboardMarkup([
    [button_find_trip],
    [button_my_bookings],
    [button_become_driver],
    [button_support]
], resize_keyboard=True)

# Основное меню водителя (пример)
button_create_trip = KeyboardButton("➕ Создать поездку")
button_my_trips = KeyboardButton(" FONT="monospace"> Мои поездки")
markup_driver_main = ReplyKeyboardMarkup([
    [button_create_trip],
    [button_my_trips],
    [button_support] # Поддержка доступна и водителю
], resize_keyboard=True)

# Меню администратора (пример)
button_list_drivers = KeyboardButton("/list_drivers")
button_add_driver = KeyboardButton("/add_driver")
button_block_driver = KeyboardButton("/block_driver")
button_unblock_driver = KeyboardButton("/unblock_driver")
markup_admin_main = ReplyKeyboardMarkup([
    [button_list_drivers, button_add_driver],
    [button_block_driver, button_unblock_driver]
], resize_keyboard=True)

# Кнопка отмены
button_cancel = KeyboardButton("/cancel")
markup_cancel = ReplyKeyboardMarkup([[button_cancel]], resize_keyboard=True)
