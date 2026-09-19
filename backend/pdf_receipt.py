"""ARMENTA OS — Server-side PDF receipt renderer.

Uses the official ARMENTA'S MOTORS brand assets (hex-A brand mark + primary
wordmark) rendered as embedded raster images, plus a red folio pill,
itemized table, totals block, signature lines and footer.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ASSETS_DIR = Path(__file__).parent / "assets"
WORDMARK_PATH = ASSETS_DIR / "armenta_wordmark.png"
HEX_PATH = ASSETS_DIR / "armenta_hex.png"

# Palette (aligned with UI)
BG_WHITE = colors.HexColor("#ffffff")
INK = colors.HexColor("#0a0a0a")
INK_SOFT = colors.HexColor("#27272a")
MUTED = colors.HexColor("#71717a")
LIGHT = colors.HexColor("#a1a1aa")
RULE = colors.HexColor("#e4e4e7")
RED = colors.HexColor("#dc2626")
RED_DARK = colors.HexColor("#991b1b")
RED_TINT = colors.HexColor("#fef2f2")
GREEN_TINT = colors.HexColor("#f0fdf4")
GREEN_TEXT = colors.HexColor("#166534")


def _fmt_money(amount: float, currency: str = "MXN") -> str:
    try:
        val = float(amount or 0)
    except Exception:
        val = 0.0
    return f"${val:,.2f} {currency}"


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        s = iso.replace("Z", "+00:00") if isinstance(iso, str) else iso
        d = datetime.fromisoformat(s) if isinstance(s, str) else s
        return d.strftime("%d %b %Y")
    except Exception:
        return str(iso)[:10]


def _draw_hex_mark(c: canvas.Canvas, cx: float, cy: float, r: float):
    """Draw the official hex-A brand mark image centered at (cx, cy)."""
    try:
        img = ImageReader(str(HEX_PATH))
        size = r * 2
        c.drawImage(img, cx - r, cy - r, width=size, height=size, mask="auto")
    except Exception:
        # Fallback: solid red hex if asset is missing
        c.setFillColor(RED)
        c.circle(cx, cy, r, stroke=0, fill=1)


def _draw_wordmark(c: canvas.Canvas, x: float, y: float, width: float = 62 * mm):
    """Draw the official ARMENTA'S / MOTORS primary logo at (x, y) top-left anchor."""
    try:
        img = ImageReader(str(WORDMARK_PATH))
        iw, ih = img.getSize()
        aspect = ih / iw
        height = width * aspect
        c.drawImage(img, x, y - height, width=width, height=height, mask="auto")
    except Exception:
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, y - 8 * mm, "ARMENTA'S MOTORS")


