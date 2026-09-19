"""ARMENTA OS — Simple, clean PDF documents (cotización / orden / nota / recibo de pago)."""
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

INK = colors.HexColor("#111111")
BLACK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
GRID = colors.HexColor("#8a8a8a")
CELL = colors.HexColor("#d9d9d9")
WHITE = colors.white
RED = colors.HexColor("#dc2626")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
METHODS = {"cash": "Efectivo", "transfer": "Transferencia", "card": "Tarjeta", "other": "Otro"}

TITLES = {"cotizacion": "COTIZACIÓN DE SERVICIO", "servicio": "ORDEN DE SERVICIO", "nota": "NOTA DE REMISIÓN", "pago": "RECIBO DE PAGO"}


def _money(v, cur="MXN"):
    try:
        return f"${float(v or 0):,.2f} {cur}"
    except Exception:
        return f"$0.00 {cur}"


def _date(iso) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")) if isinstance(iso, str) else iso
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    except Exception:
        return str(iso)[:10]


def _wrap(c, text, font, size, max_w):
    words = str(text or "").split()
    lines, cur = [], ""
    for w in words:
        cand = w if not cur else f"{cur} {w}"
        if c.stringWidth(cand, font, size) <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _header(c, settings, title, page_w, x, y):
    """Black logo box + company name + tagline + document title. Returns new y."""
    box_w, box_h = 76 * mm, 40 * mm
    bx = (page_w - box_w) / 2
    c.setFillColor(BLACK)
    c.rect(bx, y - box_h, box_w, box_h, stroke=0, fill=1)
    try:
        img = ImageReader(str(WORDMARK_PATH))
        iw, ih = img.getSize()
        lw = box_w - 12 * mm
        lh = lw * ih / iw
        if lh > box_h - 6 * mm:
            lh = box_h - 6 * mm
            lw = lh * iw / ih
        c.drawImage(img, bx + (box_w - lw) / 2, y - box_h + (box_h - lh) / 2, width=lw, height=lh, mask="auto")
    except Exception:
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_w / 2, y - box_h / 2, "ARMENTA'S MOTORS")
    y -= box_h + 8 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, y, (settings.get("company_name") or "ARMENTA'S MOTORS").upper())
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, "Servicio Automotriz Profesional a Domicilio")
    y -= 5 * mm
    meta = " · ".join(v for v in [settings.get("company_address"), f"Tel. {settings['company_phone']}" if settings.get("company_phone") else None, settings.get("company_email")] if v)
    if meta:
        c.drawString(x, y, meta)
        y -= 5 * mm
    if settings.get("company_rfc"):
        c.drawString(x, y, f"RFC: {settings['company_rfc']}")
        y -= 5 * mm
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, title)
    return y - 8 * mm


def _kv_table(c, rows, x, y, w, label_w=58 * mm, row_h=7 * mm):
    c.setLineWidth(0.6)
    for k, v in rows:
        c.setStrokeColor(GRID)
        c.setFillColor(CELL)
        c.rect(x, y - row_h, w, row_h, stroke=1, fill=1)
        c.line(x + label_w, y, x + label_w, y - row_h)
        c.setFillColor(INK)
        c.setFont("Helvetica", 9.5)
        c.drawString(x + 3 * mm, y - row_h + 3 * mm, f"{k}:")
        c.drawString(x + label_w + 3 * mm, y - row_h + 3 * mm, str(v or "—"))
        y -= row_h
    return y


