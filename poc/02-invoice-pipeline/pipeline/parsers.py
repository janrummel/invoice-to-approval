"""Format-Erkennung und Parser: UBL-XML, CII-XML, ZUGFeRD-PDF, PDF-Fallback.

Strategie (Reihenfolge = Zuverlässigkeit):
  1. XML (XRechnung): UBL oder CII — deterministisch, confidence 1.0
  2. PDF mit eingebettetem XML (ZUGFeRD/Factur-X): XML extrahieren -> wie 1.
  3. PDF ohne XML: Text-Extraktion + Regex-Heuristik, confidence 0.6.
     Hier würde produktiv eine LLM-Extraktion (Vision-Modell + Pydantic-Schema,
     z.B. via instructor) andocken — siehe llm_extract_stub().
"""

import io
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber
from lxml import etree
from pypdf import PdfReader

from .models import Invoice, LineItem, Party, SourceFormat, TaxBreakdown

NS_UBL = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
NS_CII = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


def parse_file(path: Path) -> Invoice:
    if path.suffix.lower() == ".xml":
        return _parse_xml(path.read_bytes(), path.name)
    if path.suffix.lower() == ".pdf":
        embedded = _extract_embedded_xml(path)
        if embedded is not None:
            inv = _parse_xml(embedded, path.name)
            inv.source_format = SourceFormat.ZUGFERD_PDF
            return inv
        return _parse_pdf_fallback(path)
    raise ValueError(f"Nicht unterstütztes Format: {path.name}")


# --- XML (XRechnung: UBL / CII) -----------------------------------------

# Gehärteter Parser: Eingangsrechnungen sind Fremddaten. Keine Entity-Expansion,
# kein DTD-Load, kein Netzwerkzugriff — schließt XXE und Billion-Laughs aus.
_SAFE_XML = etree.XMLParser(
    resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
)


def _parse_xml(data: bytes, filename: str) -> Invoice:
    root = etree.fromstring(data, parser=_SAFE_XML)
    tag = etree.QName(root).localname
    if tag == "Invoice":
        return _parse_ubl(root, filename)
    if tag == "CrossIndustryInvoice":
        return _parse_cii(root, filename)
    raise ValueError(f"Unbekanntes XML-Root-Element: {tag}")


def _x(root, xpath: str, ns) -> str | None:
    r = root.xpath(xpath, namespaces=ns)
    return r[0].text.strip() if r and r[0].text else None


def _parse_ubl(root, filename: str) -> Invoice:
    ns = NS_UBL
    lines = []
    for il in root.xpath("//cac:InvoiceLine", namespaces=ns):
        lines.append(LineItem(
            description=_x(il, ".//cac:Item/cbc:Name", ns) or "?",
            quantity=Decimal(_x(il, "./cbc:InvoicedQuantity", ns) or "0"),
            unit_price=Decimal(_x(il, ".//cac:Price/cbc:PriceAmount", ns) or "0"),
            net_amount=Decimal(_x(il, "./cbc:LineExtensionAmount", ns) or "0"),
        ))
    taxes = []
    for ts in root.xpath("//cac:TaxTotal/cac:TaxSubtotal", namespaces=ns):
        taxes.append(TaxBreakdown(
            rate=Decimal(_x(ts, ".//cac:TaxCategory/cbc:Percent", ns) or "0"),
            base=Decimal(_x(ts, "./cbc:TaxableAmount", ns) or "0"),
            amount=Decimal(_x(ts, "./cbc:TaxAmount", ns) or "0"),
        ))
    return Invoice(
        invoice_number=_x(root, "/inv:Invoice/cbc:ID", ns) or "?",
        issue_date=date.fromisoformat(_x(root, "/inv:Invoice/cbc:IssueDate", ns)),
        currency=_x(root, "/inv:Invoice/cbc:DocumentCurrencyCode", ns) or "EUR",
        seller=Party(
            name=_x(root, "//cac:AccountingSupplierParty//cac:PartyLegalEntity/cbc:RegistrationName", ns) or "?",
            vat_id=_x(root, "//cac:AccountingSupplierParty//cac:PartyTaxScheme/cbc:CompanyID", ns),
            iban=_x(root, "//cac:PaymentMeans//cac:PayeeFinancialAccount/cbc:ID", ns),
        ),
        buyer_name=_x(root, "//cac:AccountingCustomerParty//cac:PartyLegalEntity/cbc:RegistrationName", ns),
        purchase_order_ref=_x(root, "//cac:OrderReference/cbc:ID", ns),
        lines=lines, taxes=taxes,
        total_net=Decimal(_x(root, "//cac:LegalMonetaryTotal/cbc:LineExtensionAmount", ns) or "0"),
        total_tax=Decimal(_x(root, "/inv:Invoice/cac:TaxTotal/cbc:TaxAmount", ns) or "0"),
        total_gross=Decimal(_x(root, "//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", ns) or "0"),
        source_format=SourceFormat.UBL, source_file=filename,
    )


