import os
from dotenv import load_dotenv

load_dotenv() # Загружает переменные из .env файла

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./default_bot.db")

if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в переменных окружения!")
if not ADMIN_IDS:
    print("Внимание: Не найдены ADMIN_IDS в переменных окружения!")
