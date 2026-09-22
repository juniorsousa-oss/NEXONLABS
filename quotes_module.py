"""Orçamentos comerciais: cálculo interno, histórico e geração de PDF.

O PDF contém somente a proposta comercial. Horas, custo/hora e margens nunca
são enviados ao gerador de PDF e só aparecem na área autenticada do sistema.
"""
from __future__ import annotations

import base64
import io
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape as xml_escape

from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

CENT = Decimal("0.01")
def dec(value):
    return Decimal(str(value))
def money(value):
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)
def brl(value):
    return "R$ " + f"{money(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

class LineIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    quantity: int = Field(default=1, ge=1, le=1000)
    hours_per_unit: Decimal = Field(ge=0, le=100000, max_digits=10, decimal_places=2)
    @field_validator("title")
    @classmethod
    def title_clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Informe a descrição da etapa.")
        return value

class QuoteIn(BaseModel):
    client_name: str = Field(min_length=2, max_length=180)
    client_contact: str = Field(default="", max_length=140)
    client_email: str = Field(default="", max_length=180)
    project_name: str = Field(min_length=2, max_length=180)
    scope: str = Field(min_length=5, max_length=5000)
    delivery_days: int = Field(default=30, ge=1, le=3650)
    validity_days: int = Field(default=15, ge=1, le=365)
    payment_terms: str = Field(default="A combinar", max_length=1500)
    assumptions: str = Field(default="", max_length=3000)
    items: list[LineIn] = Field(min_length=1, max_length=40)
    hourly_cost: Decimal = Field(gt=0, le=100000, max_digits=10, decimal_places=2)
    reserve_pct: Decimal = Field(default=Decimal("15"), ge=0, le=100, max_digits=5, decimal_places=2)
    project_expenses: Decimal = Field(default=Decimal("0"), ge=0, le=10000000, max_digits=12, decimal_places=2)
    margin_pct: Decimal = Field(default=Decimal("25"), ge=0, le=95, max_digits=5, decimal_places=2)
    fees_pct: Decimal = Field(default=Decimal("8"), ge=0, le=95, max_digits=5, decimal_places=2)
    monthly_cost: Decimal = Field(default=Decimal("0"), ge=0, le=10000000, max_digits=12, decimal_places=2)
    monthly_description: str = Field(default="Hospedagem, suporte e manutenção", max_length=500)
    status: str = Field(default="rascunho")

    @field_validator("client_name", "client_contact", "client_email", "project_name", "scope", "payment_terms", "assumptions", "monthly_description")
    @classmethod
    def trim(cls, value):
        return value.strip()

    @field_validator("status")
    @classmethod
    def status_check(cls, value):
        if value not in ("rascunho", "enviado", "aprovado", "recusado"):
            raise ValueError("Status inválido.")
        return value

    @model_validator(mode="after")
    def valid(self):
        if self.margin_pct + self.fees_pct >= 100:
            raise ValueError("A soma da margem e das taxas deve ser inferior a 100%.")
        if not self.client_name or not self.project_name or not self.scope:
            raise ValueError("Preencha cliente, projeto e escopo.")
        if self.monthly_cost > 0 and not self.monthly_description:
            raise ValueError("Descreva o serviço mensal.")
        if not any(item.hours_per_unit > 0 for item in self.items):
            raise ValueError("Informe horas em pelo menos uma etapa.")
        return self

class CompanyIn(BaseModel):
    name: str = Field(default="Nexon Labs", min_length=2, max_length=160)
    subtitle: str = Field(default="Soluções digitais sob medida", max_length=180)
    document: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=180)
    phone: str = Field(default="", max_length=80)
    website: str = Field(default="", max_length=180)
    address: str = Field(default="", max_length=240)
    logo_data: str = Field(default="", max_length=450000)

    @field_validator("name", "subtitle", "document", "email", "phone", "website", "address")
    @classmethod
    def clean(cls, value):
        return value.strip()

    @field_validator("logo_data")
    @classmethod
    def logo_check(cls, value):
        if not value:
            return ""
        if not re.match(r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/=]+$", value):
            raise ValueError("Envie logo PNG ou JPEG.")
        try:
            data = base64.b64decode(value.split(",", 1)[1], validate=True)
            if len(data) > 300000:
                raise ValueError("A imagem deve ter no máximo 300 KB.")
            image = ImageReader(io.BytesIO(data))
            width, height = image.getSize()
            if width > 2500 or height > 2500 or not data:
                raise ValueError("Dimensões da imagem acima do limite.")
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("Imagem inválida, utilize PNG ou JPEG com até 300 KB.") from exc
        return value

