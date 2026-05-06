from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4

# Palette proche du modèle officiel.
BORDER = colors.HexColor('#1f2d3d')
LIGHT_GREY = colors.HexColor('#eeeeee')
MEDIUM_GREY = colors.HexColor('#d7d7d7')
TEXT = colors.HexColor('#3f3f3f')

LAB_ADDRESS_DP = [
    'Rue Abou-Bakr Seddiq - Im Bahia (2ème Etage)',
    'Q.I. Ménara - 40020 MARRAKECH',
    'Tel./Fax : +212 (0) 5 24.43.86.98',
    'GSM : +212 (0) 6 80.58.75.02',
    'Mail : achats@laboratoire-2a2e.ma',
    'Web : www.laboratoire-2a2e.ma',
]

LAB_ADDRESS_BC = [
    'Rue Abou-Bakr Seddiq - Im Bahia (2ème Etage)',
    'Q.I. Ménara - 40020 MARRAKECH',
    'Tel./Fax : +212 (0) 5 24.43.86.98',
    'GSM : +212 (0) 6 80.58.75.02',
    'Mail : laboratoire2a2e@gmail.com',
    'Web : www.laboratoire2a2e.com',
]

FOOTER_LINES = [
    'LABORATOIRE 2A2E S.A.R.L',
    'RC : 55797 - Patente : 46296098 - IF : 06527613',
    'CNSS : 9426489 - ICE : 001458946000061',
]


def _fmt_date(value=None) -> str:
    if not value:
        value = date.today()
    return value.strftime('%d/%m/%Y') if hasattr(value, 'strftime') else str(value)


def _money(value) -> str:
    try:
        return f'{float(value or 0):,.2f}'.replace(',', ' ').replace('.', ',')
    except Exception:
        return '0,00'


def _qty(value) -> str:
    try:
        val = float(value or 0)
        return str(int(val)) if val.is_integer() else str(val).replace('.', ',')
    except Exception:
        return str(value or '')


def _value(obj, *names, default=''):
    for name in names:
        value = getattr(obj, name, None)
        if value not in (None, ''):
            return value
    return default


def _clean(text) -> str:
    return '' if text is None else str(text).replace('\r', ' ').replace('\n', ' ').strip()


def _set_font(c, size=8, bold=False):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.setFillColor(TEXT)


def _draw_text(c, x, y, text, size=8, bold=False, align='left'):
    text = _clean(text)
    _set_font(c, size, bold)
    if align == 'center':
        c.drawCentredString(x, y, text)
    elif align == 'right':
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def _wrap_text(c, text: str, width: float, font='Helvetica', size=8) -> List[str]:
    text = _clean(text)
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    line = ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if c.stringWidth(candidate, font, size) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            # Coupe les mots trop longs pour garder la grille intacte.
            if c.stringWidth(word, font, size) > width:
                piece = ''
                for ch in word:
                    if c.stringWidth(piece + ch, font, size) <= width:
                        piece += ch
                    else:
                        if piece:
                            lines.append(piece)
                        piece = ch
                line = piece
            else:
                line = word
    if line:
        lines.append(line)
    return lines


def _draw_wrapped(c, x, y, text, width, size=8, bold=False, leading=10, max_lines=None, align='left'):
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    lines = _wrap_text(c, text, width, font, size)
    if max_lines:
        lines = lines[:max_lines]
    _set_font(c, size, bold)
    for i, line in enumerate(lines):
        yy = y - i * leading
        if align == 'center':
            c.drawCentredString(x + width / 2, yy, line)
        elif align == 'right':
            c.drawRightString(x + width, yy, line)
        else:
            c.drawString(x, yy, line)
    return len(lines)


def _rect(c, x, y, w, h, fill=None, stroke=BORDER, lw=0.7):
    c.setLineWidth(lw)
    c.setStrokeColor(stroke)
    if fill:
        c.setFillColor(fill)
        c.rect(x, y, w, h, fill=1, stroke=1)
    else:
        c.rect(x, y, w, h, fill=0, stroke=1)


def _line(c, x1, y1, x2, y2, lw=0.7):
    c.setStrokeColor(BORDER)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)


