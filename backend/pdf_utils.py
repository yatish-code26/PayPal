"""FreightGuard PDF Document Utility
Generates clean, valid PDF documents for commercial dispute packets and audit reports.
Pure Python implementation producing standard PDF-1.4 documents without external dependencies.
"""
import io
from typing import Dict, Any, List
from backend.policy_engine import cents_to_dollars

def generate_dispute_pdf(dispute: Dict[str, Any], findings: List[Dict[str, Any]]) -> bytes:
    """Generates a formal, professional commercial dispute notice PDF."""
    invoice_num = dispute.get("invoice_number", "INV-UNKNOWN")
    carrier = dispute.get("carrier_name", "Carrier")
    disputed_cents = dispute.get("disputed_amount_cents", 0)
    disputed_str = cents_to_dollars(disputed_cents)
    credit_ref = dispute.get("credit_note_ref") or "PENDING"
    letter_text = dispute.get("dispute_letter_text", "Discrepancy notice issued pursuant to contracted Master Service Agreement.")

    # Escape parentheses and backslashes for PDF string literals
    def clean(s: str) -> str:
        return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = [
        "FREIGHTGUARD COMMERCIAL DISPUTE NOTICE",
        f"Notice ID: {clean(dispute.get('id', 'DISP-001'))}",
        f"Invoice Number: #{clean(invoice_num)}",
        f"Carrier: {clean(carrier)}",
        f"Total Disputed Amount: ${disputed_str} USD",
        f"Credit Note Reference: {clean(credit_ref)}",
        "----------------------------------------------------------------------",
        "EXECUTIVE SUMMARY & CONTRACTUAL CITATIONS:",
    ]

    for paragraph in letter_text.split("\n"):
        if paragraph.strip():
            # Wrap long lines simply
            p = paragraph.strip()
            while len(p) > 75:
                lines.append(clean(p[:75]))
                p = p[75:]
            lines.append(clean(p))

    lines.append("----------------------------------------------------------------------")
    lines.append("ITEMIZED DISCREPANCY FINDINGS & MATHEMATICAL PROOF:")

    for idx, f in enumerate(findings, 1):
        var_dlr = cents_to_dollars(f.get("variance_cents", 0))
        lines.append(f"{idx}. {clean(f.get('clause_citation', 'Contract Rule'))}: Flagged ${var_dlr}")
        lines.append(f"   Explanation: {clean(f.get('explanation', ''))[:70]}")

    lines.append("----------------------------------------------------------------------")
    lines.append("Payment Terms: Undisputed balance approved. Disputed balance held.")
    lines.append("Authorized by FreightGuard Autonomous Financial Control Engine.")

    # Construct minimal valid PDF-1.4 stream
    content_stream = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
    for l in lines:
        content_stream.append(f"({l}) '")
    content_stream.append("ET")
    stream_data = "\n".join(content_stream).encode("latin-1", errors="replace")

    objects = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    # 4: Contents
    objects.append(f"<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1") + stream_data + b"\nendstream")
    # 5: Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = []
    for idx, obj in enumerate(objects, 1):
        offsets.append(buf.tell())
        buf.write(f"{idx} 0 obj\n".encode("latin-1"))
        buf.write(obj)
        buf.write(b"\nendobj\n")

    xref_pos = buf.tell()
    buf.write(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode("latin-1"))

    buf.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1"))
    return buf.getvalue()