def _items_table(c, items, cur, x, y, w):
    cols = [("SERVICIO", 0.30, "left"), ("DESCRIPCIÓN", 0.44, "left"), ("CANT.", 0.08, "center"), ("PRECIO", 0.18, "right")]
    head_h = 9 * mm
    c.setFillColor(BLACK)
    c.rect(x, y - head_h, w, head_h, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 9)
    cx = x
    for name, frac, align in cols:
        cw = w * frac
        if align == "right":
            c.drawRightString(cx + cw - 3 * mm, y - head_h + 3.2 * mm, name)
        elif align == "center":
            c.drawCentredString(cx + cw / 2, y - head_h + 3.2 * mm, name)
        else:
            c.drawString(cx + 3 * mm, y - head_h + 3.2 * mm, name)
        cx += cw
    y -= head_h
    if not items:
        items = [{"description": "Sin conceptos registrados", "quantity": 0, "unit_price": 0}]
    for it in items:
        name = str(it.get("description", ""))
        detail = "Mano de obra" if it.get("is_labor") else "Refacciones / materiales"
        if it.get("detail"):
            detail = str(it["detail"])
        l1 = _wrap(c, name, "Helvetica", 9.5, w * 0.30 - 6 * mm)[:3]
        l2 = _wrap(c, detail, "Helvetica", 9.5, w * 0.44 - 6 * mm)[:3]
        n = max(len(l1), len(l2))
        row_h = 4.5 * mm * n + 4.5 * mm
        c.setStrokeColor(GRID)
        c.setFillColor(CELL)
        c.rect(x, y - row_h, w, row_h, stroke=1, fill=1)
        cx = x
        for _, frac, _ in cols[:-1]:
            cx += w * frac
            c.line(cx, y, cx, y - row_h)
        c.setFillColor(INK)
        c.setFont("Helvetica", 9.5)
        ty = y - 6.5 * mm
        for i in range(n):
            if i < len(l1):
                c.drawString(x + 3 * mm, ty - i * 4.5 * mm, l1[i])
            if i < len(l2):
                c.drawString(x + w * 0.30 + 3 * mm, ty - i * 4.5 * mm, l2[i])
        qty = it.get("quantity", 0) or 0
        c.drawCentredString(x + w * 0.74 + w * 0.08 / 2, ty, f"{qty:g}")
        c.drawRightString(x + w - 3 * mm, ty, _money((qty or 0) * (it.get("unit_price", 0) or 0), cur))
        y -= row_h
    return y


def _totals_table(c, rows, x, y, w, value_w=42 * mm, row_h=8 * mm):
    for label, value, dark in rows:
        c.setStrokeColor(GRID)
        c.setLineWidth(0.6)
        c.setFillColor(BLACK if dark else CELL)
        c.rect(x, y - row_h, w, row_h, stroke=1, fill=1)
        c.setFillColor(WHITE if dark else INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 3 * mm, y - row_h + 3.2 * mm, label)
        c.drawRightString(x + w - 3 * mm, y - row_h + 3.2 * mm, value)
        y -= row_h
    return y


def _bullets(c, title, lines, x, y, w):
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, title)
    y -= 7 * mm
    c.setFont("Helvetica", 9.5)
    for line in lines:
        for i, sub in enumerate(_wrap(c, line, "Helvetica", 9.5, w - 6 * mm)[:3]):
            c.drawString(x, y, ("• " if i == 0 else "   ") + sub)
            y -= 4.8 * mm
    return y


def _ensure(c, settings, y, needed, page_w, page_h, margin_x):
    """Start a new page (with footer on the current one) if `needed` mm won't fit."""
    if y - needed < 30 * mm:
        _footer(c, settings, page_w, margin_x)
        c.showPage()
        return page_h - 22 * mm
    return y


