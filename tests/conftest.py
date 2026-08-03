"""Gemeinsame Fixtures. Das Pipeline-Paket liegt unter poc/02-invoice-pipeline
und ist kein installierbares Paket — bewusst einfacher sys.path-Eintrag."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "poc" / "02-invoice-pipeline"))

from pipeline.models import Invoice, LineItem, Party, SourceFormat, TaxBreakdown  # noqa: E402

TODAY = date(2026, 7, 28)                      # wie run.py — fixierter Stichtag
VALID_IBAN = "DE89370400440532013000"          # Stammdaten "Alpha Buero GmbH"
VALID_VAT = "DE136695976"


@pytest.fixture
def make_invoice():
    """Baut eine in sich konsistente Rechnung (Basis: Szenario s1, 714,00 EUR,
    Bestellung PO-4711); jedes Feld per kwargs überschreibbar."""
    def _make(**over):
        base = dict(
            invoice_number="TEST-001",
            issue_date=date(2026, 7, 1),
            currency="EUR",
            seller=Party(name="Alpha Buero GmbH", vat_id=VALID_VAT,
                         iban=VALID_IBAN),
            purchase_order_ref="PO-4711",
            lines=[LineItem(description="Kopierpapier", quantity=Decimal("10"),
                            unit_price=Decimal("60"),
                            net_amount=Decimal("600.00"))],
            taxes=[TaxBreakdown(rate=Decimal("19"), base=Decimal("600.00"),
                                amount=Decimal("114.00"))],
            total_net=Decimal("600.00"),
            total_tax=Decimal("114.00"),
            total_gross=Decimal("714.00"),
            source_format=SourceFormat.UBL,
            source_file="test.xml",
        )
        base.update(over)
        return Invoice(**base)
    return _make
