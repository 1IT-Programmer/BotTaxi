# src/config.py
import os
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("Токен бота (BOT_TOKEN) не найден в переменных окружения!")
    raise ValueError("Необходимо установить BOT_TOKEN")

# ID администраторов (список целых чисел)
ADMIN_IDS_STR = os.getenv('ADMIN_IDS', '')
try:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS не установлены или пусты в переменных окружения.")
except ValueError:
    logger.error("ADMIN_IDS в переменных окружения имеют неверный формат. Ожидается список ID через запятую.")
    ADMIN_IDS = []

# Строка подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./travel_bot.db')
logger.info(f"Используется база данных: {DATABASE_URL.split('://')[0]}")

# Роли пользователей
ROLE_PASSENGER = 'passenger'
ROLE_DRIVER = 'driver'
ROLE_ADMIN = 'admin'

# Состояния для ConversationHandler (пример)
(ASK_PHONE, ASK_FULL_NAME, REGISTRATION_COMPLETE, # Common registration
 CHOOSE_ACTION, # Main menu state if needed
 ASK_DEPARTURE_CITY, ASK_ARRIVAL_CITY, ASK_TRIP_DATE, # Passenger find trip
 ASK_CAR_MAKE, ASK_CAR_MODEL, ASK_CAR_COLOR, ASK_CAR_PLATE, # Driver registration
 ASK_TRIP_DEPARTURE_CITY, ASK_TRIP_ARRIVAL_CITY, ASK_TRIP_DEPARTURE_DATETIME,
 ASK_TRIP_ARRIVAL_DATETIME, ASK_TRIP_SEATS, # Driver create trip
 SUPPORT_MESSAGE # Support state
 ) = range(17)
