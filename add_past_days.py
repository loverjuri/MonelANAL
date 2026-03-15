#!/usr/bin/env python3
"""
Добавить записи о работе за прошлые дни.
Использование:
  python add_past_days.py
  # или с датами:
  python add_past_days.py 2025-03-11 2025-03-12

По умолчанию добавляет 11 и 12 число текущего месяца (8 ч, статус Work).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime
from zoneinfo import ZoneInfo
from db.repositories import get_session, add_work_log
from services.calculations import calc_hour_rate_snapshot_for_date

TZ = ZoneInfo("Europe/Moscow")
JOB_MAIN = "Main"
STATUS_WORK = "Work"


def main():
    if len(sys.argv) > 1:
        dates = sys.argv[1:]
    else:
        now = datetime.now(TZ)
        dates = [
            f"{now.year}-{now.month:02d}-11",
            f"{now.year}-{now.month:02d}-12",
        ]

    session = get_session()
    try:
        for date_str in dates:
            hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
            add_work_log(session, date_str, JOB_MAIN, 8, STATUS_WORK, hour_rate)
            print(f"Добавлено: {date_str} — 8 ч (основная работа)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
