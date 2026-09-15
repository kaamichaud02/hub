import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Session, select, func

from .database import init_db, get_session
from .models import Board, Column, Task
from .schemas import (
    BoardCreate, BoardReorder,
    ColumnCreate, ColumnReorder,
    TaskCreate, TaskUpdate, TaskMove,
)
from .timesheets_db import get_session_st
from .timesheets_models import AuthUser
from .timesheets_auth import get_verified_email, extract_token, get_current_user, CF_ACCESS_TEAM_DOMAIN
from .timesheets_schemas import CurrentUser, WhoamiUpdate
from .timesheets_routes import router as timesheets_router
from .admin_routes import router as admin_router

app = FastAPI(title="Hub - kaa.zone")
app.include_router(timesheets_router)
app.include_router(admin_router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_default_data()


def seed_default_data():
    """Crée le board suivi_temps avec ses colonnes/tâches par défaut si la base est vide."""
    from sqlmodel import Session as _S
    from .database import engine
    with _S(engine) as session:
        existing = session.exec(select(Board)).first()
        if existing:
            return

        board = Board(
            name="suivi_temps",
            icon="🕒",
            color="#00d4a0",
            description="Refonte de l'app de lookup employés/feuilles de temps (ex-OpenERP)",
            position=0,
        )
        session.add(board)
        session.commit()
        session.refresh(board)

        col_names = ["Idées", "À faire", "En cours", "Terminé"]
        columns = {}
        for i, name in enumerate(col_names):
            col = Column(board_id=board.id, name=name, position=i)
            session.add(col)
            session.commit()
            session.refresh(col)
            columns[name] = col

        seed_tasks = [
            ("À faire", "Réorganiser la structure du projet", "restructuration du code Flask, séparation routes/modèles/templates"),
            ("À faire", "Ajouter le hub comme point d'entrée", "lien depuis hub.kaa.zone vers time.aim-recycling.com"),
            ("Idées", "Export CSV en plus du PDF", ""),
            ("Idées", "Recherche employé par nom partiel", ""),
        ]
        for i, (col_name, title, desc) in enumerate(seed_tasks):
            task = Task(column_id=columns[col_name].id, title=title, description=desc, position=i)
            session.add(task)
        session.commit()


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


@app.get("/api/version")
def version():
    # GIT_SHA vient du build-arg passé par le CI (voir Dockerfile et
    # .github/workflows/hub-docker.yml) — utile pour vérifier rapidement
    # quelle version tourne réellement (les caches navigateur/Cloudflare ont
    # causé plusieurs confusions "ça a l'air pas à jour" pendant les tests).
    return {"version": os.environ.get("GIT_SHA", "dev")[:7]}


@app.get("/api/whoami")
def whoami(request: Request, session_st: Session = Depends(get_session_st)):
    # Vérifie réellement la signature du JWT Cloudflare Access (JWKS) au lieu
    # de faire confiance à un header — voir timesheets_auth.py. N'exige pas de
    # compte auth_user : un utilisateur kanban-only doit pouvoir passer ici,
    # seules les routes /api/timesheets et /api/admin exigent un compte.
    email = get_verified_email(extract_token(request))
    if not email:
        return {
            "email": None, "first_name": None, "last_name": None,
            "is_superuser": False, "has_account": False, "logout_url": None,
        }
    user = session_st.exec(
        select(AuthUser).where(func.lower(AuthUser.email) == email.lower())
    ).first()
    return {
        "email": email,
        "first_name": user.first_name if user else None,
        "last_name": user.last_name if user else None,
        "is_superuser": user.is_superuser if user else False,
        "has_account": user is not None,
        "logout_url": f"https://{CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/logout",
    }


@app.patch("/api/whoami")
def update_whoami(
    payload: WhoamiUpdate,
    user: CurrentUser = Depends(get_current_user),
    session_st: Session = Depends(get_session_st),
):
    # Permet à l'utilisateur connecté de modifier son propre prénom/nom dans
    # auth_user (même champs que suivi_temps/l'admin) — n'existe que pour les
    # comptes déjà créés (get_current_user renvoie 403 sinon).
    user_row = session_st.get(AuthUser, user.id)
    if payload.first_name is not None:
        user_row.first_name = payload.first_name
    if payload.last_name is not None:
        user_row.last_name = payload.last_name
    session_st.add(user_row)
    session_st.commit()
    session_st.refresh(user_row)
    return {
        "email": user_row.email,
        "first_name": user_row.first_name,
        "last_name": user_row.last_name,
        "is_superuser": user_row.is_superuser,
        "has_account": True,
        "logout_url": f"https://{CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/logout",
    }


# ---------- Boards ----------

@app.get("/api/boards")
def list_boards(session: Session = Depends(get_session)):
    boards = session.exec(select(Board).order_by(Board.position)).all()
    return boards


@app.post("/api/boards")
def create_board(payload: BoardCreate, session: Session = Depends(get_session)):
    max_pos = session.exec(select(Board)).all()
    board = Board(
        name=payload.name,
        icon=payload.icon,
        color=payload.color,
        description=payload.description,
        position=len(max_pos),
    )
    session.add(board)
    session.commit()
    session.refresh(board)

    for i, name in enumerate(["À faire", "En cours", "Terminé"]):
        session.add(Column(board_id=board.id, name=name, position=i))
    session.commit()
    return board


@app.get("/api/boards/{board_id}")
def get_board(board_id: int, session: Session = Depends(get_session)):
    board = session.get(Board, board_id)
    if not board:
        raise HTTPException(404, "Board introuvable")
    columns = session.exec(select(Column).where(Column.board_id == board_id).order_by(Column.position)).all()
    result = []
    for col in columns:
        tasks = session.exec(select(Task).where(Task.column_id == col.id).order_by(Task.position)).all()
        result.append({"id": col.id, "name": col.name, "position": col.position, "tasks": tasks})
    return {"board": board, "columns": result}


@app.patch("/api/boards/{board_id}/reorder")
def reorder_board(board_id: int, payload: BoardReorder, session: Session = Depends(get_session)):
    board = session.get(Board, board_id)
    if not board:
        raise HTTPException(404, "Board introuvable")
    board.position = payload.position
    session.add(board)
    session.commit()
    return board


@app.delete("/api/boards/{board_id}")
def delete_board(board_id: int, session: Session = Depends(get_session)):
    board = session.get(Board, board_id)
    if not board:
        raise HTTPException(404, "Board introuvable")
    session.delete(board)
    session.commit()
    return {"ok": True}


# ---------- Columns ----------

@app.post("/api/columns")
def create_column(payload: ColumnCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Column).where(Column.board_id == payload.board_id)).all()
    col = Column(board_id=payload.board_id, name=payload.name, position=len(existing))
    session.add(col)
    session.commit()
    session.refresh(col)
    return col


