"""Tax calculations: NDFL, self-employment, IIS hints."""
from db.repositories import get_finance_for_period
from services.calculations import get_today_msk


def get_second_income_year(session) -> float:
    today = get_today_msk()
    year = today[:4]
    rows = get_finance_for_period(session, f"{year}-01-01", f"{year}-12-31")
    return sum(r.amount for r in rows if r.type == "IncomeSecond")


def calc_ndfl(income: float) -> dict:
    """NDFL 13%/15% calculation."""
    threshold = 5_000_000
    if income <= threshold:
        tax = income * 0.13
        rate = 13
    else:
        tax = threshold * 0.13 + (income - threshold) * 0.15
        rate = 15
    return {"income": income, "tax": int(tax), "rate": rate}


def get_tax_summary(session) -> str:
    income = get_second_income_year(session)
    today = get_today_msk()
    ndfl = calc_ndfl(income)
    lines = [
        f"Налоги за {today[:4]}",
        f"Доход (вторая работа): {int(income)} руб.",
        f"НДФЛ ({ndfl['rate']}%): ~{ndfl['tax']} руб.",
        "",
        "Самозанятость (НПД): 4% физлица / 6% юрлица",
        f"  НПД 4%: ~{int(income * 0.04)} руб.",
        f"  НПД 6%: ~{int(income * 0.06)} руб.",
        "",
        "ИИС: вычет типа А до 52 000 руб./год (13% от 400 000)",
    ]
    return "\n".join(lines)
