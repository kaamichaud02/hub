"""
Logique métier pour le calcul des heures des feuilles de temps.

Toute la logique de durée était auparavant dupliquée dans models.py,
timesheet_list, generate_pdf_report et generate_word_report — centralisée
ici pour n'exister qu'à un seul endroit.
"""
from datetime import datetime, timedelta
from django.db import connection


def entry_duration(entry_date, start_time, end_time):
    """Durée d'une entrée horaire (timedelta). Gère les quarts qui passent minuit
    (ex: 22:00 -> 06:00) sans planter en fin de mois.

    L'ancien code faisait `end.replace(day=end.day + 1)`, qui lève une
    exception dès que le jour dépasse le nombre de jours du mois (ex: 32
    janvier). `timedelta(days=1)` gère correctement le changement de mois.
    """
    start = datetime.combine(entry_date, start_time)
    end = datetime.combine(entry_date, end_time)
    if end < start:
        end += timedelta(days=1)
    return end - start


def timesheet_duration(timesheet):
    """Durée totale (heures, minutes) d'une feuille de temps (somme de ses entrées)."""
    total = timedelta()
    for entry in timesheet.entries.all():
        if entry.start_time and entry.end_time:
            total += entry_duration(timesheet.date, entry.start_time, entry.end_time)

    hours = int(total.total_seconds() // 3600)
    minutes = int((total.total_seconds() % 3600) // 60)
    return hours, minutes


def add_durations(hours1, minutes1, hours2, minutes2):
    """Additionne deux durées (h, m) et renvoie le résultat normalisé (h, m)."""
    total_minutes = (hours1 * 60 + minutes1) + (hours2 * 60 + minutes2)
    return total_minutes // 60, total_minutes % 60


def week_bounds(a_date):
    """Renvoie (lundi, dimanche) de la semaine contenant `a_date`."""
    monday = a_date - timedelta(days=a_date.weekday())
    return monday, monday + timedelta(days=6)


def total_duration(timesheets):
    """Durée totale (heures, minutes) d'un ensemble de feuilles de temps."""
    total_hours, total_minutes = 0, 0
    for timesheet in timesheets:
        hours, minutes = timesheet_duration(timesheet)
        total_hours, total_minutes = add_durations(total_hours, total_minutes, hours, minutes)
    return total_hours, total_minutes


def group_timesheets_by_week(timesheets):
    """Regroupe une liste de feuilles de temps par semaine (lundi-dimanche),
    triée de la semaine la plus récente à la plus ancienne, avec le total
    de chaque semaine déjà calculé.
    """
    weeks = {}
    for timesheet in timesheets:
        monday, sunday = week_bounds(timesheet.date)
        key = monday.isoformat()
        if key not in weeks:
            weeks[key] = {
                "monday": monday,
                "sunday": sunday,
                "timesheets": [],
                "total_hours": 0,
                "total_minutes": 0,
            }
        weeks[key]["timesheets"].append(timesheet)
        hours, minutes = timesheet_duration(timesheet)
        weeks[key]["total_hours"], weeks[key]["total_minutes"] = add_durations(
            weeks[key]["total_hours"], weeks[key]["total_minutes"], hours, minutes
        )

    return sorted(weeks.values(), key=lambda w: w["monday"], reverse=True)


def get_weekly_summary_rows(user_id):
    """Lit la vue Postgres `timesheet_weekly_summary` pour un utilisateur.

    Requête inchangée par rapport à l'ancien code (déplacée ici pour ne
    plus être mélangée à la logique de vue Django) : la vue SQL elle-même
    n'est pas gérée par les migrations Django.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                user_id,
                username,
                first_name,
                last_name,
                monday_date,
                sunday_date,
                timesheet_count,
                total_hours,
                total_minutes
            FROM timesheet_weekly_summary
            WHERE user_id = %s
            ORDER BY monday_date DESC
            """,
            [user_id],
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