def _footer(c, settings, page_w, margin_x):
    survey_url = (settings.get("survey_url") or "").strip()
    if survey_url:
        from reportlab.graphics.barcode import qr as _qr
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        qsize = 18 * mm
        widget = _qr.QrCodeWidget(survey_url)
        bx, by, bw, bh = widget.getBounds()
        d = Drawing(qsize, qsize, transform=[qsize / (bw - bx), 0, 0, qsize / (bh - by), 0, 0])
        d.add(widget)
        qx = page_w - margin_x - qsize
        renderPDF.draw(d, c, qx, 14 * mm)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(qx - 3 * mm, 26 * mm, "¿Cómo fue tu servicio?")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawRightString(qx - 3 * mm, 22 * mm, "Escanea el código y califícanos en 1 minuto.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    note = settings.get("footer_note") or "Gracias por confiar en ARMENTA'S MOTORS."
    for i, line in enumerate(_wrap(c, note, "Helvetica", 7.5, page_w * 0.55)[:2]):
        c.drawString(margin_x, 18 * mm - i * 3.5 * mm, line)


def build_receipt_pdf(doc: dict, settings: dict, kind: str = "servicio", photos: Optional[list] = None) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    page_w, page_h = LETTER
    margin_x = 20 * mm
    x, w = margin_x, page_w - 2 * margin_x
    cur = settings.get("currency") or "MXN"
    is_quote = kind == "cotizacion"

    y = _header(c, settings, TITLES.get(kind, "DOCUMENTO"), page_w, x, page_h - 18 * mm)

    client = doc.get("client") or {}
    vehicle = doc.get("vehicle") or {}
    veh_line = " ".join(str(v) for v in (vehicle.get("make"), vehicle.get("model"), vehicle.get("year")) if v)
    rows = [("Folio", doc.get("folio")), ("Fecha", _date(doc.get("created_at"))), ("Cliente", client.get("nombre"))]
    if client.get("telefono"):
        rows.append(("Teléfono", client.get("telefono")))
    if veh_line:
        rows.append(("Vehículo", veh_line))
    if vehicle.get("engine"):
        rows.append(("Motor", vehicle.get("engine")))
    if vehicle.get("plates"):
        rows.append(("Placas", vehicle.get("plates")))
    if kind == "servicio" and (doc.get("technician") or {}).get("name"):
        rows.append(("Técnico", doc["technician"]["name"]))
    if is_quote and doc.get("expires_at"):
        rows.append(("Vigencia", _date(doc.get("expires_at"))))
    y = _kv_table(c, rows, x + 8 * mm, y, w - 16 * mm)

    y -= 8 * mm
    y = _ensure(c, settings, y, 36 * mm, page_w, page_h, margin_x)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, "DETALLE DE SERVICIOS")
    y -= 6 * mm
    y = _items_table(c, doc.get("items") or [], cur, x, y, w)

    tax_rate = doc.get("tax_rate", 0) or 0
    totals = [("SUBTOTAL:", _money(doc.get("subtotal"), cur), False),
              (f"IVA ({round(tax_rate * 100)}%):", _money(doc.get("tax"), cur), False),
              ("TOTAL:", _money(doc.get("total"), cur), True)]
    if kind == "servicio":
        totals += [("PAGADO:", _money(doc.get("paid"), cur), False), ("SALDO PENDIENTE:", _money(doc.get("balance"), cur), False)]
    if kind == "nota":
        totals += [("PAGADO:", _money(doc.get("paid_amount"), cur), False), ("SALDO PENDIENTE:", _money(doc.get("balance"), cur), False)]
    y -= 6 * mm
    y = _ensure(c, settings, y, len(totals) * 8 * mm + 4 * mm, page_w, page_h, margin_x)
    y = _totals_table(c, totals, x, y, w)

    pays = doc.get("payments") or []
    if kind == "servicio" and pays:
        y -= 9 * mm
        y = _ensure(c, settings, y, (len(pays) + 2) * 8 * mm, page_w, page_h, margin_x)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(x, y, "PAGOS RECIBIDOS")
        y -= 6 * mm
        y = _kv_table(c, [(f"{p['folio']} · {_date(p.get('date'))}", f"{METHODS.get(p.get('method'), p.get('method'))} · {_money(p.get('amount'), cur)}") for p in pays], x, y, w, label_w=w * 0.5, row_h=7.5 * mm)

    y -= 9 * mm
    y = _ensure(c, settings, y, 28 * mm, page_w, page_h, margin_x)
    if is_quote:
        lines = [f"Cotización válida por {doc.get('valid_days') or 7} días.", "Servicio realizado por técnicos especializados.",
                 "Garantía limitada sobre mano de obra.", f"Precios expresados en {cur} e incluyen IVA."]
    elif kind == "nota":
        lines = ["Nota de remisión sin efectos fiscales.", "Garantía limitada sobre mano de obra.", f"Precios expresados en {cur} e incluyen IVA."]
    else:
        lines = ["Servicio realizado por técnicos especializados a domicilio.", "Garantía limitada sobre mano de obra.",
                 f"Precios expresados en {cur} e incluyen IVA."]
    y = _bullets(c, "CONDICIONES Y GARANTÍA", lines, x, y, w)

    for label, text in (("NOTAS", doc.get("notes")), ("RECOMENDACIONES", doc.get("recommendations") if kind == "servicio" else None)):
        if text:
            y -= 5 * mm
            y = _ensure(c, settings, y, 24 * mm, page_w, page_h, margin_x)
            y = _bullets(c, label, [text], x, y, w)

    _footer(c, settings, page_w, margin_x)
    c.showPage()

    if photos:
        for i in range(0, len(photos), 4):
            batch = photos[i:i + 4]
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin_x, page_h - 20 * mm, "EVIDENCIAS DEL SERVICIO")
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(margin_x, page_h - 26 * mm, f"Folio {doc.get('folio', '')}  ·  Página {i // 4 + 1} de {(len(photos) + 3) // 4}")
            c.setStrokeColor(BLACK)
            c.setLineWidth(1)
            c.line(margin_x, page_h - 29 * mm, page_w - margin_x, page_h - 29 * mm)
            cell_w = (w - 6 * mm) / 2
            cell_h = (page_h - 66 * mm) / 2
            grid_top = page_h - 34 * mm
            for j, photo in enumerate(batch):
                col, row = j % 2, j // 2
                cx = margin_x + col * (cell_w + 6 * mm)
                cy = grid_top - (row + 1) * cell_h - row * 6 * mm
                c.setStrokeColor(GRID)
                c.setLineWidth(0.6)
                c.rect(cx, cy, cell_w, cell_h, stroke=1, fill=0)
                try:
                    img = ImageReader(BytesIO(photo["bytes"]))
                    iw, ih = img.getSize()
                    scale = min((cell_w - 6 * mm) / iw, (cell_h - 10 * mm) / ih)
                    dw, dh = iw * scale, ih * scale
                    c.drawImage(img, cx + (cell_w - dw) / 2, cy + cell_h - 7 * mm - dh, width=dw, height=dh, mask="auto")
                except Exception:
                    c.setFillColor(MUTED)
                    c.setFont("Helvetica-Oblique", 8)
                    c.drawCentredString(cx + cell_w / 2, cy + cell_h / 2, "Imagen no disponible")
                caption = str(photo.get("caption") or "")[:80]
                if caption:
                    c.setFillColor(INK)
                    c.setFont("Helvetica", 7)
                    c.drawString(cx + 3 * mm, cy + 4 * mm, caption)
            _footer(c, settings, page_w, margin_x)
            c.showPage()

    c.save()
    return buf.getvalue()


