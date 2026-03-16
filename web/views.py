"""Web views: dashboard, expense, budget, goals, debts, etc."""
from flask import render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import login_required, current_user
from . import web_bp
from db.models import get_session
from db.repositories import (
    get_config_param,
    add_finance_entry,
    get_finance_for_period,
    get_finance_history,
    get_budget_limits_map,
    get_active_goals,
    get_active_debts,
    get_debt_summary,
    get_active_subscriptions,
    get_templates,
    use_template,
    get_template,
    get_work_log_for_period,
    get_top_categories,
    get_achievements,
    get_debt_payments,
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
)
from services.gamification import get_streak, ACHIEVEMENTS
from services.reports import get_period_range
from services.excel_import import parse_alfa_bank
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


@web_bp.route("/")
def index():
    """Redirect /web to login or dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return redirect(url_for("web.login"))


@web_bp.route("/dashboard")
@login_required
def dashboard():
    session = get_session()
    try:
        data = _get_status_data(session)
        recent = get_finance_history(session, limit=10)
        return render_template("dashboard.html", status=data, recent=recent)
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
                return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today)
            if amount <= 0:
                flash("Сумма должна быть положительной", "error")
                return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today)
            add_finance_entry(session, date_str, "Expense", amount, category, comment)
            flash(f"Расход {int(amount)} руб. записан", "success")
            return redirect(url_for("web.dashboard"))
        return render_template("expense.html", categories=EXPENSE_CATEGORIES, today=today)
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
            flash(f"Доход {int(amount)} руб. записан", "success")
            return redirect(url_for("web.dashboard"))
        return render_template("income.html", today=today)
    finally:
        session.close()


@web_bp.route("/budget")
@login_required
def budget():
    session = get_session()
    try:
        st = get_budget_status(session)
        forecast = get_forecast_end_of_month(session)
        return render_template("budget.html", budget=st, forecast=forecast)
    finally:
        session.close()


@web_bp.route("/goals")
@login_required
def goals():
    session = get_session()
    try:
        goals_list = get_active_goals(session)
        return render_template("goals.html", goals=goals_list)
    finally:
        session.close()


@web_bp.route("/debts")
@login_required
def debts():
    session = get_session()
    try:
        debts_list = get_active_debts(session)
        summary = get_debt_summary(session)
        return render_template("debts.html", debts=debts_list, summary=summary)
    finally:
        session.close()


@web_bp.route("/subscriptions")
@login_required
def subscriptions():
    session = get_session()
    try:
        subs = get_active_subscriptions(session)
        return render_template("subscriptions.html", subscriptions=subs)
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
        return render_template("analytics.html", period=period, chart_data=chart_data,
                               income=int(income), expense=int(expense), balance=int(income - expense))
    finally:
        session.close()


@web_bp.route("/history")
@login_required
def history():
    page = max(1, int(request.args.get("page", 1)))
    per_page = 30
    offset = (page - 1) * per_page
    from db.models import Finance
    session = get_session()
    try:
        rows = session.query(Finance).filter(Finance.is_deleted == False).order_by(
            Finance.date.desc(), Finance.id.desc()
        ).offset(offset).limit(per_page + 1).all()
        has_more = len(rows) > per_page
        rows = rows[:per_page]
        return render_template("history.html", rows=rows, page=page, has_more=has_more)
    finally:
        session.close()


@web_bp.route("/templates")
@login_required
def templates_list():
    session = get_session()
    try:
        templates = get_templates(session)
        return render_template("templates.html", templates=templates)
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
        flash(f"Расход {int(data['amount'])} руб. по шаблону «{data['name']}»", "success")
    finally:
        session.close()
    return redirect(url_for("web.dashboard"))


@web_bp.route("/worklog")
@login_required
def worklog():
    session = get_session()
    try:
        today = get_today_msk()
        start = today[:7] + "-01"
        entries = get_work_log_for_period(session, start, today, job_type="Main")
        return render_template("worklog.html", entries=entries)
    finally:
        session.close()


@web_bp.route("/more")
@login_required
def more():
    """More menu: debts, subscriptions, analytics, history, settings."""
    return render_template("more.html")


@web_bp.route("/settings")
@login_required
def settings():
    session = get_session()
    try:
        config = {}
        for k in ["FixedSalary", "PayDay1", "PayDay2", "WorkHoursNorm"]:
            config[k] = get_config_param(session, k)
        return render_template("settings.html", config=config)
    finally:
        session.close()


@web_bp.route("/achievements")
@login_required
def achievements():
    session = get_session()
    try:
        unlocked = get_achievements(session)
        streak = get_streak(session)
        return render_template("achievements.html", achievements=unlocked, streak=streak, ACHIEVEMENTS=ACHIEVEMENTS)
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