def _header(c, app_root: Path, doc_title: str, doc_no: str, is_order=False, codification="PR-13-ACHFOUR-F07", version="1", date_mise_application="01/07/2024"):
    # Logo officiel : plus grand, proportions conservées, aligné en haut à gauche.
    logo = app_root / "static" / "images" / "laboratoire_2a2e_logo.png"
    if logo.exists():
        try:
            c.drawImage(ImageReader(str(logo)), 24, 768, width=116, height=54, preserveAspectRatio=True, anchor="nw", mask="auto")
        except Exception:
            pass

    _draw_text(c, PAGE_W / 2, 795, "LABORATOIRE 2A2E", size=12.2, bold=True, align="center")
    subtitle = "Analyses Alimentaires, Eaux et Environnement" if is_order else "Analyses Alimentaires Eaux et Environnement"
    _draw_text(c, PAGE_W / 2, 779, subtitle, size=8.5, align="center")

    if is_order:
        right_x = 568
        _draw_text(c, right_x, 798, doc_title, size=13.5, bold=True, align="right")
        _draw_text(c, right_x, 782, doc_no, size=8.4, align="right")
        _draw_text(c, right_x, 764, f"Codification : {codification}", size=5.8, align="right")
        _draw_text(c, right_x, 754, f"version : {version}", size=5.8, align="right")
        _draw_text(c, right_x, 744, f"Mise en app. : {date_mise_application}", size=5.8, align="right")
    else:
        _rect(c, 405, 784, 163, 39, fill=MEDIUM_GREY, stroke=MEDIUM_GREY, lw=0)
        _draw_text(c, 560, 807, doc_title, size=8.5, bold=True, align="right")
        _draw_text(c, 560, 792, doc_no, size=8.5, bold=True, align="right")


def _supplier_block(c, x, y_top, w, h, supplier, address, phone, contact, ref, contact_label="Interlocuteur"):
    # Bloc fournisseur en grille : libellés fixes à gauche, valeurs alignées dans une colonne unique.
    _rect(c, x, y_top - h, w, h, fill=None)
    pad_x = 9
    label_w = 92
    value_x = x + pad_x + label_w
    value_w = w - label_w - (pad_x * 2)
    start_y = y_top - 18
    row_gap = 16
    rows = [
        ("Fournisseur :", supplier, True),
        ("Adresse :", address, False),
        ("Tél :", phone, False),
        (f"{contact_label} :", contact, False),
        ("Réf. fournisseur :", ref, False),
    ]
    for i, (label, val, is_bold) in enumerate(rows):
        yy = start_y - i * row_gap
        _draw_text(c, x + pad_x, yy, label, size=7.8, bold=True)
        _draw_wrapped(c, value_x, yy, val, value_w, size=7.8, bold=is_bold, leading=8.5, max_lines=1)


def _lab_block(c, x, y_top, w, h, title, lines, grey=True):
    _rect(c, x, y_top - h, w, h, fill=MEDIUM_GREY if grey else None, stroke=MEDIUM_GREY if grey else BORDER, lw=0 if grey else 0.7)
    _draw_text(c, x + 6, y_top - 17, title, size=10 if title == 'Laboratoire 2A2E' else 8.5, bold=True)
    y = y_top - 36
    for line in lines:
        _draw_text(c, x + 6, y, line, size=6.7)
        y -= 10


def _footer(c):
    y = 36
    _draw_text(c, PAGE_W / 2, y, FOOTER_LINES[0], size=6.5, bold=True, align='center')
    _draw_text(c, PAGE_W / 2, y - 11, FOOTER_LINES[1], size=6.2, align='center')
    _draw_text(c, PAGE_W / 2, y - 22, FOOTER_LINES[2], size=6.2, align='center')


def _request_lines(req) -> list[dict]:
    rows = []
    for line in getattr(req, 'lines', []) or []:
        designation = _value(line, 'item_name', default='') or _value(req, 'project_name', default='')
        ref = _value(line, 'item_reference', default='')
        desc = _value(line, 'description', default='')
        if ref and ref not in designation:
            designation = f'{designation} - Réf. {ref}'
        if desc and desc not in designation:
            designation = f'{designation} - {desc}'
        rows.append({
            'designation': designation,
            'code': _value(line, 'manufacturer_code', 'code_fabricant', default=''),
            'qty': _value(line, 'quantity', default=0) or 0,
            'unit_price': _value(line, 'estimated_unit_price', default=0) or 0,
        })
    if not rows:
        rows.append({'designation': _value(req, 'project_name', 'description', default=''), 'code': '', 'qty': 1, 'unit_price': _value(req, 'estimated_amount', default=0) or 0})
    return rows


