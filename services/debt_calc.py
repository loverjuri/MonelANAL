"""Payment calculation for loans (annuity/fixed)."""
import math


def calc_annuity_payment(principal: float, annual_rate: float, months: int) -> float:
    """
    Annuity: M = P * (r * (1+r)^n) / ((1+r)^n - 1)
    r = monthly rate = annual/12/100
    """
    if months <= 0 or principal <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / months
    r = annual_rate / 12 / 100
    if r <= 0:
        return principal / months
    factor = (1 + r) ** months
    return principal * (r * factor) / (factor - 1)


def calc_fixed_first_payment(principal: float, annual_rate: float, months: int) -> float:
    """
    Differentiated (fixed principal): first payment = principal/n + interest on full principal.
    principal_part = P/n, interest = P * r (monthly)
    """
    if months <= 0 or principal <= 0:
        return 0.0
    principal_part = principal / months
    if annual_rate <= 0:
        return principal_part
    monthly_interest = principal * (annual_rate / 12 / 100)
    return principal_part + monthly_interest
