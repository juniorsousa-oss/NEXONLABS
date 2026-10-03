"""Dados de demonstração isolados do ATRIA.

O seed é idempotente: cria a conta Demo somente quando existe
ATRIA_DEMO_PASSWORD e popula dados fictícios apenas quando a organização
ATRIA Demo ainda não possui projetos.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from tenant_module import ATRIA_DEMO_ORG_ID


def seed_demo_environment(
    DB,
    Account,
    Member,
    Project,
    Task,
    Activity,
    Meeting,
    MeetingClosure,
    MeetingAttendee,
    Quote,
    Company,
    Ticket,
    TicketEvent,
    hash_password,
    password_in_use,
):
    password = os.getenv("ATRIA_DEMO_PASSWORD", "").strip()

    with DB() as db:
        demo_account = db.scalar(
            select(Account).where(Account.organization_id == ATRIA_DEMO_ORG_ID).limit(1)
        )
        if password and demo_account is None:
            if len(password) < 8:
                raise RuntimeError("ATRIA_DEMO_PASSWORD deve ter pelo menos 8 caracteres.")
            if password_in_use(db, Account, password):
                raise RuntimeError("ATRIA_DEMO_PASSWORD deve ser diferente das senhas de outros usuários.")
            db.add(Account(
                organization_id=ATRIA_DEMO_ORG_ID,
                name="Demonstração ATRIA",
                password_hash=hash_password(password),
                role="admin",
                active=True,
            ))
            db.commit()

        # Não sobrescrever alterações feitas durante demonstrações.
        existing_projects = db.scalar(
            select(func.count()).select_from(Project).where(
                Project.organization_id == ATRIA_DEMO_ORG_ID
            )
        )
        if existing_projects:
            return

        today = date.today()

        members = [
            Member(organization_id=ATRIA_DEMO_ORG_ID, name="Marina Costa", role="Gerente de Projetos", email="marina@empresa-demo.com"),
            Member(organization_id=ATRIA_DEMO_ORG_ID, name="Lucas Almeida", role="Analista de Operações", email="lucas@empresa-demo.com"),
            Member(organization_id=ATRIA_DEMO_ORG_ID, name="Camila Rocha", role="Customer Success", email="camila@empresa-demo.com"),
            Member(organization_id=ATRIA_DEMO_ORG_ID, name="Rafael Nunes", role="Desenvolvedor", email="rafael@empresa-demo.com"),
        ]
        db.add_all(members)
        db.flush()
        by_name = {member.name: member for member in members}

        projects = [
            Project(
                organization_id=ATRIA_DEMO_ORG_ID,
                name="Portal de Operações",
                description="Centralização de rotinas operacionais e indicadores em um único ambiente.",
                client="Aurora Engenharia",
                owner="Marina Costa",
                status="em_andamento",
                progress=72,
                started_at=today - timedelta(days=20),
                due_at=today + timedelta(days=12),
            ),
            Project(
                organization_id=ATRIA_DEMO_ORG_ID,
                name="Automação de Compras",
                description="Fluxo digital para solicitações, aprovações e acompanhamento de compras.",
                client="Vitta Foods",
                owner="Lucas Almeida",
                status="em_andamento",
                progress=48,
                started_at=today - timedelta(days=11),
                due_at=today + timedelta(days=25),
            ),
            Project(
                organization_id=ATRIA_DEMO_ORG_ID,
                name="Dashboard Executivo",
                description="Visão consolidada de metas, entregas, produtividade e resultados.",
                client="Atlas Facilities",
                owner="Camila Rocha",
                status="planejamento",
                progress=20,
                started_at=today - timedelta(days=3),
                due_at=today + timedelta(days=40),
            ),
            Project(
                organization_id=ATRIA_DEMO_ORG_ID,
                name="Integração de Atendimento",
                description="Integração do atendimento com histórico de chamados e SLA.",
                client="Orbe Logística",
                owner="Rafael Nunes",
                status="em_andamento",
                progress=86,
                started_at=today - timedelta(days=32),
                due_at=today + timedelta(days=7),
            ),
        ]
        db.add_all(projects)
        db.flush()
        p = {project.name: project for project in projects}

        tasks = [
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Portal de Operações"].id, title="Validar indicadores do dashboard", assignee="Marina Costa", due_at=today + timedelta(days=2), completed=False, hours=3.5),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Portal de Operações"].id, title="Revisar fluxo de aprovações", assignee="Lucas Almeida", due_at=today + timedelta(days=4), completed=True, hours=4.0),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Automação de Compras"].id, title="Mapear regras de alçada", assignee="Lucas Almeida", due_at=today + timedelta(days=6), completed=False, hours=2.0),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Automação de Compras"].id, title="Homologar fornecedores piloto", assignee="Camila Rocha", due_at=today + timedelta(days=10), completed=False, hours=1.5),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Dashboard Executivo"].id, title="Definir KPIs da diretoria", assignee="Camila Rocha", due_at=today + timedelta(days=8), completed=False, hours=2.5),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Integração de Atendimento"].id, title="Teste final do histórico de chamados", assignee="Rafael Nunes", due_at=today + timedelta(days=1), completed=False, hours=5.0),
            Task(organization_id=ATRIA_DEMO_ORG_ID, project_id=p["Integração de Atendimento"].id, title="Treinamento da equipe de suporte", assignee="Marina Costa", due_at=today + timedelta(days=5), completed=False, hours=3.0),
        ]
        db.add_all(tasks)

        meetings = [
            Meeting(
                organization_id=ATRIA_DEMO_ORG_ID,
                title="Kickoff executivo",
                client="Atlas Facilities",
                project_id=p["Dashboard Executivo"].id,
                meeting_date=today + timedelta(days=2),
                start_time="09:00",
                end_time="10:00",
                location="Microsoft Teams",
                meeting_url="https://teams.microsoft.com/",
                notes="Apresentação de escopo, indicadores e próximos marcos.",
            ),
            Meeting(
                organization_id=ATRIA_DEMO_ORG_ID,
                title="Homologação do fluxo",
                client="Aurora Engenharia",
                project_id=p["Portal de Operações"].id,
                meeting_date=today + timedelta(days=5),
                start_time="14:30",
                end_time="15:30",
                location="Sala de projetos",
                notes="Validação do fluxo antes da liberação para usuários-chave.",
            ),
            Meeting(
                organization_id=ATRIA_DEMO_ORG_ID,
                title="Revisão de atendimento",
                client="Orbe Logística",
                project_id=p["Integração de Atendimento"].id,
                meeting_date=today - timedelta(days=1),
                start_time="16:00",
                end_time="17:00",
                location="Google Meet",
                meeting_url="https://meet.google.com/",
                notes="Revisão de SLA e indicadores do piloto.",
            ),
        ]
        db.add_all(meetings)
        db.flush()

        db.add_all([
            MeetingAttendee(meeting_id=meetings[0].id, member_id=by_name["Marina Costa"].id),
            MeetingAttendee(meeting_id=meetings[0].id, member_id=by_name["Camila Rocha"].id),
            MeetingAttendee(meeting_id=meetings[1].id, member_id=by_name["Marina Costa"].id),
            MeetingAttendee(meeting_id=meetings[1].id, member_id=by_name["Lucas Almeida"].id),
            MeetingAttendee(meeting_id=meetings[2].id, member_id=by_name["Rafael Nunes"].id),
            MeetingAttendee(meeting_id=meetings[2].id, member_id=by_name["Camila Rocha"].id),
            MeetingClosure(
                meeting_id=meetings[2].id,
                status="realizada",
                note="Piloto aprovado e próximos ajustes priorizados.",
                updated_at=datetime.now(timezone.utc),
                updated_by="Demonstração ATRIA",
            ),
        ])

        from quotes_module import QuoteIn
        quote_payloads = [
            QuoteIn.model_validate({
                "client_name": "Aurora Engenharia",
                "client_contact": "Fernanda Lima",
                "client_email": "fernanda@aurora-demo.com",
                "project_name": "Expansão do Portal de Operações",
                "scope": "Ampliação do portal com novos indicadores, automações e painel gerencial.",
                "delivery_days": 30,
                "validity_days": 15,
                "payment_terms": "40% na aprovação e 60% na entrega.",
                "items": [
                    {"title": "Mapeamento e UX", "quantity": 1, "hours_per_unit": 12},
                    {"title": "Desenvolvimento e integrações", "quantity": 1, "hours_per_unit": 36},
                    {"title": "Homologação e treinamento", "quantity": 1, "hours_per_unit": 10},
                ],
                "hourly_cost": "75.00",
                "reserve_pct": "12",
                "margin_pct": "28",
                "fees_pct": "7",
                "status": "enviado",
            }),
            QuoteIn.model_validate({
                "client_name": "Nova Horizonte Indústria",
                "client_contact": "Eduardo Ramos",
                "project_name": "Gestão de manutenção",
                "scope": "Aplicação para abertura, priorização e acompanhamento de ordens de manutenção.",
                "delivery_days": 45,
                "validity_days": 20,
                "payment_terms": "A combinar",
                "items": [
                    {"title": "Descoberta e arquitetura", "quantity": 1, "hours_per_unit": 16},
                    {"title": "Implementação", "quantity": 1, "hours_per_unit": 52},
                ],
                "hourly_cost": "78.00",
                "reserve_pct": "15",
                "margin_pct": "30",
                "fees_pct": "7",
                "status": "rascunho",
            }),
        ]
        db.add_all([
            Quote(organization_id=ATRIA_DEMO_ORG_ID, payload=item.model_dump_json())
            for item in quote_payloads
        ])

        from quotes_module import CompanyIn
        company = CompanyIn(
            name="ATRIA Demo",
            subtitle="Ambiente de demonstração · Powered by Nexon Labs",
            website="https://atria.nexonlabs.com.br",
        )
        db.add(Company(organization_id=ATRIA_DEMO_ORG_ID, payload=company.model_dump_json()))

        from tickets_module import TicketInput
        ticket_specs = [
            (TicketInput(
                title="Ajustar permissão de aprovador",
                client="Aurora Engenharia",
                requester="Fernanda Lima",
                description="Usuário responsável precisa aprovar solicitações acima do limite configurado.",
                type="solicitacao",
                priority="normal",
                status="aberto",
                assignee="Lucas Almeida",
                project_id=p["Portal de Operações"].id,
                due_at=today + timedelta(days=3),
            ), "abertura", "Chamado registrado para ajuste de permissão."),
            (TicketInput(
                title="Indicador não atualizou após importação",
                client="Vitta Foods",
                requester="Paulo Mendes",
                description="Após a nova importação, o card de compras pendentes manteve o valor anterior.",
                type="erro",
                priority="alta",
                status="em_atendimento",
                assignee="Rafael Nunes",
                project_id=p["Automação de Compras"].id,
                due_at=today + timedelta(days=1),
            ), "situacao", "Chamado em análise técnica pela equipe."),
            (TicketInput(
                title="Adicionar filtro por período",
                client="Atlas Facilities",
                requester="Juliana Prado",
                description="Solicitação de filtro mensal e trimestral no dashboard executivo.",
                type="melhoria",
                priority="baixa",
                status="aguardando_cliente",
                assignee="Camila Rocha",
                project_id=p["Dashboard Executivo"].id,
                due_at=today + timedelta(days=8),
            ), "situacao", "Aguardando validação do cliente sobre os períodos desejados."),
        ]
        for payload, kind, event_message in ticket_specs:
            ticket = Ticket(
                organization_id=ATRIA_DEMO_ORG_ID,
                payload=payload.model_dump_json(),
                project_id=payload.project_id,
            )
            db.add(ticket)
            db.flush()
            db.add(TicketEvent(ticket_id=ticket.id, kind=kind, message=event_message))

        activities = [
            "Projeto Portal de Operações atualizado para 72% de progresso.",
            "Reunião de revisão com Orbe Logística concluída.",
            "Novo orçamento preparado para Nova Horizonte Indústria.",
            "Chamado prioritário de Vitta Foods entrou em atendimento.",
            "Dashboard Executivo iniciou etapa de definição de KPIs.",
        ]
        db.add_all([
            Activity(organization_id=ATRIA_DEMO_ORG_ID, message=message)
            for message in activities
        ])

        db.commit()
