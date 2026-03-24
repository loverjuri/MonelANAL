"""Web views: dashboard, expense, budget, goals, debts, etc."""
from flask import render_template, redirect, url_for, request, flash, jsonify, send_file, send_from_directory
from flask_login import login_required, current_user
import os
from . import web_bp
from db.models import get_session
from db.models import Finance
from db.repositories import (
    get_config_param,
    set_config_param,
    add_finance_entry,
    get_finance_for_period,
    get_finance_history,
    get_budget_limits_map,
    set_budget_plan_limit,
    get_active_goals,
    add_goal,
    update_goal_current,
    update_goal,
    get_goal,
    get_active_debts,
    get_debt_summary,
    add_debt,
    add_debt_payment,
    update_debt,
    get_debt,
    get_active_subscriptions,
    add_subscription,
    update_subscription,
    get_subscription,
    advance_subscription_date,
    get_templates,
    use_template,
    get_template,
    add_template,
    update_template,
    get_work_log_for_period,
    add_work_log,
    get_work_log,
    update_work_log,
    get_top_categories,
    get_achievements,
    get_debt_payments,
    get_finance_by_id,
    update_finance_entry,
    soft_delete_finance_entry,
    # Orders
    get_orders_for_period,
    get_order,
    add_order,
    update_order,
    delete_order,
    # Tags
    get_tags,
    add_tag,
    update_tag,
    delete_tag,
    # Calculations
    get_calculations,
    get_calculation,
    add_calculation,
    update_calculation,
    # Mass operations
    mass_finance_operations,
    # Goals extended
    get_archived_goals,
    archive_goal,
    transfer_between_goals,
    # Debts extended
    update_debt_payment,
    delete_debt_payment,
    # Subscriptions extended
    delete_subscription,
    get_inactive_subscriptions,
    get_overdue_subscriptions,
    # Templates extended
    delete_template,
    # Categories
    get_root_categories,
    add_category,
    # Search
    search_finance,
)
from services.calculations import (
    get_today_msk,
    get_accrued_summary_for_payday,
    get_next_pay_date,
    get_budget_balance,
    get_accrued_second_for_period,
    calc_hour_rate_snapshot_for_date,
)
from services.budget import (
    get_budget_status,
    get_month_range,
    get_forecast_end_of_month,
    suggest_plan_from_history,
    get_5030_20_hint,
)
from services.gamification import get_streak, check_achievements, ACHIEVEMENTS
from services.goals import get_goal_pace_hint, get_cushion_target, get_goal_icon
from services.recommendations import get_template_advice, generate_daily_digest
from services.reports import get_period_range, get_top_expenses, get_daily_average, compare_with_previous
from services.excel_import import parse_alfa_bank
from .cache_helpers import (
    get_cached_status,
    set_cached_status,
    get_cached_budget,
    set_cached_budget,
    invalidate_status,
    invalidate_budget,
)
import io
from datetime import datetime, timedelta

# Categories (from bot/keyboards)
EXPENSE_CATEGORIES = [
    "Еда", "Транспорт", "ЗП Выплата", "Жильё", "Здоровье", "Развлечения", "Прочее",
]

def _get_status_data(session):
    """Cached status data for dashboard."""
    today = get_today_msk()
    acc = get_accrued_summary_for_payday(session)
    next_pay = get_next_pay_date(today, session)
    balance = get_budget_balance(session)
    start_month = today[:7] + "-01"
    second_month = get_accrued_second_for_period(start_month, today, session)
    debt_sum = get_debt_summary(session)
    return {
        "accrued_main": int(acc["accruedMain"]),
        "accrued_second_month": int(second_month),
        "balance": int(balance),
        "next_pay": next_pay,
        "debt_owe": int(debt_sum["owe"]),
        "debt_lent": int(debt_sum["lent"]),
    }


def _get_session_data():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@web_bp.route("/sw.js")
def service_worker():
    """Serve service worker at /web/sw.js for correct scope."""
    return send_from_directory(os.path.join(os.path.dirname(__file__), "static"), "sw.js", mimetype="application/javascript")