def _order_lines(req, offer) -> list[dict]:
    # Quand l'export part d'une commande existante, on utilise ses lignes réelles.
    order = getattr(offer, 'order', None)
    if order is not None and getattr(order, 'lines', None):
        rows = []
        for line in order.lines:
            qty = float(_value(line, 'quantity_ordered', default=0) or 0)
            unit_price = float(_value(line, 'unit_price', default=0) or 0)
            rows.append({
                'designation': _value(line, 'item_name', default=''),
                'code': _value(line, 'manufacturer_code', 'code_fabricant', default=''),
                'qty': qty,
                'unit_price': unit_price,
                'total': qty * unit_price,
            })
        return rows

    rows = []
    for line in getattr(req, 'lines', []) or []:
        qty = float(_value(line, 'quantity', default=0) or 0)
        offer_line = next((ol for ol in getattr(offer, 'lines', []) if getattr(ol, 'request_line_id', None) == getattr(line, 'id', None)), None)
        unit_price = float(_value(offer_line, 'price_ht', default=None) if offer_line else (_value(line, 'estimated_unit_price', default=0) or 0))
        rows.append({
            'designation': _value(line, 'item_name', default='') or _value(req, 'project_name', default=''),
            'code': _value(line, 'manufacturer_code', 'code_fabricant', default=''),
            'qty': qty,
            'unit_price': unit_price,
            'total': qty * unit_price,
        })
    target_total = float(_value(offer, 'amount', default=0) or _value(req, 'estimated_amount', default=0) or 0)
    current_total = sum(r['total'] for r in rows)
    if rows and target_total > 0 and abs(current_total - target_total) > 0.01:
        rows[-1]['total'] += target_total - current_total
        rows[-1]['unit_price'] = rows[-1]['total'] / max(rows[-1]['qty'], 1)
    if not rows:
        rows.append({'designation': _value(req, 'project_name', default=''), 'code': '', 'qty': 1, 'unit_price': target_total, 'total': target_total})
    return rows


def _draw_dp_table(c, rows: Iterable[dict]):
    x = 20
    y_top = 628
    w = 548
    header_h = 20
    body_h = 350
    col1, col2, col3 = 348, 129, 71
    _rect(c, x, y_top - header_h - body_h, w, header_h + body_h)
    _line(c, x, y_top - header_h, x + w, y_top - header_h)
    _line(c, x + col1, y_top, x + col1, y_top - header_h - body_h)
    _line(c, x + col1 + col2, y_top, x + col1 + col2, y_top - header_h - body_h)
    _draw_text(c, x + 4, y_top - 14, 'Désignation - Conditionnement - Références', size=7.5, bold=True)
    _draw_text(c, x + col1 + 4, y_top - 14, 'Code fabriquant', size=7.5, bold=True)
    _draw_text(c, x + col1 + col2 + col3 / 2, y_top - 14, 'Quantité', size=7.5, bold=True, align='center')

    # Lignes compactes en haut du tableau : hauteur adaptée, pas de cellules énormes.
    y = y_top - header_h - 17
    row_h = 25
    for row in list(rows)[:12]:
        designation_lines = _wrap_text(c, row['designation'], col1 - 10, 'Helvetica', 7.5)[:2]
        code_lines = _wrap_text(c, row['code'], col2 - 10, 'Helvetica', 7.5)[:2]
        for i, txt in enumerate(designation_lines):
            _draw_text(c, x + 5, y - i * 9, txt, size=7.5)
        for i, txt in enumerate(code_lines):
            _draw_text(c, x + col1 + 5, y - i * 9, txt, size=7.5)
        _draw_text(c, x + col1 + col2 + col3 / 2, y, _qty(row['qty']), size=7.5, align='center')
        y -= row_h