def calculate(data: QuoteIn):
    hours = sum((dec(item.quantity) * item.hours_per_unit for item in data.items), Decimal(0))
    labor = hours * data.hourly_cost
    reserve = labor * data.reserve_pct / 100
    cost = labor + reserve + data.project_expenses
    rate = Decimal(1) - (data.margin_pct + data.fees_pct) / 100
    setup_price = money(cost / rate)
    monthly_price = money(data.monthly_cost / rate) if data.monthly_cost > 0 else Decimal("0.00")
    # Distribuição de preço entre etapas por horas estimadas; último item absorve os centavos.
    remaining = setup_price
    prices = []
    for item in data.items[:-1]:
        amount = money(setup_price * (item.hours_per_unit * item.quantity) / hours)
        prices.append(amount)
        remaining -= amount
    prices.append(money(remaining))
    return dict(
        total_hours=float(hours), labor_cost=float(money(labor)),
        contingency_cost=float(money(reserve)), total_cost=float(money(cost)),
        setup_price=float(setup_price), monthly_price=float(monthly_price),
        estimated_result=float(money(setup_price - cost - setup_price * data.fees_pct / 100)),
        line_prices=[float(p) for p in prices]
    )

def install_quotes(app, Base, DB, engine, authorized, log, Project):
    class Quote(Base):
        __tablename__ = "commercial_quotes"
        id: Mapped[int] = mapped_column(primary_key=True)
        payload: Mapped[str] = mapped_column(Text, nullable=False)
        created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
        project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    class Company(Base):
        __tablename__ = "commercial_company"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        payload: Mapped[str] = mapped_column(Text, nullable=False)

    Base.metadata.create_all(engine, tables=[Quote.__table__, Company.__table__])
    app.state.Quote = Quote

    def session():
        with DB() as db:
            yield db

    def company_dict(db):
        record = db.get(Company, 1)
        return CompanyIn.model_validate_json(record.payload).model_dump() if record else CompanyIn().model_dump()

    def quote_dict(record):
        data = QuoteIn.model_validate_json(record.payload)
        public = data.model_dump(mode="json")
        calc = calculate(data)
        valid_until = record.created_at.date() + timedelta(days=data.validity_days)
        status = data.status
        if status in ("rascunho", "enviado") and date.today() > valid_until:
            status = "vencido"
        return {
            **public, "id": record.id,
            "number": f"ORC-{record.created_at.year}-{record.id:05d}",
            "created_at": iso(record.created_at),
            "updated_at": iso(record.updated_at),
            "valid_until": valid_until.isoformat(),
            "effective_status": status,
            "project_id": record.project_id,
            "pricing": calc
        }

    @app.get("/api/quotes", dependencies=[Depends(authorized)])
    def list_quotes(db: Session = Depends(session)):
        return [quote_dict(q) for q in db.scalars(select(Quote).order_by(Quote.id.desc())).all()]

    @app.post("/api/quotes", dependencies=[Depends(authorized)], status_code=201)
    def add_quote(data: QuoteIn, db: Session = Depends(session)):
        record = Quote(payload=data.model_dump_json())
        db.add(record)
        log(db, f"Orçamento de {data.project_name} criado.")
        db.commit()
        db.refresh(record)
        return quote_dict(record)

    @app.put("/api/quotes/{quote_id}", dependencies=[Depends(authorized)])
    def update_quote(quote_id: int, data: QuoteIn, db: Session = Depends(session)):
        record = db.get(Quote, quote_id)
        if not record:
            raise HTTPException(404, "Orçamento não encontrado.")
        old = QuoteIn.model_validate_json(record.payload)
        if record.project_id is not None:
            raise HTTPException(409, "O orçamento já foi convertido em projeto. Crie uma nova proposta para alterações.")
        if old.status == "aprovado" and data.status != "aprovado":
            raise HTTPException(409, "Orçamento aprovado não pode voltar à negociação.")
        record.payload = data.model_dump_json()
        record.updated_at = datetime.now(timezone.utc)
        log(db, f"Orçamento {quote_id} atualizado.")
        db.commit()
        db.refresh(record)
        return quote_dict(record)

    @app.delete("/api/quotes/{quote_id}", dependencies=[Depends(authorized)])
    def delete_quote(quote_id: int, db: Session = Depends(session)):
        record = db.get(Quote, quote_id)
        if not record:
            raise HTTPException(404, "Orçamento não encontrado.")
        if record.project_id is not None or QuoteIn.model_validate_json(record.payload).status == "aprovado":
            raise HTTPException(409, "Orçamentos aprovados ou vinculados a projetos não podem ser excluídos.")
        db.delete(record)
        log(db, f"Orçamento {quote_id} excluído.")
        db.commit()
        return {"ok": True}

    @app.get("/api/quotes/company", dependencies=[Depends(authorized)])
    def get_company(db: Session = Depends(session)):
        return company_dict(db)

    @app.put("/api/quotes/company", dependencies=[Depends(authorized)])
    def put_company(data: CompanyIn, db: Session = Depends(session)):
        record = db.get(Company, 1)
        if record:
            record.payload = data.model_dump_json()
        else:
            db.add(Company(id=1, payload=data.model_dump_json()))
        db.commit()
        return data.model_dump()

    @app.post("/api/quotes/{quote_id}/project", dependencies=[Depends(authorized)], status_code=201)
    def convert_to_project(quote_id: int, db: Session = Depends(session)):
        record = db.get(Quote, quote_id)
        if record is None:
            raise HTTPException(404, "Orçamento não encontrado.")
        if record.project_id:
            raise HTTPException(409, "Orçamento já convertido em projeto.")
        data = QuoteIn.model_validate_json(record.payload)
        if data.status != "aprovado":
            raise HTTPException(409, "Aprove o orçamento antes de criar o projeto.")
        project = Project(name=data.project_name[:160], description=data.scope[:2000], client=data.client_name[:160],
                          status="planejamento", progress=0,
                          started_at=date.today(), due_at=date.today() + timedelta(days=data.delivery_days))
        db.add(project)
        db.flush()
        record.project_id = project.id
        log(db, f"Projeto {project.name} criado a partir do orçamento {quote_id}.")
        db.commit()
        return {"id": project.id, "name": project.name}

    @app.get("/api/quotes/{quote_id}/pdf", dependencies=[Depends(authorized)])
    def quote_pdf(quote_id: int, db: Session = Depends(session)):
        record = db.get(Quote, quote_id)
        if record is None:
            raise HTTPException(404, "Orçamento não encontrado.")
        data = QuoteIn.model_validate_json(record.payload)
        calc = calculate(data)
        company = CompanyIn.model_validate(company_dict(db))
        doc_info = quote_dict(record)
        pdf_bytes = build_pdf(data, calc, company, doc_info)
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="orcamento-{doc_info["number"]}.pdf"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff"
            }
        )

