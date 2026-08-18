"""Add new columns to existing tables."""
from db.models import engine
from sqlalchemy import text

MIGRATIONS = [
    "ALTER TABLE finance ADD COLUMN source VARCHAR(128) DEFAULT ''",
    "ALTER TABLE finance ADD COLUMN income_tag VARCHAR(128) DEFAULT ''",
    "ALTER TABLE calculations ADD COLUMN source VARCHAR(128) DEFAULT 'Main'",
    "CREATE TABLE IF NOT EXISTS income_sources (id VARCHAR(36) PRIMARY KEY, name VARCHAR(128) UNIQUE NOT NULL, source_type VARCHAR(32) DEFAULT 'manual', hourly_rate REAL DEFAULT 0, weekend_hour_rate REAL DEFAULT 0, use_weekend_rate INTEGER DEFAULT 0, full_day_hours REAL DEFAULT 11, max_daily_hours REAL DEFAULT 24, sick_enabled INTEGER DEFAULT 0, sick_hour_rate REAL DEFAULT 0, paid_sick_hours REAL DEFAULT 0, is_active INTEGER DEFAULT 1)",
    "ALTER TABLE subscriptions ADD COLUMN requires_confirmation INTEGER DEFAULT 1",
    "ALTER TABLE subscriptions ADD COLUMN last_reminder_date VARCHAR(10) DEFAULT ''",
    "ALTER TABLE subscriptions ADD COLUMN source VARCHAR(128) DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS ip_savings (id VARCHAR(36) PRIMARY KEY, date VARCHAR(10) NOT NULL, revenue_amount REAL NOT NULL, reserve_amount REAL NOT NULL, tag VARCHAR(128) DEFAULT '', comment TEXT DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS ip_wallet_operations (id VARCHAR(36) PRIMARY KEY, date VARCHAR(10) NOT NULL, operation_type VARCHAR(16) NOT NULL, amount REAL NOT NULL, comment TEXT DEFAULT '')",
    "ALTER TABLE finance ADD COLUMN account_id VARCHAR(36) DEFAULT ''",
    "CREATE TABLE IF NOT EXISTS accounts (id VARCHAR(36) PRIMARY KEY, name VARCHAR(128) UNIQUE NOT NULL, account_type VARCHAR(32) DEFAULT 'card', opening_balance REAL DEFAULT 0, is_active INTEGER DEFAULT 1, created_at DATETIME)",
    "CREATE TABLE IF NOT EXISTS account_transfers (id VARCHAR(36) PRIMARY KEY, date VARCHAR(10) NOT NULL, from_account_id VARCHAR(36) NOT NULL, to_account_id VARCHAR(36) NOT NULL, amount REAL NOT NULL, comment TEXT DEFAULT '')",
    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, level VARCHAR(16), message TEXT)",
    "ALTER TABLE finance ADD COLUMN is_deleted INTEGER DEFAULT 0",
    "ALTER TABLE finance ADD COLUMN exclude_from_budget INTEGER DEFAULT 0",
    "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, chat_id VARCHAR(32), entity VARCHAR(32), entity_id VARCHAR(64), action VARCHAR(16), field VARCHAR(64), old_value TEXT, new_value TEXT)",
    "ALTER TABLE debts ADD COLUMN payment_cycle TEXT DEFAULT 'monthly'",
    "ALTER TABLE debts ADD COLUMN next_payment_date TEXT",
    "ALTER TABLE debts ADD COLUMN debt_kind TEXT DEFAULT 'credit'",
    "ALTER TABLE budget_plan ADD COLUMN period_type TEXT DEFAULT 'month'",
    "ALTER TABLE goals ADD COLUMN goal_type TEXT DEFAULT 'other'",
    "ALTER TABLE goals ADD COLUMN auto_fund_percent REAL DEFAULT 0",
    "ALTER TABLE goals ADD COLUMN auto_fund_amount REAL DEFAULT 0",
    "ALTER TABLE goals ADD COLUMN is_archived INTEGER DEFAULT 0",
    'ALTER TABLE subscriptions ADD COLUMN "group" TEXT DEFAULT \'other\'',
    "ALTER TABLE subscriptions ADD COLUMN sub_type TEXT DEFAULT 'expense'",
    "ALTER TABLE subscriptions ADD COLUMN is_overdue INTEGER DEFAULT 0",
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(64) UNIQUE NOT NULL,
        password_hash VARCHAR(256) NOT NULL,
        totp_secret VARCHAR(64),
        totp_verified INTEGER DEFAULT 0,
        created_at DATETIME
    )""",
    "ALTER TABLE users ADD COLUMN telegram_user_id VARCHAR(32)",
    "CREATE INDEX IF NOT EXISTS ix_finance_date_type_deleted ON finance (date, type, is_deleted)",
    "CREATE INDEX IF NOT EXISTS ix_finance_category_period ON finance (date, category, is_deleted)",
    "CREATE TABLE IF NOT EXISTS processed_updates (update_id INTEGER PRIMARY KEY, processed_at DATETIME NOT NULL)",
    "CREATE INDEX IF NOT EXISTS ix_processed_updates_processed_at ON processed_updates (processed_at)",
    "CREATE INDEX IF NOT EXISTS ix_worklog_date_job_status ON worklog (date, job_type, status)",
    "CREATE INDEX IF NOT EXISTS ix_orders_date ON orders (date)",
    "CREATE INDEX IF NOT EXISTS ix_state_chat_id ON state (chat_id)",
    "CREATE INDEX IF NOT EXISTS ix_subscriptions_due ON subscriptions (next_date, is_active, auto_create_expense)",
]

conn = engine.connect()
for sql in MIGRATIONS:
    try:
        conn.execute(text(sql))
        conn.commit()
        print(f"OK: {sql[:60]}")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"Skip (exists): {sql[:60]}")
        else:
            print(f"Note: {e}")
conn.close()
print("All migrations done")
