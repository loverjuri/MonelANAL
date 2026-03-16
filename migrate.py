"""Add new columns to existing tables."""
from db.models import engine
from sqlalchemy import text

MIGRATIONS = [
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