def build_payment_receipt_pdf(p: dict, settings: dict) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    page_w, page_h = LETTER
    margin_x = 20 * mm
    x, w = margin_x, page_w - 2 * margin_x
    cur = settings.get("currency") or "MXN"
    client = p.get("client") or {}
    svc = p.get("service") or {}

    y = _header(c, settings, TITLES["pago"], page_w, x, page_h - 18 * mm)
    rows = [("Folio", p.get("folio")), ("Fecha", _date(p.get("date") or p.get("created_at"))), ("Cliente", client.get("nombre"))]
    if client.get("telefono"):
        rows.append(("Teléfono", client.get("telefono")))
    if svc:
        rows.append(("Orden de servicio", svc.get("folio")))
    if p.get("vehicle"):
        rows.append(("Vehículo", p["vehicle"]))
    rows.append(("Método de pago", METHODS.get(p.get("method"), p.get("method"))))
    if p.get("reference"):
        rows.append(("Referencia", p["reference"]))
    y = _kv_table(c, rows, x + 8 * mm, y, w - 16 * mm)

    y -= 8 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, "DETALLE DEL PAGO")
    y -= 6 * mm
    totals = [("MONTO RECIBIDO:", _money(p.get("amount"), cur), True)]
    if svc:
        totals = [("TOTAL DE LA ORDEN:", _money(svc.get("total"), cur), False), ("MONTO RECIBIDO:", _money(p.get("amount"), cur), True),
                  ("PAGADO ACUMULADO:", _money(svc.get("paid"), cur), False), ("SALDO PENDIENTE:", _money(svc.get("balance"), cur), False)]
    y = _totals_table(c, totals, x, y, w)

    if p.get("notes"):
        y -= 10 * mm
        y = _ensure(c, settings, y, 24 * mm, page_w, page_h, margin_x)
        y = _bullets(c, "NOTAS", [p["notes"]], x, y, w)

    y -= 9 * mm
    y = _ensure(c, settings, y, 24 * mm, page_w, page_h, margin_x)
    _bullets(c, "CONDICIONES", ["Este recibo comprueba el pago recibido por el monto indicado.",
                                f"Importes expresados en {cur}.", "Conserve este documento para cualquier aclaración."], x, y, w)
    _footer(c, settings, page_w, margin_x)
    c.showPage()
    c.save()
    return buf.getvalue()
