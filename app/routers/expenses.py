"""
Трекер трат (доп. задача, см. docs/decisions/DECISIONS.md → «Этап "Доделай"
+ guide + wger»): категория кнопкой + сумма степпером, итог месяца по
категориям. Доступен любому вошедшему (не завязан на активный сезон —
можно вести учёт даже без цели expense_tracking, но ссылка на /expenses
показывается на её карточке цели).
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services.expenses import CATEGORIES, log_expense, month_totals_by_category
from app.services.usertime import today_for

router = APIRouter()


@router.get("/expenses")
def expenses_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    today = today_for(user)
    totals = month_totals_by_category(db, user.id, today)
    return render(
        request,
        "expenses.html",
        {
            "categories": CATEGORIES,
            "totals": totals,
            "month_total": sum(t.total for t in totals),
            "lang": user.language,
        },
    )


@router.post("/expenses/log")
def expenses_log(
    request: Request,
    category: str = Form(...),
    amount: float = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    if category in CATEGORIES and amount > 0:
        log_expense(db, user.id, category, amount, today_for(user))
    return RedirectResponse("/expenses", status_code=303)
