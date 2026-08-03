"""Routing-Punktetabelle (routing.py): jede Regel isoliert, eigener
Stammdaten-Satz je Test (tmp_path), frischer Router (Dubletten-Register!)."""

import json
from decimal import Decimal

import pytest

from pipeline.models import Finding, Party, Route, Severity
from pipeline.routing import Router
from tests.conftest import VALID_IBAN, VALID_VAT

ANDERE_IBAN = "DE02120300000000202051"   # gültig, aber nicht die Stammdaten-IBAN


@pytest.fixture
def router(tmp_path):
    (tmp_path / "vendors.json").write_text(json.dumps({
        VALID_VAT: {"name": "Alpha Buero GmbH", "iban": VALID_IBAN}}))
    (tmp_path / "purchase_orders.json").write_text(json.dumps({
        "PO-4711": {"vendor_vat_id": VALID_VAT, "net_amount": "600.00",
                    "goods_received": True},
        "PO-OHNE-WE": {"vendor_vat_id": VALID_VAT, "net_amount": "600.00",
                       "goods_received": False},
        "PO-NEU": {"vendor_vat_id": "DE999999999", "net_amount": "600.00",
                   "goods_received": True}}))
    return Router(tmp_path / "vendors.json")


def test_sauberer_beleg_wird_dunkelgebucht(router, make_invoice):
    d = router.route(make_invoice(), [])
    assert (d.route, d.risk_score) == (Route.AUTO_POST, 0)


def test_dublette_wird_abgewiesen(router, make_invoice):
    router.route(make_invoice(), [])
    d = router.route(make_invoice(), [])
    assert (d.route, d.risk_score) == (Route.REJECT, 100)


def test_validierungsfehler_40_punkte(router, make_invoice):
    f = [Finding(code="V01", severity=Severity.ERROR, message="x")]
    d = router.route(make_invoice(), f)
    assert (d.route, d.risk_score) == (Route.REVIEW, 40)


def test_iban_abweichung_50_punkte(router, make_invoice):
    inv = make_invoice(seller=Party(name="Alpha Buero GmbH", vat_id=VALID_VAT,
                                    iban=ANDERE_IBAN))
    d = router.route(inv, [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 50)


def test_neuer_lieferant_30_punkte(router, make_invoice):
    # Eigene Bestellung PO-NEU des neuen Lieferanten, sonst schlägt zusätzlich
    # der 3-Way-Match an ("Bestellung gehört zu anderem Lieferanten", +40)
    inv = make_invoice(seller=Party(name="Neu GmbH", vat_id="DE999999999",
                                    iban=VALID_IBAN),
                       purchase_order_ref="PO-NEU")
    d = router.route(inv, [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 30)


def test_fremdwaehrung_20_punkte(router, make_invoice):
    d = router.route(make_invoice(currency="USD"), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 20)


def test_grossbetrag_20_punkte(router, make_invoice):
    d = router.route(make_invoice(total_gross=Decimal("15000.00")), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 20)


def test_ohne_iban_10_punkte(router, make_invoice):
    inv = make_invoice(seller=Party(name="Alpha Buero GmbH", vat_id=VALID_VAT,
                                    iban=None))
    d = router.route(inv, [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 10)


def test_niedrige_confidence_25_punkte(router, make_invoice):
    d = router.route(make_invoice(extraction_confidence=0.6), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 25)


def test_kein_bestellbezug_15_punkte(router, make_invoice):
    d = router.route(make_invoice(purchase_order_ref=None), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 15)


def test_unbekannte_bestellung_30_punkte(router, make_invoice):
    d = router.route(make_invoice(purchase_order_ref="PO-9999"), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 30)


def test_netto_ueber_bestellwert_toleranz_30_punkte(router, make_invoice):
    d = router.route(make_invoice(total_net=Decimal("650.00")), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 30)


def test_netto_innerhalb_toleranz_bleibt_auto(router, make_invoice):
    d = router.route(make_invoice(total_net=Decimal("612.00")), [])
    assert d.route == Route.AUTO_POST


def test_fehlender_wareneingang_25_punkte(router, make_invoice):
    d = router.route(make_invoice(purchase_order_ref="PO-OHNE-WE"), [])
    assert (d.route, d.risk_score) == (Route.REVIEW, 25)


def test_warnung_erhoeht_score_aber_erzwingt_kein_review(router, make_invoice):
    # Charakterisierung des IST-Verhaltens (bekannte Design-Lücke T1):
    # Warnungen geben +5 Punkte, erzeugen aber KEINEN Grund — und nur Gründe
    # erzwingen REVIEW. Eine Nur-Warnung-Rechnung wird also dunkelgebucht.
    # Offene Design-Frage (V07-Warnung "älter als 1 Jahr" rutscht durch).
    f = [Finding(code="V05", severity=Severity.WARNING, message="x")]
    d = router.route(make_invoice(), f)
    assert (d.route, d.risk_score) == (Route.AUTO_POST, 5)
