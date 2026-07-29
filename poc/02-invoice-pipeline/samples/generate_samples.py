"""Erzeugt die Beispiel-Eingangsrechnungen für die Pipeline-Demo.

  s1_xrechnung_ubl_ok.xml       UBL, konsistent, bekannter Lieferant  -> AUTO_POST
  s2_xrechnung_cii_summenfehler.xml  CII, Positionssumme != Netto     -> REVIEW
  s3_zugferd_iban_geaendert.pdf PDF mit eingebettetem CII-XML, IBAN
                                weicht von Stammdaten ab              -> REVIEW (Fraud)
  s4_xrechnung_ubl_grossbetrag.xml   UBL, konsistent, > 10k EUR       -> REVIEW (Freigabe)
  s5_xrechnung_ubl_dublette.xml Kopie von s1 (neue Datei)             -> REJECT
  s6_scan_ohne_xml.pdf          PDF ohne XML (Alt-/Auslandsbeleg)     -> REVIEW (Fallback)
  s7_xrechnung_ubl_po_abweichung.xml  UBL konsistent, aber Netto über
                                Bestellwert + Toleranz                -> REVIEW (3-Way-Match)
"""

import io
from pathlib import Path

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

OUT = Path(__file__).parent


def ubl(num, d, seller, vat, iban_, lines, net, tax, gross, rate=19, po=None):
    po_block = (f"\n  <cac:OrderReference><cbc:ID>{po}</cbc:ID></cac:OrderReference>"
                if po else "")
    items = "".join(f"""
  <cac:InvoiceLine>
    <cbc:ID>{i+1}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">{q}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">{la}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>{desc}</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="EUR">{p}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>""" for i, (desc, q, p, la) in enumerate(lines))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
  <cbc:ID>{num}</cbc:ID>
  <cbc:IssueDate>{d}</cbc:IssueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>{po_block}
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyTaxScheme><cbc:CompanyID>{vat}</cbc:CompanyID>
      <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>
    <cac:PartyLegalEntity><cbc:RegistrationName>{seller}</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyLegalEntity><cbc:RegistrationName>Handelshaus Sued GmbH</cbc:RegistrationName></cac:PartyLegalEntity>
  </cac:Party></cac:AccountingCustomerParty>
  <cac:PaymentMeans><cbc:PaymentMeansCode>58</cbc:PaymentMeansCode>
    <cac:PayeeFinancialAccount><cbc:ID>{iban_}</cbc:ID></cac:PayeeFinancialAccount>
  </cac:PaymentMeans>
  <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">{tax}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="EUR">{net}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="EUR">{tax}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>{rate}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="EUR">{net}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="EUR">{net}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">{gross}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">{gross}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>{items}
