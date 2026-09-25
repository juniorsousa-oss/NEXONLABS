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

class Meeting(Base):
    """Reunião com cliente; independente do cronograma de produção."""
    __tablename__ = 'meetings'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    client: Mapped[str] = mapped_column(String(160), default='')
    project_id: Mapped[int | None] = mapped_column(ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    location: Mapped[str] = mapped_column(String(250), default='')
    meeting_url: Mapped[str] = mapped_column(String(500), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MeetingClosure(Base):
    """Histórico de conclusão independente dos agendamentos existentes."""
    __tablename__='meeting_closures'
    meeting_id: Mapped[int]=mapped_column(ForeignKey('meetings.id',ondelete='CASCADE'),primary_key=True)
    status: Mapped[str]=mapped_column(String(16),nullable=False,default='agendada')
    note: Mapped[str]=mapped_column(Text,nullable=False,default='')
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_by: Mapped[str]=mapped_column(String(120),nullable=False,default='')


Base.metadata.create_all(engine)
from accounts_module import setup_accounts, public, session_user, find_by_password, password_in_use, hash_password, verify_password, MAX_ACCOUNTS
Account = setup_accounts(Base, engine, DB)

# Nova tabela independente: evita modificar contas já cadastradas no PostgreSQL.
class AccountPhoto(Base):
    __tablename__ = 'app_account_photos'
    account_id: Mapped[int] = mapped_column(ForeignKey('app_accounts.id', ondelete='CASCADE'), primary_key=True)
    image: Mapped[bytes] = mapped_column(nullable=False)

Base.metadata.create_all(engine, tables=[AccountPhoto.__table__])

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
    whatsapp: str = Field(default='', max_length=40)
    city: str = Field(default='Patos de Minas - MG', max_length=120)
    site: str = Field(default='https://nexonlabs.onrender.com', max_length=250)

    @field_validator('name','role','email','whatsapp','city','site')
    @classmethod
    def tidy_member(cls,value):
        return value.strip()

    @field_validator('site')
    @classmethod
    def validate_site(cls,value):
        if value and not value.startswith(('https://','http://')):
            raise ValueError('O site deve começar com https:// ou http://.')
        return value

class MeetingIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    client: str = Field(default='', max_length=160)
    project_id: int | None = Field(default=None, gt=0)
    meeting_date: date
    start_time: str = Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    end_time: str = Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    location: str = Field(default='', max_length=250)
    meeting_url: str = Field(default='', max_length=500)
    notes: str = Field(default='', max_length=4000)

    @field_validator('title', 'client', 'location', 'meeting_url', 'notes')
    @classmethod
    def tidy(cls, value: str) -> str:
        return value.strip()

class LoginIn(BaseModel):
    password: str

app = FastAPI(title='Nexon Labs | Gestão de Projetos', docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SESSION_SECRET', 'LOCAL_DEVELOPMENT_ONLY_CHANGE_ME'), same_site='lax', https_only=os.getenv('COOKIE_SECURE', '0') == '1')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

def authorized(request: Request):
    current = session_user(request, DB, Account)
    if current is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail='Sessão encerrada. Faça login novamente.')
    return current

def admin_only(request: Request):
    current = authorized(request)
    if current["role"] != "admin":
        raise HTTPException(status_code=403, detail='Somente administradores podem gerenciar acessos.')
    return current

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

def member_dict(member: Member, db: Session):
    return dict(id=member.id, name=member.name, role=member.role,
                email=member.email, **member_brand_extra(db,member))

@app.get('/')
def index(request: Request):
    if session_user(request, DB, Account) is None:
        return FileResponse(ROOT / 'static' / 'login.html', headers={'Cache-Control':'no-store'})
    return FileResponse(ROOT / 'static' / 'index.html', headers={'Cache-Control':'no-store'})

_LOGIN_FAILURES = {}

@app.post('/api/login')
def login(data: LoginIn, request: Request):
    # Restrição simples por endereço de conexão; mensagens não revelam quais contas existem.
    from time import monotonic
    origin = request.client.host if request.client else "unknown"
    now = monotonic()
    fails = [stamp for stamp in _LOGIN_FAILURES.get(origin, []) if now - stamp < 300]
    if len(fails) >= 12:
        raise HTTPException(status_code=429, detail='Muitas tentativas de acesso. Tente novamente em alguns minutos.')
    with DB() as db:
        account = find_by_password(db, Account, data.password)
        if account is None:
            fails.append(now)
            _LOGIN_FAILURES[origin] = fails
            raise HTTPException(status_code=401, detail='Senha incorreta.')
        request.session.clear()
        request.session['account_id'] = account.id
        request.session['account_version'] = account.session_version
        _LOGIN_FAILURES.pop(origin, None)
        return {'ok': True, 'user': public(account)}

@app.post('/api/logout')
def logout(request: Request):
    request.session.clear()
    return {'ok': True}

class AccountCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=256)
    role: Literal['admin', 'usuario'] = 'usuario'

    @field_validator('name')
    @classmethod
    def trim_name(cls, value: str):
        return value.strip()

class AccountUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: Literal['admin', 'usuario']
    active: bool
    new_password: str | None = Field(default=None, min_length=8, max_length=256)

    @field_validator('name')
    @classmethod
    def trim_name(cls, value: str):
        return value.strip()

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str | None = Field(default=None, min_length=8, max_length=256)

    @field_validator('name')
    @classmethod
    def trim_name(cls, value: str):
        return value.strip()

@app.get('/api/accounts', dependencies=[Depends(admin_only)])
def list_accounts(db: Session = Depends(session)):
    return [public(a) for a in db.scalars(select(Account).order_by(Account.id)).all()]

@app.post('/api/accounts', dependencies=[Depends(admin_only)], status_code=201)
def create_account(data: AccountCreate, db: Session = Depends(session)):
    if not data.name:
        raise HTTPException(422, 'Informe o nome do usuário.')
    if db.scalar(select(func.count()).select_from(Account)) >= MAX_ACCOUNTS:
        raise HTTPException(422, 'Limite de contas atingido.')
    if password_in_use(db, Account, data.password):
        raise HTTPException(409, 'Essa senha já está vinculada a outro usuário. Defina uma senha exclusiva.')
    account=Account(name=data.name, password_hash=hash_password(data.password), role=data.role)
    db.add(account)
    log(db, f'Conta de acesso criada para {account.name}.')
    db.commit()
    db.refresh(account)
    return public(account)

@app.put('/api/accounts/{account_id}', dependencies=[Depends(admin_only)])
def update_account(account_id: int, data: AccountUpdate, request: Request, db: Session = Depends(session)):
    account=db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, 'Usuário não encontrado.')
    if not data.name:
        raise HTTPException(422, 'Informe o nome do usuário.')
    current=authorized(request)
    if account.id == current['id'] and (not data.active or data.role != 'admin'):
        raise HTTPException(409, 'Não é permitido desativar ou remover sua própria função administrativa.')
    if account.role == 'admin' and (data.role != 'admin' or not data.active):
        remaining=db.scalar(select(func.count()).select_from(Account).where(
            Account.role == 'admin', Account.active.is_(True), Account.id != account_id))
        if not remaining:
            raise HTTPException(409, 'Mantenha pelo menos um administrador ativo.')
    if data.new_password and password_in_use(db, Account, data.new_password, skip_id=account.id):
        raise HTTPException(409, 'Essa senha já está vinculada a outro usuário.')
    credentials_changed=(account.active != data.active or account.role != data.role or bool(data.new_password))
    account.name,account.active,account.role=data.name,data.active,data.role
    if data.new_password:
        account.password_hash=hash_password(data.new_password)
    if credentials_changed:
        account.session_version+=1
    log(db, f'Acesso de {account.name} atualizado.')
    db.commit()
    db.refresh(account)
    return public(account)

