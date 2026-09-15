"""Port des tests purs de suivi_temps/timesheets/tests.py (aucune DB requise)."""
from datetime import date, time
from unittest.mock import MagicMock

from app.timesheets_services import (
    entry_duration, add_durations, timesheet_duration, week_bounds,
)


def _entry(start_h, start_m, end_h, end_m):
    e = MagicMock()
    e.start_time = time(start_h, start_m)
    e.end_time = time(end_h, end_m)
    return e


def test_entry_duration_same_day():
    d = entry_duration(date(2026, 3, 10), time(9, 0), time(17, 30))
    assert d.total_seconds() == 8.5 * 3600


def test_entry_duration_overnight():
    d = entry_duration(date(2026, 3, 10), time(22, 0), time(6, 0))
    assert d.total_seconds() == 8 * 3600


def test_entry_duration_overnight_month_end():
    # Régression : end.replace(day=end.day + 1) plantait le 31 janvier
    d = entry_duration(date(2026, 1, 31), time(23, 0), time(5, 0))
    assert d.total_seconds() == 6 * 3600


def test_add_durations_carry():
    assert add_durations(1, 45, 2, 30) == (4, 15)


def test_add_durations_no_carry():
    assert add_durations(1, 0, 2, 0) == (3, 0)


def test_timesheet_duration_multi_entry():
    entries = [_entry(9, 0, 12, 0), _entry(13, 0, 17, 30)]
    assert timesheet_duration(date(2026, 3, 10), entries) == (7, 30)


def test_week_bounds():
    # 16 sept 2026 est un mercredi
    monday, sunday = week_bounds(date(2026, 9, 16))
    assert monday == date(2026, 9, 14)
    assert sunday == date(2026, 9, 20)
