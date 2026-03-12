"""SQLAlchemy models for SQLite."""
from datetime import datetime
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DB_PATH

Base = declarative_base()


def generate_id() -> str:
    return str(uuid.uuid4())


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    parameter = Column(String(64), unique=True, nullable=False)
    value = Column(Text)


class WorkLog(Base):
    __tablename__ = "worklog"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    job_type = Column(String(32), nullable=False)
    hours_worked = Column(Float, default=0)
    hour_rate_snapshot = Column(Float, default=0)
    status = Column(String(32), nullable=False)
    sick_day_index = Column(Integer)
    is_paid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    description = Column(Text)
    amount = Column(Float, default=0)
    status = Column(String(32), default="New")


class Finance(Base):
    __tablename__ = "finance"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    type = Column(String(32), nullable=False)
    amount = Column(Float, default=0)
    category = Column(String(64))
    comment = Column(Text)


class State(Base):
    __tablename__ = "state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(32), nullable=False)
    scenario = Column(String(64), nullable=False)
    step = Column(String(64), nullable=False)
    payload = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(16), nullable=False)
    message = Column(Text)


class Calculation(Base):
    __tablename__ = "calculations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    period_start = Column(String(10))
    period_end = Column(String(10))
    accrued_salary = Column(Float)
    received_salary = Column(Float)
    difference = Column(Float)


# Engine and session
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    return SessionLocal()
