"""Chamados internos de atendimento: histórico imutável de eventos e acompanhamento.
Acesso protegido pela sessão da aplicação. Não oferece portal externo ao cliente.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

TicketType = Literal["suporte", "erro", "melhoria", "solicitacao"]
TicketStatus = Literal["aberto", "em_atendimento", "aguardando_cliente", "resolvido", "fechado"]
TicketPriority = Literal["baixa", "normal", "alta", "critica"]


class TicketInput(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    client: str = Field(min_length=2, max_length=160)
    requester: str = Field(default="", max_length=140)
    contact: str = Field(default="", max_length=180)
    description: str = Field(min_length=5, max_length=6000)
    type: TicketType = "suporte"
    priority: TicketPriority = "normal"
    status: TicketStatus = "aberto"
    assignee: str = Field(default="", max_length=140)
    project_id: int | None = Field(default=None, gt=0)
    due_at: date | None = None

    @field_validator("title", "client", "requester", "contact", "description", "assignee")
    @classmethod
    def clean(cls, value: str):
        return value.strip()

    @model_validator(mode="after")
    def required_trimmed(self):
        if not self.title or not self.client or not self.description:
            raise ValueError("Informe título, cliente e descrição.")
        return self


class TicketTransitionIn(BaseModel):
    status: Literal["aberto", "em_atendimento", "aguardando_cliente", "resolvido", "fechado"]
    message: str = Field(min_length=5, max_length=4000)

    @field_validator("message")
    @classmethod
    def tidy_reason(cls, value: str):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Descreva o atendimento, a solução ou o motivo em pelo menos 5 caracteres.")
        return value


class TicketCommentInput(BaseModel):
    message: str = Field(min_length=2, max_length=4000)

    @field_validator("message")
    @classmethod
    def clean(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Informe o texto do registro.")
        return value


def install_tickets(app, Base, DB, engine, authorized, log, Project):
    class Ticket(Base):
        __tablename__ = "service_tickets"
        id: Mapped[int] = mapped_column(primary_key=True)
        payload: Mapped[str] = mapped_column(Text, nullable=False)
        project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
        closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    class TicketEvent(Base):
        __tablename__ = "service_ticket_events"
        id: Mapped[int] = mapped_column(primary_key=True)
        ticket_id: Mapped[int] = mapped_column(ForeignKey("service_tickets.id", ondelete="CASCADE"), nullable=False)
        kind: Mapped[str] = mapped_column(String(24), nullable=False)
        message: Mapped[str] = mapped_column(Text, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    Base.metadata.create_all(engine, tables=[Ticket.__table__, TicketEvent.__table__])

    def session():
        with DB() as db:
            yield db

    def stamp(value):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def verify_project(db, project_id):
        if project_id is not None and db.get(Project, project_id) is None:
            raise HTTPException(422, "Projeto informado não existe.")

    def to_dict(record, db):
        data = TicketInput.model_validate_json(record.payload)
        events = db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == record.id).order_by(TicketEvent.id)).all()
        public = data.model_dump(mode="json")
        # O vínculo deve refletir a tabela de projetos, não uma cópia antiga no payload.
        public["project_id"] = record.project_id if record.project_id is not None and db.get(Project, record.project_id) is not None else None
        return {
            **public,
            "id": record.id,
            "number": f"CH-{record.created_at.year}-{record.id:05d}",
            "created_at": stamp(record.created_at),
            "updated_at": stamp(record.updated_at),
            "closed_at": stamp(record.closed_at),
            "events": [
                dict(id=event.id, kind=event.kind, message=event.message, created_at=stamp(event.created_at))
                for event in events
            ],
        }

    @app.get("/api/tickets", dependencies=[Depends(authorized)])
    def list_tickets(db: Session = Depends(session)):
        records = db.scalars(select(Ticket).order_by(Ticket.id.desc())).all()
        return [to_dict(record, db) for record in records]

    @app.post("/api/tickets", dependencies=[Depends(authorized)], status_code=201)
    def add_ticket(data: TicketInput, db: Session = Depends(session)):
        if data.status != "aberto":
            raise HTTPException(422, "Novos chamados começam abertos; atualize o andamento depois do cadastro.")
        verify_project(db, data.project_id)
        record = Ticket(payload=data.model_dump_json(), project_id=data.project_id)
        db.add(record)
        db.flush()
        db.add(TicketEvent(ticket_id=record.id, kind="abertura", message="Chamado registrado."))
        log(db, f"Chamado {record.id} aberto: {data.title}.")
        db.commit()
        db.refresh(record)
        return to_dict(record, db)

    @app.put("/api/tickets/{ticket_id}", dependencies=[Depends(authorized)])
    def update_ticket(ticket_id: int, data: TicketInput, db: Session = Depends(session)):
        record = db.get(Ticket, ticket_id)
        if record is None:
            raise HTTPException(404, "Chamado não encontrado.")
        verify_project(db, data.project_id)
        previous = TicketInput.model_validate_json(record.payload)
        if data.status != previous.status and (
            data.status in ("resolvido", "fechado") or previous.status in ("resolvido", "fechado")
        ):
            raise HTTPException(422, "Para concluir, fechar ou reabrir um chamado, utilize a ação específica e registre o motivo.")
        changed = []
        labels = {
            "status": "Situação",
            "priority": "Prioridade",
            "assignee": "Responsável",
            "due_at": "Prazo",
            "project_id": "Projeto",
            "title": "Título",
            "client": "Cliente",
            "requester": "Solicitante",
            "contact": "Contato",
            "description": "Descrição",
            "type": "Categoria",
        }
        for key, label in labels.items():
            before, after = getattr(previous, key), getattr(data, key)
            if before != after:
                changed.append(f"{label}: {before or '—'} → {after or '—'}")
        if not changed:
            return to_dict(record, db)
        now = datetime.now(timezone.utc)
        record.payload = data.model_dump_json()
        record.project_id = data.project_id
        record.updated_at = now
        if data.status == "fechado" and previous.status != "fechado":
            record.closed_at = now
        elif previous.status == "fechado" and data.status != "fechado":
            record.closed_at = None
        # Histórico registra mudanças sem armazenar descrições completas nos eventos.
        audit = []
        for entry in changed:
            if entry.startswith("Descrição:"):
                audit.append("Descrição atualizada.")
            elif entry.startswith("Contato:"):
                audit.append("Contato atualizado.")
            else:
                audit.append(entry[:360])
        db.add(TicketEvent(ticket_id=record.id, kind="alteracao", message="; ".join(audit)[:1800]))
        log(db, f"Chamado {record.id} atualizado.")
        db.commit()
        db.refresh(record)
        return to_dict(record, db)

    @app.post("/api/tickets/{ticket_id}/transition", dependencies=[Depends(authorized)])
    def transition_ticket(ticket_id: int, data: TicketTransitionIn, request: Request,
                          db: Session = Depends(session)):
        record = db.get(Ticket, ticket_id)
        if record is None:
            raise HTTPException(404, "Chamado não encontrado.")
        previous = TicketInput.model_validate_json(record.payload)
        before, after = previous.status, data.status
        if before == after:
            raise HTTPException(409, "O chamado já está nessa situação.")
        # Um chamado fechado ou resolvido só volta a operar mediante reabertura registrada.
        if before in ("fechado", "resolvido") and after not in ("aberto", "em_atendimento", "fechado"):
            raise HTTPException(409, "Reabra o chamado antes de atualizar o andamento.")
        if before == "fechado" and after == "fechado":
            raise HTTPException(409, "O chamado já está fechado.")
        # Um chamado resolvido pode ser fechado ou reaberto; um fechado pode apenas ser reaberto.
        if before == "fechado" and after not in ("aberto", "em_atendimento"):
            raise HTTPException(409, "Reabra o chamado antes de alterar a situação.")
        if before == "resolvido" and after == "fechado":
            pass
        elif before == "resolvido" and after not in ("aberto", "em_atendimento"):
            raise HTTPException(409, "Reabra o chamado ou finalize o fechamento.")
        previous.status = after
        record.payload = previous.model_dump_json()
        record.updated_at = datetime.now(timezone.utc)
        record.closed_at = record.updated_at if after == "fechado" else None
        labels = {"aberto": "Aberto", "em_atendimento": "Em atendimento",
                  "aguardando_cliente": "Aguardando cliente", "resolvido": "Resolvido",
                  "fechado": "Fechado"}
        current = authorized(request)
        message = f"{labels[before]} → {labels[after]} por {current['name']}. {data.message}"
        db.add(TicketEvent(ticket_id=record.id, kind="situacao", message=message))
        log(db, f"Chamado {record.id}: {labels[before]} → {labels[after]} por {current['name']}.")
        db.commit()
        db.refresh(record)
        return to_dict(record, db)

    @app.post("/api/tickets/{ticket_id}/comments", dependencies=[Depends(authorized)], status_code=201)
    def add_ticket_comment(ticket_id: int, data: TicketCommentInput, db: Session = Depends(session)):
        record = db.get(Ticket, ticket_id)
        if record is None:
            raise HTTPException(404, "Chamado não encontrado.")
        now = datetime.now(timezone.utc)
        db.add(TicketEvent(ticket_id=record.id, kind="comentario", message=data.message))
        record.updated_at = now
        log(db, f"Novo registro no chamado {ticket_id}.")
        db.commit()
        db.refresh(record)
        return to_dict(record, db)
