"""Routes JSON pour la section "Suivi de temps" du hub. Remplace les vues
Django de suivi_temps/timesheets/views.py par une API REST consommée par
static/js/timesheets.js (SPA vanilla JS, même pattern que le Kanban)."""
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .timesheets_db import get_session_st
from .timesheets_models import AuthUser, TimesheetST, TimeEntryST
from .timesheets_schemas import CurrentUser, TimesheetCreate, TimesheetUpdate
from .timesheets_auth import get_current_user
from . import timesheets_services as services
from .timesheets_reports.common import build_week_report_data
from .timesheets_reports.pdf import render_pdf_report
from .timesheets_reports.docx import render_docx_report

router = APIRouter(prefix="/api/timesheets", tags=["timesheets"])


def _get_auth_user_row(session_st: Session, user: CurrentUser) -> AuthUser:
    row = session_st.get(AuthUser, user.id)
    if not row:
        raise HTTPException(404, "Utilisateur introuvable")
    return row


def _serialize_entry(entry: TimeEntryST) -> dict:
    return {"id": entry.id, "start_time": entry.start_time, "end_time": entry.end_time}


def _serialize_timesheet(ts: TimesheetST, entries: list[TimeEntryST]) -> dict:
    hours, minutes = services.timesheet_duration(ts.date, entries)
    return {
        "id": ts.id,
        "date": ts.date,
        "summary": ts.summary,
        "total_hours": hours,
        "total_minutes": minutes,
        "entries": [_serialize_entry(e) for e in entries],
    }


def _serialize_week(week: dict) -> dict:
    return {
        "monday": week["monday"],
        "sunday": week["sunday"],
        "total_hours": week["total_hours"],
        "total_minutes": week["total_minutes"],
        "timesheets": [_serialize_timesheet(ts, entries) for ts, entries in week["timesheets"]],
    }


def _get_owned_timesheet(session_st: Session, timesheet_id: int, user: CurrentUser) -> TimesheetST:
    ts = session_st.exec(
        select(TimesheetST).where(TimesheetST.id == timesheet_id, TimesheetST.user_id == user.id)
    ).first()
    if not ts:
        raise HTTPException(404, "Feuille de temps introuvable")
    return ts


def _check_date_conflict(session_st: Session, user_id: int, ts_date: date, exclude_id: int | None = None):
    query = select(TimesheetST).where(TimesheetST.user_id == user_id, TimesheetST.date == ts_date)
    if exclude_id is not None:
        query = query.where(TimesheetST.id != exclude_id)
    if session_st.exec(query).first():
        raise HTTPException(409, "Une feuille de temps existe déjà pour cette date")


# ---------- Routes à motif fixe : DOIVENT être déclarées avant /{timesheet_id} ----------

@router.get("/weekly-summary")
def weekly_summary(
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    user_row = _get_auth_user_row(session_st, user)
    return {"summaries": services.get_weekly_summary_rows(session_st, user_row)}


@router.get("/report/pdf/{monday}")
def report_pdf(
    monday: str,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    try:
        monday_date = datetime.strptime(monday, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Date invalide")
    user_row = _get_auth_user_row(session_st, user)
    data = build_week_report_data(session_st, user_row, monday_date)
    return render_pdf_report(data, monday)


@router.get("/report/word/{monday}")
def report_word(
    monday: str,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    try:
        monday_date = datetime.strptime(monday, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Date invalide")
    user_row = _get_auth_user_row(session_st, user)
    data = build_week_report_data(session_st, user_row, monday_date)
    return render_docx_report(data, monday)


# ---------- Liste / CRUD ----------

@router.get("")
def list_timesheets(
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    timesheets = session_st.exec(
        select(TimesheetST).where(TimesheetST.user_id == user.id).order_by(TimesheetST.date.desc())
    ).all()
    pairs = [(ts, services.entries_for(session_st, ts.id)) for ts in timesheets]
    weeks = services.group_timesheets_by_week(pairs)
    current_monday, _ = services.week_bounds(date.today())
    return {"weeks": [_serialize_week(w) for w in weeks], "current_monday": current_monday}


@router.post("")
def create_timesheet(
    payload: TimesheetCreate,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    _check_date_conflict(session_st, user.id, payload.date)

    ts = TimesheetST(user_id=user.id, date=payload.date, summary=payload.summary)
    session_st.add(ts)
    try:
        session_st.commit()
    except IntegrityError:
        session_st.rollback()
        raise HTTPException(409, "Une feuille de temps existe déjà pour cette date")
    session_st.refresh(ts)

    for entry in payload.entries:
        session_st.add(TimeEntryST(timesheet_id=ts.id, start_time=entry.start_time, end_time=entry.end_time))
    session_st.commit()

    entries = services.entries_for(session_st, ts.id)
    return _serialize_timesheet(ts, entries)


@router.get("/{timesheet_id}")
def get_timesheet(
    timesheet_id: int,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    ts = _get_owned_timesheet(session_st, timesheet_id, user)
    entries = services.entries_for(session_st, ts.id)
    return _serialize_timesheet(ts, entries)


@router.patch("/{timesheet_id}")
def update_timesheet(
    timesheet_id: int,
    payload: TimesheetUpdate,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    ts = _get_owned_timesheet(session_st, timesheet_id, user)

    if payload.date is not None and payload.date != ts.date:
        _check_date_conflict(session_st, user.id, payload.date, exclude_id=ts.id)
        ts.date = payload.date
    if payload.summary is not None:
        ts.summary = payload.summary
    session_st.add(ts)

    if payload.entries is not None:
        for item in payload.entries:
            if item.id is not None:
                entry = session_st.exec(
                    select(TimeEntryST).where(TimeEntryST.id == item.id, TimeEntryST.timesheet_id == ts.id)
                ).first()
                if not entry:
                    raise HTTPException(400, f"Entrée {item.id} introuvable sur cette feuille de temps")
                if item.delete:
                    session_st.delete(entry)
                else:
                    if item.start_time is not None:
                        entry.start_time = item.start_time
                    if item.end_time is not None:
                        entry.end_time = item.end_time
                    session_st.add(entry)
            elif item.start_time and item.end_time and not item.delete:
                session_st.add(TimeEntryST(timesheet_id=ts.id, start_time=item.start_time, end_time=item.end_time))

    try:
        session_st.commit()
    except IntegrityError:
        session_st.rollback()
        raise HTTPException(409, "Une feuille de temps existe déjà pour cette date")

    session_st.refresh(ts)
    entries = services.entries_for(session_st, ts.id)
    return _serialize_timesheet(ts, entries)


@router.delete("/{timesheet_id}")
def delete_timesheet(
    timesheet_id: int,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    ts = _get_owned_timesheet(session_st, timesheet_id, user)
    for entry in services.entries_for(session_st, ts.id):
        session_st.delete(entry)
    session_st.delete(ts)
    session_st.commit()
    return {"ok": True}
