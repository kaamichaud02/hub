from django.db import models
from django.contrib.auth.models import User
from . import services


class Timesheet(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='timesheets')
    date = models.DateField()
    summary = models.TextField(blank=True)

    class Meta:
        unique_together = ['user', 'date']

    def __str__(self):
        return f"Feuille de temps - {self.user.username} - {self.date}"

    def total_hours(self):
        return services.timesheet_duration(self)


class TimeEntry(models.Model):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='entries')
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"Entrée: {self.start_time} - {self.end_time}"
