"""SQLAlchemy ORM models. See ARCHITECTURE.md §4 for the schema rationale."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EstimateType(str, enum.Enum):
    historical = "historical"
    qtd = "qtd"


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Kpi(Base):
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class Estimate(Base):
    """Append-only fact ledger. Publishing inserts; the current value is the
    latest publish per logical key (see ``current_estimates`` view in init_db)."""

    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String, nullable=False)
    est_type: Mapped[EstimateType] = mapped_column(
        Enum(EstimateType, name="estimate_type"), nullable=False
    )
    value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String, default="seed")

    company: Mapped[Company] = relationship()
    kpi: Mapped[Kpi] = relationship()

    __table_args__ = (
        Index("ix_est_series", "company_id", "kpi_id", "period_start"),
        Index(
            "ix_est_qtd",
            "company_id",
            "kpi_id",
            "as_of",
            postgresql_where=(est_type == EstimateType.qtd),
        ),
    )
