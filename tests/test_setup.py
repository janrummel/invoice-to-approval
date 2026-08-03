"""Beweist: Testinfrastruktur steht, Pipeline importierbar, Basis-Beleg valide."""

from pipeline.validation import validate
from tests.conftest import TODAY


def test_basisbeleg_ist_fehlerfrei(make_invoice):
    inv = make_invoice()
    findings = validate(inv, TODAY)
    assert [f for f in findings if f.severity.value == "error"] == []
