# src/database/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import DATABASE_URL, logger

try:
    # echo=True полезно для отладки SQL запросов
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("Соединение с базой данных установлено успешно.")
except Exception as e:
    logger.error(f"Ошибка подключения к базе данных: {e}")
    raise

# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функция для инициализации (создания таблиц)
def init_db():
    try:
        # Импортируем модели здесь, чтобы избежать циклических зависимостей
        from . import models
        logger.info("Создание таблиц базы данных...")
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы базы данных успешно созданы (или уже существуют).")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        raise

# Если запустить этот файл напрямую, он создаст таблицы
if __name__ == "__main__":
    print("Инициализация базы данных...")
    init_db()
    print("База данных инициализирована.")
