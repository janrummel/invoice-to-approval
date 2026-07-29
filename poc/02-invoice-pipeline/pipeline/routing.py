"""Risk-tiered Routing — Schicht 3 der Pipeline.

Umsetzung des Musters "risk-tiered autonomy" aus der Research-Note:
Dunkelbuchung (AUTO_POST) nur, wenn ALLE Bedingungen erfüllt sind —
jede Auffälligkeit eskaliert in die Review-Queue, Dubletten werden abgewiesen.
Die Regeln sind bewusst deterministisch und erklärbar (Audit-Trail!).
"""

import json
from decimal import Decimal
from pathlib import Path

from .models import Finding, Invoice, Route, RoutingDecision, Severity

AUTO_POST_LIMIT = Decimal("10000")   # Brutto-Schwelle für Dunkelbuchung
MIN_CONFIDENCE = 0.9                 # darunter immer Review
PO_TOLERANZ = Decimal("0.02")        # Rechnung darf Bestellwert um max. 2 % übersteigen


class Router:
    def __init__(self, masterdata_path: Path):
        self.vendors: dict = json.loads(masterdata_path.read_text())
        po_path = masterdata_path.parent / "purchase_orders.json"
        self.purchase_orders: dict = (
            json.loads(po_path.read_text()) if po_path.exists() else {}
        )
        self.seen: set[tuple[str, str]] = set()   # (vat_id|name, invoice_number)

    def route(self, inv: Invoice, findings: list[Finding]) -> RoutingDecision:
        reasons, risk = [], 0
        errors = [f for f in findings if f.severity == Severity.ERROR]
        warnings = [f for f in findings if f.severity == Severity.WARNING]

        # 1. Dublette -> REJECT (härteste Regel zuerst)
        key = (inv.seller.vat_id or inv.seller.name, inv.invoice_number)
        if key in self.seen:
            return RoutingDecision(
                invoice_number=inv.invoice_number, source_file=inv.source_file,
                total_gross=inv.total_gross, currency=inv.currency,
                route=Route.REJECT, risk_score=100,
                reasons=[f"Dublette: Rechnung {inv.invoice_number} von "
                         f"{inv.seller.name} bereits verarbeitet"],
                findings=findings)
        self.seen.add(key)

        # 2. Validierungsfehler -> Review
        if errors:
            risk += 40
            reasons += [f"Validierungsfehler {e.code}: {e.message}" for e in errors]

        # 3. Stammdaten-Abgleich
        vendor = self.vendors.get(inv.seller.vat_id or "")
        if vendor is None:
            risk += 30
            reasons.append(f"Neuer Lieferant '{inv.seller.name}' — "
                           "Stammdatenprüfung erforderlich")
        elif inv.seller.iban and vendor["iban"] != inv.seller.iban:
            risk += 50
            reasons.append(f"Bankverbindung weicht von Stammdaten ab "
                           f"({vendor['iban']} -> {inv.seller.iban}) — Fraud-Check!")

        # 4. Währung: alle Schwellwerte sind in EUR definiert
        if inv.currency != "EUR":
            risk += 20
            reasons.append(f"Fremdwährung {inv.currency} — Schwellwert- und "
                           "Stammdatenprüfung nur für EUR definiert, "
                           "manuelle Prüfung erforderlich")

        # 5. Betragsschwelle
        if inv.total_gross > AUTO_POST_LIMIT:
            risk += 20
            reasons.append(f"Brutto {inv.total_gross} {inv.currency} über "
                           f"Dunkelbuchungsgrenze {AUTO_POST_LIMIT} EUR — "
                           "Freigabe erforderlich")

        # 6. Zahlweg: ohne IBAN keine Dunkelbuchung
        if not inv.seller.iban:
            risk += 10
            reasons.append("Keine IBAN im Beleg — Zahlweg ungeklärt, "
                           "keine Dunkelbuchung möglich")

        # 7. Extraktions-Confidence (Fallback-Pfad)
        if inv.extraction_confidence < MIN_CONFIDENCE:
            risk += 25
            reasons.append(f"Extraktions-Confidence {inv.extraction_confidence:.0%} "
                           f"unter Schwellwert {MIN_CONFIDENCE:.0%} — "
                           "manuelle Prüfung der extrahierten Felder")

        # 8. Bestellbezug: 2-/3-Way-Match gegen Bestellung und Wareneingang.
        #    Ohne erfolgreichen Match keine Dunkelbuchung — die Rechnung mag in
        #    sich stimmen, aber nur der Abgleich gegen die externe Referenz
        #    beweist, dass bestellt und geliefert wurde.
        if not inv.purchase_order_ref:
            risk += 15
            reasons.append("Kein Bestellbezug — Dunkelbuchung nur mit "
                           "erfolgreichem 3-Way-Match möglich")
        else:
            po = self.purchase_orders.get(inv.purchase_order_ref)
            if po is None:
                risk += 30
                reasons.append(f"Bestellung {inv.purchase_order_ref} unbekannt "
                               "— Bestellbezug klären")
            else:
                if po.get("vendor_vat_id") and \
                        po["vendor_vat_id"] != (inv.seller.vat_id or ""):
                    risk += 40
                    reasons.append(f"Bestellung {inv.purchase_order_ref} gehört "
                                   "zu einem anderen Lieferanten — prüfen")
                limit = Decimal(str(po["net_amount"])) * (1 + PO_TOLERANZ)
                if inv.total_net > limit:
                    risk += 30
                    reasons.append(f"Netto {inv.total_net} über Bestellwert "
                                   f"{po['net_amount']} zzgl. {PO_TOLERANZ:.0%} "
                                   "Toleranz — Preis-/Mengenabweichung klären")
                if not po.get("goods_received", False):
                    risk += 25
                    reasons.append(f"Wareneingang zu {inv.purchase_order_ref} "
                                   "fehlt — 3-Way-Match unvollständig")

        if warnings:
            risk += 5 * len(warnings)

        route = Route.REVIEW if reasons else Route.AUTO_POST
        if route == Route.AUTO_POST:
            reasons.append("Alle Prüfungen bestanden — Dunkelbuchung")
        return RoutingDecision(
            invoice_number=inv.invoice_number, source_file=inv.source_file,
            total_gross=inv.total_gross, currency=inv.currency,
            route=route, risk_score=min(risk, 100),
            reasons=reasons, findings=findings)
