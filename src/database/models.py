"""
SQLAlchemy ORM Models for Multi-Agent RevOps Orchestrator.

Tables:
- dealers: Master list of dealers/distributors
- revenue_records: Monthly revenue per dealer (6+ months history)
- competitor_signals: External pricing & market signals captured by Signal Scraper
- run_logs: Full audit trail of every agent execution (required for portfolio proof)
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


class Dealer(Base):
    """Master dealer / channel partner table."""

    __tablename__ = "dealers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dealer_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)  # A, B, C
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    revenue_records: Mapped[list["RevenueRecord"]] = relationship(
        back_populates="dealer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_dealers_region_tier", "region", "tier"),
    )

    def __repr__(self) -> str:
        return f"<Dealer(code={self.dealer_code}, name={self.name}, tier={self.tier})>"


class RevenueRecord(Base):
    """Monthly revenue performance per dealer."""

    __tablename__ = "revenue_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dealer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dealers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False)  # first day of month
    revenue_inr: Mapped[float] = mapped_column(Float, nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    target_inr: Mapped[float] = mapped_column(Float, nullable=False)
    growth_pct: Mapped[Optional[float]] = mapped_column(Float)  # YoY or MoM

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dealer: Mapped["Dealer"] = relationship(back_populates="revenue_records")

    __table_args__ = (
        Index("ix_revenue_dealer_period", "dealer_id", "period", unique=True),
        Index("ix_revenue_period", "period"),
    )

    def __repr__(self) -> str:
        return f"<RevenueRecord(dealer={self.dealer_id}, period={self.period}, revenue={self.revenue_inr})>"


class CompetitorSignal(Base):
    """External market signals captured by the Signal Scraper Agent."""

    __tablename__ = "competitor_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    competitor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pricing, news, hiring, etc.
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    __table_args__ = (
        Index("ix_signals_competitor_type", "competitor_name", "signal_type"),
        Index("ix_signals_detected_at", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<CompetitorSignal(competitor={self.competitor_name}, type={self.signal_type})>"


class RunLog(Base):
    """
    Complete audit trail for every node execution.
    This is critical for production observability and portfolio demonstration.
    """

    __tablename__ = "run_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # started, success, failed, retried
    input_summary: Mapped[Optional[str]] = mapped_column(Text)
    output_summary: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_run_logs_run_id_node", "run_id", "node_name"),
        Index("ix_run_logs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<RunLog(run_id={self.run_id}, node={self.node_name}, status={self.status})>"
