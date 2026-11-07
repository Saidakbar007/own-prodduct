"""
Трекер трат (доп. задача, см. docs/decisions/DECISIONS.md → «Этап "Доделай"
+ guide + wger»): категории кнопками + сумма степпером, итог месяца по
категориям — для цели expense_tracking (её guide уже обещает ровно эти 5
категорий, content/spheres/finance.yaml).
"""

from datetime import date
from typing import NamedTuple

from sqlmodel import Session, select

from app.models import ExpenseEntry

CATEGORIES = ["food", "transport", "entertainment", "essentials", "other"]


class CategoryTotal(NamedTuple):
    category: str
    total: float


def log_expense(db: Session, uid: int, category: str, amount: float, today: date) -> ExpenseEntry:
    entry = ExpenseEntry(uid=uid, category=category, amount=amount, logged_on=today)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def month_totals_by_category(db: Session, uid: int, today: date) -> list[CategoryTotal]:
    """Сумма трат текущего календарного месяца по каждой из 5 категорий, в
    фиксированном порядке CATEGORIES (а не по сумме) — проще сравнивать
    неделя к неделе на одном и том же месте."""
    month_start = today.replace(day=1)
    rows = db.exec(
        select(ExpenseEntry).where(
            ExpenseEntry.uid == uid,
            ExpenseEntry.logged_on >= month_start,
            ExpenseEntry.logged_on <= today,
        )
    ).all()
    totals = {category: 0.0 for category in CATEGORIES}
    for row in rows:
        if row.category in totals:
            totals[row.category] += row.amount
    return [CategoryTotal(category, totals[category]) for category in CATEGORIES]
