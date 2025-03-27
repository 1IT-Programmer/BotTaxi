from .models import Base # Импорт Base из models.py

def init_db():
    # Создает все таблицы
    Base.metadata.create_all(bind=engine) # engine должен быть определен ранее

if __name__ == "__main__":
    print("Инициализация базы данных...")
    init_db()
    print("База данных инициализирована.")
