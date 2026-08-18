"""Initialize database tables and default config."""
from db.models import Base, engine, SessionLocal, Config


def create_tables():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def init_config_defaults():
    """Insert any missing default config rows without overwriting user values."""
    session = SessionLocal()
    try:
        count = session.query(Config).count()
        defaults = [
            ("FixedSalary", "100000"),
            ("SecondJobPercent", "10"),
            ("PayDay1", "10"),
            ("PayDay2", "25"),
            ("WorkHoursNorm", "8"),
            ("FullDayHours", "11"),
            ("MaxDailyHours", "24"),
            ("WeekendSeparateRate", "0"),
            ("WeekendHourRate", "0"),
            ("SickEnabled", "0"),
            ("SickHourRate", "0"),
            ("PaidSickHours", "0"),
            ("ChatID", ""),
            ("TimeZone", "Europe/Moscow"),
        ]
        existing = {r.parameter for r in session.query(Config).all()}
        for param, value in defaults:
            if param not in existing:
                session.add(Config(parameter=param, value=value))
        session.commit()
    finally:
        session.close()


def init_all():
    """Create tables and init config defaults."""
    create_tables()
    init_config_defaults()
