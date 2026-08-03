"""Charakterisierungs-Tests der Validierungsregeln V01-V07 (validation.py).
Jede Regel wird isoliert verletzt; geprüft wird der erwartete Finding-Code."""

from datetime import date
from decimal import Decimal

from pipeline.models import LineItem, Party, TaxBreakdown
from pipeline.validation import validate
from tests.conftest import TODAY, VALID_IBAN, VALID_VAT


def codes(inv):
    return {(f.code, f.severity.value) for f in validate(inv, TODAY)}


def test_v01_positionssumme_ungleich_netto(make_invoice):
    inv = make_invoice(lines=[LineItem(description="x", quantity=Decimal("1"),
                                       unit_price=Decimal("500"),
                                       net_amount=Decimal("500.00"))])
    assert ("V01", "error") in codes(inv)


def test_v02_steuer_falsch_gerechnet(make_invoice):
    inv = make_invoice(taxes=[TaxBreakdown(rate=Decimal("19"),
                                           base=Decimal("600.00"),
                                           amount=Decimal("100.00"))])
    assert ("V02", "error") in codes(inv)


def test_v03_brutto_passt_nicht(make_invoice):
    inv = make_invoice(total_gross=Decimal("999.00"))
    assert ("V03", "error") in codes(inv)


def test_v04_iban_pruefsumme(make_invoice):
    inv = make_invoice(seller=Party(name="X", vat_id=VALID_VAT,
                                    iban="DE00370400440532013000"))
    assert ("V04", "error") in codes(inv)


def test_v05_ustid_nicht_validierbar(make_invoice):
    inv = make_invoice(seller=Party(name="X", vat_id="DE000000000",
                                    iban=VALID_IBAN))
    assert ("V05", "warning") in codes(inv)


def test_v05_ustid_fehlt(make_invoice):
    inv = make_invoice(seller=Party(name="X", vat_id=None, iban=VALID_IBAN))
    assert ("V05", "warning") in codes(inv)


def test_v06_rechnungsnummer_fehlt(make_invoice):
    inv = make_invoice(invoice_number="")
    assert ("V06", "error") in codes(inv)


def test_v06_iban_fehlt_ist_warnung(make_invoice):
    inv = make_invoice(seller=Party(name="X", vat_id=VALID_VAT, iban=None))
    assert ("V06", "warning") in codes(inv)


def test_v07_datum_in_zukunft(make_invoice):
    inv = make_invoice(issue_date=date(2026, 12, 31))
    assert ("V07", "error") in codes(inv)


def test_v07_datum_aelter_ein_jahr(make_invoice):
    inv = make_invoice(issue_date=date(2025, 1, 1))
    assert ("V07", "warning") in codes(inv)
