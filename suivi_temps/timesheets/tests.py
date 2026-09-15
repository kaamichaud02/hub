from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from . import services
from .models import Timesheet, TimeEntry


class EntryDurationTests(TestCase):
    def test_simple_same_day_duration(self):
        duration = services.entry_duration(date(2026, 1, 15), time(9, 0), time(17, 30))
        self.assertEqual(duration.total_seconds(), 8.5 * 3600)

    def test_overnight_shift_within_month(self):
        duration = services.entry_duration(date(2026, 1, 15), time(22, 0), time(6, 0))
        self.assertEqual(duration.total_seconds(), 8 * 3600)

    def test_overnight_shift_across_month_end(self):
        # Ancien bug : end.replace(day=end.day + 1) plantait ici (31 janvier -> jour 32)
        duration = services.entry_duration(date(2026, 1, 31), time(23, 0), time(5, 0))
        self.assertEqual(duration.total_seconds(), 6 * 3600)


class AddDurationsTests(TestCase):
    def test_carries_minutes_into_hours(self):
        self.assertEqual(services.add_durations(1, 45, 2, 30), (4, 15))

    def test_no_carry_needed(self):
        self.assertEqual(services.add_durations(1, 10, 2, 20), (3, 30))


class TimesheetDurationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='jf', password='x')
        self.timesheet = Timesheet.objects.create(user=self.user, date=date(2026, 1, 31))

    def test_total_hours_across_multiple_entries(self):
        TimeEntry.objects.create(timesheet=self.timesheet, start_time=time(9, 0), end_time=time(12, 0))
        TimeEntry.objects.create(timesheet=self.timesheet, start_time=time(13, 0), end_time=time(17, 30))
        self.assertEqual(services.timesheet_duration(self.timesheet), (7, 30))

    def test_model_method_delegates_to_services(self):
        TimeEntry.objects.create(timesheet=self.timesheet, start_time=time(9, 0), end_time=time(10, 0))
        self.assertEqual(self.timesheet.total_hours(), (1, 0))


class WeekBoundsTests(TestCase):
    def test_monday_to_sunday(self):
        # Le 14 sept. 2026 est un lundi
        monday, sunday = services.week_bounds(date(2026, 9, 16))
        self.assertEqual(monday, date(2026, 9, 14))
        self.assertEqual(sunday, date(2026, 9, 20))


class CloudflareAccessMiddlewareTests(TestCase):
    """Vérifie les 3 scénarios de CloudflareAccessMiddleware sans dépendre
    d'un vrai JWT — on simule get_verified_email() directement.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='jf', email='kaamichaud02@outlook.com', password='unused',
        )

    @patch('timesheets.middleware.get_verified_email')
    def test_known_email_logs_in_automatically(self, mock_get_email):
        mock_get_email.return_value = 'kaamichaud02@outlook.com'
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.user, self.user)

    @patch('timesheets.middleware.get_verified_email')
    def test_unknown_email_returns_403(self, mock_get_email):
        mock_get_email.return_value = 'inconnu@example.com'
        response = self.client.get('/')
        self.assertEqual(response.status_code, 403)

    @patch('timesheets.middleware.get_verified_email')
    def test_no_token_returns_401(self, mock_get_email):
        mock_get_email.return_value = None
        response = self.client.get('/')
        self.assertEqual(response.status_code, 401)
