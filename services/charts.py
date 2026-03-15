"""Chart generation using matplotlib. Returns path to PNG."""
import os
import tempfile

def _ensure_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


def generate_pie_chart(data: dict, title: str = "Расходы по категориям") -> str | None:
    """Generate pie chart PNG. data = {category: amount}. Returns file path or None."""
    plt = _ensure_matplotlib()
    if not plt or not data:
        return None
    labels = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90)
    ax.set_title(title)
    fd, path = tempfile.mkstemp(suffix=".png", prefix="chart_")
    os.close(fd)
    fig.savefig(path, bbox_inches="tight", dpi=100)
    plt.close(fig)
    return path


def generate_bar_chart(plan: dict, fact: dict, title: str = "План vs Факт") -> str | None:
    """Generate grouped bar chart. plan/fact = {category: amount}."""
    plt = _ensure_matplotlib()
    if not plt:
        return None
    import numpy as np
    cats = sorted(set(list(plan.keys()) + list(fact.keys())))
    if not cats:
        return None
    plan_vals = [plan.get(c, 0) for c in cats]
    fact_vals = [fact.get(c, 0) for c in cats]
    x = np.arange(len(cats))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - w / 2, plan_vals, w, label="План")
    ax.bar(x + w / 2, fact_vals, w, label="Факт")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=45, ha="right")
    ax.legend()
    ax.set_title(title)
    ax.set_ylabel("Руб.")
    fd, path = tempfile.mkstemp(suffix=".png", prefix="chart_")
    os.close(fd)
    fig.savefig(path, bbox_inches="tight", dpi=100)
    plt.close(fig)
    return path
