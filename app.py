"""Nexon Labs — gestão de projetos. API, HTML e banco de dados.

Inicie com: uvicorn app:app --host 0.0.0.0 --port 8000
Configure APP_PASSWORD e SESSION_SECRET no ambiente antes de publicar.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED
import hmac

ROOT = Path(__file__).resolve().parent
if os.getenv('APP_ENV') == 'production':
    if not os.getenv('APP_PASSWORD') or len(os.getenv('SESSION_SECRET', '')) < 32:
        raise RuntimeError('APP_PASSWORD e SESSION_SECRET forte são obrigatórios em produção.')
    if not os.getenv('DATABASE_URL'):
        raise RuntimeError('Configure DATABASE_URL com banco de dados persistente em produção.')
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "nexonlabs.db"}')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgres://'):]
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+psycopg://' + DATABASE_URL[len('postgresql://'):]
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite:') else {}, pool_pre_ping=True)
DB = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Member(Base):
    __tablename__ = 'members'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(120), default='Equipe')
    email: Mapped[str] = mapped_column(String(200), default='')

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    client: Mapped[str] = mapped_column(String(160), default='')
    owner: Mapped[str] = mapped_column(String(120), default='')
    status: Mapped[str] = mapped_column(String(32), default='planejamento')
    progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    tasks: Mapped[list['Task']] = relationship(back_populates='project', cascade='all, delete-orphan')

class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    assignee: Mapped[str] = mapped_column(String(120), default='')
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(default=False)
    hours: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    project: Mapped[Project] = relationship(back_populates='tasks')

class Activity(Base):
    __tablename__ = 'activities'
    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(String(350))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

Status = Literal['planejamento', 'em_andamento', 'concluido']

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default='', max_length=2000)
    client: str = Field(default='', max_length=160)
    owner: str = Field(default='', max_length=120)
    status: Status = 'planejamento'
    progress: int = Field(default=0, ge=0, le=100)
    started_at: date | None = None
    due_at: date | None = None

    @field_validator('name', 'description', 'client', 'owner')
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

class TaskIn(BaseModel):
    project_id: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=200)
    assignee: str = Field(default='', max_length=120)
    due_at: date | None = None
    completed: bool = False
    hours: float = Field(default=0, ge=0, le=100000)

class MemberIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(default='Equipe', max_length=120)
    email: str = Field(default='', max_length=200)

class LoginIn(BaseModel):
    password: str

app = FastAPI(title='Nexon Labs | Gestão de Projetos', docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SESSION_SECRET', 'LOCAL_DEVELOPMENT_ONLY_CHANGE_ME'), same_site='lax', https_only=os.getenv('COOKIE_SECURE', '0') == '1')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

def authorized(request: Request):
    configured = os.getenv('APP_PASSWORD', '')
    if configured and request.session.get('logged_in') is not True:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail='Sessão encerrada. Faça login novamente.')
    return True

def session():
    with DB() as db:
        yield db

def stamp(dt: datetime | None):
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt and dt.tzinfo is None else dt.isoformat() if dt else None

def effective_status(p: Project):
    if p.status == 'concluido': return 'concluido'
    if p.due_at and p.due_at < datetime.now(ZoneInfo('America/Sao_Paulo')).date(): return 'atrasado'
    return p.status

def project_dict(p: Project):
    return dict(id=p.id, name=p.name, description=p.description, client=p.client, owner=p.owner,
                status=effective_status(p), saved_status=p.status, progress=p.progress,
                started_at=p.started_at.isoformat() if p.started_at else None,
                due_at=p.due_at.isoformat() if p.due_at else None,
                created_at=stamp(p.created_at), updated_at=stamp(p.updated_at))

def task_dict(t: Task):
    return dict(id=t.id, project_id=t.project_id, title=t.title, assignee=t.assignee,
                due_at=t.due_at.isoformat() if t.due_at else None,
                completed=t.completed, hours=t.hours, created_at=stamp(t.created_at))

def log(db: Session, msg: str):
    db.add(Activity(message=msg[:350]))

@app.get('/')
def index(request: Request):
    if os.getenv('APP_PASSWORD') and not request.session.get('logged_in'):
        return FileResponse(ROOT / 'static' / 'login.html')
    return FileResponse(ROOT / 'static' / 'index.html')

@app.post('/api/login')
def login(data: LoginIn, request: Request):
    actual = os.getenv('APP_PASSWORD', '')
    if not actual or hmac.compare_digest(data.password, actual):
        request.session['logged_in'] = True
        return {'ok': True}
    raise HTTPException(status_code=401, detail='Senha incorreta.')

@app.post('/api/logout')
def logout(request: Request):
    request.session.clear()
    return {'ok': True}

@app.get('/api/state', dependencies=[Depends(authorized)])
def state(db: Session = Depends(session)):
    projects = db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())).all()
    tasks = db.scalars(select(Task).order_by(Task.id.desc())).all()
    members = db.scalars(select(Member).order_by(Member.name)).all()
    activities = db.scalars(select(Activity).order_by(Activity.id.desc()).limit(30)).all()
    return dict(projects=[project_dict(p) for p in projects], tasks=[task_dict(t) for t in tasks],
                members=[dict(id=m.id, name=m.name, role=m.role, email=m.email) for m in members],
                activities=[dict(id=a.id, message=a.message, created_at=stamp(a.created_at)) for a in activities],
                user=os.getenv('APP_DISPLAY_NAME', 'Equipe Nexon Labs'),
                auth_enabled=bool(os.getenv('APP_PASSWORD')))

@app.post('/api/projects', dependencies=[Depends(authorized)], status_code=201)
def add_project(data: ProjectIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    p = Project(**data.model_dump())
    db.add(p)
    log(db, f'Projeto {p.name} cadastrado.')
    db.commit(); db.refresh(p)
    return project_dict(p)

@app.put('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def edit_project(project_id: int, data: ProjectIn, db: Session = Depends(session)):
    p = db.get(Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    for key, val in data.model_dump().items(): setattr(p, key, val)
    p.updated_at = datetime.now(timezone.utc)
    log(db, f'Projeto {p.name} atualizado.')
    db.commit(); db.refresh(p)
    return project_dict(p)

@app.delete('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def remove_project(project_id: int, db: Session = Depends(session)):
    p = db.get(Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    log(db, f'Projeto {p.name} excluído.')
    db.delete(p); db.commit()
    return {'ok': True}

@app.post('/api/tasks', dependencies=[Depends(authorized)], status_code=201)
def add_task(data: TaskIn, db: Session = Depends(session)):
    if db.get(Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    task = Task(**data.model_dump(exclude={'title'}), title=data.title.strip())
    db.add(task); log(db, f'Tarefa {task.title} cadastrada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.put('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def edit_task(task_id: int, data: TaskIn, db: Session = Depends(session)):
    task = db.get(Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    if db.get(Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    for key, value in data.model_dump().items(): setattr(task, key, value)
    task.title = task.title.strip()
    log(db, f'Tarefa {task.title} atualizada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.delete('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def remove_task(task_id: int, db: Session = Depends(session)):
    task = db.get(Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    db.delete(task); db.commit(); return {'ok': True}

@app.post('/api/members', dependencies=[Depends(authorized)], status_code=201)
def add_member(data: MemberIn, db: Session = Depends(session)):
    if not data.name.strip(): raise HTTPException(422, 'Informe o nome.')
    if db.scalar(select(Member).where(func.lower(Member.name) == data.name.strip().lower())):
        raise HTTPException(409, 'Já existe um integrante com esse nome.')
    member = Member(name=data.name.strip(), role=data.role.strip(), email=data.email.strip())
    db.add(member); log(db, f'{member.name} adicionado à equipe.')
    db.commit(); db.refresh(member)
    return dict(id=member.id, name=member.name, role=member.role, email=member.email)

@app.delete('/api/members/{member_id}', dependencies=[Depends(authorized)])
def remove_member(member_id: int, db: Session = Depends(session)):
    member = db.get(Member, member_id)
    if member is None: raise HTTPException(404, 'Integrante não encontrado.')
    db.delete(member); db.commit(); return {'ok': True}

@app.get('/api/export/projects.csv', dependencies=[Depends(authorized)])
def export_projects(db: Session = Depends(session)):
    buffer = io.StringIO(); out = csv.writer(buffer, delimiter=';')
    out.writerow(['ID', 'Projeto', 'Descrição', 'Cliente', 'Responsável', 'Status', 'Progresso (%)', 'Início', 'Prazo'])
    for p in db.scalars(select(Project).order_by(Project.id)):
        out.writerow([p.id, p.name, p.description, p.client, p.owner, effective_status(p), p.progress,
                      p.started_at.isoformat() if p.started_at else '', p.due_at.isoformat() if p.due_at else ''])
    buffer.seek(0)
    return StreamingResponse(iter(['\ufeff' + buffer.getvalue()]), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="nexonlabs_projetos.csv"'})

@app.get('/health')
def health(): return {'status': 'ok'}
