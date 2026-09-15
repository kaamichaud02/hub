"""
Logique métier pour le calcul des heures des feuilles de temps.

Port de suivi_temps/timesheets/services.py. La logique de durée
(entry_duration, add_durations, week_bounds, ...) est préservée à
l'identique — en particulier le calcul de durée qui gère les quarts
passant minuit sans planter en fin de mois (timedelta(days=1) plutôt que
end.replace(day=end.day + 1)).
"""
from datetime import date, time, datetime, timedelta
from sqlmodel import Session, select

from .timesheets_models import TimesheetST, TimeEntryST, AuthUser


def entry_duration(entry_date: date, start_time: time, end_time: time) -> timedelta:
    """Durée d'une entrée horaire. Gère les quarts qui passent minuit
    (ex: 22:00 -> 06:00) sans planter en fin de mois."""
    start = datetime.combine(entry_date, start_time)
    end = datetime.combine(entry_date, end_time)
    if end < start:
        end += timedelta(days=1)
    return end - start


def timesheet_duration(ts_date: date, entries: list[TimeEntryST]) -> tuple[int, int]:
    """Durée totale (heures, minutes) d'une feuille de temps (somme de ses entrées)."""
    total = timedelta()
    for entry in entries:
        if entry.start_time and entry.end_time:
            total += entry_duration(ts_date, entry.start_time, entry.end_time)

    hours = int(total.total_seconds() // 3600)
    minutes = int((total.total_seconds() % 3600) // 60)
    return hours, minutes


def add_durations(hours1: int, minutes1: int, hours2: int, minutes2: int) -> tuple[int, int]:
    """Additionne deux durées (h, m) et renvoie le résultat normalisé (h, m)."""
    total_minutes = (hours1 * 60 + minutes1) + (hours2 * 60 + minutes2)
    return total_minutes // 60, total_minutes % 60


def week_bounds(a_date: date) -> tuple[date, date]:
    """Renvoie (lundi, dimanche) de la semaine contenant `a_date`."""
    monday = a_date - timedelta(days=a_date.weekday())
    return monday, monday + timedelta(days=6)


def total_duration(pairs: list[tuple[TimesheetST, list[TimeEntryST]]]) -> tuple[int, int]:
    """Durée totale (heures, minutes) d'un ensemble de (feuille, entrées)."""
    total_hours, total_minutes = 0, 0
    for ts, entries in pairs:
        hours, minutes = timesheet_duration(ts.date, entries)
        total_hours, total_minutes = add_durations(total_hours, total_minutes, hours, minutes)
    return total_hours, total_minutes


def group_timesheets_by_week(pairs: list[tuple[TimesheetST, list[TimeEntryST]]]) -> list[dict]:
    """Regroupe une liste de (feuille, entrées) par semaine (lundi-dimanche),
    triée de la semaine la plus récente à la plus ancienne, avec le total
    de chaque semaine déjà calculé.
    """
    weeks: dict[str, dict] = {}
    for ts, entries in pairs:
        monday, sunday = week_bounds(ts.date)
        key = monday.isoformat()
        if key not in weeks:
            weeks[key] = {
                "monday": monday,
                "sunday": sunday,
                "timesheets": [],
                "total_hours": 0,
                "total_minutes": 0,
            }
        weeks[key]["timesheets"].append((ts, entries))
        hours, minutes = timesheet_duration(ts.date, entries)
        weeks[key]["total_hours"], weeks[key]["total_minutes"] = add_durations(
            weeks[key]["total_hours"], weeks[key]["total_minutes"], hours, minutes
        )

    return sorted(weeks.values(), key=lambda w: w["monday"], reverse=True)


def entries_for(session_st: Session, timesheet_id: int) -> list[TimeEntryST]:
    return session_st.exec(
        select(TimeEntryST).where(TimeEntryST.timesheet_id == timesheet_id).order_by(TimeEntryST.id)
    ).all()


def get_weekly_summary_rows(session_st: Session, user: AuthUser) -> list[dict]:
    """Équivalent de l'ancienne vue Postgres `timesheet_weekly_summary`
    (non documentée dans le repo Django, objet hors-bande) — recalculé ici
    en Python à partir des tables existantes plutôt que de dépendre de cette
    vue SQL non versionnée.
    """
    timesheets = session_st.exec(
        select(TimesheetST).where(TimesheetST.user_id == user.id).order_by(TimesheetST.date)
    ).all()
    pairs = [(ts, entries_for(session_st, ts.id)) for ts in timesheets]
    weeks = group_timesheets_by_week(pairs)
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "monday_date": w["monday"],
            "sunday_date": w["sunday"],
            "timesheet_count": len(w["timesheets"]),
            "total_hours": w["total_hours"],
            "total_minutes": w["total_minutes"],
        }
        for w in weeks
    ]