def _parse_cii(root, filename: str) -> Invoice:
    ns = NS_CII
    lines = []
    for il in root.xpath("//ram:IncludedSupplyChainTradeLineItem", namespaces=ns):
        lines.append(LineItem(
            description=_x(il, ".//ram:SpecifiedTradeProduct/ram:Name", ns) or "?",
            quantity=Decimal(_x(il, ".//ram:BilledQuantity", ns) or "0"),
            unit_price=Decimal(_x(il, ".//ram:NetPriceProductTradePrice/ram:ChargeAmount", ns) or "0"),
            net_amount=Decimal(_x(il, ".//ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount", ns) or "0"),
        ))
    taxes = []
    for tt in root.xpath("//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax", namespaces=ns):
        taxes.append(TaxBreakdown(
            rate=Decimal(_x(tt, "./ram:RateApplicablePercent", ns) or "0"),
            base=Decimal(_x(tt, "./ram:BasisAmount", ns) or "0"),
            amount=Decimal(_x(tt, "./ram:CalculatedAmount", ns) or "0"),
        ))
    ds = _x(root, "//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString", ns)
    return Invoice(
        invoice_number=_x(root, "//rsm:ExchangedDocument/ram:ID", ns) or "?",
        issue_date=datetime.strptime(ds, "%Y%m%d").date(),
        currency=_x(root, "//ram:InvoiceCurrencyCode", ns) or "EUR",
        seller=Party(
            name=_x(root, "//ram:SellerTradeParty/ram:Name", ns) or "?",
            vat_id=_x(root, "//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", ns),
            iban=_x(root, "//ram:PayeePartyCreditorFinancialAccount/ram:IBANID", ns),
        ),
        buyer_name=_x(root, "//ram:BuyerTradeParty/ram:Name", ns),
        purchase_order_ref=_x(root, "//ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID", ns),
        lines=lines, taxes=taxes,
        total_net=Decimal(_x(root, "//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:LineTotalAmount", ns) or "0"),
        total_tax=Decimal(_x(root, "//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount", ns) or "0"),
        total_gross=Decimal(_x(root, "//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount", ns) or "0"),
        source_format=SourceFormat.CII, source_file=filename,
    )


# --- ZUGFeRD: eingebettetes XML aus PDF/A-3 ------------------------------

XML_ATTACHMENT_NAMES = {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml"}


def _extract_embedded_xml(path: Path) -> bytes | None:
    reader = PdfReader(str(path))
    for name, content_list in reader.attachments.items():
        if name.lower() in XML_ATTACHMENT_NAMES:
            return content_list[0]
    return None


# --- PDF-Fallback: Text + Regex (produktiv: LLM-Extraktion) ---------------

MONEY = r"([\d.]+,\d{2})"


def _dec(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def _parse_pdf_fallback(path: Path) -> Invoice:
    with pdfplumber.open(str(path)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    def find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1) if m else default

    num = find(r"Rechnung(?:s-?Nr\.?|snummer)[:\s]+(\S+)", "?")
    d = find(r"Datum[:\s]+(\d{2}\.\d{2}\.\d{4})")
    net = find(rf"Netto(?:betrag)?[:\s]+{MONEY}")
    tax = find(rf"(?:USt|MwSt)\.?\s*(?:19|7)?\s*%?[:\s]+{MONEY}")
    gross = find(rf"(?:Brutto|Gesamt)(?:betrag)?[:\s]+{MONEY}")
    seller = find(r"^(.+?)\n", "Unbekannt")
    iban = find(r"IBAN[:\s]+([A-Z]{2}\d[\dA-Z ]{12,32})")

    return Invoice(
        invoice_number=num,
        issue_date=datetime.strptime(d, "%d.%m.%Y").date() if d else date(1900, 1, 1),
        seller=Party(name=seller.strip(), vat_id=find(r"(DE\d{9})"),
                     iban=iban.replace(" ", "") if iban else None),
        total_net=_dec(net) if net else Decimal(0),
        total_tax=_dec(tax) if tax else Decimal(0),
        total_gross=_dec(gross) if gross else Decimal(0),
        source_format=SourceFormat.PDF_FALLBACK,
        extraction_confidence=0.6,
        source_file=path.name,
    )


def llm_extract_stub(path: Path) -> None:
    """Andockpunkt für produktive LLM-Extraktion unstrukturierter Belege.

    Muster (siehe Research-Note): Vision-LLM (z.B. Claude) erhält das Belegbild
    plus das Pydantic-JSON-Schema von `Invoice` und liefert validierte Felder;
    Bibliothek `instructor` erzwingt Schema-Konformität mit Retry.

    Ehrlichkeits-Hinweis: Im POC ist extraction_confidence eine gesetzte
    Konstante (0.6 Text-Heuristik, 0.85 LLM-Demo) — bewusst so gewählt, dass
    beide Pfade unter dem Routing-Schwellwert 0.9 bleiben und nie dunkel
    gebucht werden. Produktiv würde der Wert aus Modell-Logprobs bzw.
    Feld-Heuristiken abgeleitet.
    """
    raise NotImplementedError