@app.put('/api/profile', dependencies=[Depends(authorized)])
def update_my_profile(data: ProfileUpdate, request: Request, db: Session = Depends(session)):
    current=authorized(request)
    account=db.get(Account, current['id'])
    if not data.name:
        raise HTTPException(422, 'Informe seu nome.')
    if data.new_password:
        if not data.current_password or not verify_password(
            data.current_password, account.password_hash):
            raise HTTPException(403, 'A senha atual não confere.')
        if password_in_use(db, Account, data.new_password, skip_id=account.id):
            raise HTTPException(409, 'Essa senha já está vinculada a outro usuário.')
        account.password_hash=hash_password(data.new_password)
        account.session_version+=1
    account.name=data.name
    db.commit()
    db.refresh(account)
    if data.new_password:
        request.session.clear()
        request.session['account_id']=account.id
        request.session['account_version']=account.session_version
    return public(account)

class ProfilePhotoIn(BaseModel):
    # Base64 do arquivo original; limite validado novamente após decodificação.
    photo_data: str = Field(min_length=24, max_length=2_800_000)

@app.get('/api/profile/avatar', dependencies=[Depends(authorized)])
def get_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.get(AccountPhoto, current['id'])
    if photo is None:
        raise HTTPException(404, 'Foto de perfil não cadastrada.')
    return Response(
        content=photo.image, media_type='image/jpeg',
        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    )

