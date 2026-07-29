"""Kanonisches Rechnungsmodell (Pydantic) + Validierungs-/Routing-Typen.

Das Modell ist bewusst schlanker als EN 16931 — es enthält die Felder, die für
Validierung, Matching und Routing gebraucht werden. Ein produktives System würde
zusätzlich die KoSIT-Validator-Prüfung (Schematron) vorschalten.
"""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    UBL = "xrechnung-ubl"
    CII = "xrechnung-cii"
    ZUGFERD_PDF = "zugferd-pdf"
    PDF_FALLBACK = "pdf-fallback"


class Party(BaseModel):
    name: str
    vat_id: str | None = None
    iban: str | None = None


class LineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    net_amount: Decimal


class TaxBreakdown(BaseModel):
    rate: Decimal          # Prozent, z.B. 19
    base: Decimal          # Bemessungsgrundlage
    amount: Decimal        # Steuerbetrag


class Invoice(BaseModel):
    invoice_number: str
    issue_date: date
    currency: str = "EUR"
    seller: Party
    buyer_name: str | None = None
    # Bestellbezug (EN-16931 BT-13) — externe Referenz für den 2-/3-Way-Match
    purchase_order_ref: str | None = None
    lines: list[LineItem] = Field(default_factory=list)
    taxes: list[TaxBreakdown] = Field(default_factory=list)
    total_net: Decimal
    total_tax: Decimal
    total_gross: Decimal
    source_format: SourceFormat
    # 1.0 = strukturierte E-Rechnung (deterministisch geparst),
    # < 1.0 = Fallback-Extraktion (Text/LLM) — fließt ins Routing ein
    extraction_confidence: float = 1.0
    source_file: str = ""


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class Finding(BaseModel):
    code: str
    severity: Severity
    message: str


class Route(str, Enum):
    AUTO_POST = "AUTO_POST"      # dunkelverarbeitet buchen
    REVIEW = "REVIEW"            # Human-in-the-Loop-Queue
    REJECT = "REJECT"            # abweisen (z.B. Dublette)


class RoutingDecision(BaseModel):
    invoice_number: str
    source_file: str
    total_gross: Decimal
    currency: str
    route: Route
    risk_score: int              # 0-100; steuert Queue-Ranking UND via DMN die Freigabestufe (>= 50 -> Teamleitung)
    reasons: list[str]
    findings: list[Finding]
