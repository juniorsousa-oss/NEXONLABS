"""ATRIA by Nexon Labs — gestão integrada de projetos e operações. API, HTML e banco de dados.

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
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, create_engine, func, select
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

from tenant_module import (
    NEXON_LABS_ORG_ID,
    ATRIA_DEMO_ORG_ID,
    ensure_organization_columns,
    ensure_member_tenant_uniqueness,
    organization_public,
    setup_organizations,
)
Organization = setup_organizations(Base, engine, DB)

class Member(Base):
    __tablename__ = 'members'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), default='Equipe')
    email: Mapped[str] = mapped_column(String(200), default='')

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
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
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
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
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
    message: Mapped[str] = mapped_column(String(350))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Meeting(Base):
    """Reunião com cliente; independente do cronograma de produção."""
    __tablename__ = 'meetings'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
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

class MeetingAttendee(Base):
    """Participantes internos obrigatórios usados para detectar conflitos de agenda."""
    __tablename__='meeting_attendees'
    meeting_id: Mapped[int]=mapped_column(ForeignKey('meetings.id',ondelete='CASCADE'),primary_key=True)
    member_id: Mapped[int]=mapped_column(ForeignKey('members.id',ondelete='CASCADE'),primary_key=True)

class ProjectClientSite(Base):
    """URL pública do cliente sem alterar a tabela histórica de projetos."""
    __tablename__='project_client_sites'
    project_id: Mapped[int]=mapped_column(ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True)
    url: Mapped[str]=mapped_column(String(500),nullable=False,default='')


Base.metadata.create_all(engine)
ensure_organization_columns(engine, ['members', 'projects', 'tasks', 'activities', 'meetings'], NEXON_LABS_ORG_ID)
ensure_member_tenant_uniqueness(engine)
from accounts_module import setup_accounts, public, session_user, find_by_password, password_in_use, hash_password, verify_password, MAX_ACCOUNTS, SESSION_IDLE_TIMEOUT_SECONDS
Account = setup_accounts(Base, engine, DB, NEXON_LABS_ORG_ID)

# Nova tabela independente: evita modificar contas já cadastradas no PostgreSQL.
class AccountPhoto(Base):
    __tablename__ = 'app_account_photos'
    account_id: Mapped[int] = mapped_column(ForeignKey('app_accounts.id', ondelete='CASCADE'), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'), nullable=False, default=NEXON_LABS_ORG_ID, index=True)
    image: Mapped[bytes] = mapped_column(nullable=False)

class OrganizationBrandAsset(Base):
    __tablename__ = 'organization_brand_assets'
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

Base.metadata.create_all(engine, tables=[AccountPhoto.__table__, OrganizationBrandAsset.__table__])
ensure_organization_columns(engine, ['app_account_photos'], NEXON_LABS_ORG_ID)

Status = Literal['planejamento', 'em_andamento', 'concluido']

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default='', max_length=2000)
    client: str = Field(default='', max_length=160)
    client_site: str = Field(default='', max_length=500)
    owner: str = Field(default='', max_length=120)
    status: Status = 'planejamento'
    progress: int = Field(default=0, ge=0, le=100)
    started_at: date | None = None
    due_at: date | None = None

    @field_validator('name', 'description', 'client', 'client_site', 'owner')
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator('client_site')
    @classmethod
    def validate_client_site(cls, value: str) -> str:
        if value and not value.startswith(('https://','http://')):
            raise ValueError('O site do cliente deve começar com https:// ou http://.')
        return value

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
    site: str = Field(default='https://nexonlabs.com.br', max_length=250)

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
    attendee_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator('title', 'client', 'location', 'meeting_url', 'notes')
    @classmethod
    def tidy(cls, value: str) -> str:
        return value.strip()

class LoginIn(BaseModel):
    password: str

app = FastAPI(title='ATRIA | Gestão de Projetos e Operações', docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SESSION_SECRET', 'LOCAL_DEVELOPMENT_ONLY_CHANGE_ME'),
    same_site='lax',
    https_only=os.getenv('COOKIE_SECURE', '0') == '1',
    max_age=SESSION_IDLE_TIMEOUT_SECONDS,
)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

def authorized(request: Request):
    cached = getattr(request.state, 'current_user', None)
    if cached is not None:
        return cached
    current = session_user(request, DB, Account)
    if current is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail='Sessão encerrada. Faça login novamente.')
    request.state.current_user = current
    return current

def admin_only(request: Request):
    current = authorized(request)
    if current["role"] != "admin":
        raise HTTPException(status_code=403, detail='Somente administradores podem gerenciar acessos.')
    return current

def session(request: Request):
    current = authorized(request)
    with DB() as db:
        db.info['organization_id'] = current['organization_id']
        yield db

def organization_id(db: Session) -> int:
    value = db.info.get('organization_id')
    if value is None:
        raise RuntimeError('Sessão de banco sem organização ativa.')
    return int(value)

def tenant_get(db: Session, model, record_id: int):
    return db.scalar(select(model).where(
        model.id == record_id,
        model.organization_id == organization_id(db)
    ).limit(1))

def stamp(dt: datetime | None):
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt and dt.tzinfo is None else dt.isoformat() if dt else None

def effective_status(p: Project):
    if p.status == 'concluido': return 'concluido'
    if p.due_at and p.due_at < datetime.now(ZoneInfo('America/Sao_Paulo')).date(): return 'atrasado'
    return p.status

def project_site(db: Session, project_id: int):
    row=db.get(ProjectClientSite,project_id)
    return row.url if row else ''

def sync_project_site(db: Session, project_id: int, url: str):
    row=db.get(ProjectClientSite,project_id)
    if url:
        if row is None:
            row=ProjectClientSite(project_id=project_id,url=url);db.add(row)
        else:
            row.url=url
    elif row is not None:
        db.delete(row)

def project_dict(p: Project, db: Session):
    return dict(id=p.id, name=p.name, description=p.description, client=p.client,
                client_site=project_site(db,p.id), owner=p.owner,
                status=effective_status(p), saved_status=p.status, progress=p.progress,
                started_at=p.started_at.isoformat() if p.started_at else None,
                due_at=p.due_at.isoformat() if p.due_at else None,
                created_at=stamp(p.created_at), updated_at=stamp(p.updated_at))

def task_dict(t: Task):
    return dict(id=t.id, project_id=t.project_id, title=t.title, assignee=t.assignee,
                due_at=t.due_at.isoformat() if t.due_at else None,
                completed=t.completed, hours=t.hours, created_at=stamp(t.created_at))

def log(db: Session, msg: str):
    db.add(Activity(organization_id=organization_id(db), message=msg[:350]))

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
        request.session['organization_id'] = account.organization_id
        request.session['account_version'] = account.session_version
        request.session['last_activity'] = int(__import__('time').time())
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
    org_id = organization_id(db)
    return [public(a) for a in db.scalars(
        select(Account).where(Account.organization_id == org_id).order_by(Account.id)
    ).all()]

@app.post('/api/accounts', dependencies=[Depends(admin_only)], status_code=201)
def create_account(data: AccountCreate, request: Request, db: Session = Depends(session)):
    if not data.name:
        raise HTTPException(422, 'Informe o nome do usuário.')
    org_id = organization_id(db)
    if db.scalar(select(func.count()).select_from(Account).where(Account.organization_id == org_id)) >= MAX_ACCOUNTS:
        raise HTTPException(422, 'Limite de contas atingido.')
    if password_in_use(db, Account, data.password):
        raise HTTPException(409, 'Essa senha já está vinculada a outro usuário. Defina uma senha exclusiva.')
    current = authorized(request)
    account=Account(organization_id=org_id, name=data.name, password_hash=hash_password(data.password), role=data.role)
    db.add(account)
    log(db, f'Conta de acesso criada para {account.name}.')
    db.commit()
    db.refresh(account)
    return public(account)

@app.put('/api/accounts/{account_id}', dependencies=[Depends(admin_only)])
def update_account(account_id: int, data: AccountUpdate, request: Request, db: Session = Depends(session)):
    current=authorized(request)
    account=db.scalar(select(Account).where(
        Account.id == account_id,
        Account.organization_id == current['organization_id']
    ).limit(1))
    if account is None:
        raise HTTPException(404, 'Usuário não encontrado.')
    if not data.name:
        raise HTTPException(422, 'Informe o nome do usuário.')
    if account.id == current['id'] and (not data.active or data.role != 'admin'):
        raise HTTPException(409, 'Não é permitido desativar ou remover sua própria função administrativa.')
    if account.role == 'admin' and (data.role != 'admin' or not data.active):
        remaining=db.scalar(select(func.count()).select_from(Account).where(
            Account.organization_id == current['organization_id'],
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
        request.session['organization_id']=account.organization_id
        request.session['account_version']=account.session_version
        request.session['last_activity']=int(__import__('time').time())
    return public(account)

class ProfilePhotoIn(BaseModel):
    # Base64 do arquivo original; limite validado novamente após decodificação.
    photo_data: str = Field(min_length=24, max_length=2_800_000)

class OrganizationBrandSettingsIn(BaseModel):
    primary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    use_custom_brand: bool = False

    @field_validator('primary_color', 'secondary_color')
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()

class OrganizationBrandAssetIn(BaseModel):
    image_data: str = Field(min_length=32, max_length=4_200_000)

@app.get('/api/profile/avatar', dependencies=[Depends(authorized)])
def get_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
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
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        photo.image = safe_image
    else:
        db.add(AccountPhoto(account_id=current['id'], organization_id=current['organization_id'], image=safe_image))
    db.commit()
    return {'ok': True, 'has_photo': True}

@app.delete('/api/profile/avatar', dependencies=[Depends(authorized)])
def delete_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        db.delete(photo)
        db.commit()
    return {'ok': True, 'has_photo': False}

BRAND_ASSET_KINDS = {'logo', 'logo_dark', 'favicon', 'watermark'}

def organization_brand_payload(db: Session, organization):
    payload = organization_public(organization)
    kinds = set(db.scalars(select(OrganizationBrandAsset.kind).where(
        OrganizationBrandAsset.organization_id == organization.id
    )).all())
    payload['assets'] = {kind: kind in kinds for kind in sorted(BRAND_ASSET_KINDS)}
    payload['asset_urls'] = {
        kind: f'/api/organization/brand/assets/{kind}' if kind in kinds else ''
        for kind in sorted(BRAND_ASSET_KINDS)
    }
    payload['is_demo'] = organization.id == ATRIA_DEMO_ORG_ID
    payload['signature'] = 'Powered by ATRIA · by Nexon Labs'
    return payload

def decode_brand_asset(kind: str, image_data: str):
    import base64
    import binascii
    from PIL import Image, UnidentifiedImageError
    if kind not in BRAND_ASSET_KINDS:
        raise HTTPException(404, 'Tipo de identidade visual não encontrado.')
    prefixes = {
        'data:image/png;base64,': 'image/png',
        'data:image/jpeg;base64,': 'image/jpeg',
        'data:image/webp;base64,': 'image/webp',
    }
    mime_type = next((mime for prefix, mime in prefixes.items() if image_data.startswith(prefix)), None)
    if mime_type is None:
        raise HTTPException(422, 'Envie uma imagem PNG, JPEG ou WebP.')
    try:
        raw = base64.b64decode(image_data.partition(',')[2], validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(422, 'Não foi possível ler a imagem enviada.') from error
    max_bytes = 1_000_000 if kind == 'favicon' else 2_500_000
    if len(raw) > max_bytes:
        raise HTTPException(413, 'A imagem excede o limite permitido para este campo.')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise HTTPException(422, 'Arquivo de imagem inválido.') from error
    if width < 32 or height < 32 or width > 4096 or height > 4096:
        raise HTTPException(422, 'Use uma imagem entre 32 e 4096 pixels por lado.')
    if kind == 'favicon' and abs(width - height) > max(4, int(max(width, height) * .04)):
        raise HTTPException(422, 'O favicon precisa ser quadrado.')
    return raw, mime_type

@app.get('/api/organization/brand', dependencies=[Depends(authorized)])
def get_organization_brand(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    organization = db.get(Organization, current['organization_id'])
    if organization is None:
        raise HTTPException(404, 'Organização não encontrada.')
    return organization_brand_payload(db, organization)

@app.put('/api/organization/brand', dependencies=[Depends(admin_only)])
def update_organization_brand(data: OrganizationBrandSettingsIn, request: Request, db: Session = Depends(session)):
    current = authorized(request)
    organization = db.get(Organization, current['organization_id'])
    if organization is None:
        raise HTTPException(404, 'Organização não encontrada.')
    if organization.id == ATRIA_DEMO_ORG_ID and data.use_custom_brand:
        raise HTTPException(409, 'O ambiente ATRIA Demo usa a identidade oficial do produto.')
    organization.primary_color = data.primary_color
    organization.secondary_color = data.secondary_color
    organization.use_custom_brand = bool(data.use_custom_brand and organization.id != ATRIA_DEMO_ORG_ID)
    log(db, 'Identidade visual da organização atualizada.')
    db.commit()
    db.refresh(organization)
    return organization_brand_payload(db, organization)

@app.put('/api/organization/brand/assets/{kind}', dependencies=[Depends(admin_only)])
def upload_organization_brand_asset(kind: str, data: OrganizationBrandAssetIn, request: Request, db: Session = Depends(session)):
    current = authorized(request)
    if current['organization_id'] == ATRIA_DEMO_ORG_ID:
        raise HTTPException(409, 'O ambiente ATRIA Demo mantém a identidade oficial do ATRIA.')
    raw, mime_type = decode_brand_asset(kind, data.image_data)
    asset = db.scalar(select(OrganizationBrandAsset).where(
        OrganizationBrandAsset.organization_id == current['organization_id'],
        OrganizationBrandAsset.kind == kind
    ).limit(1))
    if asset is None:
        asset = OrganizationBrandAsset(
            organization_id=current['organization_id'],
            kind=kind,
            mime_type=mime_type,
            image=raw,
        )
        db.add(asset)
    else:
        asset.mime_type = mime_type
        asset.image = raw
        asset.updated_at = datetime.now(timezone.utc)
    organization = db.get(Organization, current['organization_id'])
    organization.use_custom_brand = True
    log(db, f'Arquivo de identidade visual atualizado: {kind}.')
    db.commit()
    return {'ok': True, 'kind': kind}

@app.delete('/api/organization/brand/assets/{kind}', dependencies=[Depends(admin_only)])
def delete_organization_brand_asset(kind: str, request: Request, db: Session = Depends(session)):
    current = authorized(request)
    if kind not in BRAND_ASSET_KINDS:
        raise HTTPException(404, 'Tipo de identidade visual não encontrado.')
    asset = db.scalar(select(OrganizationBrandAsset).where(
        OrganizationBrandAsset.organization_id == current['organization_id'],
        OrganizationBrandAsset.kind == kind
    ).limit(1))
    if asset is not None:
        db.delete(asset)
        log(db, f'Arquivo de identidade visual removido: {kind}.')
        db.commit()
    return {'ok': True, 'kind': kind}

@app.get('/api/organization/brand/assets/{kind}', dependencies=[Depends(authorized)])
def get_organization_brand_asset(kind: str, request: Request, db: Session = Depends(session)):
    current = authorized(request)
    if kind not in BRAND_ASSET_KINDS:
        raise HTTPException(404, 'Tipo de identidade visual não encontrado.')
    asset = db.scalar(select(OrganizationBrandAsset).where(
        OrganizationBrandAsset.organization_id == current['organization_id'],
        OrganizationBrandAsset.kind == kind
    ).limit(1))
    if asset is None:
        raise HTTPException(404, 'Arquivo de identidade visual não cadastrado.')
    return Response(
        content=asset.image,
        media_type=asset.mime_type,
        headers={'Cache-Control': 'private, no-store'}
    )

@app.get('/api/state', dependencies=[Depends(authorized)])
def state(request: Request, db: Session = Depends(session)):
    """Carga inicial em lote.

    O banco de produção é remoto ao container do app. Evitar consultas N+1 aqui
    reduz bastante a latência percebida no primeiro carregamento.
    """
    org_id = organization_id(db)
    projects = db.scalars(select(Project).where(Project.organization_id == org_id).order_by(Project.created_at.desc(), Project.id.desc())).all()
    tasks = db.scalars(select(Task).where(Task.organization_id == org_id).order_by(Task.id.desc())).all()
    members = db.scalars(select(Member).where(Member.organization_id == org_id).order_by(Member.name)).all()
    activities = db.scalars(select(Activity).where(Activity.organization_id == org_id).order_by(Activity.id.desc()).limit(30)).all()
    meetings = db.scalars(select(Meeting).where(Meeting.organization_id == org_id).order_by(Meeting.meeting_date, Meeting.start_time, Meeting.id)).all()

    project_ids = [p.id for p in projects]
    member_ids = [m.id for m in members]
    meeting_ids = [m.id for m in meetings]

    sites = {}
    if project_ids:
        sites = {
            row.project_id: row.url
            for row in db.scalars(
                select(ProjectClientSite).where(ProjectClientSite.project_id.in_(project_ids))
            ).all()
        }

    brand_profiles = {}
    if member_ids:
        brand_profiles = {
            row.member_id: row
            for row in db.scalars(
                select(MemberBrand).where(MemberBrand.member_id.in_(member_ids))
            ).all()
        }

    closures = {}
    attendee_rows = []
    if meeting_ids:
        closures = {
            row.meeting_id: row
            for row in db.scalars(
                select(MeetingClosure).where(MeetingClosure.meeting_id.in_(meeting_ids))
            ).all()
        }
        attendee_rows = db.scalars(
            select(MeetingAttendee).where(MeetingAttendee.meeting_id.in_(meeting_ids))
        ).all()

    members_by_id = {member.id: member for member in members}
    attendee_ids_by_meeting = {meeting_id: [] for meeting_id in meeting_ids}
    for row in attendee_rows:
        if row.member_id in members_by_id:
            attendee_ids_by_meeting.setdefault(row.meeting_id, []).append(row.member_id)

    def project_payload(project):
        return dict(
            id=project.id,
            name=project.name,
            description=project.description,
            client=project.client,
            client_site=sites.get(project.id, ''),
            owner=project.owner,
            status=effective_status(project),
            saved_status=project.status,
            progress=project.progress,
            started_at=project.started_at.isoformat() if project.started_at else None,
            due_at=project.due_at.isoformat() if project.due_at else None,
            created_at=stamp(project.created_at),
            updated_at=stamp(project.updated_at),
        )

    def member_payload(member):
        profile = brand_profiles.get(member.id)
        return dict(
            id=member.id,
            name=member.name,
            role=member.role,
            email=member.email,
            whatsapp=profile.whatsapp if profile else '',
            city=profile.city if profile else 'Patos de Minas - MG',
            site=profile.site if profile else 'https://nexonlabs.onrender.com',
        )

    meeting_status_by_id = {
        meeting.id: (closures[meeting.id].status if meeting.id in closures else 'agendada')
        for meeting in meetings
    }

    def conflicts_for(meeting):
        if meeting_status_by_id.get(meeting.id) == 'cancelada':
            return []
        selected = set(attendee_ids_by_meeting.get(meeting.id, []))
        if not selected:
            return []
        conflicts = []
        for other in meetings:
            if other.id == meeting.id or other.meeting_date != meeting.meeting_date:
                continue
            if meeting_status_by_id.get(other.id) == 'cancelada':
                continue
            if not (other.start_time < meeting.end_time and other.end_time > meeting.start_time):
                continue
            shared = selected.intersection(attendee_ids_by_meeting.get(other.id, []))
            if not shared:
                continue
            ordered = sorted(shared, key=lambda member_id: members_by_id[member_id].name.lower())
            conflicts.append(dict(
                meeting_id=other.id,
                title=other.title,
                start_time=other.start_time,
                end_time=other.end_time,
                attendee_ids=ordered,
                attendee_names=[members_by_id[member_id].name for member_id in ordered],
            ))
        return sorted(conflicts, key=lambda item: (item['start_time'], item['meeting_id']))

    def meeting_payload(meeting):
        lifecycle = closures.get(meeting.id)
        attendee_ids = attendee_ids_by_meeting.get(meeting.id, [])
        ordered_ids = sorted(attendee_ids, key=lambda member_id: members_by_id[member_id].name.lower())
        conflicts = conflicts_for(meeting)
        return dict(
            id=meeting.id,
            title=meeting.title,
            client=meeting.client,
            project_id=meeting.project_id,
            meeting_date=meeting.meeting_date.isoformat(),
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            location=meeting.location,
            meeting_url=meeting.meeting_url,
            notes=meeting.notes,
            created_at=stamp(meeting.created_at),
            status=lifecycle.status if lifecycle else 'agendada',
            closure_note=lifecycle.note if lifecycle else '',
            closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
            closure_by=lifecycle.updated_by if lifecycle else '',
            attendee_ids=ordered_ids,
            attendee_names=[members_by_id[member_id].name for member_id in ordered_ids],
            has_conflict=bool(conflicts),
            conflicts=conflicts,
        )

    current = authorized(request)
    organization = db.get(Organization, current['organization_id'])
    has_photo = db.scalar(select(AccountPhoto.account_id).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == org_id
    ).limit(1)) is not None

    return dict(
        projects=[project_payload(project) for project in projects],
        tasks=[task_dict(task) for task in tasks],
        meetings=[meeting_payload(meeting) for meeting in meetings],
        members=[member_payload(member) for member in members],
        activities=[dict(id=a.id, message=a.message, created_at=stamp(a.created_at)) for a in activities],
        user=current['name'],
        user_id=current['id'],
        user_role=current['role'],
        organization=organization_brand_payload(db, organization) if organization else None,
        has_photo=has_photo,
        auth_enabled=True,
    )

@app.post('/api/projects', dependencies=[Depends(authorized)], status_code=201)
def add_project(data: ProjectIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    p = Project(organization_id=organization_id(db), **data.model_dump(exclude={'client_site'}))
    db.add(p);db.flush()
    sync_project_site(db,p.id,data.client_site)
    log(db, f'Projeto {p.name} cadastrado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.put('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def edit_project(project_id: int, data: ProjectIn, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    for key, val in data.model_dump(exclude={'client_site'}).items(): setattr(p, key, val)
    sync_project_site(db,p.id,data.client_site)
    p.updated_at = datetime.now(timezone.utc)
    log(db, f'Projeto {p.name} atualizado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.delete('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def remove_project(project_id: int, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    log(db, f'Projeto {p.name} excluído.')
    site=db.get(ProjectClientSite,project_id)
    if site:db.delete(site)
    db.delete(p); db.commit()
    return {'ok': True}

@app.post('/api/tasks', dependencies=[Depends(authorized)], status_code=201)
def add_task(data: TaskIn, db: Session = Depends(session)):
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    task = Task(organization_id=organization_id(db), **data.model_dump(exclude={'title'}), title=data.title.strip())
    db.add(task); log(db, f'Tarefa {task.title} cadastrada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.put('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def edit_task(task_id: int, data: TaskIn, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    for key, value in data.model_dump().items(): setattr(task, key, value)
    task.title = task.title.strip()
    log(db, f'Tarefa {task.title} atualizada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.delete('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def remove_task(task_id: int, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    db.delete(task); db.commit(); return {'ok': True}

@app.post('/api/members', dependencies=[Depends(authorized)], status_code=201)
def add_member(data: MemberIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome.')
    org_id = organization_id(db)
    if db.scalar(select(Member).where(Member.organization_id == org_id, func.lower(Member.name) == data.name.lower())):
        raise HTTPException(409, 'Já existe um integrante com esse nome.')
    member=Member(organization_id=org_id,name=data.name,role=data.role,email=data.email)
    db.add(member);db.flush()
    member_brand_sync(db,member,data)
    log(db,f'{member.name} adicionado à equipe.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.put('/api/members/{member_id}', dependencies=[Depends(authorized)])
def edit_member(member_id: int, data: MemberIn, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Colaborador não encontrado.')
    if not data.name:raise HTTPException(422,'Informe o nome.')
    duplicate=db.scalar(select(Member).where(
        Member.organization_id==organization_id(db),
        func.lower(Member.name)==data.name.lower(),
        Member.id!=member_id
    ))
    if duplicate:raise HTTPException(409,'Já existe outro colaborador com esse nome.')
    member.name,member.role,member.email=data.name,data.role,data.email
    member_brand_sync(db,member,data)
    log(db,f'Colaborador {member.name} atualizado.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.delete('/api/members/{member_id}', dependencies=[Depends(authorized)])
def remove_member(member_id: int, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Integrante não encontrado.')
    profile=db.get(MemberBrand,member_id)
    if profile:db.delete(profile)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.member_id==member_id)).all():
        db.delete(attendee)
    db.delete(member);db.commit();return {'ok':True}

def meeting_status(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    return lifecycle.status if lifecycle else 'agendada'

def meeting_attendees(m: Meeting, db: Session):
    ids=list(db.scalars(select(MeetingAttendee.member_id).where(
        MeetingAttendee.meeting_id==m.id
    )).all())
    if not ids:return [],[]
    members=db.scalars(select(Member).where(
        Member.organization_id==m.organization_id,
        Member.id.in_(ids)
    ).order_by(Member.name)).all()
    names=[member.name for member in members]
    existing={member.id for member in members}
    clean_ids=[member_id for member_id in ids if member_id in existing]
    return clean_ids,names

def meeting_conflicts(m: Meeting, db: Session, attendee_ids: list[int] | None=None):
    if meeting_status(m,db)=='cancelada':return []
    if attendee_ids is None:
        attendee_ids,_=meeting_attendees(m,db)
    if not attendee_ids:return []
    candidates=db.scalars(select(Meeting).where(
        Meeting.organization_id==m.organization_id,
        Meeting.id!=m.id,
        Meeting.meeting_date==m.meeting_date,
        Meeting.start_time < m.end_time,
        Meeting.end_time > m.start_time
    ).order_by(Meeting.start_time,Meeting.id)).all()
    conflicts=[]
    selected=set(attendee_ids)
    for other in candidates:
        if meeting_status(other,db)=='cancelada':continue
        other_ids,other_names=meeting_attendees(other,db)
        shared=selected.intersection(other_ids)
        if not shared:continue
        shared_names=[name for mid,name in zip(other_ids,other_names) if mid in shared]
        # zip não é confiável se a ordenação de ids/names divergir; consultar nomes compartilhados.
        shared_members=db.scalars(select(Member).where(
            Member.organization_id==m.organization_id,
            Member.id.in_(shared)
        ).order_by(Member.name)).all()
        conflicts.append(dict(
            meeting_id=other.id,title=other.title,start_time=other.start_time,end_time=other.end_time,
            attendee_ids=sorted(shared),attendee_names=[x.name for x in shared_members]
        ))
    return conflicts

def meeting_dict(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    attendee_ids,attendee_names=meeting_attendees(m,db)
    conflicts=meeting_conflicts(m,db,attendee_ids)
    return dict(id=m.id, title=m.title, client=m.client, project_id=m.project_id,
                meeting_date=m.meeting_date.isoformat(), start_time=m.start_time,
                end_time=m.end_time, location=m.location, meeting_url=m.meeting_url,
                notes=m.notes, created_at=stamp(m.created_at),
                status=lifecycle.status if lifecycle else 'agendada',
                closure_note=lifecycle.note if lifecycle else '',
                closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
                closure_by=lifecycle.updated_by if lifecycle else '',
                attendee_ids=attendee_ids,attendee_names=attendee_names,
                has_conflict=bool(conflicts),conflicts=conflicts)

def validate_meeting(data: MeetingIn, db: Session, exclude_id: int | None = None):
    if not data.title.strip():
        raise HTTPException(422, 'Informe o título da reunião.')
    if data.end_time <= data.start_time:
        raise HTTPException(422, 'A reunião deve terminar depois do início.')
    org_id = organization_id(db)
    if data.project_id is not None and tenant_get(db, Project, data.project_id) is None:
        raise HTTPException(422, 'O projeto selecionado não existe.')
    if data.meeting_url and not data.meeting_url.startswith(('https://', 'http://')):
        raise HTTPException(422, 'O link deve começar com https:// ou http://.')
    attendee_ids=list(dict.fromkeys(data.attendee_ids))
    if not attendee_ids:
        raise HTTPException(422,'Selecione pelo menos um colaborador da Nexon Labs para a reunião.')
    valid_members=set(db.scalars(select(Member.id).where(
        Member.organization_id==org_id,
        Member.id.in_(attendee_ids)
    )).all())
    missing=[member_id for member_id in attendee_ids if member_id not in valid_members]
    if missing:
        raise HTTPException(422,'Um ou mais colaboradores selecionados não existem mais.')

    # Impede apenas duplicação literal. Sobreposição de agenda é permitida,
    # mas será sinalizada como conflito para tratativa.
    duplicate = select(Meeting).where(
        Meeting.organization_id == org_id,
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

def sync_meeting_attendees(db: Session, meeting_id: int, attendee_ids: list[int]):
    for row in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(row)
    for member_id in dict.fromkeys(attendee_ids):
        db.add(MeetingAttendee(meeting_id=meeting_id,member_id=member_id))

@app.post('/api/meetings', dependencies=[Depends(authorized)], status_code=201)
def add_meeting(data: MeetingIn, db: Session = Depends(session)):
    validate_meeting(data, db)
    values=data.model_dump(exclude={'attendee_ids'})
    meeting = Meeting(organization_id=organization_id(db), **values)
    db.add(meeting)
    db.flush()
    sync_meeting_attendees(db,meeting.id,data.attendee_ids)
    log(db, f'Reunião {meeting.title} agendada para {meeting.meeting_date.isoformat()}.')
    db.commit()
    db.refresh(meeting)
    return meeting_dict(meeting,db)

@app.put('/api/meetings/{meeting_id}', dependencies=[Depends(authorized)])
def edit_meeting(meeting_id: int, data: MeetingIn, db: Session = Depends(session)):
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    validate_meeting(data, db, exclude_id=meeting_id)
    for key, value in data.model_dump(exclude={'attendee_ids'}).items():
        setattr(meeting, key, value)
    sync_meeting_attendees(db,meeting_id,data.attendee_ids)
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
    meeting=tenant_get(db,Meeting,meeting_id)
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
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    # Exclusão é distinta do cancelamento: preserve a reunião cancelada no histórico.
    lifecycle=db.get(MeetingClosure,meeting_id)
    if lifecycle:db.delete(lifecycle)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(attendee)
    log(db, f'Reunião {meeting.title} excluída.')
    db.delete(meeting)
    db.commit()
    return {'ok': True}

@app.get('/api/export/projects.csv', dependencies=[Depends(authorized)])
def export_projects(db: Session = Depends(session)):
    buffer = io.StringIO(); out = csv.writer(buffer, delimiter=';')
    out.writerow(['ID', 'Projeto', 'Descrição', 'Cliente', 'Site do cliente', 'Responsável', 'Status', 'Progresso (%)', 'Início', 'Prazo'])
    for p in db.scalars(select(Project).where(
        Project.organization_id == organization_id(db)
    ).order_by(Project.id)):
        out.writerow([p.id, p.name, p.description, p.client, project_site(db,p.id), p.owner, effective_status(p), p.progress,
                      p.started_at.isoformat() if p.started_at else '', p.due_at.isoformat() if p.due_at else ''])
    buffer.seek(0)
    return StreamingResponse(iter(['\ufeff' + buffer.getvalue()]), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="atria_projetos.csv"'})

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
    app, Base, DB, engine, authorized, log, Member, member_dict, Organization
)

# A referência visual original fica persistida no PostgreSQL e só é instalada pelo administrador.
from approved_template import install_reference
ApprovedArtwork = install_reference(app, Base, DB, engine, authorized, admin_only)

# Ambiente comercial de demonstração, totalmente isolado da Nexon Labs.
from demo_seed import seed_demo_environment
seed_demo_environment(
    DB=DB,
    Account=Account,
    Member=Member,
    Project=Project,
    Task=Task,
    Activity=Activity,
    Meeting=Meeting,
    MeetingClosure=MeetingClosure,
    MeetingAttendee=MeetingAttendee,
    Quote=app.state.Quote,
    Company=app.state.Company,
    Ticket=app.state.Ticket,
    TicketEvent=app.state.TicketEvent,
    hash_password=hash_password,
    password_in_use=password_in_use,
)
)
    secondary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}

@app.get('/api/profile/avatar', dependencies=[Depends(authorized)])
def get_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
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
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        photo.image = safe_image
    else:
        db.add(AccountPhoto(account_id=current['id'], organization_id=current['organization_id'], image=safe_image))
    db.commit()
    return {'ok': True, 'has_photo': True}

@app.delete('/api/profile/avatar', dependencies=[Depends(authorized)])
def delete_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        db.delete(photo)
        db.commit()
    return {'ok': True, 'has_photo': False}

@app.get('/api/state', dependencies=[Depends(authorized)])
def state(request: Request, db: Session = Depends(session)):
    """Carga inicial em lote.

    O banco de produção é remoto ao container do app. Evitar consultas N+1 aqui
    reduz bastante a latência percebida no primeiro carregamento.
    """
    org_id = organization_id(db)
    projects = db.scalars(select(Project).where(Project.organization_id == org_id).order_by(Project.created_at.desc(), Project.id.desc())).all()
    tasks = db.scalars(select(Task).where(Task.organization_id == org_id).order_by(Task.id.desc())).all()
    members = db.scalars(select(Member).where(Member.organization_id == org_id).order_by(Member.name)).all()
    activities = db.scalars(select(Activity).where(Activity.organization_id == org_id).order_by(Activity.id.desc()).limit(30)).all()
    meetings = db.scalars(select(Meeting).where(Meeting.organization_id == org_id).order_by(Meeting.meeting_date, Meeting.start_time, Meeting.id)).all()

    project_ids = [p.id for p in projects]
    member_ids = [m.id for m in members]
    meeting_ids = [m.id for m in meetings]

    sites = {}
    if project_ids:
        sites = {
            row.project_id: row.url
            for row in db.scalars(
                select(ProjectClientSite).where(ProjectClientSite.project_id.in_(project_ids))
            ).all()
        }

    brand_profiles = {}
    if member_ids:
        brand_profiles = {
            row.member_id: row
            for row in db.scalars(
                select(MemberBrand).where(MemberBrand.member_id.in_(member_ids))
            ).all()
        }

    closures = {}
    attendee_rows = []
    if meeting_ids:
        closures = {
            row.meeting_id: row
            for row in db.scalars(
                select(MeetingClosure).where(MeetingClosure.meeting_id.in_(meeting_ids))
            ).all()
        }
        attendee_rows = db.scalars(
            select(MeetingAttendee).where(MeetingAttendee.meeting_id.in_(meeting_ids))
        ).all()

    members_by_id = {member.id: member for member in members}
    attendee_ids_by_meeting = {meeting_id: [] for meeting_id in meeting_ids}
    for row in attendee_rows:
        if row.member_id in members_by_id:
            attendee_ids_by_meeting.setdefault(row.meeting_id, []).append(row.member_id)

    def project_payload(project):
        return dict(
            id=project.id,
            name=project.name,
            description=project.description,
            client=project.client,
            client_site=sites.get(project.id, ''),
            owner=project.owner,
            status=effective_status(project),
            saved_status=project.status,
            progress=project.progress,
            started_at=project.started_at.isoformat() if project.started_at else None,
            due_at=project.due_at.isoformat() if project.due_at else None,
            created_at=stamp(project.created_at),
            updated_at=stamp(project.updated_at),
        )

    def member_payload(member):
        profile = brand_profiles.get(member.id)
        return dict(
            id=member.id,
            name=member.name,
            role=member.role,
            email=member.email,
            whatsapp=profile.whatsapp if profile else '',
            city=profile.city if profile else 'Patos de Minas - MG',
            site=profile.site if profile else 'https://nexonlabs.onrender.com',
        )

    meeting_status_by_id = {
        meeting.id: (closures[meeting.id].status if meeting.id in closures else 'agendada')
        for meeting in meetings
    }

    def conflicts_for(meeting):
        if meeting_status_by_id.get(meeting.id) == 'cancelada':
            return []
        selected = set(attendee_ids_by_meeting.get(meeting.id, []))
        if not selected:
            return []
        conflicts = []
        for other in meetings:
            if other.id == meeting.id or other.meeting_date != meeting.meeting_date:
                continue
            if meeting_status_by_id.get(other.id) == 'cancelada':
                continue
            if not (other.start_time < meeting.end_time and other.end_time > meeting.start_time):
                continue
            shared = selected.intersection(attendee_ids_by_meeting.get(other.id, []))
            if not shared:
                continue
            ordered = sorted(shared, key=lambda member_id: members_by_id[member_id].name.lower())
            conflicts.append(dict(
                meeting_id=other.id,
                title=other.title,
                start_time=other.start_time,
                end_time=other.end_time,
                attendee_ids=ordered,
                attendee_names=[members_by_id[member_id].name for member_id in ordered],
            ))
        return sorted(conflicts, key=lambda item: (item['start_time'], item['meeting_id']))

    def meeting_payload(meeting):
        lifecycle = closures.get(meeting.id)
        attendee_ids = attendee_ids_by_meeting.get(meeting.id, [])
        ordered_ids = sorted(attendee_ids, key=lambda member_id: members_by_id[member_id].name.lower())
        conflicts = conflicts_for(meeting)
        return dict(
            id=meeting.id,
            title=meeting.title,
            client=meeting.client,
            project_id=meeting.project_id,
            meeting_date=meeting.meeting_date.isoformat(),
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            location=meeting.location,
            meeting_url=meeting.meeting_url,
            notes=meeting.notes,
            created_at=stamp(meeting.created_at),
            status=lifecycle.status if lifecycle else 'agendada',
            closure_note=lifecycle.note if lifecycle else '',
            closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
            closure_by=lifecycle.updated_by if lifecycle else '',
            attendee_ids=ordered_ids,
            attendee_names=[members_by_id[member_id].name for member_id in ordered_ids],
            has_conflict=bool(conflicts),
            conflicts=conflicts,
        )

    current = authorized(request)
    organization = db.get(Organization, current['organization_id'])
    has_photo = db.scalar(select(AccountPhoto.account_id).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == org_id
    ).limit(1)) is not None

    return dict(
        projects=[project_payload(project) for project in projects],
        tasks=[task_dict(task) for task in tasks],
        meetings=[meeting_payload(meeting) for meeting in meetings],
        members=[member_payload(member) for member in members],
        activities=[dict(id=a.id, message=a.message, created_at=stamp(a.created_at)) for a in activities],
        user=current['name'],
        user_id=current['id'],
        user_role=current['role'],
        organization=organization_public(organization) if organization else None,
        has_photo=has_photo,
        auth_enabled=True,
    )

@app.post('/api/projects', dependencies=[Depends(authorized)], status_code=201)
def add_project(data: ProjectIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    p = Project(organization_id=organization_id(db), **data.model_dump(exclude={'client_site'}))
    db.add(p);db.flush()
    sync_project_site(db,p.id,data.client_site)
    log(db, f'Projeto {p.name} cadastrado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.put('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def edit_project(project_id: int, data: ProjectIn, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    for key, val in data.model_dump(exclude={'client_site'}).items(): setattr(p, key, val)
    sync_project_site(db,p.id,data.client_site)
    p.updated_at = datetime.now(timezone.utc)
    log(db, f'Projeto {p.name} atualizado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.delete('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def remove_project(project_id: int, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    log(db, f'Projeto {p.name} excluído.')
    site=db.get(ProjectClientSite,project_id)
    if site:db.delete(site)
    db.delete(p); db.commit()
    return {'ok': True}

@app.post('/api/tasks', dependencies=[Depends(authorized)], status_code=201)
def add_task(data: TaskIn, db: Session = Depends(session)):
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    task = Task(organization_id=organization_id(db), **data.model_dump(exclude={'title'}), title=data.title.strip())
    db.add(task); log(db, f'Tarefa {task.title} cadastrada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.put('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def edit_task(task_id: int, data: TaskIn, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    for key, value in data.model_dump().items(): setattr(task, key, value)
    task.title = task.title.strip()
    log(db, f'Tarefa {task.title} atualizada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.delete('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def remove_task(task_id: int, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    db.delete(task); db.commit(); return {'ok': True}

@app.post('/api/members', dependencies=[Depends(authorized)], status_code=201)
def add_member(data: MemberIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome.')
    org_id = organization_id(db)
    if db.scalar(select(Member).where(Member.organization_id == org_id, func.lower(Member.name) == data.name.lower())):
        raise HTTPException(409, 'Já existe um integrante com esse nome.')
    member=Member(organization_id=org_id,name=data.name,role=data.role,email=data.email)
    db.add(member);db.flush()
    member_brand_sync(db,member,data)
    log(db,f'{member.name} adicionado à equipe.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.put('/api/members/{member_id}', dependencies=[Depends(authorized)])
def edit_member(member_id: int, data: MemberIn, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Colaborador não encontrado.')
    if not data.name:raise HTTPException(422,'Informe o nome.')
    duplicate=db.scalar(select(Member).where(
        Member.organization_id==organization_id(db),
        func.lower(Member.name)==data.name.lower(),
        Member.id!=member_id
    ))
    if duplicate:raise HTTPException(409,'Já existe outro colaborador com esse nome.')
    member.name,member.role,member.email=data.name,data.role,data.email
    member_brand_sync(db,member,data)
    log(db,f'Colaborador {member.name} atualizado.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.delete('/api/members/{member_id}', dependencies=[Depends(authorized)])
def remove_member(member_id: int, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Integrante não encontrado.')
    profile=db.get(MemberBrand,member_id)
    if profile:db.delete(profile)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.member_id==member_id)).all():
        db.delete(attendee)
    db.delete(member);db.commit();return {'ok':True}

def meeting_status(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    return lifecycle.status if lifecycle else 'agendada'

def meeting_attendees(m: Meeting, db: Session):
    ids=list(db.scalars(select(MeetingAttendee.member_id).where(
        MeetingAttendee.meeting_id==m.id
    )).all())
    if not ids:return [],[]
    members=db.scalars(select(Member).where(
        Member.organization_id==m.organization_id,
        Member.id.in_(ids)
    ).order_by(Member.name)).all()
    names=[member.name for member in members]
    existing={member.id for member in members}
    clean_ids=[member_id for member_id in ids if member_id in existing]
    return clean_ids,names

def meeting_conflicts(m: Meeting, db: Session, attendee_ids: list[int] | None=None):
    if meeting_status(m,db)=='cancelada':return []
    if attendee_ids is None:
        attendee_ids,_=meeting_attendees(m,db)
    if not attendee_ids:return []
    candidates=db.scalars(select(Meeting).where(
        Meeting.organization_id==m.organization_id,
        Meeting.id!=m.id,
        Meeting.meeting_date==m.meeting_date,
        Meeting.start_time < m.end_time,
        Meeting.end_time > m.start_time
    ).order_by(Meeting.start_time,Meeting.id)).all()
    conflicts=[]
    selected=set(attendee_ids)
    for other in candidates:
        if meeting_status(other,db)=='cancelada':continue
        other_ids,other_names=meeting_attendees(other,db)
        shared=selected.intersection(other_ids)
        if not shared:continue
        shared_names=[name for mid,name in zip(other_ids,other_names) if mid in shared]
        # zip não é confiável se a ordenação de ids/names divergir; consultar nomes compartilhados.
        shared_members=db.scalars(select(Member).where(
            Member.organization_id==m.organization_id,
            Member.id.in_(shared)
        ).order_by(Member.name)).all()
        conflicts.append(dict(
            meeting_id=other.id,title=other.title,start_time=other.start_time,end_time=other.end_time,
            attendee_ids=sorted(shared),attendee_names=[x.name for x in shared_members]
        ))
    return conflicts

def meeting_dict(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    attendee_ids,attendee_names=meeting_attendees(m,db)
    conflicts=meeting_conflicts(m,db,attendee_ids)
    return dict(id=m.id, title=m.title, client=m.client, project_id=m.project_id,
                meeting_date=m.meeting_date.isoformat(), start_time=m.start_time,
                end_time=m.end_time, location=m.location, meeting_url=m.meeting_url,
                notes=m.notes, created_at=stamp(m.created_at),
                status=lifecycle.status if lifecycle else 'agendada',
                closure_note=lifecycle.note if lifecycle else '',
                closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
                closure_by=lifecycle.updated_by if lifecycle else '',
                attendee_ids=attendee_ids,attendee_names=attendee_names,
                has_conflict=bool(conflicts),conflicts=conflicts)

def validate_meeting(data: MeetingIn, db: Session, exclude_id: int | None = None):
    if not data.title.strip():
        raise HTTPException(422, 'Informe o título da reunião.')
    if data.end_time <= data.start_time:
        raise HTTPException(422, 'A reunião deve terminar depois do início.')
    org_id = organization_id(db)
    if data.project_id is not None and tenant_get(db, Project, data.project_id) is None:
        raise HTTPException(422, 'O projeto selecionado não existe.')
    if data.meeting_url and not data.meeting_url.startswith(('https://', 'http://')):
        raise HTTPException(422, 'O link deve começar com https:// ou http://.')
    attendee_ids=list(dict.fromkeys(data.attendee_ids))
    if not attendee_ids:
        raise HTTPException(422,'Selecione pelo menos um colaborador da Nexon Labs para a reunião.')
    valid_members=set(db.scalars(select(Member.id).where(
        Member.organization_id==org_id,
        Member.id.in_(attendee_ids)
    )).all())
    missing=[member_id for member_id in attendee_ids if member_id not in valid_members]
    if missing:
        raise HTTPException(422,'Um ou mais colaboradores selecionados não existem mais.')

    # Impede apenas duplicação literal. Sobreposição de agenda é permitida,
    # mas será sinalizada como conflito para tratativa.
    duplicate = select(Meeting).where(
        Meeting.organization_id == org_id,
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

def sync_meeting_attendees(db: Session, meeting_id: int, attendee_ids: list[int]):
    for row in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(row)
    for member_id in dict.fromkeys(attendee_ids):
        db.add(MeetingAttendee(meeting_id=meeting_id,member_id=member_id))

@app.post('/api/meetings', dependencies=[Depends(authorized)], status_code=201)
def add_meeting(data: MeetingIn, db: Session = Depends(session)):
    validate_meeting(data, db)
    values=data.model_dump(exclude={'attendee_ids'})
    meeting = Meeting(organization_id=organization_id(db), **values)
    db.add(meeting)
    db.flush()
    sync_meeting_attendees(db,meeting.id,data.attendee_ids)
    log(db, f'Reunião {meeting.title} agendada para {meeting.meeting_date.isoformat()}.')
    db.commit()
    db.refresh(meeting)
    return meeting_dict(meeting,db)

@app.put('/api/meetings/{meeting_id}', dependencies=[Depends(authorized)])
def edit_meeting(meeting_id: int, data: MeetingIn, db: Session = Depends(session)):
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    validate_meeting(data, db, exclude_id=meeting_id)
    for key, value in data.model_dump(exclude={'attendee_ids'}).items():
        setattr(meeting, key, value)
    sync_meeting_attendees(db,meeting_id,data.attendee_ids)
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
    meeting=tenant_get(db,Meeting,meeting_id)
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
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    # Exclusão é distinta do cancelamento: preserve a reunião cancelada no histórico.
    lifecycle=db.get(MeetingClosure,meeting_id)
    if lifecycle:db.delete(lifecycle)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(attendee)
    log(db, f'Reunião {meeting.title} excluída.')
    db.delete(meeting)
    db.commit()
    return {'ok': True}

@app.get('/api/export/projects.csv', dependencies=[Depends(authorized)])
def export_projects(db: Session = Depends(session)):
    buffer = io.StringIO(); out = csv.writer(buffer, delimiter=';')
    out.writerow(['ID', 'Projeto', 'Descrição', 'Cliente', 'Site do cliente', 'Responsável', 'Status', 'Progresso (%)', 'Início', 'Prazo'])
    for p in db.scalars(select(Project).where(
        Project.organization_id == organization_id(db)
    ).order_by(Project.id)):
        out.writerow([p.id, p.name, p.description, p.client, project_site(db,p.id), p.owner, effective_status(p), p.progress,
                      p.started_at.isoformat() if p.started_at else '', p.due_at.isoformat() if p.due_at else ''])
    buffer.seek(0)
    return StreamingResponse(iter(['\ufeff' + buffer.getvalue()]), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="atria_projetos.csv"'})

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
    app, Base, DB, engine, authorized, log, Member, member_dict, Organization
)

# A referência visual original fica persistida no PostgreSQL e só é instalada pelo administrador.
from approved_template import install_reference
ApprovedArtwork = install_reference(app, Base, DB, engine, authorized, admin_only)

# Ambiente comercial de demonstração, totalmente isolado da Nexon Labs.
from demo_seed import seed_demo_environment
seed_demo_environment(
    DB=DB,
    Account=Account,
    Member=Member,
    Project=Project,
    Task=Task,
    Activity=Activity,
    Meeting=Meeting,
    MeetingClosure=MeetingClosure,
    MeetingAttendee=MeetingAttendee,
    Quote=app.state.Quote,
    Company=app.state.Company,
    Ticket=app.state.Ticket,
    TicketEvent=app.state.TicketEvent,
    hash_password=hash_password,
    password_in_use=password_in_use,
)
)
    use_custom_brand: bool = False

    @field_validator('primary_color', 'secondary_color')
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()

class OrganizationBrandAssetIn(BaseModel):
    image_data: str = Field(min_length=32, max_length=4_200_000)

@app.get('/api/profile/avatar', dependencies=[Depends(authorized)])
def get_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
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
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        photo.image = safe_image
    else:
        db.add(AccountPhoto(account_id=current['id'], organization_id=current['organization_id'], image=safe_image))
    db.commit()
    return {'ok': True, 'has_photo': True}

@app.delete('/api/profile/avatar', dependencies=[Depends(authorized)])
def delete_my_avatar(request: Request, db: Session = Depends(session)):
    current = authorized(request)
    photo = db.scalar(select(AccountPhoto).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == current['organization_id']
    ).limit(1))
    if photo:
        db.delete(photo)
        db.commit()
    return {'ok': True, 'has_photo': False}

@app.get('/api/state', dependencies=[Depends(authorized)])
def state(request: Request, db: Session = Depends(session)):
    """Carga inicial em lote.

    O banco de produção é remoto ao container do app. Evitar consultas N+1 aqui
    reduz bastante a latência percebida no primeiro carregamento.
    """
    org_id = organization_id(db)
    projects = db.scalars(select(Project).where(Project.organization_id == org_id).order_by(Project.created_at.desc(), Project.id.desc())).all()
    tasks = db.scalars(select(Task).where(Task.organization_id == org_id).order_by(Task.id.desc())).all()
    members = db.scalars(select(Member).where(Member.organization_id == org_id).order_by(Member.name)).all()
    activities = db.scalars(select(Activity).where(Activity.organization_id == org_id).order_by(Activity.id.desc()).limit(30)).all()
    meetings = db.scalars(select(Meeting).where(Meeting.organization_id == org_id).order_by(Meeting.meeting_date, Meeting.start_time, Meeting.id)).all()

    project_ids = [p.id for p in projects]
    member_ids = [m.id for m in members]
    meeting_ids = [m.id for m in meetings]

    sites = {}
    if project_ids:
        sites = {
            row.project_id: row.url
            for row in db.scalars(
                select(ProjectClientSite).where(ProjectClientSite.project_id.in_(project_ids))
            ).all()
        }

    brand_profiles = {}
    if member_ids:
        brand_profiles = {
            row.member_id: row
            for row in db.scalars(
                select(MemberBrand).where(MemberBrand.member_id.in_(member_ids))
            ).all()
        }

    closures = {}
    attendee_rows = []
    if meeting_ids:
        closures = {
            row.meeting_id: row
            for row in db.scalars(
                select(MeetingClosure).where(MeetingClosure.meeting_id.in_(meeting_ids))
            ).all()
        }
        attendee_rows = db.scalars(
            select(MeetingAttendee).where(MeetingAttendee.meeting_id.in_(meeting_ids))
        ).all()

    members_by_id = {member.id: member for member in members}
    attendee_ids_by_meeting = {meeting_id: [] for meeting_id in meeting_ids}
    for row in attendee_rows:
        if row.member_id in members_by_id:
            attendee_ids_by_meeting.setdefault(row.meeting_id, []).append(row.member_id)

    def project_payload(project):
        return dict(
            id=project.id,
            name=project.name,
            description=project.description,
            client=project.client,
            client_site=sites.get(project.id, ''),
            owner=project.owner,
            status=effective_status(project),
            saved_status=project.status,
            progress=project.progress,
            started_at=project.started_at.isoformat() if project.started_at else None,
            due_at=project.due_at.isoformat() if project.due_at else None,
            created_at=stamp(project.created_at),
            updated_at=stamp(project.updated_at),
        )

    def member_payload(member):
        profile = brand_profiles.get(member.id)
        return dict(
            id=member.id,
            name=member.name,
            role=member.role,
            email=member.email,
            whatsapp=profile.whatsapp if profile else '',
            city=profile.city if profile else 'Patos de Minas - MG',
            site=profile.site if profile else 'https://nexonlabs.onrender.com',
        )

    meeting_status_by_id = {
        meeting.id: (closures[meeting.id].status if meeting.id in closures else 'agendada')
        for meeting in meetings
    }

    def conflicts_for(meeting):
        if meeting_status_by_id.get(meeting.id) == 'cancelada':
            return []
        selected = set(attendee_ids_by_meeting.get(meeting.id, []))
        if not selected:
            return []
        conflicts = []
        for other in meetings:
            if other.id == meeting.id or other.meeting_date != meeting.meeting_date:
                continue
            if meeting_status_by_id.get(other.id) == 'cancelada':
                continue
            if not (other.start_time < meeting.end_time and other.end_time > meeting.start_time):
                continue
            shared = selected.intersection(attendee_ids_by_meeting.get(other.id, []))
            if not shared:
                continue
            ordered = sorted(shared, key=lambda member_id: members_by_id[member_id].name.lower())
            conflicts.append(dict(
                meeting_id=other.id,
                title=other.title,
                start_time=other.start_time,
                end_time=other.end_time,
                attendee_ids=ordered,
                attendee_names=[members_by_id[member_id].name for member_id in ordered],
            ))
        return sorted(conflicts, key=lambda item: (item['start_time'], item['meeting_id']))

    def meeting_payload(meeting):
        lifecycle = closures.get(meeting.id)
        attendee_ids = attendee_ids_by_meeting.get(meeting.id, [])
        ordered_ids = sorted(attendee_ids, key=lambda member_id: members_by_id[member_id].name.lower())
        conflicts = conflicts_for(meeting)
        return dict(
            id=meeting.id,
            title=meeting.title,
            client=meeting.client,
            project_id=meeting.project_id,
            meeting_date=meeting.meeting_date.isoformat(),
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            location=meeting.location,
            meeting_url=meeting.meeting_url,
            notes=meeting.notes,
            created_at=stamp(meeting.created_at),
            status=lifecycle.status if lifecycle else 'agendada',
            closure_note=lifecycle.note if lifecycle else '',
            closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
            closure_by=lifecycle.updated_by if lifecycle else '',
            attendee_ids=ordered_ids,
            attendee_names=[members_by_id[member_id].name for member_id in ordered_ids],
            has_conflict=bool(conflicts),
            conflicts=conflicts,
        )

    current = authorized(request)
    organization = db.get(Organization, current['organization_id'])
    has_photo = db.scalar(select(AccountPhoto.account_id).where(
        AccountPhoto.account_id == current['id'],
        AccountPhoto.organization_id == org_id
    ).limit(1)) is not None

    return dict(
        projects=[project_payload(project) for project in projects],
        tasks=[task_dict(task) for task in tasks],
        meetings=[meeting_payload(meeting) for meeting in meetings],
        members=[member_payload(member) for member in members],
        activities=[dict(id=a.id, message=a.message, created_at=stamp(a.created_at)) for a in activities],
        user=current['name'],
        user_id=current['id'],
        user_role=current['role'],
        organization=organization_public(organization) if organization else None,
        has_photo=has_photo,
        auth_enabled=True,
    )

@app.post('/api/projects', dependencies=[Depends(authorized)], status_code=201)
def add_project(data: ProjectIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    p = Project(organization_id=organization_id(db), **data.model_dump(exclude={'client_site'}))
    db.add(p);db.flush()
    sync_project_site(db,p.id,data.client_site)
    log(db, f'Projeto {p.name} cadastrado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.put('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def edit_project(project_id: int, data: ProjectIn, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.name: raise HTTPException(422, 'Informe o nome do projeto.')
    if data.started_at and data.due_at and data.due_at < data.started_at: raise HTTPException(422, 'O prazo deve ser posterior ao início.')
    for key, val in data.model_dump(exclude={'client_site'}).items(): setattr(p, key, val)
    sync_project_site(db,p.id,data.client_site)
    p.updated_at = datetime.now(timezone.utc)
    log(db, f'Projeto {p.name} atualizado.')
    db.commit(); db.refresh(p)
    return project_dict(p,db)

@app.delete('/api/projects/{project_id}', dependencies=[Depends(authorized)])
def remove_project(project_id: int, db: Session = Depends(session)):
    p = tenant_get(db, Project, project_id)
    if p is None: raise HTTPException(404, 'Projeto não encontrado.')
    log(db, f'Projeto {p.name} excluído.')
    site=db.get(ProjectClientSite,project_id)
    if site:db.delete(site)
    db.delete(p); db.commit()
    return {'ok': True}

@app.post('/api/tasks', dependencies=[Depends(authorized)], status_code=201)
def add_task(data: TaskIn, db: Session = Depends(session)):
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    task = Task(organization_id=organization_id(db), **data.model_dump(exclude={'title'}), title=data.title.strip())
    db.add(task); log(db, f'Tarefa {task.title} cadastrada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.put('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def edit_task(task_id: int, data: TaskIn, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    if tenant_get(db, Project, data.project_id) is None: raise HTTPException(404, 'Projeto não encontrado.')
    if not data.title.strip(): raise HTTPException(422, 'Informe a tarefa.')
    for key, value in data.model_dump().items(): setattr(task, key, value)
    task.title = task.title.strip()
    log(db, f'Tarefa {task.title} atualizada.')
    db.commit(); db.refresh(task)
    return task_dict(task)

@app.delete('/api/tasks/{task_id}', dependencies=[Depends(authorized)])
def remove_task(task_id: int, db: Session = Depends(session)):
    task = tenant_get(db, Task, task_id)
    if task is None: raise HTTPException(404, 'Tarefa não encontrada.')
    db.delete(task); db.commit(); return {'ok': True}

@app.post('/api/members', dependencies=[Depends(authorized)], status_code=201)
def add_member(data: MemberIn, db: Session = Depends(session)):
    if not data.name: raise HTTPException(422, 'Informe o nome.')
    org_id = organization_id(db)
    if db.scalar(select(Member).where(Member.organization_id == org_id, func.lower(Member.name) == data.name.lower())):
        raise HTTPException(409, 'Já existe um integrante com esse nome.')
    member=Member(organization_id=org_id,name=data.name,role=data.role,email=data.email)
    db.add(member);db.flush()
    member_brand_sync(db,member,data)
    log(db,f'{member.name} adicionado à equipe.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.put('/api/members/{member_id}', dependencies=[Depends(authorized)])
def edit_member(member_id: int, data: MemberIn, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Colaborador não encontrado.')
    if not data.name:raise HTTPException(422,'Informe o nome.')
    duplicate=db.scalar(select(Member).where(
        Member.organization_id==organization_id(db),
        func.lower(Member.name)==data.name.lower(),
        Member.id!=member_id
    ))
    if duplicate:raise HTTPException(409,'Já existe outro colaborador com esse nome.')
    member.name,member.role,member.email=data.name,data.role,data.email
    member_brand_sync(db,member,data)
    log(db,f'Colaborador {member.name} atualizado.')
    db.commit();db.refresh(member)
    return member_dict(member,db)

@app.delete('/api/members/{member_id}', dependencies=[Depends(authorized)])
def remove_member(member_id: int, db: Session = Depends(session)):
    member=tenant_get(db,Member,member_id)
    if member is None:raise HTTPException(404,'Integrante não encontrado.')
    profile=db.get(MemberBrand,member_id)
    if profile:db.delete(profile)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.member_id==member_id)).all():
        db.delete(attendee)
    db.delete(member);db.commit();return {'ok':True}

def meeting_status(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    return lifecycle.status if lifecycle else 'agendada'

def meeting_attendees(m: Meeting, db: Session):
    ids=list(db.scalars(select(MeetingAttendee.member_id).where(
        MeetingAttendee.meeting_id==m.id
    )).all())
    if not ids:return [],[]
    members=db.scalars(select(Member).where(
        Member.organization_id==m.organization_id,
        Member.id.in_(ids)
    ).order_by(Member.name)).all()
    names=[member.name for member in members]
    existing={member.id for member in members}
    clean_ids=[member_id for member_id in ids if member_id in existing]
    return clean_ids,names

def meeting_conflicts(m: Meeting, db: Session, attendee_ids: list[int] | None=None):
    if meeting_status(m,db)=='cancelada':return []
    if attendee_ids is None:
        attendee_ids,_=meeting_attendees(m,db)
    if not attendee_ids:return []
    candidates=db.scalars(select(Meeting).where(
        Meeting.organization_id==m.organization_id,
        Meeting.id!=m.id,
        Meeting.meeting_date==m.meeting_date,
        Meeting.start_time < m.end_time,
        Meeting.end_time > m.start_time
    ).order_by(Meeting.start_time,Meeting.id)).all()
    conflicts=[]
    selected=set(attendee_ids)
    for other in candidates:
        if meeting_status(other,db)=='cancelada':continue
        other_ids,other_names=meeting_attendees(other,db)
        shared=selected.intersection(other_ids)
        if not shared:continue
        shared_names=[name for mid,name in zip(other_ids,other_names) if mid in shared]
        # zip não é confiável se a ordenação de ids/names divergir; consultar nomes compartilhados.
        shared_members=db.scalars(select(Member).where(
            Member.organization_id==m.organization_id,
            Member.id.in_(shared)
        ).order_by(Member.name)).all()
        conflicts.append(dict(
            meeting_id=other.id,title=other.title,start_time=other.start_time,end_time=other.end_time,
            attendee_ids=sorted(shared),attendee_names=[x.name for x in shared_members]
        ))
    return conflicts

def meeting_dict(m: Meeting, db: Session):
    lifecycle=db.get(MeetingClosure,m.id)
    attendee_ids,attendee_names=meeting_attendees(m,db)
    conflicts=meeting_conflicts(m,db,attendee_ids)
    return dict(id=m.id, title=m.title, client=m.client, project_id=m.project_id,
                meeting_date=m.meeting_date.isoformat(), start_time=m.start_time,
                end_time=m.end_time, location=m.location, meeting_url=m.meeting_url,
                notes=m.notes, created_at=stamp(m.created_at),
                status=lifecycle.status if lifecycle else 'agendada',
                closure_note=lifecycle.note if lifecycle else '',
                closure_at=stamp(lifecycle.updated_at) if lifecycle else None,
                closure_by=lifecycle.updated_by if lifecycle else '',
                attendee_ids=attendee_ids,attendee_names=attendee_names,
                has_conflict=bool(conflicts),conflicts=conflicts)

def validate_meeting(data: MeetingIn, db: Session, exclude_id: int | None = None):
    if not data.title.strip():
        raise HTTPException(422, 'Informe o título da reunião.')
    if data.end_time <= data.start_time:
        raise HTTPException(422, 'A reunião deve terminar depois do início.')
    org_id = organization_id(db)
    if data.project_id is not None and tenant_get(db, Project, data.project_id) is None:
        raise HTTPException(422, 'O projeto selecionado não existe.')
    if data.meeting_url and not data.meeting_url.startswith(('https://', 'http://')):
        raise HTTPException(422, 'O link deve começar com https:// ou http://.')
    attendee_ids=list(dict.fromkeys(data.attendee_ids))
    if not attendee_ids:
        raise HTTPException(422,'Selecione pelo menos um colaborador da Nexon Labs para a reunião.')
    valid_members=set(db.scalars(select(Member.id).where(
        Member.organization_id==org_id,
        Member.id.in_(attendee_ids)
    )).all())
    missing=[member_id for member_id in attendee_ids if member_id not in valid_members]
    if missing:
        raise HTTPException(422,'Um ou mais colaboradores selecionados não existem mais.')

    # Impede apenas duplicação literal. Sobreposição de agenda é permitida,
    # mas será sinalizada como conflito para tratativa.
    duplicate = select(Meeting).where(
        Meeting.organization_id == org_id,
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

def sync_meeting_attendees(db: Session, meeting_id: int, attendee_ids: list[int]):
    for row in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(row)
    for member_id in dict.fromkeys(attendee_ids):
        db.add(MeetingAttendee(meeting_id=meeting_id,member_id=member_id))

@app.post('/api/meetings', dependencies=[Depends(authorized)], status_code=201)
def add_meeting(data: MeetingIn, db: Session = Depends(session)):
    validate_meeting(data, db)
    values=data.model_dump(exclude={'attendee_ids'})
    meeting = Meeting(organization_id=organization_id(db), **values)
    db.add(meeting)
    db.flush()
    sync_meeting_attendees(db,meeting.id,data.attendee_ids)
    log(db, f'Reunião {meeting.title} agendada para {meeting.meeting_date.isoformat()}.')
    db.commit()
    db.refresh(meeting)
    return meeting_dict(meeting,db)

@app.put('/api/meetings/{meeting_id}', dependencies=[Depends(authorized)])
def edit_meeting(meeting_id: int, data: MeetingIn, db: Session = Depends(session)):
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    validate_meeting(data, db, exclude_id=meeting_id)
    for key, value in data.model_dump(exclude={'attendee_ids'}).items():
        setattr(meeting, key, value)
    sync_meeting_attendees(db,meeting_id,data.attendee_ids)
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
    meeting=tenant_get(db,Meeting,meeting_id)
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
    meeting = tenant_get(db, Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, 'Reunião não encontrada.')
    # Exclusão é distinta do cancelamento: preserve a reunião cancelada no histórico.
    lifecycle=db.get(MeetingClosure,meeting_id)
    if lifecycle:db.delete(lifecycle)
    for attendee in db.scalars(select(MeetingAttendee).where(MeetingAttendee.meeting_id==meeting_id)).all():
        db.delete(attendee)
    log(db, f'Reunião {meeting.title} excluída.')
    db.delete(meeting)
    db.commit()
    return {'ok': True}

@app.get('/api/export/projects.csv', dependencies=[Depends(authorized)])
def export_projects(db: Session = Depends(session)):
    buffer = io.StringIO(); out = csv.writer(buffer, delimiter=';')
    out.writerow(['ID', 'Projeto', 'Descrição', 'Cliente', 'Site do cliente', 'Responsável', 'Status', 'Progresso (%)', 'Início', 'Prazo'])
    for p in db.scalars(select(Project).where(
        Project.organization_id == organization_id(db)
    ).order_by(Project.id)):
        out.writerow([p.id, p.name, p.description, p.client, project_site(db,p.id), p.owner, effective_status(p), p.progress,
                      p.started_at.isoformat() if p.started_at else '', p.due_at.isoformat() if p.due_at else ''])
    buffer.seek(0)
    return StreamingResponse(iter(['\ufeff' + buffer.getvalue()]), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="atria_projetos.csv"'})

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
    app, Base, DB, engine, authorized, log, Member, member_dict, Organization
)

# A referência visual original fica persistida no PostgreSQL e só é instalada pelo administrador.
from approved_template import install_reference
ApprovedArtwork = install_reference(app, Base, DB, engine, authorized, admin_only)

# Ambiente comercial de demonstração, totalmente isolado da Nexon Labs.
from demo_seed import seed_demo_environment
seed_demo_environment(
    DB=DB,
    Account=Account,
    Member=Member,
    Project=Project,
    Task=Task,
    Activity=Activity,
    Meeting=Meeting,
    MeetingClosure=MeetingClosure,
    MeetingAttendee=MeetingAttendee,
    Quote=app.state.Quote,
    Company=app.state.Company,
    Ticket=app.state.Ticket,
    TicketEvent=app.state.TicketEvent,
    hash_password=hash_password,
    password_in_use=password_in_use,
)