@app.put('/api/profile/avatar', dependencies=[Depends(authorized)])
def save_my_avatar(data: ProfilePhotoIn, request: Request, db: Session = Depends(session)):
    import base64
    import binascii
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not data.photo_data.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')):
        raise HTTPException(422, 'Selecione uma foto PNG, JPEG ou WebP.')
    try:
        original = base64.b64decode(data.photo_data.partition(',')[2], validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, 'Não foi possível ler a imagem.')
    if len(original) > 2_000_000:
        raise HTTPException(413, 'A foto original deve ter no máximo 2 MB.')
    try:
        from PIL import Image
        with Image.open(io.BytesIO(original)) as candidate:
            if candidate.format not in ('PNG', 'JPEG', 'WEBP'):
                raise ValueError('Formato de imagem não permitido.')
            if candidate.width < 32 or candidate.height < 32:
                raise ValueError('A foto deve ter ao menos 32 × 32 pixels.')
            if candidate.width * candidate.height > 16_000_000:
                raise ValueError('A imagem possui resolução muito alta.')
            candidate.load()
            normalized = ImageOps.exif_transpose(candidate)
            normalized.thumbnail((320, 320), Image.Resampling.LANCZOS)
            if normalized.mode in ('RGBA', 'LA') or (normalized.mode == 'P' and 'transparency' in normalized.info):
                rgba = normalized.convert('RGBA')
                white = Image.new('RGB', rgba.size, 'white')
                white.paste(rgba, mask=rgba.getchannel('A'))
                normalized = white
            else:
                normalized = normalized.convert('RGB')
            output = io.BytesIO()
            normalized.save(output, format='JPEG', quality=84, optimize=True)
            safe_image = output.getvalue()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise HTTPException(422, 'Arquivo inválido. Envie uma foto PNG, JPEG ou WebP.') from error
    current = authorized(request)
    photo = db.get(AccountPhoto, current['id'])
    if photo:
        photo.image = safe_image
    else:
        db.add(AccountPhoto(account_id=current['id'], image=safe_image))
    db.commit()
    return {'ok': True, 'has_photo': True}

@app.delete('/api/profile/avatar', dependencies=[Depends(authorized)])
def delete_my_avatar(request: Request, db: Session = Depends(session)):
    photo = db.get(AccountPhoto, authorized(request)['id'])
    if photo:
        db.delete(photo)
        db.commit()
    return {'ok': True, 'has_photo': False}

