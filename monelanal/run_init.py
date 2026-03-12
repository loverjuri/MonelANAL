#!/usr/bin/env python3
"""Initialize database and prod calendar. Run once before starting the app."""
import sys
from pathlib import Path

# Ensure we're in the right directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.init_db import init_all
from services.prod_calendar import ensure_prod_calendar_updated


def main():
    print("Creating database tables...")
    init_all()
    print("Initializing prod calendar...")
    ensure_prod_calendar_updated()
    print("Done.")


if __name__ == "__main__":
    main()