</Invoice>"""


def cii(num, d_yyyymmdd, seller, vat, iban_, lines, net, tax, gross, rate=19, po=None):
    po_block = (f"\n      <ram:BuyerOrderReferencedDocument>"
                f"<ram:IssuerAssignedID>{po}</ram:IssuerAssignedID>"
                f"</ram:BuyerOrderReferencedDocument>" if po else "")
    items = "".join(f"""
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument><ram:LineID>{i+1}</ram:LineID></ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct><ram:Name>{desc}</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>{p}</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="C62">{q}</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>{la}</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>""" for i, (desc, q, p, la) in enumerate(lines))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
 xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
 xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument>
    <ram:ID>{num}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">{d_yyyymmdd}</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>{items}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty><ram:Name>{seller}</ram:Name>
        <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{vat}</ram:ID></ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty><ram:Name>Handelshaus Sued GmbH</ram:Name></ram:BuyerTradeParty>{po_block}
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>
        <ram:PayeePartyCreditorFinancialAccount><ram:IBANID>{iban_}</ram:IBANID></ram:PayeePartyCreditorFinancialAccount>
      </ram:SpecifiedTradeSettlementPaymentMeans>
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{tax}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>{net}</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>{rate}</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{net}</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount>{net}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">{tax}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{gross}</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""


def simple_pdf(lines: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for ln in lines:
        pdf.cell(0, 8, ln, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def main() -> None:
    # s1: UBL, konsistent (600 + 114 = 714), bekannter Lieferant
    (OUT / "s1_xrechnung_ubl_ok.xml").write_text(ubl(
        "RE-2026-0815", "2026-07-20", "Alpha Buero GmbH", "DE136695976",
        "DE89370400440532013000",
        [("Kopierpapier A4", 10, "45.00", "450.00"), ("Toner schwarz", 5, "30.00", "150.00")],
        "600.00", "114.00", "714.00", po="PO-4711"))

    # s2: CII, Positionssumme 600 != Netto 650, USt falsch gerechnet
    (OUT / "s2_xrechnung_cii_summenfehler.xml").write_text(cii(
        "BL-77113", "20260722", "Beta Logistik AG", "DE811907980",
        "DE02120300000000202051",
        [("Palettentransport", 4, "100.00", "400.00"), ("Express-Zuschlag", 1, "200.00", "200.00")],
        "650.00", "123.50", "773.50", po="PO-4720"))

    # s3: ZUGFeRD-PDF — CII konsistent, aber IBAN weicht von Stammdaten ab
    xml3 = cii("GIT-2026-442", "20260718", "Gamma IT Services GmbH", "DE129273398",
               "DE02120300000000202051",   # Stammdaten: DE75512108001245126199!
               [("Consulting Juli", 8, "150.00", "1200.00")],
               "1200.00", "228.00", "1428.00", po="PO-4733")
    visual = simple_pdf([
        "Gamma IT Services GmbH", "Rechnung GIT-2026-442  Datum: 18.07.2026",
        "Consulting Juli: 1.200,00 EUR netto", "USt 19%: 228,00 EUR",
        "Gesamtbetrag: 1.428,00 EUR",
        "NEU: Bitte auf IBAN DE02 1203 0000 0000 2020 51 zahlen"])
    writer = PdfWriter(clone_from=io.BytesIO(visual))
    writer.add_attachment("factur-x.xml", xml3.encode())
    with (OUT / "s3_zugferd_iban_geaendert.pdf").open("wb") as f:
        writer.write(f)

    # s4: UBL, konsistent, aber 24.990 EUR brutto (über Dunkelbuchungsgrenze)
    (OUT / "s4_xrechnung_ubl_grossbetrag.xml").write_text(ubl(
        "DA-10077", "2026-07-24", "Delta Anlagenbau GmbH", "DE111111125",
        "DE27100777770209299700",
        [("Foerderband Modul B", 1, "21000.00", "21000.00")],
        "21000.00", "3990.00", "24990.00", po="PO-4750"))

    # s5: exakte Wiederholung von s1 unter neuem Dateinamen -> Dublette
    (OUT / "s5_xrechnung_ubl_dublette.xml").write_text(ubl(
        "RE-2026-0815", "2026-07-20", "Alpha Buero GmbH", "DE136695976",
        "DE89370400440532013000",
        [("Kopierpapier A4", 10, "45.00", "450.00"), ("Toner schwarz", 5, "30.00", "150.00")],
        "600.00", "114.00", "714.00", po="PO-4711"))

    # s6: PDF ohne eingebettetes XML (Altbeleg) -> Fallback-Extraktion
    (OUT / "s6_scan_ohne_xml.pdf").write_bytes(simple_pdf([
        "Omega Catering Service",
        "Rechnungsnummer: OC-889", "Datum: 15.07.2026",
        "Mittagsverpflegung Workshop, 20 Personen",
        "Nettobetrag: 89,90 EUR", "USt 19%: 17,08 EUR", "Bruttobetrag: 106,98 EUR",
        "IBAN: DE89 3704 0044 0532 0130 00"]))

    # s7: UBL, in sich konsistent, aber Netto 600 über Bestellwert 500 + 2 % Toleranz
    #     -> REVIEW (2-/3-Way-Match schlägt an: Preis-/Mengenabweichung)
    (OUT / "s7_xrechnung_ubl_po_abweichung.xml").write_text(ubl(
        "RE-2026-0900", "2026-07-27", "Alpha Buero GmbH", "DE136695976",
        "DE89370400440532013000",
        [("Bueromoebel Nachlieferung", 4, "150.00", "600.00")],
        "600.00", "114.00", "714.00", po="PO-4761"))

    print("7 Beispielrechnungen erzeugt ->", OUT)


if __name__ == "__main__":
    main()
