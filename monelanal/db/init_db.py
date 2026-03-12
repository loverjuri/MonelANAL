"""Initialize database tables and default config."""
from db.models import Base, engine, SessionLocal, Config


def create_tables():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def init_config_defaults():
    """Insert default config rows if Config table is empty."""
    session = SessionLocal()
    try:
        count = session.query(Config).count()
        if count > 0:
            return
        defaults = [
            ("FixedSalary", "100000"),
            ("SecondJobPercent", "10"),
            ("PayDay1", "10"),
            ("PayDay2", "25"),
            ("WorkHoursNorm", "8"),
            ("ChatID", ""),
            ("TimeZone", "Europe/Moscow"),
        ]
        for param, value in defaults:
            session.add(Config(parameter=param, value=value))
        session.commit()
    finally:
        session.close()


def init_all():
    """Create tables and init config defaults."""
    create_tables()
    init_config_defaults()
