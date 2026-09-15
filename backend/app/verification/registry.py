"""Gateway to the external government registries.

Everything the verification engine knows about "trusted external records" comes
through this interface. The prototype's implementation reads the ``mock_*``
tables; a production implementation would issue HTTP calls to GSTN, the Income
Tax Department, the Udyam portal and MCA21 behind the same method signatures.

Nothing outside this module queries a ``mock_*`` table. That is what makes the
"this simulates external systems" claim true in the codebase and not only on a
slide.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    MockCompanyRegistry,
    MockEpfoRegistry,
    MockFinancialRegistry,
    MockGstRegistry,
    MockOemRegistry,
    MockPanRegistry,
    MockUdyamRegistry,
)


@dataclass
class RegistryRecord:
    """A record returned by a registry lookup.

    ``found=False`` means the identifier is absent from the registry, which is a
    verification finding in its own right — distinct from a value mismatch.
    """

    source: str
    found: bool
    fields: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str) -> Any:
        return self.fields.get(key)


class RegistryGateway(ABC):
    @abstractmethod
    def pan(self, pan: str) -> RegistryRecord: ...

    @abstractmethod
    def gstin(self, gstin: str) -> RegistryRecord: ...

    @abstractmethod
    def udyam(self, udyam_number: str) -> RegistryRecord: ...

    @abstractmethod
    def company(self, cin: str) -> RegistryRecord: ...

    @abstractmethod
    def oem_for_dealer(self, dealer_pan: str, tender_number: str) -> RegistryRecord: ...

    @abstractmethod
    def epfo(self, establishment_code: str) -> RegistryRecord: ...

    @abstractmethod
    def financials(self, pan: str, financial_year: str) -> RegistryRecord: ...


def _missing(source: str) -> RegistryRecord:
    return RegistryRecord(source=source, found=False)


class MockRegistryGateway(RegistryGateway):
    """Prototype implementation backed by the local ``mock_*`` tables."""

    def __init__(self, db: Session):
        self.db = db

    # -- identifiers ------------------------------------------------------
    def pan(self, pan: str) -> RegistryRecord:
        row = self.db.get(MockPanRegistry, (pan or "").upper())
        if not row:
            return _missing("PAN_REGISTRY")
        return RegistryRecord(
            "PAN_REGISTRY",
            True,
            {"pan": row.pan, "name": row.name, "holder_type": row.holder_type, "status": row.status},
        )

    def gstin(self, gstin: str) -> RegistryRecord:
        row = self.db.get(MockGstRegistry, (gstin or "").upper())
        if not row:
            return _missing("GST_REGISTRY")
        return RegistryRecord(
            "GST_REGISTRY",
            True,
            {
                "gstin": row.gstin,
                "legal_name": row.legal_name,
                "trade_name": row.trade_name,
                "pan": row.pan,
                "address": row.address,
                "state_code": row.state_code,
                "status": row.status,
            },
        )

    def udyam(self, udyam_number: str) -> RegistryRecord:
        row = self.db.get(MockUdyamRegistry, (udyam_number or "").upper())
        if not row:
            return _missing("UDYAM_REGISTRY")
        return RegistryRecord(
            "UDYAM_REGISTRY",
            True,
            {
                "udyam_number": row.udyam_number,
                "business_name": row.business_name,
                "pan": row.pan,
                "gstin": row.gstin,
                "address": row.address,
                "enterprise_type": row.enterprise_type,
                "status": row.status,
            },
        )

    def company(self, cin: str) -> RegistryRecord:
        row = self.db.get(MockCompanyRegistry, (cin or "").upper())
        if not row:
            return _missing("COMPANY_REGISTRY")
        return RegistryRecord(
            "COMPANY_REGISTRY",
            True,
            {
                "cin": row.cin,
                "company_name": row.company_name,
                "pan": row.pan,
                "registered_address": row.registered_address,
                "directors": [d for d in (row.directors or "").split("|") if d.strip()],
                "status": row.status,
            },
        )

    def oem_for_dealer(self, dealer_pan: str, tender_number: str) -> RegistryRecord:
        row = (
            self.db.query(MockOemRegistry)
            .filter(MockOemRegistry.dealer_pan == (dealer_pan or "").upper())
            .filter(MockOemRegistry.tender_number == tender_number)
            .first()
        )
        if not row:
            return _missing("OEM_REGISTRY")
        return RegistryRecord(
            "OEM_REGISTRY",
            True,
            {
                "authorization_id": row.authorization_id,
                "oem_name": row.oem_name,
                "dealer_name": row.dealer_name,
                "dealer_pan": row.dealer_pan,
                "tender_number": row.tender_number,
                "product": row.product,
                "valid_until": row.valid_until,
                "status": row.status,
            },
        )

    def epfo(self, establishment_code: str) -> RegistryRecord:
        row = self.db.get(MockEpfoRegistry, (establishment_code or "").upper())
        if not row:
            return _missing("EPFO_REGISTRY")
        return RegistryRecord(
            "EPFO_REGISTRY",
            True,
            {
                "establishment_code": row.establishment_code,
                "establishment_name": row.establishment_name,
                "pan": row.pan,
                "esic_code": row.esic_code,
                "subscribers": row.subscribers,
                "status": row.status,
            },
        )

    def financials(self, pan: str, financial_year: str = "2024-25") -> RegistryRecord:
        row = (
            self.db.query(MockFinancialRegistry)
            .filter(MockFinancialRegistry.pan == (pan or "").upper())
            .filter(MockFinancialRegistry.financial_year == financial_year)
            .first()
        )
        if not row:
            return _missing("FINANCIAL_REGISTRY")
        return RegistryRecord(
            "FINANCIAL_REGISTRY",
            True,
            {
                "pan": row.pan,
                "financial_year": row.financial_year,
                "turnover_cr": row.turnover_cr,
                "profit_after_tax_cr": row.profit_after_tax_cr,
                "net_worth_cr": row.net_worth_cr,
            },
        )


def gateway_for(db: Session) -> RegistryGateway:
    """Factory. Swap the returned class to move to live government APIs."""
    return MockRegistryGateway(db)
