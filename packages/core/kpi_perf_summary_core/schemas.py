"""Pydantic DTOs shared by the API and MCP adapters."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EstType = Literal["historical", "qtd"]


class SectorOut(BaseModel):
    id: int
    name: str
    company_count: int = 0


class KpiOut(BaseModel):
    id: int
    name: str
    unit: str
    description: str | None = None


class CompanyOut(BaseModel):
    ticker: str
    name: str
    sector: str


class CompanyDetailOut(CompanyOut):
    kpis: list[KpiOut] = Field(default_factory=list)
    last_updated: datetime | None = None


class SeriesPoint(BaseModel):
    fiscal_period: str
    period_start: date
    period_end: date
    est_type: EstType
    value: float
    as_of: date | None = None


class KpiSeriesOut(BaseModel):
    ticker: str
    company_name: str
    kpi: str
    unit: str
    historical: list[SeriesPoint] = Field(default_factory=list)
    qtd: list[SeriesPoint] = Field(default_factory=list)
    last_updated: datetime | None = None
    qtd_as_of: date | None = None


class KpiSummary(BaseModel):
    """One row of the at-a-glance dashboard for a single KPI."""

    kpi: str
    unit: str
    latest_period: str | None = None
    latest_value: float | None = None
    qoq_pct: float | None = None  # vs prior quarter
    yoy_pct: float | None = None  # vs same quarter prior year
    qtd_value: float | None = None
    qtd_as_of: date | None = None


class CompanySummaryOut(BaseModel):
    ticker: str
    company_name: str
    sector: str
    last_updated: datetime | None = None
    kpis: list[KpiSummary] = Field(default_factory=list)


class SearchResultOut(BaseModel):
    sectors: list[SectorOut] = Field(default_factory=list)
    companies: list[CompanyOut] = Field(default_factory=list)
    kpis: list[KpiOut] = Field(default_factory=list)


class FavoriteIn(BaseModel):
    ticker: str
    kpi: str = Field(description="KPI id or name", examples=["Revenue"])


class FavoriteOut(BaseModel):
    """A bookmarked (company, KPI) pair, enriched with its latest at-a-glance metrics."""

    ticker: str
    company_name: str
    sector: str
    kpi: str
    kpi_id: int
    unit: str
    created_at: datetime
    metrics: KpiSummary | None = None


class PublishEstimateIn(BaseModel):
    period_start: date
    period_end: date
    fiscal_period: str = Field(examples=["2026Q1"])
    est_type: EstType
    value: float
    as_of: date | None = Field(
        default=None,
        description="Snapshot date for QTD estimates; omit for historical.",
    )


class PublishEstimateOut(BaseModel):
    id: int
    ticker: str
    kpi: str
    fiscal_period: str
    est_type: EstType
    value: float
    as_of: date | None = None
    published_at: datetime
