# src/database/models.py
from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Boolean, create_engine, UniqueConstraint)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # Для default=func.now() если нужно

# Импортируем Base из database.py
from .database import Base
from src.config import ROLE_PASSENGER

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    full_name = Column(String, index=True)
    phone_number = Column(String, index=True)
    role = Column(String, default=ROLE_PASSENGER, nullable=False) # 'passenger', 'driver', 'admin'
    is_blocked = Column(Boolean, default=False)
    registration_date = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    driver_profile = relationship("DriverProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    driver_trips = relationship("Trip", back_populates="driver")
    passenger_bookings = relationship("Booking", back_populates="passenger")

    def __repr__(self):
        return f"<User(id={self.id}, tg_id={self.telegram_id}, name='{self.full_name}', role='{self.role}')>"

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    car_make = Column(String) # Марка
    car_model = Column(String) # Модель
    car_color = Column(String) # Цвет
    car_plate = Column(String, unique=True, index=True) # Номер авто

    # Связь обратно к User
    user = relationship("User", back_populates="driver_profile")

    def __repr__(self):
        return f"<DriverProfile(user_id={self.user_id}, car='{self.car_make} {self.car_model} ({self.car_plate})')>"

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    departure_city = Column(String, index=True, nullable=False)
    arrival_city = Column(String, index=True, nullable=False)
    departure_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    estimated_arrival_datetime = Column(DateTime(timezone=True))
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    status = Column(String, default='scheduled', index=True) # 'scheduled', 'active', 'completed', 'cancelled'
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    driver = relationship("User", back_populates="driver_trips")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<Trip(id={self.id}, from='{self.departure_city}' to='{self.arrival_city}', "
                f"driver={self.driver_id}, seats={self.available_seats}/{self.total_seats})>")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    seats_booked = Column(Integer, default=1)
    status = Column(String, default='confirmed', index=True) # 'confirmed', 'cancelled_by_passenger', 'cancelled_by_driver'
    booked_at = Column(DateTime(timezone=True), server_default=func.now())

    # Ограничение, чтобы один пассажир не мог забронировать одну и ту же поездку дважды
    __table_args__ = (UniqueConstraint('passenger_id', 'trip_id', name='_passenger_trip_uc'),)

    # Связи
    passenger = relationship("User", back_populates="passenger_bookings")
    trip = relationship("Trip", back_populates="bookings")

    def __repr__(self):
        return f"<Booking(id={self.id}, trip={self.trip_id}, passenger={self.passenger_id}, seats={self.seats_booked})>"
