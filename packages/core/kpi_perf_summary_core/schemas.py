"""Pydantic DTOs shared by the API and MCP adapters."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

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
    description: Optional[str] = None


class CompanyOut(BaseModel):
    ticker: str
    name: str
    sector: str


class CompanyDetailOut(CompanyOut):
    kpis: list[KpiOut] = Field(default_factory=list)
    last_updated: Optional[datetime] = None


class SeriesPoint(BaseModel):
    fiscal_period: str
    period_start: date
    period_end: date
    est_type: EstType
    value: float
    as_of: Optional[date] = None


class KpiSeriesOut(BaseModel):
    ticker: str
    company_name: str
    kpi: str
    unit: str
    historical: list[SeriesPoint] = Field(default_factory=list)
    qtd: list[SeriesPoint] = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    qtd_as_of: Optional[date] = None


class KpiSummary(BaseModel):
    """One row of the at-a-glance dashboard for a single KPI."""

    kpi: str
    unit: str
    latest_period: Optional[str] = None
    latest_value: Optional[float] = None
    qoq_pct: Optional[float] = None  # vs prior quarter
    yoy_pct: Optional[float] = None  # vs same quarter prior year
    qtd_value: Optional[float] = None
    qtd_as_of: Optional[date] = None


class CompanySummaryOut(BaseModel):
    ticker: str
    company_name: str
    sector: str
    last_updated: Optional[datetime] = None
    kpis: list[KpiSummary] = Field(default_factory=list)


class SearchResultOut(BaseModel):
    sectors: list[SectorOut] = Field(default_factory=list)
    companies: list[CompanyOut] = Field(default_factory=list)
    kpis: list[KpiOut] = Field(default_factory=list)


class PublishEstimateIn(BaseModel):
    period_start: date
    period_end: date
    fiscal_period: str = Field(examples=["2026Q1"])
    est_type: EstType
    value: float
    as_of: Optional[date] = Field(
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
    as_of: Optional[date] = None
    published_at: datetime
