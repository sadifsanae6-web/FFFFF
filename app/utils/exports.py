from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from flask import current_app


def export_requests_to_excel(requests_list):
    instance_dir = Path(current_app.instance_path)
    file_path = instance_dir / "demandes_export.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Demandes"
    ws.append(["Code", "Projet", "Service", "Type", "Montant", "Urgence", "Criticité", "Priorité", "Statut"])
    for r in requests_list:
        ws.append([r.code, r.project_name, r.department, r.purchase_type, r.estimated_amount, r.urgency, r.criticality, r.priority_score, r.status])
    wb.save(file_path)
    return file_path


def export_requests_to_pdf(requests_list):
    instance_dir = Path(current_app.instance_path)
    file_path = instance_dir / "demandes_achat_professionnel.pdf"
    doc = SimpleDocTemplate(str(file_path), pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=14 * mm, rightMargin=14 * mm)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("<b>Liste demandes d'achat</b>", styles["Title"])
    subtitle = Paragraph(
        f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        styles["BodyText"],
    )
    story.extend([title, Spacer(1, 6), subtitle, Spacer(1, 10)])

    data = [["Code", "Projet", "Service", "Type", "Montant", "Date besoin", "Statut"]]
    total = 0
    for r in requests_list:
        total += float(r.estimated_amount or 0)
        data.append([
            r.code,
            r.project_name,
            r.department,
            r.purchase_type,
            f"{r.estimated_amount:,.2f} DH".replace(",", " "),
            r.need_date.strftime("%d/%m/%Y") if r.need_date else "-",
            r.status.replace("_", " ").capitalize(),
        ])

    data.append(["", "", "", "Total", f"{total:,.2f} DH".replace(",", " "), "", ""])

    table = Table(data, repeatRows=1, colWidths=[24 * mm, 44 * mm, 28 * mm, 28 * mm, 26 * mm, 24 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2449a6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.whitesmoke, colors.HexColor("#eef3fb")]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dbe5f7")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d5ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)
    return file_path