@app.patch("/api/columns/{column_id}/reorder")
def reorder_column(column_id: int, payload: ColumnReorder, session: Session = Depends(get_session)):
    col = session.get(Column, column_id)
    if not col:
        raise HTTPException(404, "Colonne introuvable")
    col.position = payload.position
    session.add(col)
    session.commit()
    return col


@app.delete("/api/columns/{column_id}")
def delete_column(column_id: int, session: Session = Depends(get_session)):
    col = session.get(Column, column_id)
    if not col:
        raise HTTPException(404, "Colonne introuvable")
    session.delete(col)
    session.commit()
    return {"ok": True}


# ---------- Tasks ----------

@app.post("/api/tasks")
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(Task).where(Task.column_id == payload.column_id)).all()
    task = Task(
        column_id=payload.column_id,
        title=payload.title,
        description=payload.description or "",
        tags=payload.tags or "",
        position=len(existing),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Tâche introuvable")
    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.tags is not None:
        task.tags = payload.tags
    from datetime import datetime
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}/move")
def move_task(task_id: int, payload: TaskMove, session: Session = Depends(get_session)):
    """Déplace une tâche vers une colonne (même colonne ou une autre) et une position donnée."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Tâche introuvable")

    old_column_id = task.column_id
    task.column_id = payload.column_id
    task.position = payload.position
    session.add(task)
    session.commit()

    # Renormalise les positions dans la colonne de destination (et d'origine si différente)
    for col_id in {old_column_id, payload.column_id}:
        tasks = session.exec(
            select(Task).where(Task.column_id == col_id).order_by(Task.position)
        ).all()
        for i, t in enumerate(tasks):
            if t.position != i:
                t.position = i
                session.add(t)
    session.commit()
    session.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Tâche introuvable")
    session.delete(task)
    session.commit()
    return {"ok": True}