def build_pdf(data: QuoteIn, calc: dict, company: CompanyIn, info: dict):
    """PDF de proposta comercial: dados financeiros internos não entram no documento."""
    navy = colors.HexColor("#0B2D4A")
    teal = colors.HexColor("#14B8A6")
    gray = colors.HexColor("#63748B")
    paper = colors.HexColor("#F2F7FA")
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=43, leftMargin=43,
                            topMargin=50, bottomMargin=57, title=f"Proposta {info['number']}")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BrandQ", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=navy))
    styles.add(ParagraphStyle(name="TitleQ", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=navy, spaceBefore=14, spaceAfter=9))
    styles.add(ParagraphStyle(name="BodyQ", fontName="Helvetica", fontSize=9.4, leading=14.2, textColor=navy, spaceAfter=5))
    styles.add(ParagraphStyle(name="SmallQ", fontName="Helvetica", fontSize=8.2, leading=11, textColor=gray))
    styles.add(ParagraphStyle(name="HeadCellQ", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white))
    styles.add(ParagraphStyle(name="CellQ", fontName="Helvetica", fontSize=8.5, leading=12, textColor=navy))
    styles.add(ParagraphStyle(name="RightQ", parent=styles["CellQ"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="TotalQ", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=navy, alignment=TA_RIGHT))
    p = lambda value, sty="BodyQ": Paragraph(xml_escape(str(value)).replace("\n", "<br/>"), styles[sty])
    story = []
    header = []
    if company.logo_data:
        try:
            raw = base64.b64decode(company.logo_data.split(",", 1)[1])
            image = ImageReader(io.BytesIO(raw))
            w,h = image.getSize()
            factor = min(105/w, 51/h)
            from reportlab.platypus import Image
            logo = Image(io.BytesIO(raw), width=w*factor, height=h*factor, hAlign="LEFT")
            header.append(logo)
        except Exception:
            pass
    name = [p(company.name, "BrandQ"), p(company.subtitle, "SmallQ")]
    header.append(name)
    headtable = Table([header], colWidths=([116, 390] if len(header)==2 else [506]), hAlign="LEFT")
    headtable.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),
                                    ("RIGHTPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),10)]))
    story.append(headtable)
    story.append(Table([[""]], colWidths=[506], rowHeights=[3], style=TableStyle([("BACKGROUND",(0,0),(-1,-1),teal)])))
    story.append(Spacer(1, 18))
    story.append(p("PROPOSTA COMERCIAL", "TitleQ"))
    date_created = date.fromisoformat(info["created_at"][:10]).strftime("%d/%m/%Y")
    validity = date.fromisoformat(info["valid_until"]).strftime("%d/%m/%Y")
    meta = [
        [p("PROPOSTA", "SmallQ"), p(info["number"]), p("EMISSÃO", "SmallQ"), p(date_created)],
        [p("CLIENTE", "SmallQ"), p(data.client_name), p("VALIDADE", "SmallQ"), p(validity)]
    ]
    meta_table = Table(meta, colWidths=[64, 217, 65, 160], hAlign="LEFT")
    meta_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),paper),("VALIGN",(0,0),(-1,-1),"TOP"),
                                  ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    story.append(meta_table)
    if data.client_contact or data.client_email:
        story.append(Spacer(1, 7))
        story.append(p("Contato: " + " | ".join(filter(None,[data.client_contact, data.client_email])), "SmallQ"))
    story.append(p(data.project_name, "TitleQ"))
    story.append(p(data.scope))
    story.append(p("SERVIÇOS E ENTREGAS", "TitleQ"))
    rows = [[p("ETAPA / ENTREGA", "HeadCellQ"),p("QTD.", "HeadCellQ"),p("VALOR TOTAL", "HeadCellQ")]]
    for item, amount in zip(data.items, calc["line_prices"]):
        rows.append([p(item.title,"CellQ"),p(item.quantity,"CellQ"),p(brl(amount),"RightQ")])
    rows.append([p("INVESTIMENTO EM DESENVOLVIMENTO", "CellQ"),"",p(brl(calc["setup_price"]),"TotalQ")])
    table = Table(rows, colWidths=[317,52,137], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),navy),("BACKGROUND",(0,-1),(-1,-1),paper),
        ("LINEBELOW",(0,1),(-1,-2),.3,colors.HexColor("#DCE6EE")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ("SPAN",(0,-1),(1,-1))
    ]))
    story.append(table)
    if calc["monthly_price"] > 0:
        story.append(p("SERVIÇOS RECORRENTES", "TitleQ"))
        recurring = Table([
            [p(data.monthly_description, "CellQ"),p(brl(calc["monthly_price"]) + " / mês","TotalQ")]
        ], colWidths=[340,166])
        recurring.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),paper),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                                       ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12)]))
        story.append(recurring)
        story.append(Spacer(1,5))
        story.append(p("Mensalidade independente do investimento inicial. Início da cobrança e serviços incluídos conforme as condições acordadas.", "SmallQ"))
    story.append(p("PRAZOS E CONDIÇÕES", "TitleQ"))
    story.append(p(f"Prazo estimado de entrega: {data.delivery_days} dia(s) após aprovação e recebimento dos insumos necessários."))
    story.append(p("Condições de pagamento: " + (data.payment_terms or "A combinar.")))
    if data.assumptions:
        story.append(p("PREMISSAS E LIMITES DO ESCOPO", "TitleQ"))
        story.append(p(data.assumptions))
    story.append(Spacer(1,20))
    story.append(p("ACEITE DA PROPOSTA", "TitleQ"))
    story.append(p("Declaro estar de acordo com os serviços, valores e condições desta proposta."))
    story.append(Spacer(1,22))
    sign = Table([
        [p("_________________________________", "SmallQ"),p("_________________________________", "SmallQ")],
        [p("Responsável pelo cliente", "SmallQ"),p("Data", "SmallQ")]
    ], colWidths=[330,176])
    story.append(sign)
    contact = "  |  ".join(filter(None,[company.document,company.email,company.phone,company.website,company.address]))
    def page_footer(canvas, document):
        canvas.saveState()
        w,h = A4
        canvas.setStrokeColor(colors.HexColor("#DCE6EE"))
        canvas.line(43,40,w-43,40)
        canvas.setFont("Helvetica",7)
        canvas.setFillColor(gray)
        # Não imprimir dados internos, apenas contato institucional e número da página.
        footer = contact[:112]
        canvas.drawString(43,28,footer or company.name[:80])
        canvas.drawRightString(w-43,28,f"Página {document.page}")
        canvas.restoreState()
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return buffer.getvalue()
