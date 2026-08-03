"""Adversariale Belege: Angriffs- und Grenzfälle. Der XXE-Fall verankert den
Parser-Fix vom 28.07. als dauerhafte Regression."""

from decimal import Decimal
from pathlib import Path

import pytest

from pipeline.parsers import parse_file
from pipeline.validation import validate
from tests.conftest import TODAY

DATA = Path(__file__).parent / "data"


def test_xxe_entity_wird_nicht_aufgeloest():
    # Sicheres Verhalten laut Parser-Konfiguration (resolve_entities=False,
    # no_network, load_dtd=False): entweder Exception oder unaufgelöste Entity —
    # niemals Dateiinhalt (/etc/hosts enthält "localhost") im Ergebnis.
    try:
        inv = parse_file(DATA / "a1_xxe.xml")
    except Exception:
        return  # sauberes Abweisen ist sicher
    assert "localhost" not in inv.model_dump_json()


def test_kaputtes_xml_wirft_kontrollierte_exception():
    with pytest.raises(Exception):
        parse_file(DATA / "a2_kaputtes_xml.xml")


def test_leere_datei_wirft_kontrollierte_exception():
    with pytest.raises(Exception):
        parse_file(DATA / "a3_leer.xml")


def test_v08_negativer_brutto_ist_fehler(make_invoice):
    inv = make_invoice(total_gross=Decimal("-714.00"),
                       total_net=Decimal("-600.00"),
                       total_tax=Decimal("-114.00"), lines=[], taxes=[])
    assert ("V08", "error") in {(f.code, f.severity.value)
                                for f in validate(inv, TODAY)}


def test_v08_null_brutto_ist_fehler(make_invoice):
    inv = make_invoice(total_gross=Decimal("0"), total_net=Decimal("0"),
                       total_tax=Decimal("0"), lines=[], taxes=[])
    assert ("V08", "error") in {(f.code, f.severity.value)
                                for f in validate(inv, TODAY)}
