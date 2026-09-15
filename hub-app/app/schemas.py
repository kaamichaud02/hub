from typing import Optional, List
from pydantic import BaseModel


class TaskCreate(BaseModel):
    column_id: int
    title: str
    description: Optional[str] = ""
    tags: Optional[str] = ""


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


class TaskMove(BaseModel):
    column_id: int
    position: int


class ColumnCreate(BaseModel):
    board_id: int
    name: str


class ColumnReorder(BaseModel):
    position: int


class BoardCreate(BaseModel):
    name: str
    icon: Optional[str] = "📋"
    color: Optional[str] = "#5865f2"
    description: Optional[str] = ""


class BoardReorder(BaseModel):
    position: int
