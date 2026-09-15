"""Mock external registry tables.

These stand in for records that, in production, would be fetched from GSTN, the
Income Tax Department, the Udyam portal, MCA21 and OEM systems. Nothing in the
verification engine touches these tables directly — everything goes through
``app.verification.registry.RegistryGateway``, so swapping in real API clients
later is a change in one file.

All data is synthetic. See backend/data/specimen/README.md.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class MockPanRegistry(Base):
    __tablename__ = "mock_pan_registry"

    pan: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    holder_type: Mapped[str] = mapped_column(String(1), default="C")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class MockGstRegistry(Base):
    __tablename__ = "mock_gst_registry"

    gstin: Mapped[str] = mapped_column(String(15), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200))
    pan: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(400), default="")
    state_code: Mapped[str] = mapped_column(String(2), default="")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    registration_date: Mapped[datetime | None] = mapped_column(DateTime)


class MockUdyamRegistry(Base):
    __tablename__ = "mock_udyam_registry"

    udyam_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pan: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15))
    address: Mapped[str] = mapped_column(String(400), default="")
    enterprise_type: Mapped[str] = mapped_column(String(16), default="Small")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class MockCompanyRegistry(Base):
    """MCA21 stand-in, keyed by CIN."""

    __tablename__ = "mock_company_registry"

    cin: Mapped[str] = mapped_column(String(21), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pan: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    registered_address: Mapped[str] = mapped_column(String(400), default="")
    incorporation_date: Mapped[datetime | None] = mapped_column(DateTime)
    directors: Mapped[str] = mapped_column(String(600), default="")  # pipe-separated
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class MockOemRegistry(Base):
    __tablename__ = "mock_oem_registry"

    authorization_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    oem_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dealer_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    dealer_pan: Mapped[str] = mapped_column(String(10), index=True)
    tender_number: Mapped[str] = mapped_column(String(64), default="")
    product: Mapped[str] = mapped_column(String(300), default="")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class MockEpfoRegistry(Base):
    __tablename__ = "mock_epfo_registry"

    establishment_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    establishment_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pan: Mapped[str] = mapped_column(String(10), index=True)
    esic_code: Mapped[str | None] = mapped_column(String(32))
    subscribers: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class MockFinancialRegistry(Base):
    """Stand-in for CA/MCA filed financials, keyed by PAN + financial year."""

    __tablename__ = "mock_financial_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pan: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    financial_year: Mapped[str] = mapped_column(String(9), default="2024-25")
    turnover_cr: Mapped[float] = mapped_column(Float, default=0.0)
    profit_after_tax_cr: Mapped[float] = mapped_column(Float, default=0.0)
    net_worth_cr: Mapped[float] = mapped_column(Float, default=0.0)
