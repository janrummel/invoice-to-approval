"""Deterministische Validierung — Schicht 2 der Pipeline.

Kernprinzip aus der Research-Note: Nach jeder Extraktion (auch der strukturierten)
prüfen deterministische Regeln die innere Konsistenz.

Ehrliche Grenze: Bei LLM-Extraktion fangen diese Regeln INKONSISTENTE
Extraktionsfehler (Werte, die nicht zusammenpassen). Einen in sich kohärenten,
aber falschen Wertesatz erkennen sie nicht — dagegen helfen nur der Abgleich
gegen externe Referenzen (Bestellung/Wareneingang, Stammdaten) sowie das
Confidence-Gate mit Human-in-the-Loop im Routing.
"""

from datetime import date, timedelta
from decimal import Decimal

from stdnum import iban as iban_check
from stdnum.eu import vat as vat_check

from .models import Finding, Invoice, Severity

TOL = Decimal("0.01")


def validate(inv: Invoice, today: date) -> list[Finding]:
    f: list[Finding] = []

    def err(code, msg):
        f.append(Finding(code=code, severity=Severity.ERROR, message=msg))

    def warn(code, msg):
        f.append(Finding(code=code, severity=Severity.WARNING, message=msg))

    # V01: Positionssumme == Nettosumme
    if inv.lines:
        line_sum = sum(l.net_amount for l in inv.lines)
        if abs(line_sum - inv.total_net) > TOL:
            err("V01", f"Positionssumme {line_sum} != Nettosumme {inv.total_net}")

    # V02: Steuer je Satz rechnerisch korrekt
    for t in inv.taxes:
        expected = (t.base * t.rate / 100).quantize(TOL)
        if abs(expected - t.amount) > TOL:
            err("V02", f"USt {t.rate}%: erwartet {expected}, ausgewiesen {t.amount}")

    # V03: Netto + Steuer == Brutto
    if abs(inv.total_net + inv.total_tax - inv.total_gross) > TOL:
        err("V03", f"Netto {inv.total_net} + USt {inv.total_tax} "
                   f"!= Brutto {inv.total_gross}")

    # V04: IBAN-Prüfsumme
    if inv.seller.iban and not iban_check.is_valid(inv.seller.iban):
        err("V04", f"IBAN ungültig: {inv.seller.iban}")

    # V05: USt-ID (Format + Prüfziffer)
    if inv.seller.vat_id:
        if not vat_check.is_valid(inv.seller.vat_id):
            warn("V05", f"USt-ID nicht validierbar: {inv.seller.vat_id}")
    else:
        warn("V05", "Keine USt-ID des Lieferanten vorhanden")

    # V06: Pflichtfelder
    if inv.invoice_number in ("", "?"):
        err("V06", "Rechnungsnummer fehlt")
    if not inv.seller.iban:
        warn("V06", "Keine IBAN vorhanden — Zahlweg unklar")

    # V07: Datums-Plausibilität
    if inv.issue_date > today:
        err("V07", f"Rechnungsdatum liegt in der Zukunft: {inv.issue_date}")
    elif inv.issue_date < today - timedelta(days=365):
        warn("V07", f"Rechnungsdatum älter als 1 Jahr: {inv.issue_date}")

    # V08: Beträge müssen positiv sein (Grenzfall aus adversarialem Test)
    if inv.total_gross <= 0 or inv.total_net < 0:
        err("V08", f"Nicht-positiver Betrag: netto {inv.total_net}, "
                   f"brutto {inv.total_gross}")

    return f