def _draw_notes_validation(c, notes=''):
    # Zone basse indépendante du footer : elle finit au-dessus de la zone footer fixe.
    x, y_top, h = 20, 238, 138
    left_w = 348
    right_w = 200
    _rect(c, x, y_top - h, left_w, h)
    _rect(c, x + left_w, y_top - h, right_w, h)
    _draw_text(c, x + 3, y_top - 10, 'Notes :', size=7.3, bold=True)
    _draw_wrapped(c, x + 8, y_top - 25, notes, left_w - 16, size=7.2, leading=9, max_lines=8)
    _draw_text(c, x + left_w + 3, y_top - 10, 'Validation :', size=7.3, bold=True)


def generate_price_request_pdf(app_root: str | Path, output_path: str | Path, req, offer) -> Path:
    """Génère une Demande de prix PDF avec une grille fixe fidèle au modèle 2A2E."""
    app_root = Path(app_root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    c.setTitle('Demande de prix')
    c.setLineJoin(1)

    supplier = _value(offer, 'supplier_name', default='')
    address = _value(offer, 'supplier_address', default='')
    phone = _value(offer, 'supplier_phone', default='')
    contact = _value(offer, 'contact_person', 'supplier_contact', default='')
    ref = _value(offer, 'supplier_reference', default='')
    initiator = _value(req, 'department', 'requester_name', 'service', default='')
    code = _value(req, 'code', default='')
    doc_no = f'N° {code}DP du {_fmt_date()}' if code else f'N° DP du {_fmt_date()}'

    _header(c, app_root, 'Demande de prix', doc_no, is_order=False)
    _lab_block(c, 20, 742, 250, 98, f'Initiation de la demande : {initiator}', LAB_ADDRESS_DP, grey=True)
    _supplier_block(c, 284, 742, 284, 98, supplier, address, phone, contact, ref, contact_label='Interlocuteur')
    _draw_dp_table(c, _request_lines(req))
    notes = _value(offer, 'notes', default='')
    _draw_notes_validation(c, notes)
    _footer(c)
    c.save()
    return output_path


def _draw_bc_table(c, rows: Iterable[dict]):
    x = 20
    y_top = 628
    w = 548
    header_h = 20
    body_h = 350
    col_w = [348, 84, 45, 22, 49]
    col_x = [x]
    for cw in col_w[:-1]:
        col_x.append(col_x[-1] + cw)

    _rect(c, x, y_top - header_h - body_h, w, header_h + body_h)
    _line(c, x, y_top - header_h, x + w, y_top - header_h)
    cursor = x
    for cw in col_w[:-1]:
        cursor += cw
        _line(c, cursor, y_top, cursor, y_top - header_h - body_h)

    _draw_text(c, x + col_w[0] / 2, y_top - 14, 'DÉSIGNATION - MARQUE - CONDITIONNEMENT', size=7.8, align='center')
    _draw_text(c, col_x[1] + 5, y_top - 14, 'Code fabriquant', size=6.8, bold=True)
    _draw_text(c, col_x[2] + col_w[2] / 2, y_top - 14, 'Prix U. HT', size=6.7, bold=True, align='center')
    _draw_text(c, col_x[3] + col_w[3] / 2, y_top - 14, 'Qte', size=6.7, bold=True, align='center')
    _draw_text(c, col_x[4] + col_w[4] / 2, y_top - 14, 'Total HT', size=6.7, bold=True, align='center')

    y = y_top - header_h - 17
    row_h = 25
    for row in list(rows)[:12]:
        designation_lines = _wrap_text(c, row['designation'], col_w[0] - 10, 'Helvetica', 7.4)[:2]
        code_lines = _wrap_text(c, row['code'], col_w[1] - 8, 'Helvetica', 7.2)[:2]
        for i, txt in enumerate(designation_lines):
            _draw_text(c, x + 5, y - i * 9, txt, size=7.4)
        for i, txt in enumerate(code_lines):
            _draw_text(c, col_x[1] + 5, y - i * 9, txt, size=7.2)
        _draw_text(c, col_x[2] + col_w[2] - 4, y, _money(row['unit_price']), size=7.2, align='right')
        _draw_text(c, col_x[3] + col_w[3] / 2, y, _qty(row['qty']), size=7.2, align='center')
        _draw_text(c, col_x[4] + col_w[4] - 4, y, _money(row['total']), size=7.2, align='right')
        y -= row_h


def _draw_bc_bottom(c, notes, total_ht):
    # Zone basse indépendante du footer : remarques/totaux/validation finissent avant le footer.
    x, y_top, h = 20, 238, 138
    remarks_w = 348
    side_w = 200
    totals_h = 48
    validation_h = h - totals_h

    # Remarques à gauche.
    _rect(c, x, y_top - h, remarks_w, h)
    _draw_text(c, x + remarks_w / 2, y_top - 14, 'REMARQUES :', size=8, bold=True, align='center')
    _draw_wrapped(c, x + 8, y_top - 32, notes, remarks_w - 16, size=7.2, leading=9, max_lines=8)

    # Totaux et validation à droite, alignés sur le même niveau que le modèle.
    sx = x + remarks_w
    _rect(c, sx, y_top - totals_h, side_w, totals_h)
    row_h = 16
    _rect(c, sx, y_top - row_h, side_w, row_h, fill=colors.white)
    _rect(c, sx, y_top - 2 * row_h, side_w, row_h, fill=LIGHT_GREY, stroke=LIGHT_GREY)
    _rect(c, sx, y_top - 3 * row_h, side_w, row_h, fill=MEDIUM_GREY, stroke=MEDIUM_GREY)
    tva = round(float(total_ht or 0) * 0.20, 2)
    total_ttc = round(float(total_ht or 0) + tva, 2)
    totals = [('Total HT', total_ht), ('TVA 20%', tva), ('Total TTC', total_ttc)]
    for i, (label, value) in enumerate(totals):
        yy = y_top - 11 - i * row_h
        _draw_text(c, sx + 3, yy, label, size=7, bold=True)
        _draw_text(c, sx + side_w - 32, yy, _money(value), size=7, bold=True, align='right')
        _draw_text(c, sx + side_w - 4, yy, 'MAD', size=7, bold=True, align='right')

    _rect(c, sx, y_top - h, side_w, validation_h)
    _draw_text(c, sx + 3, y_top - totals_h - 10, 'Validation :', size=7.2, bold=True)


def generate_purchase_order_pdf(app_root: str | Path, output_path: str | Path, req, offer) -> Path:
    """Génère un Bon de commande PDF avec une grille fixe fidèle au modèle 2A2E."""
    app_root = Path(app_root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=A4)
    c.setTitle('Bon de commande')
    c.setLineJoin(1)

    supplier = _value(offer, 'supplier_name', default='')
    address = _value(offer, 'supplier_address', default='')
    phone = _value(offer, 'supplier_phone', default='')
    contact = _value(offer, 'contact_person', 'supplier_contact', default='')
    ref = _value(offer, 'supplier_reference', default='')
    code = _value(getattr(offer, 'order', None), 'code', default='') or _value(req, 'code', default='')
    doc_no = f'N° {code}BC du {_fmt_date()}' if code else f'N° BC du {_fmt_date()}'

    order_obj = getattr(offer, 'order', None)
    codification = _value(order_obj, 'codification', default='') or _value(offer, 'codification', default='PR-13-ACHFOUR-F07')
    version = _value(order_obj, 'version', default='') or _value(offer, 'version', default='1')
    date_mise_application = _value(order_obj, 'date_mise_application', 'mise_en_application', default='') or _value(offer, 'date_mise_application', 'mise_en_application', default='01/07/2024')
    date_mise_application = _fmt_date(date_mise_application) if hasattr(date_mise_application, 'strftime') else str(date_mise_application)
    _header(c, app_root, 'Bon de commande', doc_no, is_order=True, codification=codification, version=version, date_mise_application=date_mise_application)
    _lab_block(c, 20, 742, 250, 98, 'Laboratoire 2A2E', LAB_ADDRESS_BC, grey=True)
    _supplier_block(c, 284, 742, 284, 98, supplier, address, phone, contact, ref, contact_label='Contact')
    rows = _order_lines(req, offer)
    _draw_bc_table(c, rows)
    total_ht = sum(float(r.get('total') or 0) for r in rows)
    notes = _value(offer, 'remarks', default='') or _value(offer, 'notes', default='')
    _draw_bc_bottom(c, notes, total_ht)
    _footer(c)
    c.save()
    return output_path
