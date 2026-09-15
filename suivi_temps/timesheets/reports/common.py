"""
Prépare les données d'un rapport hebdomadaire, indépendamment du format
de sortie (PDF ou Word). Évite de dupliquer la requête et le calcul du
total dans les deux générateurs de rapport.
"""
from datetime import timedelta

from ..models import Timesheet
from .. import services


def build_week_report_data(user, monday_date):
    """Renvoie les données nécessaires pour générer un rapport (PDF ou Word)
    de la semaine commençant à `monday_date`, pour `user`.
    """
    sunday_date = monday_date + timedelta(days=6)

    timesheets = Timesheet.objects.filter(
        user=user,
        date__range=[monday_date, sunday_date],
    ).order_by('date')

    total_hours, total_minutes = services.total_duration(timesheets)

    return {
        "user": user,
        "monday_date": monday_date,
        "sunday_date": sunday_date,
        "timesheets": timesheets,
        "total_hours": total_hours,
        "total_minutes": total_minutes,
    }
