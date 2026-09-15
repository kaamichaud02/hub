from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.forms import modelformset_factory
from django.http import HttpResponse

from . import services
from .forms import TimesheetForm, TimeEntryForm
from .models import Timesheet, TimeEntry
from .reports.common import build_week_report_data
from .reports.pdf import render_pdf_report
from .reports.docx import render_docx_report


def custom_logout(request):
    """Termine la session Django ET la session Cloudflare Access, sinon
    l'utilisateur serait immédiatement reconnecté au prochain chargement
    de page par CloudflareAccessMiddleware.
    """
    logout(request)
    return redirect(f"https://{settings.CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/logout")


@login_required
def timesheet_list(request):
    timesheets = Timesheet.objects.filter(user=request.user).order_by('-date')
    weeks_list = services.group_timesheets_by_week(timesheets)

    today = datetime.today().date()
    current_monday, _ = services.week_bounds(today)

    return render(request, 'timesheets/timesheet_list.html', {
        'weeks': weeks_list,
        'current_monday': current_monday,
    })


@login_required
def timesheet_weekly_summary(request):
    results = services.get_weekly_summary_rows(request.user.id)
    return render(request, 'timesheets/weekly_summary.html', {'summaries': results})


@login_required
def timesheet_detail(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk, user=request.user)
    TimeEntryFormSet = modelformset_factory(TimeEntry, form=TimeEntryForm, extra=1, can_delete=True)

    if request.method == 'POST':
        timesheet_form = TimesheetForm(request.POST, instance=timesheet)
        formset = TimeEntryFormSet(request.POST, queryset=TimeEntry.objects.filter(timesheet=timesheet))

        if timesheet_form.is_valid() and formset.is_valid():
            timesheet_form.save()
            entries = formset.save(commit=False)
            for entry in entries:
                if entry.start_time and entry.end_time:
                    entry.timesheet = timesheet
                    entry.save()
            for obj in formset.deleted_objects:
                obj.delete()
            formset.save_m2m()
            return redirect('timesheet_list')
    else:
        timesheet_form = TimesheetForm(instance=timesheet)
        formset = TimeEntryFormSet(queryset=TimeEntry.objects.filter(timesheet=timesheet))

    return render(request, 'timesheets/timesheet_detail.html', {
        'timesheet': timesheet,
        'timesheet_form': timesheet_form,
        'formset': formset,
    })


@login_required
def timesheet_create(request):
    TimeEntryFormSet = modelformset_factory(TimeEntry, form=TimeEntryForm, extra=1)

    if request.method == 'POST':
        timesheet_form = TimesheetForm(request.POST)
        formset = TimeEntryFormSet(request.POST)

        if timesheet_form.is_valid() and formset.is_valid():
            timesheet = timesheet_form.save(commit=False)
            timesheet.user = request.user
            timesheet.save()
            entries = formset.save(commit=False)
            for entry in entries:
                if entry.start_time and entry.end_time:
                    entry.timesheet = timesheet
                    entry.save()
            formset.save_m2m()
            return redirect('timesheet_list')
    else:
        timesheet_form = TimesheetForm()
        formset = TimeEntryFormSet(queryset=TimeEntry.objects.none())

    return render(request, 'timesheets/timesheet_detail.html', {
        'timesheet_form': timesheet_form,
        'formset': formset,
    })


def _parse_monday(monday):
    return datetime.strptime(monday, '%Y-%m-%d').date()


@login_required
def generate_pdf_report(request, monday):
    try:
        monday_date = _parse_monday(monday)
    except ValueError:
        return HttpResponse("Date invalide", status=400)

    data = build_week_report_data(request.user, monday_date)
    return render_pdf_report(data, monday)


@login_required
def generate_word_report(request, monday):
    try:
        monday_date = _parse_monday(monday)
    except ValueError:
        return HttpResponse("Date invalide", status=400)

    data = build_week_report_data(request.user, monday_date)
    return render_docx_report(data, monday)