def build_receipt_pdf(doc: dict, settings: dict, kind: str = "servicio", photos: Optional[list] = None) -> bytes:
    """Render receipt PDF and return bytes.

    photos: optional list of {"bytes": <png/jpg bytes>, "caption": str} to be
    appended as evidence annex pages (2x2 grid per page)."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    page_w, page_h = LETTER
    margin_x = 18 * mm
    x = margin_x
    y = page_h - 22 * mm

    is_quote = kind == "cotizacion"
    currency = (settings or {}).get("currency") or "MXN"

    # ------------------- Header -------------------
    _draw_hex_mark(c, x + 10 * mm, y - 10 * mm, 10 * mm)
    _draw_wordmark(c, x + 24 * mm, y - 2 * mm, width=58 * mm)

    # Company meta
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    meta_y = y - 26 * mm
    for line in [
        settings.get("company_address"),
        f"Tel. {settings.get('company_phone')}" if settings.get("company_phone") else None,
        settings.get("company_email"),
        f"RFC: {settings.get('company_rfc')}" if settings.get("company_rfc") else None,
    ]:
        if line:
            c.drawString(x + 24 * mm, meta_y, line.upper())
            meta_y -= 3.4 * mm

    # Folio pill (top right)
    pill_w = 58 * mm
    pill_h = 22 * mm
    pill_x = page_w - margin_x - pill_w
    pill_y = y - pill_h
    c.setStrokeColor(RED)
    c.setLineWidth(1.2)
    c.setFillColor(RED_TINT)
    c.roundRect(pill_x, pill_y, pill_w, pill_h, 3 * mm, stroke=1, fill=1)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(pill_x + pill_w - 4 * mm, pill_y + pill_h - 6 * mm,
                       "COTIZACIÓN" if is_quote else "ORDEN DE SERVICIO")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawRightString(pill_x + pill_w - 4 * mm, pill_y + pill_h - 14 * mm, doc.get("folio", "—"))
    status = doc.get("status", "")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawRightString(pill_x + pill_w - 4 * mm, pill_y + 4 * mm, status.upper())

    # Divider
    y = pill_y - 6 * mm
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(x, y, page_w - margin_x, y)
    y -= 8 * mm

    # ------------------- Client / Vehicle / Date grid -------------------
    col_w = (page_w - 2 * margin_x) / 3
    client = doc.get("client") or {}
    vehicle = doc.get("vehicle") or {}
    technician = doc.get("technician") or {}

    def _col(cx_local, label, value, subs=None):
        c.setFillColor(LIGHT)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(cx_local, y, label.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(cx_local, y - 5 * mm, str(value or "—"))
        if subs:
            c.setFillColor(INK_SOFT)
            c.setFont("Helvetica", 8.5)
            for i, s in enumerate(subs):
                if s:
                    c.drawString(cx_local, y - (10 + i * 4) * mm, str(s))

    _col(x, "Emitido para", client.get("nombre"), [
        client.get("telefono"),
        client.get("email"),
        client.get("direccion"),
    ])
    veh_line = " ".join([str(vehicle.get("year") or ""), vehicle.get("make") or "", vehicle.get("model") or ""]).strip() or "—"
    _col(x + col_w, "Unidad", veh_line, [
        f"VIN: {vehicle.get('vin')}" if vehicle.get("vin") else None,
        f"Placas: {vehicle.get('plates')}" if vehicle.get("plates") else None,
        f"KM: {vehicle.get('mileage'):,}" if vehicle.get("mileage") not in (None, "") else None,
    ] if vehicle else None)

    date_subs = []
    if is_quote and doc.get("expires_at"):
        date_subs.append(f"Vigencia: {_fmt_date(doc.get('expires_at'))}")
    if technician.get("name"):
        date_subs.append(f"Técnico: {technician['name']}")
    _col(x + 2 * col_w, "Fecha", _fmt_date(doc.get("created_at")), date_subs)

    y -= 30 * mm

    # ------------------- Items table -------------------
    tbl_top = y
    header_h = 8 * mm
    # header
    c.setFillColor(INK)
    c.rect(x, tbl_top - header_h, page_w - 2 * margin_x, header_h, stroke=0, fill=1)
    c.setFillColor(BG_WHITE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 3 * mm, tbl_top - 5.5 * mm, "CONCEPTO")
    c.drawRightString(x + col_w * 3 - 46 * mm, tbl_top - 5.5 * mm, "CANT.")
    c.drawRightString(x + col_w * 3 - 22 * mm, tbl_top - 5.5 * mm, "PRECIO UNIT.")
    c.drawRightString(page_w - margin_x - 3 * mm, tbl_top - 5.5 * mm, "IMPORTE")

    # rows
    row_y = tbl_top - header_h - 6 * mm
    items = doc.get("items") or []
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.5)
    if not items:
        c.setFillColor(LIGHT)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(page_w / 2, row_y - 4 * mm, "Sin conceptos registrados")
        row_y -= 10 * mm
    else:
        for it in items:
            desc = it.get("description", "")
            qty = it.get("quantity", 0) or 0
            unit = it.get("unit_price", 0) or 0
            amount = qty * unit
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9.5)
            # wrap description
            max_desc_w = col_w * 3 - 70 * mm
            desc_lines = _wrap(c, desc, "Helvetica-Bold", 9.5, max_desc_w)
            for i, line in enumerate(desc_lines[:2]):
                c.drawString(x + 3 * mm, row_y - i * 4 * mm, line)
            if it.get("is_labor"):
                c.setFont("Helvetica-Bold", 6.5)
                c.setFillColor(RED)
                c.drawString(x + 3 * mm, row_y - (len(desc_lines[:2])) * 4 * mm - 2 * mm, "MANO DE OBRA")
                c.setFillColor(INK)
            c.setFont("Helvetica", 9.5)
            c.drawRightString(x + col_w * 3 - 46 * mm, row_y, f"{qty:g}")
            c.drawRightString(x + col_w * 3 - 22 * mm, row_y, _fmt_money(unit, currency))
            c.setFont("Helvetica-Bold", 9.5)
            c.drawRightString(page_w - margin_x - 3 * mm, row_y, _fmt_money(amount, currency))
            row_height = 7 * mm + (len(desc_lines[:2]) - 1) * 4 * mm + (3 * mm if it.get("is_labor") else 0)
            row_y -= row_height
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(x, row_y + 2 * mm, page_w - margin_x, row_y + 2 * mm)

    # ------------------- Totals block -------------------
    totals_w = 74 * mm
    totals_x = page_w - margin_x - totals_w
    ty = row_y - 4 * mm

    def _totals_row(label, value, big=False, tone=None):
        nonlocal ty
        if tone == "grand":
            c.setFillColor(INK)
            c.roundRect(totals_x, ty - 9 * mm, totals_w, 9 * mm, 2 * mm, stroke=0, fill=1)
            c.setFillColor(RED)
            c.rect(totals_x, ty - 9 * mm, 2 * mm, 9 * mm, stroke=0, fill=1)
            c.setFillColor(BG_WHITE)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(totals_x + 6 * mm, ty - 5.8 * mm, label)
            c.setFont("Helvetica-Bold", 11)
            c.drawRightString(totals_x + totals_w - 3 * mm, ty - 5.8 * mm, value)
            ty -= 11 * mm
        elif tone in ("outstanding", "settled"):
            bg = RED_TINT if tone == "outstanding" else GREEN_TINT
            fg = RED_DARK if tone == "outstanding" else GREEN_TEXT
            c.setFillColor(bg)
            c.setStrokeColor(fg)
            c.setLineWidth(0.6)
            c.roundRect(totals_x, ty - 7 * mm, totals_w, 7 * mm, 1.5 * mm, stroke=1, fill=1)
            c.setFillColor(fg)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(totals_x + 4 * mm, ty - 4.8 * mm, label)
            c.drawRightString(totals_x + totals_w - 3 * mm, ty - 4.8 * mm, value)
            ty -= 9 * mm
        else:
            c.setFillColor(INK_SOFT)
            c.setFont("Helvetica", 9)
            c.drawString(totals_x + 2 * mm, ty, label)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(totals_x + totals_w - 3 * mm, ty, value)
            ty -= 5 * mm

    tax_rate = doc.get("tax_rate", 0) or 0
    _totals_row("Subtotal", _fmt_money(doc.get("subtotal", 0), currency))
    _totals_row(f"IVA ({round(tax_rate * 100)}%)", _fmt_money(doc.get("tax", 0), currency))
    _totals_row("Total a pagar", _fmt_money(doc.get("total", 0), currency), tone="grand")
    if not is_quote:
        _totals_row("Pagado", _fmt_money(doc.get("paid", 0), currency))
        balance = doc.get("balance", 0) or 0
        _totals_row("Saldo pendiente", _fmt_money(balance, currency),
                    tone="outstanding" if balance > 0.001 else "settled")

    # ------------------- Notes -------------------
    notes = doc.get("notes")
    recos = doc.get("recommendations") if not is_quote else None
    notes_y = min(ty, row_y) - 6 * mm

    def _paragraph(label, text):
        nonlocal notes_y
        if not text:
            return
        c.setFillColor(LIGHT)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 3 * mm, notes_y, label.upper())
        c.setFillColor(INK_SOFT)
        c.setFont("Helvetica", 9)
        wrap_w = page_w - 2 * margin_x - 6 * mm
        for line in _wrap(c, text, "Helvetica", 9, wrap_w)[:6]:
            notes_y -= 4 * mm
            c.drawString(x + 3 * mm, notes_y, line)
        notes_y -= 6 * mm

    if notes or recos:
        c.setFillColor(colors.HexColor("#fafafa"))
        c.setStrokeColor(RED)
        c.setLineWidth(0)
        c.rect(x, notes_y + 4 * mm, 2, 1, stroke=0, fill=1)  # just to draw stripe below

    _paragraph("Notas", notes)
    _paragraph("Recomendaciones", recos)

    # ------------------- Signatures -------------------
    sig_y = 40 * mm
    sig_w = (page_w - 2 * margin_x - 20 * mm) / 2
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.5)
    c.line(x, sig_y, x + sig_w, sig_y)
    c.line(x + sig_w + 20 * mm, sig_y, x + sig_w * 2 + 20 * mm, sig_y)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x + sig_w / 2, sig_y - 4 * mm, "FIRMA / AUTORIZACIÓN")
    c.drawCentredString(x + sig_w + 20 * mm + sig_w / 2, sig_y - 4 * mm,
                        f"CLIENTE / {(client.get('nombre') or '').upper()}")

    # ------------------- Footer -------------------
    c.setStrokeColor(RULE)
    c.line(x, 22 * mm, page_w - margin_x, 22 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    footer_note = settings.get("footer_note") or "Gracias por confiar en ARMENTA'S MOTORS."
    for i, line in enumerate(_wrap(c, footer_note, "Helvetica", 7, page_w - 2 * margin_x)[:2]):
        c.drawCentredString(page_w / 2, 18 * mm - i * 3.2 * mm, line)

    c.showPage()

    # ------------------- Evidence annex (photos) -------------------
    if photos:
        page_w, page_h = LETTER
        margin_x = 18 * mm
        page_num = 0
        for i in range(0, len(photos), 4):
            page_num += 1
            batch = photos[i:i + 4]
            # Header
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin_x, page_h - 20 * mm, "EVIDENCIAS DEL SERVICIO")
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(margin_x, page_h - 26 * mm,
                         f"Folio {doc.get('folio', '')}  ·  Página {page_num} de {(len(photos) + 3) // 4}")
            c.setStrokeColor(RED)
            c.setLineWidth(1.2)
            c.line(margin_x, page_h - 29 * mm, page_w - margin_x, page_h - 29 * mm)

            # 2x2 grid
            cell_w = (page_w - 2 * margin_x - 6 * mm) / 2
            cell_h = (page_h - 60 * mm - 6 * mm) / 2
            grid_top = page_h - 34 * mm
            for j, photo in enumerate(batch):
                col = j % 2
                row = j // 2
                cx = margin_x + col * (cell_w + 6 * mm)
                cy = grid_top - (row + 1) * cell_h - row * 6 * mm
                c.setStrokeColor(RULE)
                c.setLineWidth(0.6)
                c.roundRect(cx, cy, cell_w, cell_h, 2 * mm, stroke=1, fill=0)
                try:
                    img = ImageReader(BytesIO(photo["bytes"]))
                    iw, ih = img.getSize()
                    # Fit inside cell keeping aspect
                    pad = 3 * mm
                    fit_w = cell_w - 2 * pad
                    fit_h = cell_h - 10 * mm  # leave room for caption
                    scale = min(fit_w / iw, fit_h / ih)
                    draw_w = iw * scale
                    draw_h = ih * scale
                    dx = cx + (cell_w - draw_w) / 2
                    dy = cy + cell_h - 7 * mm - draw_h
                    c.drawImage(img, dx, dy, width=draw_w, height=draw_h, mask="auto")
                except Exception:
                    c.setFillColor(LIGHT)
                    c.setFont("Helvetica-Oblique", 8)
                    c.drawCentredString(cx + cell_w / 2, cy + cell_h / 2, "Imagen no disponible")
                # Caption
                caption = str(photo.get("caption") or "")[:80]
                if caption:
                    c.setFillColor(INK_SOFT)
                    c.setFont("Helvetica", 7)
                    c.drawString(cx + 3 * mm, cy + 4 * mm, caption)

            # Footer
            c.setStrokeColor(RULE)
            c.line(margin_x, 22 * mm, page_w - margin_x, 22 * mm)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7)
            footer_note = settings.get("footer_note") or "Armenta's Motors Company"
            c.drawCentredString(page_w / 2, 18 * mm, footer_note)
            c.showPage()

    c.save()
    return buf.getvalue()


def _wrap(c: canvas.Canvas, text: str, font: str, size: float, max_w: float):
    if not text:
        return [""]
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        candidate = w if not cur else cur + " " + w
        if c.stringWidth(candidate, font, size) <= max_w:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]
