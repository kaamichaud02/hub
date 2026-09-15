from typing import Optional
from datetime import date, time, datetime
from sqlmodel import SQLModel, Field

# Ces classes mappent des tables Postgres EXISTANTES (créées par les migrations
# Django de suivi_temps), pas de nouvelles tables. Les noms de colonnes/tables
# doivent correspondre exactement au schéma Django — voir
# suivi_temps/timesheets/migrations/. Pas de Relationship() : requêtes
# explicites via select() dans les routes/services, pour éviter tout lazy-load
# surprenant entre les deux engines (HUB_DB vs base suivi_temps).


class AuthUser(SQLModel, table=True):
    __tablename__ = "auth_user"

    id: Optional[int] = Field(default=None, primary_key=True)
    password: str
    last_login: Optional[datetime] = None
    is_superuser: bool
    username: str
    first_name: str
    last_name: str
    email: str
    is_staff: bool
    is_active: bool
    date_joined: datetime


class TimesheetST(SQLModel, table=True):
    __tablename__ = "timesheets_timesheet"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    summary: str = ""
    user_id: int = Field(foreign_key="auth_user.id")


class TimeEntryST(SQLModel, table=True):
    __tablename__ = "timesheets_timeentry"

    id: Optional[int] = Field(default=None, primary_key=True)
    start_time: time
    end_time: time
    timesheet_id: int = Field(foreign_key="timesheets_timesheet.id")