@app.get('/api/state', dependencies=[Depends(authorized)])
def state(request: Request, db: Session = Depends(session)):
    projects = db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())).all()
    tasks = db.scalars(select(Task).order_by(Task.id.desc())).all()
    members = db.scalars(select(Member).order_by(Member.name)).all()
    activities = db.scalars(select(Activity).order_by(Activity.id.desc()).limit(30)).all()
    meetings = db.scalars(select(Meeting).order_by(Meeting.meeting_date, Meeting.start_time, Meeting.id)).all()
    return dict(projects=[project_dict(p) for p in projects], tasks=[task_dict(t) for t in tasks],
                meetings=[meeting_dict(m,db) for m in meetings],
                members=[member_dict(m,db) for m in members],
                activities=[dict(id=a.id, message=a.message, created_at=stamp(a.created_at)) for a in activities],
                user=authorized(request)['name'],
                user_id=authorized(request)['id'],
                user_role=authorized(request)['role'],
                has_photo=db.get(AccountPhoto, authorized(request)['id']) is not None,
                auth_enabled=True)

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
    if not data.name: raise HTTPException(422, 'Informe o nome.')
    if db.scalar(select(Member).where(func.lower(Member.name) == data.name.lower())):
        raise HTTPException(409, 'Já existe um integrante com esse nome.')
    member=Member(name=data.name,role=data.role,email=data.email)
    db.add(member);db.flush()
    member_brand_sync(db,member,data)
    log(db,f'{member.name} adicionado à equipe.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.put('/api/members/{member_id}', dependencies=[Depends(authorized)])
def edit_member(member_id: int, data: MemberIn, db: Session = Depends(session)):
    member=db.get(Member,member_id)
    if member is None:raise HTTPException(404,'Colaborador não encontrado.')
    if not data.name:raise HTTPException(422,'Informe o nome.')
    duplicate=db.scalar(select(Member).where(func.lower(Member.name)==data.name.lower(),Member.id!=member_id))
    if duplicate:raise HTTPException(409,'Já existe outro colaborador com esse nome.')
    member.name,member.role,member.email=data.name,data.role,data.email
    member_brand_sync(db,member,data)
    log(db,f'Colaborador {member.name} atualizado.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.delete('/api/members/{member_id}', dependencies=[Depends(authorized)])
def remove_member(member_id: int, db: Session = Depends(session)):
    member=db.get(Member,member_id)
    if member is None:raise HTTPException(404,'Integrante não encontrado.')
    profile=db.get(MemberBrand,member_id)
    if profile:db.delete(profile)
    db.delete(member);db.commit();return {'ok':True}

def meeting_dict(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    return dict(id=m.id, title=m.title, client=m.client, project_id=m.project_id,
                meeting_date=m.meeting_date.isoformat(), start_time=m.start_time,
                end_time=m.end_time, location=m.location, meeting_url=m.meeting_url,
                notes=m.notes, created_at=stamp(m.created_at),
                status=lifecycle.status if lifecycle else 'agendada',
                closure_note=lifecycle.note if lifecycle else '',
                closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
                closure_by=lifecycle.updated_by if lifecycle else '')

def validate_meeting(data: MeetingIn, db: Session, exclude_id: int | None = None):
    if not data.title.strip():
        raise HTTPException(422, 'Informe o título da reunião.')
    if data.end_time <= data.start_time:
        raise HTTPException(422, 'A reunião deve terminar depois do início.')
    if data.project_id is not None and db.get(Project, data.project_id) is None:
        raise HTTPException(422, 'O projeto selecionado não existe.')
    if data.meeting_url and not data.meeting_url.startswith(('https://', 'http://')):
        raise HTTPException(422, 'O link deve começar com https:// ou http://.')

    # Impede o mesmo compromisso de ser criado duas vezes por clique repetido,
    # retorno lento da rede ou nova tentativa do usuário. A edição da própria
    # reunião é excluída dessa comparação.
    duplicate = select(Meeting).where(
        Meeting.meeting_date == data.meeting_date,
        Meeting.start_time == data.start_time,
        Meeting.end_time == data.end_time,
        func.lower(func.trim(Meeting.title)) == data.title.strip().lower(),
        func.lower(func.trim(Meeting.client)) == data.client.strip().lower(),
    )
    if data.project_id is None:
        duplicate = duplicate.where(Meeting.project_id.is_(None))
    else:
        duplicate = duplicate.where(Meeting.project_id == data.project_id)
    if exclude_id is not None:
        duplicate = duplicate.where(Meeting.id != exclude_id)
    if db.scalar(duplicate.limit(1)) is not None:
        raise HTTPException(
            409,
            'Esta reunião já está cadastrada com o mesmo título, cliente, projeto, data e horário.'
        )

@app.post('/api/meetings', dependencies=[Depends(authorized)], status_code=201)
def add_meeting(data: MeetingIn, db: Session = Depends(session)):
    validate_meeting(data, db)
    meeting = Meeting(**data.model_dump())
    db.add(meeting)
    log(db, f'Reunião {meeting.title} agendada para {meeting.meeting_date.isoformat()}.')
    db.commit()
    db.refresh(meeting)
    return meeting_dict(meeting,db)

@app.put('/api/meetings/{meeting_id}', dependencies=[Depends(authorized)])
def edit_meeting(meeting_id: int, data: MeetingIn, db: Session = Depends(session)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    validate_meeting(data, db, exclude_id=meeting_id)
    for key, value in data.model_dump().items():
        setattr(meeting, key, value)
    log(db, f'Reunião {meeting.title} atualizada.')
    db.commit()
    db.refresh(meeting)
    return meeting_dict(meeting,db)

class MeetingOutcomeIn(BaseModel):
    status: Literal['agendada','realizada','cancelada']
    note: str = Field(min_length=5,max_length=2000)

    @field_validator('note')
    @classmethod
    def clean_note(cls,value):
        value=value.strip()
        if len(value)<5:raise ValueError('Registre ao menos 5 caracteres sobre o resultado ou motivo.')
        return value

@app.post('/api/meetings/{meeting_id}/outcome', dependencies=[Depends(authorized)])
def set_meeting_outcome(meeting_id: int, data: MeetingOutcomeIn, request: Request, db: Session=Depends(session)):
    meeting=db.get(Meeting,meeting_id)
    if meeting is None:raise HTTPException(404,'Reunião não encontrada.')
    existing=db.get(MeetingClosure,meeting_id)
    current=existing.status if existing else 'agendada'
    if current==data.status:raise HTTPException(409,'A reunião já está nesta situação.')
    actor=authorized(request)['name']
    if existing is None:
        existing=MeetingClosure(meeting_id=meeting_id)
        db.add(existing)
    existing.status=data.status
    existing.note=data.note
    existing.updated_at=datetime.now(timezone.utc)
    existing.updated_by=actor
    log(db,f'Reunião {meeting.id} {data.status} por {actor}.')
    db.commit()
    return meeting_dict(meeting,db)

@app.delete('/api/meetings/{meeting_id}', dependencies=[Depends(authorized)])
def remove_meeting(meeting_id: int, db: Session = Depends(session)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    # Exclusão é distinta do cancelamento: preserve a reunião cancelada no histórico.
    lifecycle=db.get(MeetingClosure,meeting_id)
    if lifecycle:db.delete(lifecycle)
    log(db, f'Reunião {meeting.title} excluída.')
    db.delete(meeting)
    db.commit()
    return {'ok': True}

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


# Módulo comercial isolado: preserva todas as rotas e tabelas existentes.
from quotes_module import install_quotes
install_quotes(app, Base, DB, engine, authorized, log, Project)

# Atendimento interno: chamados de suporte e solicitações vinculados a clientes/projetos.
from tickets_module import install_tickets
install_tickets(app, Base, DB, engine, authorized, log, Project)

# Identidade visual Opção B por colaborador; dados em tabela separada para preservar cadastros.
from brand_kit import install_brand_kit
MemberBrand, member_brand_extra, member_brand_sync = install_brand_kit(
    app, Base, DB, engine, authorized, log, Member, member_dict
)

# A referência visual original fica persistida no PostgreSQL e só é instalada pelo administrador.
from approved_template import install_reference
ApprovedArtwork = install_reference(app, Base, DB, engine, authorized, admin_only)
