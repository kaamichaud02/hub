"""
Prépare les données d'un rapport hebdomadaire, indépendamment du format
de sortie (PDF ou Word). Port de suivi_temps/timesheets/reports/common.py.
"""
from datetime import date, timedelta
from sqlmodel import Session, select

from ..timesheets_models import TimesheetST, AuthUser
from .. import timesheets_services as services


def build_week_report_data(session_st: Session, user: AuthUser, monday_date: date) -> dict:
    """Renvoie les données nécessaires pour générer un rapport (PDF ou Word)
    de la semaine commençant à `monday_date`, pour `user`.
    """
    sunday_date = monday_date + timedelta(days=6)

    timesheets = session_st.exec(
        select(TimesheetST)
        .where(TimesheetST.user_id == user.id)
        .where(TimesheetST.date >= monday_date, TimesheetST.date <= sunday_date)
        .order_by(TimesheetST.date)
    ).all()

    pairs = [(ts, services.entries_for(session_st, ts.id)) for ts in timesheets]
    total_hours, total_minutes = services.total_duration(pairs)

    return {
        "user": user,
        "monday_date": monday_date,
        "sunday_date": sunday_date,
        "timesheets": pairs,
        "total_hours": total_hours,
        "total_minutes": total_minutes,
    }
