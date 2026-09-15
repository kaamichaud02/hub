from typing import Optional, List
from datetime import date as date_, time as time_
from pydantic import BaseModel

# Import aliasés (date_/time_) : un champ nommé `date`/`time` avec une valeur
# par défaut (ex. `date: Optional[date] = None`) fait que Pydantic résout
# l'annotation comme NoneType au lieu du type réel — l'attribut de classe
# créé par la valeur par défaut masque le type importé du même nom pendant
# la résolution des annotations. D'où l'alias, systématique dans ce fichier.


class CurrentUser(BaseModel):
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    is_superuser: bool


class EntryIn(BaseModel):
    start_time: time_
    end_time: time_


class EntryPatch(BaseModel):
    id: Optional[int] = None
    start_time: Optional[time_] = None
    end_time: Optional[time_] = None
    delete: bool = False


class TimesheetCreate(BaseModel):
    date: date_
    summary: str = ""
    entries: List[EntryIn] = []


class TimesheetUpdate(BaseModel):
    date: Optional[date_] = None
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
