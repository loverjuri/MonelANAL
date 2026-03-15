"""Inflation adjustment for historical amounts."""

ANNUAL_INFLATION_RU = {
    2020: 4.9, 2021: 8.4, 2022: 11.9, 2023: 7.4, 2024: 9.5, 2025: 6.0, 2026: 5.0,
}


def get_inflation_rate(year: int) -> float:
    return ANNUAL_INFLATION_RU.get(year, 5.0) / 100


def adjust_for_inflation(amount: float, from_year: int, to_year: int = None) -> float:
    """Adjust amount from from_year to to_year (default: current year)."""
    from services.calculations import get_today_msk
    if to_year is None:
        to_year = int(get_today_msk()[:4])
    adjusted = amount
    for y in range(from_year, to_year):
        adjusted *= (1 + get_inflation_rate(y))
    return adjusted


def get_inflation_summary(amount: float, year: int) -> str:
    from services.calculations import get_today_msk
    current_year = int(get_today_msk()[:4])
    adjusted = adjust_for_inflation(amount, year, current_year)
    return f"{int(amount)} руб. ({year}) = ~{int(adjusted)} руб. ({current_year})"
