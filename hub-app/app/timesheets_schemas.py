from typing import Optional, List
from datetime import date, time
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    is_superuser: bool


class EntryIn(BaseModel):
    start_time: time
    end_time: time


class EntryPatch(BaseModel):
    id: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    delete: bool = False


class TimesheetCreate(BaseModel):
    date: date
    summary: str = ""
    entries: List[EntryIn] = []


class TimesheetUpdate(BaseModel):
    date: Optional[date] = None
    summary: Optional[str] = None
    entries: Optional[List[EntryPatch]] = None


class AdminUserCreate(BaseModel):
    email: str
    first_name: str = ""
    last_name: str = ""
    username: Optional[str] = None
    is_superuser: bool = False


class WhoamiUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
