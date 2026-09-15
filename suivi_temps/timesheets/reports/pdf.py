"""Génération du rapport hebdomadaire au format PDF."""
from io import BytesIO

from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm

from .. import services

LINE = 6 * mm
MARGIN = 20 * mm


def render_pdf_report(data, monday):
    """Construit la réponse HTTP contenant le PDF du rapport hebdomadaire.

    `data` provient de `reports.common.build_week_report_data`.
    """
    user = data["user"]
    monday_date = data["monday_date"]
    sunday_date = data["sunday_date"]
    timesheets = data["timesheets"]

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def check_page(y):
        if y < 40 * mm:
            p.showPage()
            return height - MARGIN
        return y

    p.setFont("Helvetica-Bold", 14)
    p.drawString(MARGIN, height - 20 * mm, f"Rapport des feuilles de temps de {user.first_name} {user.last_name}")
    p.setFont("Helvetica-Bold", 12)
    p.drawString(MARGIN, height - 30 * mm, f"Semaine du {monday_date.strftime('%d/%m/%Y')} au {sunday_date.strftime('%d/%m/%Y')}")

    p.setFont("Helvetica", 12)
    p.drawString(MARGIN, height - 40 * mm, f"Total: {data['total_hours']} h {data['total_minutes']} min")

    y = height - 55 * mm

    for timesheet in timesheets:
        y = check_page(y)
        hours, minutes = services.timesheet_duration(timesheet)

        date_prefix = f"Date: {timesheet.date.strftime('%d/%m/%Y')} (Total: "
        hours_text = f"{hours} h {minutes} min"
        date_suffix = ")"

        p.setFont("Helvetica-Bold", 12)
        x = MARGIN
        p.drawString(x, y, date_prefix)
        x += p.stringWidth(date_prefix, "Helvetica-Bold", 12)

        hw = p.stringWidth(hours_text, "Helvetica-Bold", 12)
        p.setFillColorRGB(1, 1, 0)
        p.rect(x - 1, y - 2, hw + 2, 13, fill=1, stroke=0)
        p.setFillColorRGB(0, 0, 0)
        p.drawString(x, y, hours_text)
        x += hw

        p.drawString(x, y, date_suffix)
        y -= LINE + 2 * mm

        p.setFont("Helvetica", 12)
        entries = timesheet.entries.all()
        if entries:
            for entry in entries:
                y = check_page(y)
                p.drawString(MARGIN, y, f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}")
                y -= LINE
        else:
            p.drawString(MARGIN, y, "Aucune entrée horaire")
            y -= LINE

        y -= LINE

        y = check_page(y)
        p.drawString(MARGIN, y, "Résumé:")
        y -= LINE

        if timesheet.summary:
            y -= LINE
            for line in timesheet.summary.split('\n'):
                if line.strip():
                    y = check_page(y)
                    p.drawString(MARGIN, y, line.strip())
                    y -= LINE

        y -= LINE * 3

    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_semaine_{monday}.pdf"'
    response.write(buffer.read())
    buffer.close()
    return response
