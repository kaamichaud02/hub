from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('timesheets', '0002_alter_timesheet_unique_together_timesheet_user_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP VIEW IF EXISTS "Marie-all-time-sheets" CASCADE;',
            reverse_sql='',
        ),
        migrations.RemoveField(
            model_name='timeentry',
            name='description',
        ),
    ]
