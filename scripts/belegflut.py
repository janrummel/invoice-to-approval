# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2", "python-stdnum"]
# ///
"""Szenario 'Belegflut' (Szenario-Abnahme): 30 konstruierte Belege mit bekannter
Soll-Verteilung laufen durch Validierung + Routing.

Soll: 18x AUTO_POST · 4x REJECT (Dubletten) · 8x REVIEW
      (3 IBAN-Fraud, 3 Grossbetrag [in sich konsistent, PO-4750 gedeckt —
      es feuert NUR die Betragsschwelle], 2 ohne Bestellbezug)
Exit-Codes: 0 = Ist entspricht Soll · 1 = Abweichung.
Aufruf:  uv run scripts/belegflut.py
"""

import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "poc" / "02-invoice-pipeline"))

from pipeline.models import Invoice, LineItem, Party, Route, SourceFormat, TaxBreakdown
from pipeline.routing import Router
from pipeline.validation import validate

TODAY = date(2026, 7, 28)
MASTER = REPO / "poc" / "02-invoice-pipeline" / "masterdata" / "vendors.json"
VALID_IBAN = "DE89370400440532013000"
ANDERE_IBAN = "DE02120300000000202051"
VALID_VAT = "DE136695976"


def beleg(nr, **over):
    base = dict(
        invoice_number=f"FLUT-{nr:03d}", issue_date=date(2026, 7, 10),
        currency="EUR",
        seller=Party(name="Alpha Buero GmbH", vat_id=VALID_VAT, iban=VALID_IBAN),
        purchase_order_ref="PO-4711",
        lines=[LineItem(description="Ware", quantity=Decimal("1"),
                        unit_price=Decimal("600"), net_amount=Decimal("600.00"))],
        taxes=[TaxBreakdown(rate=Decimal("19"), base=Decimal("600.00"),
                            amount=Decimal("114.00"))],
        total_net=Decimal("600.00"), total_tax=Decimal("114.00"),
        total_gross=Decimal("714.00"), source_format=SourceFormat.UBL,
        source_file=f"flut_{nr:03d}.xml")
    base.update(over)
    return Invoice(**base)


def main():
    belege = [beleg(i) for i in range(1, 19)]                        # 18 sauber
    belege += [beleg(i, invoice_number=f"FLUT-{i-4:03d}")            # 4 Dubletten
               for i in range(19, 23)]
    belege += [beleg(i, seller=Party(name="Alpha Buero GmbH",       # 3 IBAN-Fraud
                                     vat_id=VALID_VAT, iban=ANDERE_IBAN))
               for i in range(23, 26)]
    # 3 Grossbetrag — in sich konsistent (21.000 netto + 19 % USt) und durch
    # PO-4750 (Delta Anlagenbau, Wareneingang gebucht) gedeckt: es feuert
    # ausschliesslich die Betragsschwelle (+20)
    belege += [beleg(i,
                     seller=Party(name="Delta Anlagenbau GmbH",
                                  vat_id="DE111111125",
                                  iban="DE27100777770209299700"),
                     purchase_order_ref="PO-4750",
                     lines=[LineItem(description="Anlage",
                                     quantity=Decimal("1"),
                                     unit_price=Decimal("21000"),
                                     net_amount=Decimal("21000.00"))],
                     taxes=[TaxBreakdown(rate=Decimal("19"),
                                         base=Decimal("21000.00"),
                                         amount=Decimal("3990.00"))],
                     total_net=Decimal("21000.00"),
                     total_tax=Decimal("3990.00"),
                     total_gross=Decimal("24990.00"))
               for i in range(26, 29)]
    belege += [beleg(i, purchase_order_ref=None)                    # 2 ohne PO
               for i in range(29, 31)]

    router = Router(MASTER)
    ist = Counter()
    for inv in belege:
        d = router.route(inv, validate(inv, TODAY))
        ist[d.route] += 1
        # ALLE Gründe ausgeben, nicht nur den ersten — sonst bleibt bei
        # Mehrfach-Befunden Information verborgen (Lektion aus der Abnahme)
        print(f"{inv.source_file}  {d.route.value:9}  Risk {d.risk_score:3}  "
              f"{' | '.join(d.reasons)}")

    soll = {Route.AUTO_POST: 18, Route.REJECT: 4, Route.REVIEW: 8}
    print(f"\nSoll: {dict((k.value, v) for k, v in soll.items())}")
    print(f"Ist:  {dict((k.value, v) for k, v in ist.items())}")
    if dict(ist) != soll:
        print("BELEGFLUT FAIL")
        sys.exit(1)
    print("BELEGFLUT OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
