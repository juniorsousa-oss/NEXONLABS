"""Fundação multiempresa do ATRIA.

Esta primeira etapa é deliberadamente conservadora:
- cria organizações com IDs estáveis;
- migra registros existentes para a organização Nexon Labs;
- adiciona organization_id sem apagar ou reescrever dados históricos;
- ainda não ativa filtros de isolamento nos endpoints (etapa seguinte).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, inspect, text, select
from sqlalchemy.orm import Mapped, mapped_column

NEXON_LABS_ORG_ID = 1
ATRIA_DEMO_ORG_ID = 2


def setup_organizations(Base, engine, DB):
    class Organization(Base):
        __tablename__ = "organizations"

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(160), nullable=False)
        slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
        logo_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
        logo_dark_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
        favicon_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
        primary_color: Mapped[str] = mapped_column(String(16), default="#0B2D4A", nullable=False)
        secondary_color: Mapped[str] = mapped_column(String(16), default="#14B8A6", nullable=False)
        use_custom_brand: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
        active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
        )

    Base.metadata.create_all(engine, tables=[Organization.__table__])

    with DB() as db:
        nexon = db.get(Organization, NEXON_LABS_ORG_ID)
        if nexon is None:
            db.add(Organization(
                id=NEXON_LABS_ORG_ID,
                name="Nexon Labs",
                slug="nexon-labs",
                primary_color="#0B2D4A",
                secondary_color="#14B8A6",
                use_custom_brand=True,
            ))
        demo = db.get(Organization, ATRIA_DEMO_ORG_ID)
        if demo is None:
            db.add(Organization(
                id=ATRIA_DEMO_ORG_ID,
                name="ATRIA Demo",
                slug="atria-demo",
                primary_color="#071A33",
                secondary_color="#00E6C6",
                use_custom_brand=False,
            ))
        db.commit()

    # IDs 1 e 2 são reservados para manter migrações determinísticas.
    # Em PostgreSQL, sincronize a sequence para que o próximo cliente comece em 3.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text(
                "SELECT setval(pg_get_serial_sequence('organizations','id'), "
                "(SELECT MAX(id) FROM organizations), true)"
            ))

    return Organization


def ensure_organization_columns(engine, table_names, default_org_id=NEXON_LABS_ORG_ID):
    """Adiciona organization_id de forma idempotente em tabelas já existentes.

    Em instalações novas, o ORM já cria a coluna. Em bancos históricos, esta função
    adiciona a coluna e atribui todos os registros atuais à Nexon Labs.
    """
    inspector = inspect(engine)
    available = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name in table_names:
            if table_name not in available:
                continue
            # Nomes vêm somente de constantes internas deste módulo/chamador.
            columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
            if "organization_id" not in columns:
                conn.execute(text(
                    f'ALTER TABLE "{table_name}" ADD COLUMN organization_id INTEGER'
                ))
            conn.execute(text(
                f'UPDATE "{table_name}" SET organization_id = :org '
                'WHERE organization_id IS NULL'
            ), {"org": default_org_id})
            index_name = f"ix_{table_name}_organization_id"
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS "{index_name}" '
                f'ON "{table_name}" (organization_id)'
            ))


def organization_public(organization):
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "logo_url": organization.logo_url,
        "logo_dark_url": organization.logo_dark_url,
        "favicon_url": organization.favicon_url,
        "primary_color": organization.primary_color,
        "secondary_color": organization.secondary_color,
        "use_custom_brand": organization.use_custom_brand,
        "active": organization.active,
    }
