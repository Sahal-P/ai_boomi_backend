"""Synthetic Google Pay-style statements for tests: invented names, banks and UPI IDs only.

A minimal hand-written PDF in Helvetica laid out like the real statement's columns. The rupee sign
is drawn with a spare code that a ToUnicode map reads back as ₹, so text extraction sees what a real
statement gives.
"""

from dataclasses import dataclass, field

TO_UNICODE = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
1 beginbfrange
<20> <7E> <0020>
endbfrange
1 beginbfchar
<80> <20B9>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""
NOTE = (
    "Note: This statement reflects payments made by you on the Google Pay app. Self transfer "
    "payments are not included in the total money paid and"
)
NOTE_2 = (
    "received. Any payments transactions and activity deleted from your Google Account will not "
    "show up in this statement."
)


def _text(value: str) -> bytes:
    out = bytearray()
    for char in value:
        if char == "₹":
            out += b"\\200"
        elif char in "()\\":
            out += b"\\" + char.encode()
        else:
            out += char.encode("ascii")
    return bytes(out)


def pdf_document(pages: list[list[tuple[float, float, float, str]]]) -> bytes:
    """Pages of (x, y, size, text) runs on an A4 page."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # the page tree, once page numbers are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding "
        b"/ToUnicode 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(TO_UNICODE) + TO_UNICODE + b"\nendstream",
    ]
    kids = []
    for runs in pages:
        content = b"\n".join(
            b"BT /F1 %.1f Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET" % (size, x, y, _text(text))
            for x, y, size, text in runs
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        content_id = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content_id
        )
        kids.append(len(objects))
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % kid for kid in kids),
        len(kids),
    )
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


@dataclass
class Row:
    date: str = "01 Apr,"
    time: str = "10:42 AM"
    details: list[str] = field(default_factory=lambda: ["Paid to Asha Stores"])
    upi: str = "100000000001"
    account: str = "Paid by Sample Bank 1234"
    amount: list[str] = field(default_factory=lambda: ["₹315"])
    year: str = "2026"


def statement_pdf(
    pages: list[list[Row]],
    *,
    period: str = "01 April 2026 - 30 April 2026",
    sent: str = "₹0",
    received: str = "₹0",
    phone: str = "9000000001",
    numbering: list[tuple[int, int]] | None = None,
    title: str = "Transaction statement",
    note: str = NOTE,
) -> bytes:
    """A statement with these rows per page; totals are printed as given, not computed."""
    drawn = []
    for index, rows in enumerate(pages):
        runs: list[tuple[float, float, float, str]] = [
            (447.9, 806.1, 12, title),
            (322.2, 789.9, 12, f"{phone},"),
            (322.1, 773.5, 12, "someone@example.invalid"),
        ]
        header = 611.0 if index == 0 else 718.0
        if index == 0:
            runs += [
                (24.3, 694.0, 12, "Transaction statement period"),
                (327.6, 694.0, 12, "Sent"),
                (487.8, 694.0, 12, "Received"),
                (24.6, 677.0, 12, period),
                (306.8, 677.0, 12, sent),
                (477.6, 677.0, 12, received),
            ]
        runs += [
            (24.8, header, 9, "Date &"),
            (536.8, header, 9, "Amoun"),
            (104.4, header - 5.7, 9, "Transaction details"),
            (24.3, header - 11.9, 9, "time"),
            (537.0, header - 13.0, 9, "t"),
        ]
        top = header - 41
        for row in rows:
            runs += [
                (24.5, top, 9, row.date),
                (24.4, top - 11, 9, row.year),
                (24.4, top - 22, 9, row.time),
            ]
            lines = [*row.details, f"UPI Transaction ID: {row.upi}", row.account]
            runs += [(104.9, top - 15 * offset, 9, line) for offset, line in enumerate(lines)]
            runs += [(540.0, top - 11 * offset, 9, part) for offset, part in enumerate(row.amount)]
            top -= 15 * len(lines) + 6
        page, total = numbering[index] if numbering else (index + 1, len(pages))
        runs += [
            (24.7, 66.0, 8, note),
            (24.6, 56.0, 8, NOTE_2),
            (270.0, 20.0, 8, f"Page {page} of {total}"),
        ]
        drawn.append(runs)
    return pdf_document(drawn)
