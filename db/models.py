"""SQLAlchemy models for SQLite."""
from datetime import datetime
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    create_engine, Index, event
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
    __table_args__ = (Index("ix_worklog_date_job_status", "date", "job_type", "status"),)


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    description = Column(Text)
    amount = Column(Float, default=0)
    status = Column(String(32), default="New")
    __table_args__ = (Index("ix_orders_date", "date"),)


class Finance(Base):
    __tablename__ = "finance"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    type = Column(String(32), nullable=False)
    amount = Column(Float, default=0)
    category = Column(String(64))
    comment = Column(Text)
    tags = Column(Text, default="")
    source = Column(String(128), default="")
    income_tag = Column(String(128), default="")
    account_id = Column(String(36), default="")
    exclude_from_budget = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    __table_args__ = (
        Index("ix_finance_date_type_deleted", "date", "type", "is_deleted"),
        Index("ix_finance_category_period", "date", "category", "is_deleted"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    chat_id = Column(String(32))
    entity = Column(String(32))
    entity_id = Column(String(64))
    action = Column(String(16))
    field = Column(String(64))
    old_value = Column(Text)
    new_value = Column(Text)


class State(Base):
    __tablename__ = "state"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(32), nullable=False)
    scenario = Column(String(64), nullable=False)
    step = Column(String(64), nullable=False)
    payload = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_state_chat_id", "chat_id"),)


class ProcessedUpdate(Base):
    """Telegram update ids already accepted by the webhook."""
    __tablename__ = "processed_updates"
    update_id = Column(Integer, primary_key=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (Index("ix_processed_updates_processed_at", "processed_at"),)


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
    source = Column(String(128), default="Main")


class IncomeSource(Base):
    """Configurable work/income source (main job, Avito, client, etc.)."""
    __tablename__ = "income_sources"
    id = Column(String(36), primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    source_type = Column(String(32), default="manual")
    hourly_rate = Column(Float, default=0)
    weekend_hour_rate = Column(Float, default=0)
    use_weekend_rate = Column(Boolean, default=False)
    full_day_hours = Column(Float, default=11)
    max_daily_hours = Column(Float, default=24)
    sick_enabled = Column(Boolean, default=False)
    sick_hour_rate = Column(Float, default=0)
    paid_sick_hours = Column(Float, default=0)
    is_active = Column(Boolean, default=True)


class IPSavings(Base):
    """Separate 1% reserve from manually entered IP revenue."""
    __tablename__ = "ip_savings"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    revenue_amount = Column(Float, nullable=False)
    reserve_amount = Column(Float, nullable=False)
    tag = Column(String(128), default="")
    comment = Column(Text, default="")


class Account(Base):
    """Real money account/wallet used for balances and transfers."""
    __tablename__ = "accounts"
    id = Column(String(36), primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    account_type = Column(String(32), default="card")
    opening_balance = Column(Float, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AccountTransfer(Base):
    """Neutral movement between two real accounts."""
    __tablename__ = "account_transfers"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    from_account_id = Column(String(36), nullable=False)
    to_account_id = Column(String(36), nullable=False)
    amount = Column(Float, nullable=False)
    comment = Column(Text, default="")


class IPWalletOperation(Base):
    """Movement of real money in the separate IP reserve."""
    __tablename__ = "ip_wallet_operations"
    id = Column(String(36), primary_key=True)
    date = Column(String(10), nullable=False)
    operation_type = Column(String(16), nullable=False)  # reserve / withdrawal
    amount = Column(Float, nullable=False)
    comment = Column(Text, default="")


class BudgetPlan(Base):
    """Monthly/quarterly budget limits by category."""
    __tablename__ = "budget_plan"
    id = Column(String(36), primary_key=True)
    month_year = Column(String(7), nullable=False)
    category = Column(String(64), nullable=False)
    limit_amount = Column(Float, nullable=False)
    period_type = Column(String(16), default="month")  # month / quarter
    created_at = Column(DateTime, default=datetime.utcnow)


class Goal(Base):
    """Savings/financial goals with types and auto-fund."""
    __tablename__ = "goals"
    id = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0)
    deadline = Column(String(10))
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    goal_type = Column(String(32), default="other")  # vacation/tech/cushion/purchase/other
    auto_fund_percent = Column(Float, default=0)
    auto_fund_amount = Column(Float, default=0)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    """Recurring payments (subscriptions) with groups."""
    __tablename__ = "subscriptions"
    id = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False)
    amount = Column(Float, nullable=False)
    cycle = Column(String(32), nullable=False)
    next_date = Column(String(10), nullable=False)
    remind_days_before = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    auto_create_expense = Column(Boolean, default=False)
    category = Column(String(64), default="Прочее")
    group = Column(String(32), default="other")  # streaming/cloud/bank/other
    sub_type = Column(String(16), default="expense")  # expense / income
    is_overdue = Column(Boolean, default=False)
    requires_confirmation = Column(Boolean, default=True)
    last_reminder_date = Column(String(10), default="")
    source = Column(String(128), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_subscriptions_due", "next_date", "is_active", "auto_create_expense"),)


class Debt(Base):
    """Debts and credits."""
    __tablename__ = "debts"
    id = Column(String(36), primary_key=True)
    direction = Column(String(16), nullable=False)  # owe / lent
    counterparty = Column(String(128), nullable=False)
    original_amount = Column(Float, nullable=False)
    remaining_amount = Column(Float, nullable=False)
    interest_rate = Column(Float, default=0)
    payment_type = Column(String(16), default="fixed")  # annuity / fixed
    monthly_payment = Column(Float, default=0)
    payment_cycle = Column(String(16), default="monthly")  # monthly / biweekly / custom
    next_payment_date = Column(String(10))  # YYYY-MM-DD
    debt_kind = Column(String(32), default="credit")  # credit / installment / card / overdraft
    due_date = Column(String(10))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DebtPayment(Base):
    """Individual debt payment records."""
    __tablename__ = "debt_payments"
    id = Column(String(36), primary_key=True)
    debt_id = Column(String(36), nullable=False)
    date = Column(String(10), nullable=False)
    amount = Column(Float, nullable=False)
    comment = Column(Text, default="")


class Category(Base):
    """User/system expense categories with hierarchy."""
    __tablename__ = "categories"
    id = Column(String(36), primary_key=True)
    name = Column(String(64), nullable=False)
    parent_id = Column(String(36))  # NULL = root
    is_system = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)


class Tag(Base):
    """Tags for finance entries."""
    __tablename__ = "tags"
    id = Column(String(36), primary_key=True)
    name = Column(String(64), nullable=False)


class ExpenseTemplate(Base):
    """Quick expense templates."""
    __tablename__ = "expense_templates"
    id = Column(String(36), primary_key=True)
    name = Column(String(128), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(64), nullable=False)
    usage_count = Column(Integer, default=0)


class User(Base):
    """Web app user (single-user)."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    totp_secret = Column(String(64))
    totp_verified = Column(Boolean, default=False)
    telegram_user_id = Column(String(32))  # Telegram user id for Login Widget
    created_at = Column(DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False


class Achievement(Base):
    """Gamification achievements."""
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    unlocked_at = Column(DateTime, default=datetime.utcnow)


# Engine and session
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 5},
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record):
    """Reduce lock contention for the small SQLite database."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    return SessionLocal()