@web_bp.route("/")
def index():
    """Redirect /web to login or dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return redirect(url_for("web.login"))


@web_bp.route("/dashboard")
@login_required
def dashboard():
    data = get_cached_status()
    if data is None:
        session = get_session()
        try:
            data = _get_status_data(session)
            set_cached_status(data)
        finally:
            session.close()
    session = get_session()
    try:
        recent = get_finance_history(session, limit=10)
        advice = get_template_advice(session)
        digest = generate_daily_digest(session)
        return render_template("dashboard.html", status=data, recent=recent,
                               advice=advice, digest=digest)
    finally:
        session.close()


@web_bp.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    session = get_session()
    try:
        today = get_today_msk()
        if request.method == "POST":
            amount_str = (request.form.get("amount") or "").strip().replace(",", ".")
            category = (request.form.get("category") or "Прочее").strip()
            comment = (request.form.get("comment") or "").strip()
            date_str = (request.form.get("date") or today)[:10]
            try:
                amount = float(amount_str)
            except ValueError:
                flash("Введите корректную сумму", "error")
                last_exp = next((r for r in get_finance_history(session, limit=10) if r.type == "Expense"), None)
                last_cat = last_exp.category if last_exp and last_exp.category in EXPENSE_CATEGORIES else "Прочее"
                return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today, last_category=last_cat)
            if amount <= 0:
                flash("Сумма должна быть положительной", "error")
                last_exp = next((r for r in get_finance_history(session, limit=10) if r.type == "Expense"), None)
                last_cat = last_exp.category if last_exp and last_exp.category in EXPENSE_CATEGORIES else "Прочее"
                return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today, last_category=last_cat)
            add_finance_entry(session, date_str, "Expense", amount, category, comment)
            invalidate_status()
            invalidate_budget()
            flash(f"Расход {int(amount)} руб. записан", "success")
            return redirect(url_for("web.dashboard"))
        last_exp = next((r for r in get_finance_history(session, limit=10) if r.type == "Expense"), None)
        last_category = last_exp.category if last_exp and last_exp.category in EXPENSE_CATEGORIES else "Прочее"
        return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today, last_category=last_category)
    finally:
        session.close()


@web_bp.route("/expense/quick", methods=["POST"])
@login_required
def expense_quick():
    """Quick expense from header field: amount category or amount."""
    text = (request.form.get("q") or request.json.get("q") if request.is_json else "").strip()
    if not text:
        return jsonify({"ok": False, "error": "Пусто"})
    parts = text.split(maxsplit=1)
    try:
        amount = float(parts[0].replace(",", "."))
    except ValueError:
        return jsonify({"ok": False, "error": "Укажите сумму"})
    category = parts[1].strip() if len(parts) > 1 else "Прочее"
    if category not in EXPENSE_CATEGORIES:
        category = "Прочее"
    session = get_session()
    try:
        add_finance_entry(session, get_today_msk(), "Expense", amount, category, "")
        invalidate_status()
        invalidate_budget()
        return jsonify({"ok": True, "amount": amount})
    finally:
        session.close()


@web_bp.route("/income", methods=["GET", "POST"])
@login_required
def income():
    session = get_session()
    try:
        today = get_today_msk()
        if request.method == "POST":
            amount_str = (request.form.get("amount") or "").strip().replace(",", ".")
            comment = (request.form.get("comment") or "").strip()
            date_str = (request.form.get("date") or today)[:10]
            try:
                amount = float(amount_str)
            except ValueError:
                flash("Введите корректную сумму", "error")
                return render_template("income.html", today=today)
            if amount <= 0:
                flash("Сумма должна быть положительной", "error")
                return render_template("income.html", today=today)
            add_finance_entry(session, date_str, "IncomeSecond", amount, "", comment)
            invalidate_status()
            invalidate_budget()
            flash(f"Доход {int(amount)} руб. записан", "success")
            return redirect(url_for("web.dashboard"))
        return render_template("income.html", today=today)
    finally:
        session.close()


@web_bp.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    session = get_session()
    try:
        today = get_today_msk()
        month_year = request.args.get("month") or request.form.get("month") or today[:7]
        if len(month_year) == 7 and month_year[4] == "-":
            pass
        else:
            month_year = today[:7]

        if request.method == "POST":
            action = request.form.get("action")
            if action == "set":
                cat = request.form.get("category")
                amt = request.form.get("amount")
                if cat and cat in EXPENSE_CATEGORIES and amt is not None:
                    try:
                        amount = float(amt.replace(",", "."))
                        if amount >= 0:
                            set_budget_plan_limit(session, month_year, cat, amount)
                            flash("Лимит обновлён", "success")
                    except ValueError:
                        flash("Некорректная сумма", "error")
                return redirect(url_for("web.budget", month=month_year))
            if action == "bulk":
                for cat in EXPENSE_CATEGORIES:
                    amt = request.form.get(f"limit_{cat}")
                    if amt is not None and amt.strip() != "":
                        try:
                            amount = float(amt.replace(",", "."))
                            if amount >= 0:
                                set_budget_plan_limit(session, month_year, cat, amount)
                        except ValueError:
                            pass
                invalidate_budget(month_year)
                flash("Лимиты сохранены", "success")
                return redirect(url_for("web.budget", month=month_year))
            if action == "suggest":
                suggested = suggest_plan_from_history(session)
                if suggested:
                    for cat, amt in suggested.items():
                        set_budget_plan_limit(session, month_year, cat, amt)
                    flash("План предложен по средним за 3 месяца", "success")
                else:
                    flash("Недостаточно данных для предложения", "error")
                invalidate_budget(month_year)
                return redirect(url_for("web.budget", month=month_year))

        st = get_cached_budget(month_year)
        if st is None:
            st = get_budget_status(session, month_year)
            set_cached_budget(month_year, st)
        forecast = get_forecast_end_of_month(session)
        limits = st.get("limits", {})
        hint_5030 = get_5030_20_hint(session)
        return render_template(
            "budget.html",
            budget=st,
            forecast=forecast,
            month_year=month_year,
            categories=EXPENSE_CATEGORIES,
            limits=limits,
            hint_5030=hint_5030,
        )
    finally:
        session.close()


@web_bp.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                name = (request.form.get("name") or "").strip()
                target = request.form.get("target_amount")
                deadline = (request.form.get("deadline") or "").strip()[:10] or None
                if name and target:
                    try:
                        amt = float(target.replace(",", "."))
                        if amt > 0:
                            add_goal(session, name, amt, deadline)
                            flash("Цель добавлена", "success")
                    except ValueError:
                        flash("Некорректная сумма", "error")
                else:
                    flash("Введите название и сумму", "error")
                return redirect(url_for("web.goals"))
            if action == "fund":
                gid = request.form.get("goal_id")
                amt_str = request.form.get("amount")
                if gid and amt_str:
                    try:
                        amt = float(amt_str.replace(",", "."))
                        if amt > 0 and update_goal_current(session, gid, amt):
                            flash("Цель пополнена", "success")
                        else:
                            flash("Ошибка пополнения", "error")
                    except ValueError:
                        flash("Некорректная сумма", "error")
                return redirect(url_for("web.goals"))
            if action == "archive":
                gid = request.form.get("goal_id")
                if gid:
                    update_goal(session, gid, is_active=False, is_archived=True)
                    flash("Цель в архиве", "success")
                return redirect(url_for("web.goals"))
            if action == "edit":
                gid = request.form.get("goal_id")
                name = (request.form.get("name") or "").strip()
                target = request.form.get("target_amount")
                current = request.form.get("current_amount")
                deadline = (request.form.get("deadline") or "").strip()[:10]
                if gid:
                    kw = {}
                    if name:
                        kw["name"] = name
                    if target is not None and target != "":
                        try:
                            kw["target_amount"] = float(target.replace(",", "."))
                        except ValueError:
                            pass
                    if current is not None and current != "":
                        try:
                            kw["current_amount"] = float(current.replace(",", "."))
                        except ValueError:
                            pass
                    if deadline is not None:
                        kw["deadline"] = deadline
                    if kw and update_goal(session, gid, **kw):
                        flash("Цель обновлена", "success")
                return redirect(url_for("web.goals"))

            if action == "transfer":
                from_id = request.form.get("from_goal_id")
                to_id = request.form.get("to_goal_id")
                amt_str = request.form.get("amount") or "0"
                try:
                    amt = float(amt_str.replace(",", "."))
                    if amt > 0 and transfer_between_goals(session, from_id, to_id, amt):
                        flash("Перевод выполнен", "success")
                    else:
                        flash("Ошибка перевода", "error")
                except ValueError:
                    flash("Некорректная сумма", "error")
                return redirect(url_for("web.goals"))

        goals_list = get_active_goals(session)
        archived = get_archived_goals(session)
        cushion = get_cushion_target(session)
        pace_hints = {}
        for g in goals_list:
            pace_hints[g.id] = get_goal_pace_hint(g)
        return render_template("goals.html", goals=goals_list, archived=archived,
                               cushion=int(cushion), pace_hints=pace_hints)
    finally:
        session.close()


@web_bp.route("/goals/<goal_id>/edit")
@login_required
def goal_edit_form(goal_id):
    session = get_session()
    try:
        g = get_goal(session, goal_id)
        if not g:
            flash("Цель не найдена", "error")
            return redirect(url_for("web.goals"))
        return render_template("goal_edit.html", goal=g)
    finally:
        session.close()


@web_bp.route("/debts", methods=["GET", "POST"])
@login_required
def debts():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                direction = request.form.get("direction")
                counterparty = (request.form.get("counterparty") or "").strip()
                amount_str = request.form.get("amount") or "0"
                try:
                    amount = float(amount_str.replace(",", "."))
                except ValueError:
                    amount = 0
                if not counterparty or amount <= 0:
                    flash("Укажите контрагента и сумму", "error")
                    return redirect(url_for("web.debts"))
                add_debt(session, direction=direction or "owe", counterparty=counterparty,
                         original_amount=amount, next_payment_date=request.form.get("next_payment_date") or "",
                         due_date=request.form.get("due_date") or "")
                invalidate_status()
                flash(f"Долг «{counterparty}» добавлен", "success")
            elif action == "payment":
                debt_id = request.form.get("debt_id")
                amount_str = request.form.get("amount") or "0"
                try:
                    amount = float(amount_str.replace(",", "."))
                except ValueError:
                    amount = 0
                if not debt_id or amount <= 0:
                    flash("Укажите сумму платежа", "error")
                    return redirect(url_for("web.debts"))
                pid = add_debt_payment(session, debt_id, amount,
                                       comment=request.form.get("comment") or "",
                                       date=request.form.get("payment_date") or None)
                if pid:
                    invalidate_status()
                    flash("Платёж учтён", "success")
                else:
                    flash("Долг не найден", "error")
            elif action == "edit":
                debt_id = request.form.get("debt_id")
                debt = get_debt(session, debt_id)
                if not debt:
                    flash("Долг не найден", "error")
                    return redirect(url_for("web.debts"))
                kwargs = {}
                if "counterparty" in request.form:
                    kwargs["counterparty"] = (request.form.get("counterparty") or "").strip()
                if request.form.get("remaining_amount", "").strip() != "":
                    try:
                        ra = float(request.form.get("remaining_amount", "0").replace(",", "."))
                        kwargs["remaining_amount"] = max(0, ra)
                        kwargs["is_active"] = ra > 0
                    except ValueError:
                        pass
                if "due_date" in request.form:
                    kwargs["due_date"] = request.form.get("due_date") or ""
                if "next_payment_date" in request.form:
                    kwargs["next_payment_date"] = request.form.get("next_payment_date") or None
                if kwargs:
                    update_debt(session, debt_id, **kwargs)
                    invalidate_status()
                    flash("Долг обновлён", "success")
                return redirect(url_for("web.debts"))
            return redirect(url_for("web.debts"))
        debts_list = get_active_debts(session)
        summary = get_debt_summary(session)
        return render_template("debts.html", debts=debts_list, summary=summary, now=get_today_msk())
    finally:
        session.close()


@web_bp.route("/debts/edit/<debt_id>", methods=["GET", "POST"])
@login_required
def debt_edit_form(debt_id):
    session = get_session()
    try:
        d = get_debt(session, debt_id)
        if not d:
            flash("Долг не найден", "error")
            return redirect(url_for("web.debts"))
        if request.method == "POST":
            action = request.form.get("action")
            if action == "delete_payment":
                pid = request.form.get("payment_id")
                if pid and delete_debt_payment(session, pid):
                    flash("Платёж удалён", "success")
                return redirect(url_for("web.debt_edit_form", debt_id=debt_id))
            if action == "edit_payment":
                pid = request.form.get("payment_id")
                amt_str = request.form.get("amount") or ""
                date_str = request.form.get("date") or None
                try:
                    amt = float(amt_str.replace(",", ".")) if amt_str else None
                except ValueError:
                    amt = None
                if pid and update_debt_payment(session, pid, amount=amt, date=date_str):
                    flash("Платёж обновлён", "success")
                return redirect(url_for("web.debt_edit_form", debt_id=debt_id))
        payments = get_debt_payments(session, debt_id)
        return render_template("debt_edit.html", debt=d, payments=payments)
    finally:
        session.close()


@web_bp.route("/subscriptions", methods=["GET", "POST"])
@login_required
def subscriptions():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                name = (request.form.get("name") or "").strip()
                amount_str = request.form.get("amount") or "0"
                cycle = request.form.get("cycle") or "monthly"
                next_date = request.form.get("next_date") or get_today_msk()
                try:
                    amount = float(amount_str.replace(",", "."))
                except ValueError:
                    amount = 0
                if not name or amount <= 0:
                    flash("Укажите название и сумму", "error")
                    return redirect(url_for("web.subscriptions"))
                add_subscription(session, name=name, amount=amount, cycle=cycle,
                                next_date=next_date, category=request.form.get("category") or "Прочее")
                flash(f"Подписка «{name}» добавлена", "success")
            elif action == "edit":
                sub_id = request.form.get("subscription_id")
                sub = get_subscription(session, sub_id)
                if not sub:
                    flash("Подписка не найдена", "error")
                    return redirect(url_for("web.subscriptions"))
                kwargs = {}
                if request.form.get("name"):
                    kwargs["name"] = request.form.get("name").strip()
                if request.form.get("amount"):
                    try:
                        kwargs["amount"] = float(request.form.get("amount").replace(",", "."))
                    except ValueError:
                        pass
                if request.form.get("cycle"):
                    kwargs["cycle"] = request.form.get("cycle")
                if request.form.get("next_date"):
                    kwargs["next_date"] = request.form.get("next_date")[:10]
                if kwargs:
                    update_subscription(session, sub_id, **kwargs)
                    flash("Подписка обновлена", "success")
                return redirect(url_for("web.subscriptions"))
            elif action == "pause":
                sub_id = request.form.get("subscription_id")
                if get_subscription(session, sub_id):
                    update_subscription(session, sub_id, is_active=False)
                    flash("Подписка приостановлена", "success")
                else:
                    flash("Подписка не найдена", "error")
            elif action == "advance":
                sub_id = request.form.get("subscription_id")
                if advance_subscription_date(session, sub_id):
                    flash("Дата следующего платежа перенесена", "success")
                else:
                    flash("Подписка не найдена", "error")
            elif action == "delete":
                sub_id = request.form.get("subscription_id")
                if sub_id and delete_subscription(session, sub_id):
                    flash("Подписка удалена", "success")
                else:
                    flash("Подписка не найдена", "error")
            elif action == "reactivate":
                sub_id = request.form.get("subscription_id")
                if sub_id and get_subscription(session, sub_id):
                    update_subscription(session, sub_id, is_active=True)
                    flash("Подписка возобновлена", "success")
            return redirect(url_for("web.subscriptions"))
        subs = get_active_subscriptions(session)
        inactive = get_inactive_subscriptions(session)
        overdue = get_overdue_subscriptions(session)
        return render_template("subscriptions.html", subscriptions=subs, inactive=inactive,
                               overdue=overdue, now=get_today_msk(), categories=EXPENSE_CATEGORIES)
    finally:
        session.close()


@web_bp.route("/subscriptions/edit/<sub_id>")
@login_required
def subscription_edit_form(sub_id):
    session = get_session()
    try:
        s = get_subscription(session, sub_id)
        if not s:
            flash("Подписка не найдена", "error")
            return redirect(url_for("web.subscriptions"))
        return render_template("subscription_edit.html", subscription=s)
    finally:
        session.close()


@web_bp.route("/analytics")
@login_required
def analytics():
    period = request.args.get("period", "month")
    session = get_session()
    try:
        start, end = get_period_range(period)
        rows = get_finance_for_period(session, start, end)
        by_cat = {}
        income = expense = 0
        for r in rows:
            amt = r.amount or 0
            if r.type in ("IncomeSalary", "IncomeSecond"):
                income += amt
            elif r.type == "Expense" and not getattr(r, "exclude_from_budget", False):
                expense += amt
                cat = r.category or "Без категории"
                by_cat[cat] = by_cat.get(cat, 0) + amt
        chart_data = [{"category": k, "amount": v} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]
        top_expenses = get_top_expenses(session, start, end, limit=5)
        daily_avg = get_daily_average(session, start, end)
        comparison = compare_with_previous(session, period)
        return render_template("analytics.html", period=period, chart_data=chart_data,
                               income=int(income), expense=int(expense), balance=int(income - expense),
                               start=start, end=end, top_expenses=top_expenses,
                               daily_avg=int(daily_avg), comparison=comparison)
    finally:
        session.close()


@web_bp.route("/history", methods=["GET", "POST"])
@login_required
def history():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "delete":
                fid = request.form.get("entry_id")
                if fid and soft_delete_finance_entry(session, fid):
                    invalidate_status()
                    invalidate_budget()
                    flash("Запись удалена", "success")
                else:
                    flash("Запись не найдена", "error")
            elif action == "edit":
                fid = request.form.get("entry_id")
                entry = get_finance_by_id(session, fid)
                if not entry:
                    flash("Запись не найдена", "error")
                    return redirect(url_for("web.history"))
                kwargs = {}
                if request.form.get("amount") not in (None, ""):
                    try:
                        kwargs["amount"] = float(request.form.get("amount").replace(",", "."))
                    except ValueError:
                        pass
                if "category" in request.form:
                    kwargs["category"] = request.form.get("category") or None
                if "comment" in request.form:
                    kwargs["comment"] = request.form.get("comment") or None
                if "date" in request.form and request.form.get("date"):
                    kwargs["date"] = request.form.get("date")[:10]
                if kwargs:
                    update_finance_entry(session, fid, **kwargs)
                    invalidate_status()
                    invalidate_budget()
                    flash("Запись обновлена", "success")
                return redirect(url_for("web.history"))
            return redirect(url_for("web.history"))

        page = max(1, int(request.args.get("page", 1)))
        per_page = 30
        offset = (page - 1) * per_page
        search_q = (request.args.get("q") or "").strip()
        category_filter = (request.args.get("category") or "").strip()

        if search_q and not category_filter:
            all_results = search_finance(session, search_q, limit=500)
            try:
                amount_val = float(search_q.replace(",", "."))
                extra = session.query(Finance).filter(
                    Finance.is_deleted == False, Finance.amount == amount_val
                ).order_by(Finance.date.desc()).limit(50).all()
                seen = {r.id for r in all_results}
                all_results.extend(r for r in extra if r.id not in seen)
            except ValueError:
                pass
            all_results.sort(key=lambda r: (r.date or "", r.id or 0), reverse=True)
            rows = all_results[offset:offset + per_page + 1]
        else:
            q = session.query(Finance).filter(Finance.is_deleted == False)
            if search_q:
                from sqlalchemy import or_
                text_filt = or_(
                    Finance.comment.contains(search_q),
                    Finance.category.contains(search_q),
                    Finance.type.contains(search_q)
                )
                try:
                    amount_val = float(search_q.replace(",", "."))
                    q = q.filter(or_(text_filt, Finance.amount == amount_val))
                except ValueError:
                    q = q.filter(text_filt)
            if category_filter:
                q = q.filter(Finance.category == category_filter)
            q = q.order_by(Finance.date.desc(), Finance.id.desc())
            rows = q.offset(offset).limit(per_page + 1).all()
        has_more = len(rows) > per_page
        rows = rows[:per_page]

        cat_rows = session.query(Finance.category).filter(
            Finance.is_deleted == False, Finance.category.isnot(None)
        ).distinct().all()
        categories = list(sorted(set(r[0] for r in cat_rows if r[0])))
        return render_template("history.html", rows=rows, page=page, has_more=has_more,
                               search_q=search_q, category=category_filter, categories=categories)
    finally:
        session.close()


@web_bp.route("/history/edit/<entry_id>")
@login_required
def history_edit_form(entry_id):
    session = get_session()
    try:
        entry = get_finance_by_id(session, entry_id)
        if not entry:
            flash("Запись не найдена", "error")
            return redirect(url_for("web.history"))
        return render_template("history_edit.html", entry=entry, categories=EXPENSE_CATEGORIES)
    finally:
        session.close()


@web_bp.route("/templates", methods=["GET", "POST"])
@login_required
def templates_list():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                name = (request.form.get("name") or "").strip()
                amount_str = request.form.get("amount") or "0"
                category = request.form.get("category") or "Прочее"
                try:
                    amount = float(amount_str.replace(",", "."))
                except ValueError:
                    amount = 0
                if not name or amount <= 0:
                    flash("Укажите название и сумму", "error")
                    return redirect(url_for("web.templates_list"))
                add_template(session, name=name, amount=amount, category=category)
                flash(f"Шаблон «{name}» создан", "success")
            elif action == "edit":
                template_id = request.form.get("template_id")
                t = get_template(session, template_id)
                if not t:
                    flash("Шаблон не найден", "error")
                    return redirect(url_for("web.templates_list"))
                kwargs = {}
                if request.form.get("name"):
                    kwargs["name"] = request.form.get("name").strip()
                if request.form.get("amount"):
                    try:
                        kwargs["amount"] = float(request.form.get("amount").replace(",", "."))
                    except ValueError:
                        pass
                if request.form.get("category"):
                    kwargs["category"] = request.form.get("category")
                if kwargs:
                    update_template(session, template_id, **kwargs)
                    flash("Шаблон обновлён", "success")
                return redirect(url_for("web.templates_list"))
            elif action == "delete":
                template_id = request.form.get("template_id")
                if template_id and delete_template(session, template_id):
                    flash("Шаблон удалён", "success")
                else:
                    flash("Шаблон не найден", "error")
            return redirect(url_for("web.templates_list"))
        templates = get_templates(session)
        return render_template("templates.html", templates=templates, categories=EXPENSE_CATEGORIES)
    finally:
        session.close()


@web_bp.route("/templates/edit/<template_id>")
@login_required
def template_edit_form(template_id):
    session = get_session()
    try:
        t = get_template(session, template_id)
        if not t:
            flash("Шаблон не найден", "error")
            return redirect(url_for("web.templates_list"))
        return render_template("template_edit.html", template=t, categories=EXPENSE_CATEGORIES)
    finally:
        session.close()


@web_bp.route("/templates/use/<template_id>", methods=["POST"])
@login_required
def template_use(template_id):
    session = get_session()
    try:
        data = use_template(session, template_id)
        if not data:
            flash("Шаблон не найден", "error")
            return redirect(url_for("web.templates_list"))
        add_finance_entry(session, get_today_msk(), "Expense", data["amount"], data["category"], data["name"])
        invalidate_status()
        invalidate_budget()
        flash(f"Расход {int(data['amount'])} руб. по шаблону «{data['name']}»", "success")
    finally:
        session.close()
    return redirect(url_for("web.dashboard"))


@web_bp.route("/worklog", methods=["GET", "POST"])
@login_required
def worklog():
    session = get_session()
    try:
        today = get_today_msk()
        month_arg = request.args.get("month") or request.form.get("month") or today[:7]
        start = month_arg + "-01"
        end = today
        if month_arg < today[:7]:
            from datetime import datetime
            try:
                yr, mo = int(month_arg[:4]), int(month_arg[5:7])
                end = f"{yr:04d}-{mo:02d}-{(datetime(yr, mo % 12 + 1, 1) - timedelta(days=1)).day:02d}"
            except (ValueError, TypeError):
                end = start

        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                date_str = request.form.get("date") or get_today_msk()
                hours_str = request.form.get("hours") or "0"
                status = request.form.get("status") or "Work"
                try:
                    hours = float(hours_str.replace(",", "."))
                except ValueError:
                    hours = 0
                if hours <= 0 and status != "Sick":
                    flash("Укажите часы", "error")
                    return redirect(url_for("web.worklog", month=month_arg))
                if status == "Sick":
                    hours = 0
                hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
                add_work_log(session, date_str=date_str, job_type="Main", hours_worked=hours,
                             status=status, hour_rate=hour_rate)
                flash("Запись добавлена", "success")
            elif action == "edit":
                wl_id = request.form.get("worklog_id")
                month_arg = request.form.get("month") or month_arg
                w = get_work_log(session, wl_id)
                if not w:
                    flash("Запись не найдена", "error")
                    return redirect(url_for("web.worklog", month=month_arg))
                kwargs = {}
                if request.form.get("date"):
                    kwargs["date"] = request.form.get("date")[:10]
                hrs = request.form.get("hours")
                if hrs is not None and str(hrs).strip() != "":
                    try:
                        kwargs["hours_worked"] = float(str(hrs).replace(",", "."))
                    except ValueError:
                        pass
                if request.form.get("status"):
                    kwargs["status"] = request.form.get("status")
                if kwargs:
                    update_work_log(session, wl_id, **kwargs)
                    flash("Запись обновлена", "success")
                return redirect(url_for("web.worklog", month=month_arg))
            return redirect(url_for("web.worklog", month=month_arg))

        entries = get_work_log_for_period(session, start, end, job_type="Main")
        return render_template("worklog.html", entries=entries, month=month_arg, today=today)
    finally:
        session.close()


@web_bp.route("/worklog/edit/<wl_id>")
@login_required
def worklog_edit_form(wl_id):
    session = get_session()
    try:
        w = get_work_log(session, wl_id)
        if not w:
            flash("Запись не найдена", "error")
            return redirect(url_for("web.worklog"))
        return render_template("worklog_edit.html", entry=w)
    finally:
        session.close()


@web_bp.route("/more")
@login_required
def more():
    """More menu: debts, subscriptions, analytics, history, settings."""
    return render_template("more.html")


@web_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    session = get_session()
    try:
        config_keys = ["FixedSalary", "PayDay1", "PayDay2", "WorkHoursNorm",
                        "LargeExpenseThreshold", "QuietHoursStart", "QuietHoursEnd", "ChatID"]
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add_category":
                cat_name = (request.form.get("category_name") or "").strip()
                if cat_name:
                    add_category(session, cat_name)
                    flash(f"Категория «{cat_name}» добавлена", "success")
                return redirect(url_for("web.settings"))
            if action == "delete_all":
                from services.backup import delete_all_data
                delete_all_data(session)
                flash("Все данные удалены", "success")
                return redirect(url_for("web.settings"))
            for k in config_keys:
                v = request.form.get(k)
                if v is not None:
                    set_config_param(session, k, str(v).strip() or "")
            flash("Настройки сохранены", "success")
            return redirect(url_for("web.settings"))
        config = {k: get_config_param(session, k) for k in config_keys}
        categories = get_root_categories(session)
        return render_template("settings.html", config=config, categories=categories)
    finally:
        session.close()


@web_bp.route("/settings/backup")
@login_required
def settings_backup():
    session = get_session()
    try:
        from services.backup import create_backup_json
        path = create_backup_json(session)
        return send_file(path, as_attachment=True, download_name="monel_backup.json",
                         mimetype="application/json")
    finally:
        session.close()


@web_bp.route("/achievements")
@login_required
def achievements():
    session = get_session()
    try:
        check_achievements(session)
        unlocked = get_achievements(session)
        unlocked_codes = {a.code for a in unlocked if hasattr(a, 'code')}
        streak = get_streak(session)
        return render_template("achievements.html", achievements=unlocked,
                               unlocked_codes=unlocked_codes, streak=streak,
                               ACHIEVEMENTS=ACHIEVEMENTS)
    finally:
        session.close()


@web_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_data():
    if request.method == "GET":
        return render_template("import.html")
    f = request.files.get("file")
    if not f or not f.filename.endswith((".xlsx", ".xls")):
        flash("Загрузите файл Excel (.xlsx)", "error")
        return redirect(url_for("web.import_data"))
    content = f.read()
    if len(content) > 1_000_000:  # 1 MB limit
        flash("Файл слишком большой (макс 1 MB)", "error")
        return redirect(url_for("web.import_data"))
    from db.repositories import has_finance_duplicate
    rows = parse_alfa_bank(io.BytesIO(content))
    session = get_session()
    added = 0
    try:
        for r in rows[:500]:  # limit 500 rows
            date_str = r.get("date")
            amount = r.get("amount", 0)
            if not date_str or amount == 0:
                continue
            if amount < 0:
                entry_type = "Expense"
                amount = abs(amount)
            else:
                entry_type = "IncomeSecond"
            if has_finance_duplicate(session, date_str, amount):
                continue
            add_finance_entry(session, date_str, entry_type, amount, r.get("category_bank", "Импорт"), r.get("description", ""))
            added += 1
        if added:
            invalidate_status()
            invalidate_budget()
        flash(f"Импортировано {added} записей", "success")
    finally:
        session.close()
    return redirect(url_for("web.dashboard"))


@web_bp.route("/export")
@login_required
def export_data():
    session = get_session()
    try:
        from datetime import datetime
        start = (request.args.get("start") or (datetime.now().replace(day=1) - timedelta(days=365)).strftime("%Y-%m-%d"))[:10]
        end = (request.args.get("end") or get_today_msk())[:10]
        rows = get_finance_for_period(session, start, end)
        buf = io.StringIO()
        buf.write("date\ttype\tamount\tcategory\tcomment\n")
        for r in rows:
            buf.write(f"{r.date}\t{r.type}\t{r.amount}\t{r.category or ''}\t{r.comment or ''}\n")
        buf.seek(0)
        return send_file(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"monelanal_export_{start}_{end}.csv",
        )
    finally:
        session.close()


# ─── Orders (Second Job) ──────────────────────────────────────
@web_bp.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    session = get_session()
    try:
        today = get_today_msk()
        month_arg = request.args.get("month") or today[:7]
        start = month_arg + "-01"
        end = month_arg + "-31"

        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                date_str = (request.form.get("date") or today)[:10]
                desc = (request.form.get("description") or "").strip()
                try:
                    amount = float((request.form.get("amount") or "0").replace(",", ".").replace(" ", ""))
                except ValueError:
                    amount = 0
                if amount > 0:
                    add_order(session, date_str, desc, amount)
                    flash("Заказ добавлен", "success")
                else:
                    flash("Введите сумму", "error")
            elif action == "delete":
                oid = request.form.get("order_id")
                if oid:
                    delete_order(session, oid)
                    flash("Заказ удалён", "success")
            return redirect(url_for("web.orders", month=month_arg))

        entries = get_orders_for_period(session, start, end)
        entries.sort(key=lambda o: o.date, reverse=True)
        total = sum(o.amount for o in entries)
        return render_template("orders.html", entries=entries, month=month_arg, today=today, total=total)
    finally:
        session.close()


@web_bp.route("/orders/edit/<order_id>", methods=["GET", "POST"])
@login_required
def order_edit(order_id):
    session = get_session()
    try:
        o = get_order(session, order_id)
        if not o:
            flash("Заказ не найден", "error")
            return redirect(url_for("web.orders"))
        if request.method == "POST":
            kwargs = {}
            for field in ("date", "description", "amount", "status"):
                v = request.form.get(field)
                if v is not None:
                    if field == "amount":
                        try:
                            kwargs[field] = float(v.replace(",", ".").replace(" ", ""))
                        except ValueError:
                            pass
                    else:
                        kwargs[field] = v.strip()
            if kwargs:
                update_order(session, order_id, **kwargs)
                flash("Заказ обновлён", "success")
            return redirect(url_for("web.orders"))
        return render_template("order_edit.html", entry=o)
    finally:
        session.close()


@web_bp.route("/orders/add-bulk", methods=["GET", "POST"])
@login_required
def orders_add_bulk():
    if request.method == "GET":
        return render_template("orders_add_bulk.html", today=get_today_msk())
    text = (request.form.get("data") or "").strip()
    if not text:
        flash("Введите данные", "error")
        return redirect(url_for("web.orders_add_bulk"))
    session = get_session()
    added = 0
    try:
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            date_raw, amount_raw, desc = parts[0], parts[-1], " ".join(parts[1:-1])
            try:
                amount = float(amount_raw.replace(",", ".").replace(" ", ""))
            except ValueError:
                try:
                    amount = float(parts[1].replace(",", ".").replace(" ", ""))
                    desc = " ".join(parts[2:])
                except (ValueError, IndexError):
                    continue
            if len(date_raw) <= 2:
                today = get_today_msk()
                date_str = f"{today[:8]}{int(date_raw):02d}"
            else:
                date_str = date_raw[:10]
            add_order(session, date_str, desc, amount)
            added += 1
        flash(f"Добавлено {added} заказов", "success")
    finally:
        session.close()
    return redirect(url_for("web.orders"))


# ─── WorkLog bulk add ─────────────────────────────────────────
@web_bp.route("/worklog/add-bulk", methods=["GET", "POST"])
@login_required
def worklog_add_bulk():
    if request.method == "GET":
        return render_template("worklog_add_bulk.html", today=get_today_msk())
    text = (request.form.get("dates") or "").strip()
    hours_str = (request.form.get("hours") or "8").strip()
    try:
        hours = float(hours_str.replace(",", "."))
    except ValueError:
        hours = 8
    if not text:
        flash("Введите даты", "error")
        return redirect(url_for("web.worklog_add_bulk"))
    session = get_session()
    added = 0
    try:
        today = get_today_msk()
        dates = _parse_date_input(text, today)
        for date_str in dates:
            hour_rate = calc_hour_rate_snapshot_for_date(date_str, session)
            add_work_log(session, date_str, "Main", hours, "Work", hour_rate)
            added += 1
        flash(f"Добавлено {added} записей", "success")
    finally:
        session.close()
    return redirect(url_for("web.worklog"))


def _parse_date_input(text: str, today: str) -> list[str]:
    """Parse dates: '11-13' (range), '11 12 13' (list), '2026-03-11' (full)."""
    text = text.strip()
    result = []
    if "-" in text and len(text) <= 5 and text.replace("-", "").isdigit():
        parts = text.split("-")
        try:
            d1, d2 = int(parts[0]), int(parts[1])
            for d in range(d1, d2 + 1):
                result.append(f"{today[:8]}{d:02d}")
        except (ValueError, IndexError):
            pass
        return result
    for part in text.replace(",", " ").split():
        part = part.strip()
        if not part:
            continue
        if len(part) >= 8 and "-" in part:
            result.append(part[:10])
        elif part.isdigit() and len(part) <= 2:
            result.append(f"{today[:8]}{int(part):02d}")
    return result


# ─── Tags ──────────────────────────────────────────────────────
@web_bp.route("/tags", methods=["GET", "POST"])
@login_required
def tags():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                name = (request.form.get("name") or "").strip()
                if name:
                    add_tag(session, name)
                    flash("Тег добавлен", "success")
            elif action == "delete":
                tid = request.form.get("tag_id")
                if tid:
                    delete_tag(session, tid)
                    flash("Тег удалён", "success")
            elif action == "rename":
                tid = request.form.get("tag_id")
                name = (request.form.get("name") or "").strip()
                if tid and name:
                    update_tag(session, tid, name)
                    flash("Тег переименован", "success")
            return redirect(url_for("web.tags"))
        all_tags = get_tags(session)
        return render_template("tags.html", tags=all_tags)
    finally:
        session.close()


# ─── Calculations (ЗП) ─────────────────────────────────────────
@web_bp.route("/calculations", methods=["GET", "POST"])
@login_required
def calculations():
    session = get_session()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                ps = (request.form.get("period_start") or "").strip()[:10]
                pe = (request.form.get("period_end") or "").strip()[:10]
                try:
                    accrued = float((request.form.get("accrued_salary") or "0").replace(",", "."))
                    received = float((request.form.get("received_salary") or "0").replace(",", "."))
                except ValueError:
                    flash("Некорректная сумма", "error")
                    return redirect(url_for("web.calculations"))
                if ps and pe:
                    add_calculation(session, ps, pe, accrued, received)
                    flash("Расчёт добавлен", "success")
                else:
                    flash("Укажите период", "error")
            return redirect(url_for("web.calculations"))
        calcs = get_calculations(session)
        return render_template("calculations.html", calculations=calcs, today=get_today_msk())
    finally:
        session.close()


@web_bp.route("/calculations/edit/<int:calc_id>", methods=["GET", "POST"])
@login_required
def calculation_edit(calc_id):
    session = get_session()
    try:
        c = get_calculation(session, calc_id)
        if not c:
            flash("Запись не найдена", "error")
            return redirect(url_for("web.calculations"))
        if request.method == "POST":
            kwargs = {}
            for field in ("period_start", "period_end", "accrued_salary", "received_salary", "difference"):
                v = request.form.get(field)
                if v is not None:
                    if field in ("accrued_salary", "received_salary", "difference"):
                        try:
                            kwargs[field] = float(v.replace(",", ".").replace(" ", ""))
                        except ValueError:
                            pass
                    else:
                        kwargs[field] = v.strip()
            if kwargs:
                update_calculation(session, calc_id, **kwargs)
                flash("Расчёт обновлён", "success")
            return redirect(url_for("web.calculations"))
        return render_template("calculation_edit.html", calc=c)
    finally:
        session.close()


# ─── Mass operations ───────────────────────────────────────────
@web_bp.route("/mass-operations", methods=["GET", "POST"])
@login_required
def mass_operations():
    if request.method == "GET":
        return render_template("mass_operations.html", today=get_today_msk(), categories=EXPENSE_CATEGORIES)
    session = get_session()
    try:
        start = (request.form.get("start") or "")[:10]
        end = (request.form.get("end") or "")[:10]
        category = request.form.get("category") or "all"
        action = request.form.get("mass_action") or "soft_delete"
        if not start or not end:
            flash("Укажите период", "error")
            return redirect(url_for("web.mass_operations"))
        count = mass_finance_operations(session, start, end, category, action)
        if action == "soft_delete":
            flash(f"Удалено {count} записей", "success")
        else:
            flash(f"Исключено из бюджета: {count} записей", "success")
        invalidate_status()
        invalidate_budget()
    finally:
        session.close()
    return redirect(url_for("web.mass_operations"))


# ─── Prod calendar admin ───────────────────────────────────────
@web_bp.route("/admin/refresh-calendar")
@login_required
def refresh_calendar():
    from services.prod_calendar import refresh_calendar_from_api, get_month_norm_hours_for_date
    today = get_today_msk()
    year = int(today[:4])
    ok = refresh_calendar_from_api(year)
    norm = get_month_norm_hours_for_date(today)
    if ok:
        flash(f"Календарь {year} обновлён с xmlcalendar.ru. Норма текущего месяца: {int(norm)} ч.", "success")
    else:
        flash(f"Не удалось обновить с API. Используется локальный ({int(norm)} ч.)", "error")
    return redirect(url_for("web.settings"))
