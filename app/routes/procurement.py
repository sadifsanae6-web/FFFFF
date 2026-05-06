from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from werkzeug.utils import secure_filename

from ..db import db
from ..models import (
    PurchaseRequest,
    PurchaseRequestLine,
    SupplierOffer,
    SupplierOfferLine,
    PurchaseOrder,
    PurchaseOrderLine,
    Reception,
    ReceptionLine,
    NonConformity,
    SupplierReturn,
    Attachment,
    AuditLog,
    SupplierDirectory,
)
from ..utils.auth_helpers import login_required, role_required
from ..utils.codes import next_code
from ..utils.pdf_documents import generate_price_request_pdf, generate_purchase_order_pdf

procurement_bp = Blueprint('procurement', __name__)


DEFAULT_SUPPLIER_CATALOG = [
    {
        'name': 'Test Réactifs',
        'email': 'testreactifs@hotmail.com ; assistente.fatima@test-reactifs.com',
        'phone': '0537855756 / 62',
        'address': '13 bd Lalla Asmaa résid. Chams n°4, fabrique t, Salé 11000',
        'service': 'Matériel de laboratoire, consommables, MC, réactifs chimiques',
    },
    {
        'name': 'Biolab Diagnostics',
        'email': 'info.biolabdiagnostics@gmail.com',
        'phone': '0522600506 / 07',
        'address': '12 Bd Hassan Al Alaoui, Rés Nissrine, Ain Borja, Casablanca',
        'service': 'Matériel de laboratoire, réactifs et produits chimiques, consommables et MC',
    },
    {
        'name': 'Normalab',
        'email': 'normalabsarl@gmail.com',
        'phone': '0522661350 / 52',
        'address': "N°9 Allée des orangers, Lot du départ, Ain Sbaa, Casablanca",
        'service': 'Matériel de laboratoire, réactifs et produits chimiques, consommables',
    },
    {
        'name': 'Isolab',
        'email': 'isolab@isolabmaroc.com',
        'phone': '0522592306 / 07 / 8 / 9',
        'address': 'Lot N° 30, parc industriel CFCIM, Bouskoura, 27182 Bouskoura',
        'service': 'Équipements, matériel de laboratoire, consommables',
    },
]


def _supplier_to_dict(record):
    return {
        'name': record.name,
        'email': record.email or '',
        'phone': record.phone or '',
        'address': record.address or '',
        'service': record.service or '',
    }


def _get_supplier_catalog():
    suppliers = SupplierDirectory.query.order_by(SupplierDirectory.name.asc()).all()
    if not suppliers:
        for row in DEFAULT_SUPPLIER_CATALOG:
            db.session.add(SupplierDirectory(**row))
        db.session.commit()
        suppliers = SupplierDirectory.query.order_by(SupplierDirectory.name.asc()).all()
    return [_supplier_to_dict(item) for item in suppliers]


def _get_supplier_lookup():
    return {item['name']: item for item in _get_supplier_catalog()}


def _upsert_supplier_directory(name, email='', phone='', address='', service=''):
    name = (name or '').strip()
    if not name:
        return None
    supplier = SupplierDirectory.query.filter(db.func.lower(SupplierDirectory.name) == name.lower()).first()
    if supplier is None:
        supplier = SupplierDirectory(name=name)
        db.session.add(supplier)
    supplier.name = name
    if (email or '').strip():
        supplier.email = email.strip()
    if (phone or '').strip():
        supplier.phone = phone.strip()
    if (address or '').strip():
        supplier.address = address.strip()
    if (service or '').strip():
        supplier.service = service.strip()
    db.session.flush()
    return supplier


def _current_actor_name():
    return session.get('user', {}).get('name', 'Utilisateur')


def _current_actor_id():
    return session.get('user', {}).get('id')


def _parse_float(value, default=0.0):
    raw = (value or '').replace(',', '.').strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d').date()


def _save_files(files, entity_type, entity_id, folder_name, author_name, attachment_type='document'):
    saved = []
    upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / folder_name
    upload_dir.mkdir(parents=True, exist_ok=True)
    for uploaded_file in files:
        if not uploaded_file or not uploaded_file.filename:
            continue
        filename = secure_filename(uploaded_file.filename)
        if not filename:
            continue
        filepath = upload_dir / filename
        base = filepath.stem
        ext = filepath.suffix
        i = 1
        while filepath.exists():
            filepath = upload_dir / f'{base}_{i}{ext}'
            i += 1
        uploaded_file.save(filepath)
        att = Attachment(
            filename=filepath.name,
            filepath=str(filepath),
            entity_type=entity_type,
            entity_id=entity_id,
            author_name=author_name,
            attachment_type=attachment_type,
        )
        db.session.add(att)
        saved.append(att)
    return saved


def _log(entity_type, entity_id, action, details=''):
    db.session.add(AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, actor_name=_current_actor_name(), details=details))


def _recompute_order(order: PurchaseOrder):
    for line in order.lines:
        line.recompute_status()
    order.refresh_status_from_lines()
    if order.purchase_request:
        if any(inv.status != 'archivee' for inv in order.invoices):
            order.purchase_request.mark_as_invoiced()
        elif order.status in {
            PurchaseOrder.STATUS_CONFORME,
            PurchaseOrder.STATUS_RECEPTION_PARTIELLE,
            PurchaseOrder.STATUS_PARTIELLEMENT_ACCEPTEE,
            PurchaseOrder.STATUS_RESERVE,
            PurchaseOrder.STATUS_QUARANTAINE,
            PurchaseOrder.STATUS_NON_CONFORME,
            PurchaseOrder.STATUS_RETOUR_EN_COURS,
            PurchaseOrder.STATUS_RETOUR_CLOTURE,
        }:
            order.purchase_request.mark_as_received()
        else:
            order.purchase_request.mark_as_ordered()



def _save_offer_lines(offer: SupplierOffer, form):
    prices = form.getlist('offer_line_price_ht[]')
    request_line_ids = form.getlist('offer_line_request_line_id[]')
    SupplierOfferLine.query.filter_by(offer_id=offer.id).delete()
    total = 0.0
    for idx, request_line_id in enumerate(request_line_ids):
        req_line = PurchaseRequestLine.query.get(int(request_line_id or 0))
        if not req_line or req_line.request_id != offer.request_id:
            continue
        price_ht = _parse_float(prices[idx] if idx < len(prices) else '0')
        total += (req_line.quantity or 0) * price_ht
        db.session.add(SupplierOfferLine(
            offer_id=offer.id,
            request_line_id=req_line.id,
            item_name=req_line.item_name,
            quantity_ordered=req_line.quantity,
            price_ht=price_ht,
        ))
    offer.amount = round(total, 2)

def _reception_attachments(reception_id):
    return Attachment.query.filter_by(entity_type='reception', entity_id=reception_id).order_by(Attachment.created_at.desc()).all()


@procurement_bp.route('/consultations')
@login_required
def consultations():
    requests_list = PurchaseRequest.query.filter(
        PurchaseRequest.status.in_([
            PurchaseRequest.STATUS_VALIDEE,
            PurchaseRequest.STATUS_EN_CONSULTATION,
            PurchaseRequest.STATUS_OFFRE_SELECTIONNEE,
            PurchaseRequest.STATUS_COMMANDEE,
            PurchaseRequest.STATUS_RECUE,
            PurchaseRequest.STATUS_FACTUREE,
            PurchaseRequest.STATUS_PAYEE,
        ])
    ).order_by(PurchaseRequest.created_at.desc()).all()
    return render_template('procurement/consultations.html', requests_list=requests_list)


@procurement_bp.route('/consultations/<int:request_id>', methods=['GET', 'POST'])
@role_required('acheteur')
def offers(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)

    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name', '').strip()
        catalog_supplier = _get_supplier_lookup().get(supplier_name, {})
        offer = SupplierOffer(
            supplier_name=supplier_name,
            supplier_email=request.form.get('supplier_email', '').strip() or catalog_supplier.get('email', ''),
            supplier_phone=request.form.get('supplier_phone', '').strip() or catalog_supplier.get('phone', ''),
            supplier_address=request.form.get('supplier_address', '').strip() or catalog_supplier.get('address', ''),
            supplier_service=request.form.get('supplier_service', '').strip() or catalog_supplier.get('service', ''),
            contact_person=request.form.get('contact_person', '').strip(),
            supplier_reference=request.form.get('supplier_reference', '').strip(),
            amount=0,
            delay_days=0,
            notes=request.form.get('notes', '').strip(),
            remarks=request.form.get('remarks', '').strip(),
            request_id=req.id,
            is_plan_b_offer=request.form.get('is_plan_b_offer') == '1',
        )
        db.session.add(offer)
        _upsert_supplier_directory(offer.supplier_name, offer.supplier_email, offer.supplier_phone, offer.supplier_address, offer.supplier_service)
        if req.status == PurchaseRequest.STATUS_VALIDEE:
            req.open_supplier_consultation()
        db.session.commit()
        flash('Offre ajoutée.', 'success')
        return redirect(url_for('procurement.offers', request_id=req.id))

    offers_list = SupplierOffer.query.filter_by(request_id=req.id, is_archived=False).order_by(SupplierOffer.amount.asc()).all()
    archived_offers = SupplierOffer.query.filter_by(request_id=req.id, is_archived=True).order_by(SupplierOffer.created_at.desc()).all()
    return render_template('procurement/offers.html', req=req, offers_list=offers_list, archived_offers=archived_offers, supplier_catalog=_get_supplier_catalog())


@procurement_bp.route('/consultations/<int:request_id>/archives')
@role_required('acheteur')
def archived_offers(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    offers_list = SupplierOffer.query.filter_by(request_id=req.id, is_archived=True).order_by(SupplierOffer.created_at.desc()).all()
    return render_template('procurement/archived_offers.html', req=req, offers_list=offers_list)


@procurement_bp.route('/offres/<int:offer_id>/selectionner', methods=['POST'])
@role_required('acheteur')
def select_offer(offer_id):
    offer = SupplierOffer.query.get_or_404(offer_id)
    offer.select()
    db.session.commit()
    flash('Offre sélectionnée.', 'success')
    return redirect(url_for('procurement.offers', request_id=offer.request_id))


@procurement_bp.route('/offres/<int:offer_id>/modifier', methods=['GET', 'POST'])
@role_required('acheteur')
def edit_offer(offer_id):
    offer = SupplierOffer.query.get_or_404(offer_id)
    if request.method == 'POST':
        offer.supplier_name = request.form.get('supplier_name', offer.supplier_name).strip()
        offer.supplier_email = request.form.get('supplier_email', offer.supplier_email).strip()
        offer.supplier_phone = request.form.get('supplier_phone', offer.supplier_phone).strip()
        offer.supplier_address = request.form.get('supplier_address', offer.supplier_address).strip()
        offer.supplier_service = request.form.get('supplier_service', offer.supplier_service).strip()
        offer.contact_person = request.form.get('contact_person', offer.contact_person).strip()
        offer.supplier_reference = request.form.get('supplier_reference', offer.supplier_reference).strip()
        offer.notes = request.form.get('notes', offer.notes).strip()
        offer.remarks = request.form.get('remarks', getattr(offer, 'remarks', '')).strip()
        _save_offer_lines(offer, request.form)
        offer.is_plan_b_offer = request.form.get('is_plan_b_offer') == '1'
        _upsert_supplier_directory(offer.supplier_name, offer.supplier_email, offer.supplier_phone, offer.supplier_address, offer.supplier_service)
        db.session.commit()
        flash('Offre modifiée.', 'success')
        return redirect(url_for('procurement.offers', request_id=offer.request_id))
    return render_template('procurement/edit_offer.html', offer=offer, supplier_catalog=_get_supplier_catalog())




@procurement_bp.route('/offres/<int:offer_id>/demande-prix')
@role_required('acheteur')
def generate_offer_price_request(offer_id):
    offer = SupplierOffer.query.get_or_404(offer_id)
    req = offer.purchase_request
    folder = Path(current_app.config['UPLOAD_FOLDER']) / f'request_{offer.request_id}' / 'price_requests'
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(offer.supplier_name or f'fournisseur_{offer.id}') or f'fournisseur_{offer.id}'
    file_path = folder / f'demande_prix_{req.code}_{safe_name}_{uuid4().hex[:8]}.pdf'
    generate_price_request_pdf(Path(current_app.root_path), file_path, req, offer)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@procurement_bp.route('/consultations/<int:request_id>/bon-commande')
@role_required('acheteur')
def generate_purchase_order_document(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    selected = req.get_selected_offer()
    if not selected:
        flash("Sélectionnez d'abord une offre.", 'danger')
        return redirect(url_for('procurement.offers', request_id=req.id))

    folder = Path(current_app.config['UPLOAD_FOLDER']) / f'request_{req.id}' / 'purchase_orders'
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(selected.supplier_name or f'fournisseur_{selected.id}') or f'fournisseur_{selected.id}'
    file_path = folder / f'bon_commande_{req.code}_{safe_name}_{uuid4().hex[:8]}.pdf'
    generate_purchase_order_pdf(Path(current_app.root_path), file_path, req, selected)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@procurement_bp.route('/offres/<int:offer_id>/archiver', methods=['POST'])
@role_required('acheteur')
def archive_offer(offer_id):
    offer = SupplierOffer.query.get_or_404(offer_id)
    req = offer.purchase_request
    request_id = offer.request_id
    was_selected = offer.is_selected
    offer.archive()
    db.session.flush()
    remaining_offers = SupplierOffer.query.filter_by(request_id=request_id, is_archived=False).all()
    remaining_selected = any(item.is_selected for item in remaining_offers)
    if req:
        if not remaining_offers:
            req.status = PurchaseRequest.STATUS_VALIDEE
        elif was_selected or not remaining_selected:
            req.open_supplier_consultation()
    db.session.commit()
    flash('Offre archivée.', 'info')
    return redirect(url_for('procurement.offers', request_id=request_id))


@procurement_bp.route('/offres/<int:offer_id>/restaurer', methods=['POST'])
@role_required('acheteur')
def restore_offer(offer_id):
    offer = SupplierOffer.query.get_or_404(offer_id)
    offer.restore()
    req = offer.purchase_request
    active_offers = SupplierOffer.query.filter_by(request_id=offer.request_id, is_archived=False).all()
    if req:
        if any(item.is_selected for item in active_offers):
            req.mark_offer_selected()
        elif active_offers:
            req.open_supplier_consultation()
        else:
            req.status = PurchaseRequest.STATUS_VALIDEE
    db.session.commit()
    flash('Offre restaurée.', 'success')
    return redirect(url_for('procurement.archived_offers', request_id=offer.request_id))


@procurement_bp.route('/commandes')
@login_required
def orders():
    orders_list = PurchaseOrder.query.filter(PurchaseOrder.status != PurchaseOrder.STATUS_ARCHIVEE).order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('procurement/orders.html', orders_list=orders_list)


@procurement_bp.route('/commandes/archives')
@login_required
def archived_orders():
    orders_list = PurchaseOrder.query.filter_by(status=PurchaseOrder.STATUS_ARCHIVEE).order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('procurement/archived_orders.html', orders_list=orders_list)


@procurement_bp.route('/commandes/<int:order_id>/modifier', methods=['GET', 'POST'])
@role_required('acheteur')
def edit_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    if order.status == PurchaseOrder.STATUS_ARCHIVEE:
        flash("Une commande archivée doit d'abord être restaurée.", 'warning')
        return redirect(url_for('procurement.order_detail', order_id=order.id))

    if request.method == 'POST':
        order.supplier_name = request.form.get('supplier_name', order.supplier_name)
        order.supplier_email = request.form.get('supplier_email', order.supplier_email)
        order.supplier_phone = request.form.get('supplier_phone', order.supplier_phone)
        order.amount = _parse_float(request.form.get('amount'), order.amount)
        order.reception_site = request.form.get('reception_site', order.reception_site)

        for line in order.lines:
            line.item_name = request.form.get(f'item_name_{line.id}', line.item_name)
            line.item_reference = request.form.get(f'item_reference_{line.id}', line.item_reference)
            line.uom = request.form.get(f'uom_{line.id}', line.uom)
            line.quantity_ordered = _parse_float(request.form.get(f'quantity_{line.id}'), line.quantity_ordered)
            line.unit_price = _parse_float(request.form.get(f'unit_price_{line.id}'), line.unit_price)
            line.delivery_site = request.form.get(f'delivery_site_{line.id}', line.delivery_site)
            line.quality_control_required = request.form.get(f'quality_control_required_{line.id}', '0') == '1'

        _recompute_order(order)
        _log('purchase_order', order.id, 'Commande modifiée', 'Mise à jour manuelle de la commande')
        db.session.commit()
        flash('Commande modifiée.', 'success')
        return redirect(url_for('procurement.order_detail', order_id=order.id))

    return render_template('procurement/edit_order.html', order=order)


@procurement_bp.route('/commandes/<int:order_id>/archiver', methods=['POST'])
@role_required('acheteur')
def archive_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    order.archive()
    _log('purchase_order', order.id, 'Commande archivée', order.code)
    db.session.commit()
    flash('Commande archivée.', 'info')
    return redirect(url_for('procurement.orders'))


@procurement_bp.route('/commandes/<int:order_id>/restaurer', methods=['POST'])
@role_required('acheteur')
def restore_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)

    # Correction définitive : la restauration ne passe plus par refresh_status_from_lines()
    # car cette méthode protège le statut "archivee" et pouvait laisser la commande
    # dans la liste des archives. On force la sortie d'archive directement en base.
    PurchaseOrder.query.filter_by(id=order.id).update({
        PurchaseOrder.status: PurchaseOrder.STATUS_COMMANDEE,
        PurchaseOrder.payment_blocked: False,
        PurchaseOrder.stock_blocked: False,
    }, synchronize_session=False)
    _log('purchase_order', order.id, 'Commande restaurée', order.code)
    db.session.commit()
    db.session.expire_all()

    flash('Commande restaurée.', 'success')
    return redirect(url_for('procurement.orders'))


@procurement_bp.route('/consultations/<int:request_id>/creer-commande', methods=['POST'])
@role_required('acheteur')
def create_order(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    selected = req.get_selected_offer()
    if not selected:
        flash("Sélectionnez d'abord une offre.", 'danger')
        return redirect(url_for('procurement.offers', request_id=req.id))

    active = PurchaseOrder.query.filter(
        PurchaseOrder.request_id == req.id,
        PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_COMMANDEE,
            PurchaseOrder.STATUS_EN_RECEPTION,
            PurchaseOrder.STATUS_RECEPTION_PARTIELLE,
            PurchaseOrder.STATUS_ATTENTE_QUALITE,
            PurchaseOrder.STATUS_PARTIELLEMENT_ACCEPTEE,
            PurchaseOrder.STATUS_RESERVE,
            PurchaseOrder.STATUS_QUARANTAINE,
            PurchaseOrder.STATUS_NON_CONFORME,
            PurchaseOrder.STATUS_LITIGE,
            PurchaseOrder.STATUS_RETOUR_EN_COURS,
        ])
    ).first()
    if active:
        flash('Une commande active existe déjà pour cette demande.', 'warning')
        return redirect(url_for('procurement.order_detail', order_id=active.id))

    req.recompute_estimated_amount()
    order = PurchaseOrder(
        code=next_code(PurchaseOrder, 'CMD'),
        supplier_name=selected.supplier_name,
        supplier_email=selected.supplier_email,
        supplier_phone=selected.supplier_phone,
        amount=selected.amount or req.estimated_amount,
        request_id=req.id,
        selected_offer_id=selected.id,
        status=PurchaseOrder.STATUS_COMMANDEE,
        reception_site=req.lines[0].delivery_site if req.lines else 'Dépôt principal',
    )
    req.mark_as_ordered()
    db.session.add(order)
    db.session.flush()

    request_lines = req.lines or [
        PurchaseRequestLine(
            request_id=req.id,
            line_no=1,
            item_name=req.project_name,
            item_reference=req.code,
            line_type='service' if req.purchase_type == 'Services' else 'article',
            uom='Unité',
            quantity=1,
            estimated_unit_price=req.estimated_amount,
            quality_control_required=(req.purchase_type != 'Services'),
            delivery_site='Dépôt principal',
            description=req.description,
        )
    ]
    if not req.lines:
        db.session.add(request_lines[0])
        db.session.flush()

    for idx, req_line in enumerate(request_lines, start=1):
        db.session.add(PurchaseOrderLine(
            order_id=order.id,
            request_line_id=req_line.id,
            item_name=req_line.item_name,
            item_reference=req_line.item_reference,
            manufacturer_code=req_line.manufacturer_code,
            uom=req_line.uom,
            quantity_ordered=req_line.quantity,
            unit_price=next((ol.price_ht for ol in selected.lines if ol.request_line_id == req_line.id), req_line.estimated_unit_price),
            quality_control_required=req_line.quality_control_required,
            delivery_site=req_line.delivery_site,
        ))
        req_line.status = 'commandee'
    _log('purchase_order', order.id, 'Création commande', f'Commande créée depuis offre {selected.supplier_name}')
    db.session.commit()
    flash('Commande créée avec plusieurs lignes.', 'success')
    return redirect(url_for('procurement.order_detail', order_id=order.id))


@procurement_bp.route('/commandes/<int:order_id>')
@login_required
def order_detail(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    history = PurchaseOrder.query.filter_by(request_id=order.request_id).order_by(PurchaseOrder.created_at.desc()).all()
    alternatives = SupplierOffer.query.filter_by(request_id=order.request_id, is_plan_b_offer=True, is_archived=False).all()
    logs = AuditLog.query.filter_by(entity_type='purchase_order', entity_id=order.id).order_by(AuditLog.created_at.desc()).all()
    return render_template('procurement/order_detail.html', order=order, history=history, alternatives=alternatives, logs=logs, supplier_catalog=_get_supplier_catalog())


@procurement_bp.route('/commandes/<int:order_id>/plan-b', methods=['POST'])
@role_required('acheteur')
def add_plan_b_offer(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    supplier_name = request.form.get('supplier_name', '').strip()
    catalog_supplier = _get_supplier_lookup().get(supplier_name, {})
    offer = SupplierOffer(
        supplier_name=supplier_name,
        supplier_email=request.form.get('supplier_email', '').strip() or catalog_supplier.get('email', ''),
        supplier_phone=request.form.get('supplier_phone', '').strip() or catalog_supplier.get('phone', ''),
        supplier_address=request.form.get('supplier_address', '').strip() or catalog_supplier.get('address', ''),
        supplier_service=request.form.get('supplier_service', '').strip() or catalog_supplier.get('service', ''),
        contact_person=request.form.get('contact_person', '').strip(),
        supplier_reference=request.form.get('supplier_reference', '').strip(),
        amount=0,
        delay_days=0,
        notes=request.form.get('notes', '').strip(),
        remarks=request.form.get('remarks', '').strip(),
        request_id=order.request_id,
        is_plan_b_offer=True,
    )
    db.session.add(offer)
    db.session.flush()
    # Crée des lignes plan B basées uniquement sur les articles de la commande en cours.
    # Le prix HT est saisi ligne par ligne et sera repris dans la nouvelle commande / bon de commande.
    for line in order.lines:
        price_ht = _parse_float(request.form.get(f'price_ht_{line.id}'))
        db.session.add(SupplierOfferLine(
            offer_id=offer.id,
            request_line_id=line.request_line_id,
            item_name=line.item_name,
            quantity_ordered=line.quantity_ordered,
            price_ht=round(price_ht, 2),
        ))
    offer.recompute_amount()
    _upsert_supplier_directory(offer.supplier_name, offer.supplier_email, offer.supplier_phone, offer.supplier_address, offer.supplier_service)
    db.session.commit()
    flash('Nouvelle offre plan B ajoutée.', 'success')
    return redirect(url_for('procurement.order_detail', order_id=order.id))


@procurement_bp.route('/commandes/<int:order_id>/remplacer', methods=['POST'])
@role_required('acheteur')
def replace_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    if order.status not in {
        PurchaseOrder.STATUS_COMMANDEE,
        PurchaseOrder.STATUS_RECEPTION_PARTIELLE,
        PurchaseOrder.STATUS_PARTIELLEMENT_ACCEPTEE,
        PurchaseOrder.STATUS_RESERVE,
        PurchaseOrder.STATUS_NON_CONFORME,
        PurchaseOrder.STATUS_LITIGE,
    }:
        flash("Le remplacement n'est possible que pour une commande active.", 'warning')
        return redirect(url_for('procurement.order_detail', order_id=order.id))

    offer_id = int(request.form.get('offer_id') or 0)
    selected = SupplierOffer.query.get_or_404(offer_id)
    if selected.request_id != order.request_id:
        flash("Cette offre n'appartient pas à la même demande.", 'danger')
        return redirect(url_for('procurement.order_detail', order_id=order.id))

    order.cancel_for_plan_b(reason=request.form.get('reason', ''))
    selected.select()
    new_order = PurchaseOrder(
        code=next_code(PurchaseOrder, 'CMD'),
        supplier_name=selected.supplier_name,
        supplier_email=selected.supplier_email,
        supplier_phone=selected.supplier_phone,
        amount=selected.amount,
        status=PurchaseOrder.STATUS_COMMANDEE,
        request_id=order.request_id,
        selected_offer_id=selected.id,
        previous_order_id=order.id,
        reception_site=order.reception_site,
    )
    db.session.add(new_order)
    db.session.flush()
    for old_line in order.lines:
        db.session.add(PurchaseOrderLine(
            order_id=new_order.id,
            request_line_id=old_line.request_line_id,
            item_name=old_line.item_name,
            item_reference=old_line.item_reference,
            manufacturer_code=old_line.manufacturer_code,
            uom=old_line.uom,
            quantity_ordered=old_line.quantity_ordered,
            unit_price=next((ol.price_ht for ol in selected.lines if ol.request_line_id == old_line.request_line_id), old_line.unit_price),
            quality_control_required=old_line.quality_control_required,
            delivery_site=old_line.delivery_site,
        ))
    _log('purchase_order', order.id, 'Plan B activé', f'Commande remplacée par {selected.supplier_name}')
    db.session.commit()
    flash('Plan B fournisseur activé.', 'success')
    return redirect(url_for('procurement.order_detail', order_id=new_order.id))


@procurement_bp.route('/commandes/<int:order_id>/bon-commande')
@role_required('acheteur')
def export_order_purchase_order(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    req = order.purchase_request
    folder = Path(current_app.config['UPLOAD_FOLDER']) / f'request_{req.id}' / 'purchase_orders'
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(order.supplier_name or f'fournisseur_{order.id}') or f'fournisseur_{order.id}'
    file_path = folder / f'bon_commande_{order.code}_{safe_name}_{uuid4().hex[:8]}.pdf'
    supplier_like = SimpleNamespace(
        order=order,
        codification=getattr(order, 'codification', 'PR-13-ACHFOUR-F07'),
        version=getattr(order, 'version', '1'),
        date_mise_application=getattr(order, 'date_mise_application', '01/07/2024'),
        supplier_name=order.supplier_name,
        supplier_email=order.supplier_email,
        supplier_phone=order.supplier_phone,
        supplier_address=getattr(order.selected_offer, 'supplier_address', ''),
        supplier_service=getattr(order.selected_offer, 'supplier_service', ''),
        contact_person=getattr(order.selected_offer, 'contact_person', ''),
        supplier_reference=getattr(order.selected_offer, 'supplier_reference', ''),
        amount=order.amount,
        delay_days=0,
        notes=getattr(order.selected_offer, 'remarks', '') if order.selected_offer else '',
    )
    generate_purchase_order_pdf(Path(current_app.root_path), file_path, req, supplier_like)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@procurement_bp.route('/receptions')
@login_required
def receptions():
    orders_list = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('procurement/receptions.html', orders_list=orders_list)


@procurement_bp.route('/receptions/<int:order_id>')
@login_required
def reception_detail(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    selected_reception_id = request.args.get('reception_id', type=int)
    selected_reception = None
    if selected_reception_id:
        selected_reception = Reception.query.filter_by(id=selected_reception_id, order_id=order.id).first()
    if not selected_reception:
        selected_reception = Reception.query.filter_by(order_id=order.id, status=Reception.STATUS_QUALITE_A_TRAITER).order_by(Reception.created_at.asc()).first()
    pending_quality = Reception.query.filter_by(order_id=order.id, status=Reception.STATUS_QUALITE_A_TRAITER).order_by(Reception.created_at.asc()).all()
    logs = AuditLog.query.filter_by(entity_type='purchase_order', entity_id=order.id).order_by(AuditLog.created_at.desc()).all()
    all_ncs = NonConformity.query.join(Reception).filter(Reception.order_id == order.id).order_by(NonConformity.created_at.desc()).all()
    return render_template(
        'procurement/reception_form.html',
        order=order,
        logs=logs,
        pending_quality=pending_quality,
        selected_reception=selected_reception,
        all_ncs=all_ncs,
    )


@procurement_bp.route('/pieces-jointes/<int:attachment_id>/telecharger')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    return send_file(attachment.filepath, as_attachment=True, download_name=attachment.filename)


@procurement_bp.route('/pieces-jointes/<int:attachment_id>/supprimer', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    redirect_target = url_for('procurement.receptions')
    if attachment.entity_type == 'reception' and attachment.entity_id:
        reception = Reception.query.get(attachment.entity_id)
        if reception:
            redirect_target = url_for('procurement.reception_detail', order_id=reception.order_id, reception_id=reception.id)
    try:
        Path(attachment.filepath).unlink(missing_ok=True)
    except Exception:
        pass
    db.session.delete(attachment)
    db.session.commit()
    flash('Pièce jointe supprimée.', 'info')
    return redirect(redirect_target)


@procurement_bp.route('/receptions/<int:order_id>/saisir', methods=['POST'])
@role_required('acheteur', 'magasinier', 'controle_qualite')
def save_reception(order_id):
    order = PurchaseOrder.query.get_or_404(order_id)
    if order.status == PurchaseOrder.STATUS_ANNULEE:
        flash('Cette commande est annulée : la saisie de réception est désactivée et le paiement reste bloqué.', 'warning')
        return redirect(url_for('procurement.reception_detail', order_id=order.id))
    stage = request.form.get('stage', 'logistic')
    errors = []

    if stage == 'logistic':
        logistic_status = request.form.get('logistic_status', Reception.LOGISTIC_COMPLETE)
        observations = request.form.get('observations', '')
        refusal_reason = request.form.get('refusal_reason', '')
        transport_reservations = ''

        reception = Reception(
            code=next_code(Reception, 'REC'),
            order_id=order.id,
            reception_date=_parse_date(request.form.get('reception_date')) or date.today(),
            delivery_note_number=request.form.get('delivery_note_number', ''),
            delivery_note_date=None,
            carrier=request.form.get('carrier', ''),
            reception_site=request.form.get('reception_site', order.reception_site),
            warehouse='',
            logistic_status=logistic_status,
            status=Reception.STATUS_QUALITE_A_TRAITER,
            transport_reservations=transport_reservations,
            refusal_reason=refusal_reason,
            observations=observations,
            received_by_id=_current_actor_id(),
            received_by_name=_current_actor_name(),
            is_final=request.form.get('is_final') == '1',
        )
        db.session.add(reception)
        db.session.flush()

        total_delivered = 0.0
        total_refused = 0.0
        for line in order.lines:
            delivered_now = _parse_float(request.form.get(f'delivered_now_{line.id}'))
            refused_dock = _parse_float(request.form.get(f'refused_dock_{line.id}'))
            if delivered_now < 0 or refused_dock < 0:
                errors.append(f"Les quantités de la ligne {line.item_name} doivent être positives.")
                continue
            if delivered_now + refused_dock <= 0:
                continue
            if delivered_now + refused_dock > line.quantity_remaining_to_deliver:
                errors.append(f"La ligne {line.item_name} dépasse la quantité commandée restante.")
                continue
            if logistic_status == Reception.LOGISTIC_REFUSED_TOTAL and delivered_now > 0:
                errors.append(f"Refus total à quai incohérent sur {line.item_name}.")
            if refused_dock > 0 and not refusal_reason.strip():
                errors.append("Un motif de refus à quai est obligatoire en cas de refus à quai.")

            rec_line = ReceptionLine(
                reception_id=reception.id,
                order_line_id=line.id,
                quantity_ordered=line.quantity_ordered,
                quantity_delivered_before=line.quantity_delivered_total,
                quantity_delivered_now=delivered_now,
                quantity_refused_dock=refused_dock,
                quantity_remaining=max(line.quantity_remaining_to_deliver - delivered_now - refused_dock, 0),
                status=ReceptionLine.STATUS_REFUS_QUAI if delivered_now <= 0 and refused_dock > 0 else ReceptionLine.STATUS_A_CONTROLER,
                comment=request.form.get(f'log_comment_{line.id}', ''),
                lot_number=request.form.get(f'lot_{line.id}', ''),
                serial_number=request.form.get(f'serial_{line.id}', ''),
                expiry_date=_parse_date(request.form.get(f'expiry_{line.id}')),
                storage_location=request.form.get(f'storage_{line.id}', ''),
            )
            db.session.add(rec_line)
            line.quantity_delivered_total += delivered_now
            total_delivered += delivered_now
            total_refused += refused_dock
            line.recompute_status()

        if total_delivered <= 0 and total_refused <= 0:
            errors.append('Aucune quantité livrée ou refusée à quai n’a été saisie.')

        if errors:
            db.session.rollback()
            for msg in errors:
                flash(msg, 'danger')
            return redirect(url_for('procurement.reception_detail', order_id=order.id))

        _save_files(request.files.getlist('attachments'), 'reception', reception.id, f'reception_{reception.id}', _current_actor_name(), request.form.get('attachment_type', 'document'))
        _recompute_order(order)
        _log('purchase_order', order.id, 'Réception logistique', f'{reception.code} - {reception.logistic_status}')
        db.session.commit()
        flash('Réception logistique enregistrée. La décision qualité est maintenant attendue.', 'success')
        return redirect(url_for('procurement.reception_detail', order_id=order.id, reception_id=reception.id))

    reception_id = int(request.form.get('reception_id') or 0)
    reception = Reception.query.filter_by(id=reception_id, order_id=order.id).first_or_404()
    if reception.status == Reception.STATUS_CLOTUREE:
        flash('Cette réception a déjà été clôturée.', 'info')
        return redirect(url_for('procurement.reception_detail', order_id=order.id, reception_id=reception.id))

    has_open_issue = False
    decision_values = []
    for rec_line in reception.lines:
        accepted = _parse_float(request.form.get(f'accepted_{rec_line.id}'))
        severity = request.form.get(f'severity_{rec_line.id}', NonConformity.SEVERITY_MAJEURE)
        nc_decision = request.form.get(f'nc_decision_{rec_line.id}', NonConformity.DECISION_REMPLACEMENT)
        accepted = max(accepted, 0)

        if rec_line.quantity_delivered_now <= 0:
            rec_line.status = ReceptionLine.STATUS_REFUS_QUAI
            rec_line.quality_decision = 'refus_a_quai'
            continue

        if nc_decision in {NonConformity.DECISION_PRODUIT_CONFORME, NonConformity.DECISION_ACCEPTER}:
            if nc_decision == NonConformity.DECISION_PRODUIT_CONFORME:
                accepted = rec_line.quantity_delivered_now
                severity = NonConformity.SEVERITY_PRODUIT_CONFORME

        if accepted > rec_line.quantity_delivered_now:
            errors.append(f"La quantité acceptée ne peut pas dépasser la quantité livrée pour {rec_line.order_line.item_name}.")
            continue

        if nc_decision == NonConformity.DECISION_PRODUIT_CONFORME and accepted < rec_line.quantity_delivered_now:
            errors.append(f"La décision produit conforme exige l'acceptation totale de la ligne {rec_line.order_line.item_name}.")
            continue

        rejected = max(round(rec_line.quantity_delivered_now - accepted, 2), 0)
        quarantine = 0
        comment = ''
        reason = '' if rejected <= 0 else f"Quantité refusée après contrôle qualité - décision {nc_decision}"
        decision_values.append(nc_decision)

        rec_line.quantity_accepted = accepted
        rec_line.quantity_quarantine = quarantine
        rec_line.quantity_rejected = rejected
        rec_line.defect_reason = reason
        rec_line.comment = comment
        rec_line.quality_decision = ReceptionLine.DECISION_ACCEPT if nc_decision in {NonConformity.DECISION_PRODUIT_CONFORME, NonConformity.DECISION_ACCEPTER} else ReceptionLine.DECISION_REJECT
        rec_line.quantity_remaining = max(rec_line.quantity_ordered - (rec_line.quantity_delivered_before + rec_line.quantity_delivered_now + rec_line.quantity_refused_dock), 0)

        order_line = rec_line.order_line
        order_line.quantity_accepted_total += accepted
        order_line.quantity_quarantine_total += quarantine
        order_line.quantity_rejected_total += rejected

        open_line_ncs = [item for item in order_line.non_conformities if item.is_open]
        existing_nc = next((item for item in rec_line.non_conformities if item.is_open), None)
        if nc_decision in {NonConformity.DECISION_PRODUIT_CONFORME, NonConformity.DECISION_ACCEPTER} and rejected <= 0:
            rec_line.status = ReceptionLine.STATUS_ACCEPTEE
            for open_nc in open_line_ncs:
                open_nc.close(decision=nc_decision)
        else:
            rec_line.status = ReceptionLine.STATUS_REJETEE
            has_open_issue = True
            if not existing_nc:
                existing_nc = NonConformity(
                    reception_id=reception.id,
                    reception_line_id=rec_line.id,
                    order_line_id=order_line.id,
                    reason=reason or 'Non-conformité',
                    comment=comment,
                    severity=severity,
                    decision=nc_decision,
                    status=NonConformity.STATUS_EN_ANALYSE,
                    payment_blocked=(nc_decision == NonConformity.DECISION_REJETER),
                    stock_blocked=(rejected > 0),
                )
                db.session.add(existing_nc)
            else:
                existing_nc.reason = reason or existing_nc.reason
                existing_nc.comment = comment or existing_nc.comment
                existing_nc.severity = severity
                existing_nc.decision = nc_decision
                existing_nc.status = NonConformity.STATUS_EN_ANALYSE
                existing_nc.payment_blocked = (nc_decision == NonConformity.DECISION_REJETER)
                existing_nc.stock_blocked = rejected > 0

    if errors:
        db.session.rollback()
        for msg in errors:
            flash(msg, 'danger')
        return redirect(url_for('procurement.reception_detail', order_id=order.id, reception_id=reception.id))

    reception.status = Reception.STATUS_CLOTUREE
    reception.quality_decided_by_id = _current_actor_id()
    reception.quality_decided_by_name = _current_actor_name()
    reception.quality_decision_date = date.today()
    for line in order.lines:
        line.recompute_status()
    _recompute_order(order)
    positive_decisions = {NonConformity.DECISION_PRODUIT_CONFORME, NonConformity.DECISION_ACCEPTER}
    if reception.logistic_status == Reception.LOGISTIC_REFUSED_TOTAL and reception.is_final:
        order.status = PurchaseOrder.STATUS_REFUSEE
        order.payment_blocked = True
    elif NonConformity.DECISION_REMPLACEMENT in decision_values:
        order.status = PurchaseOrder.STATUS_RECEPTION_PARTIELLE
        order.payment_blocked = False
    elif NonConformity.DECISION_REJETER in decision_values:
        order.status = PurchaseOrder.STATUS_REFUSEE if reception.is_final and order.qty_accepted_total <= 0 and order.qty_remaining_total <= 0 else PurchaseOrder.STATUS_RECEPTION_PARTIELLE
        order.payment_blocked = (order.status == PurchaseOrder.STATUS_REFUSEE)
    elif decision_values and all(dec in positive_decisions for dec in decision_values):
        order.status = PurchaseOrder.STATUS_CONFORME if reception.is_final and order.qty_remaining_total <= 0 else PurchaseOrder.STATUS_RECEPTION_PARTIELLE
        order.payment_blocked = False
    action_text = 'Décision qualité avec litige' if has_open_issue else 'Décision qualité conforme'
    _log('purchase_order', order.id, action_text, f'{reception.code} clôturée')
    db.session.commit()
    flash('Décisions qualité enregistrées.', 'success')
    return redirect(url_for('procurement.reception_detail', order_id=order.id, reception_id=reception.id))


@procurement_bp.route('/non-conformites/<int:nc_id>/mettre-a-jour', methods=['POST'])
@role_required('acheteur', 'controle_qualite')
def update_non_conformity(nc_id):
    nc = NonConformity.query.get_or_404(nc_id)
    order = nc.reception.purchase_order
    nc.severity = request.form.get('severity', nc.severity)
    nc.reason = request.form.get('reason', nc.reason)
    nc.comment = request.form.get('comment', nc.comment)
    nc.decision = request.form.get('decision', nc.decision)
    nc.status = request.form.get('status', nc.status)
    nc.payment_blocked = nc.severity in {NonConformity.SEVERITY_MAJEURE, NonConformity.SEVERITY_CRITIQUE} and nc.status != NonConformity.STATUS_CLOTUREE
    nc.stock_blocked = nc.status not in {NonConformity.STATUS_RESOLUE, NonConformity.STATUS_CLOTUREE} and nc.reception_line.quantity_quarantine > 0

    if request.form.get('close_nc') == '1':
        nc.close(decision=nc.decision)

    _recompute_order(order)
    _log('purchase_order', order.id, 'Mise à jour non-conformité', f'NC {nc.id} - {nc.status}')
    db.session.commit()
    flash('Non-conformité mise à jour.', 'success')
    return redirect(url_for('procurement.reception_detail', order_id=order.id))


@procurement_bp.route('/non-conformites/<int:nc_id>/retour', methods=['POST'])
@role_required('acheteur', 'controle_qualite')
def create_supplier_return(nc_id):
    nc = NonConformity.query.get_or_404(nc_id)
    if nc.return_case:
        flash('Un retour existe déjà pour cette non-conformité.', 'info')
        return redirect(url_for('procurement.reception_detail', order_id=nc.reception.order_id))
    rtype = request.form.get('return_type', 'remplacement')
    qty = _parse_float(request.form.get('quantity')) or max(nc.reception_line.quantity_rejected, nc.reception_line.quantity_quarantine)
    supplier_return = SupplierReturn(
        non_conformity_id=nc.id,
        return_type=rtype,
        quantity=qty,
        status=SupplierReturn.STATUS_EN_COURS,
        decision_comment=request.form.get('decision_comment', ''),
        stock_impact='stock_bloque' if nc.reception_line.quantity_quarantine > 0 else 'stock_non_integre',
        payment_impact='paiement_bloque' if nc.payment_blocked else 'paiement_partiel_autorise',
    )
    db.session.add(supplier_return)
    nc.status = NonConformity.STATUS_ACTION_FOURNISSEUR
    order = nc.reception.purchase_order
    order.status = PurchaseOrder.STATUS_RETOUR_EN_COURS
    _recompute_order(order)
    _log('purchase_order', order.id, 'Retour fournisseur lancé', f'NC {nc.id} - {rtype}')
    db.session.commit()
    flash('Retour fournisseur créé.', 'success')
    return redirect(url_for('procurement.reception_detail', order_id=order.id))


@procurement_bp.route('/retours/<int:return_id>/mettre-a-jour', methods=['POST'])
@role_required('acheteur', 'controle_qualite')
def update_supplier_return(return_id):
    supplier_return = SupplierReturn.query.get_or_404(return_id)
    nc = supplier_return.non_conformity
    order = nc.reception.purchase_order
    order_line = nc.order_line

    supplier_return.status = request.form.get('status', supplier_return.status)
    supplier_return.shipped_at = _parse_date(request.form.get('shipped_at')) or supplier_return.shipped_at
    supplier_return.resolved_at = _parse_date(request.form.get('resolved_at')) or supplier_return.resolved_at
    supplier_return.final_decision = request.form.get('final_decision', supplier_return.final_decision)
    supplier_return.decision_comment = request.form.get('decision_comment', supplier_return.decision_comment)
    supplier_return.stock_impact = request.form.get('stock_impact', supplier_return.stock_impact)
    supplier_return.payment_impact = request.form.get('payment_impact', supplier_return.payment_impact)

    if supplier_return.status in {SupplierReturn.STATUS_REMPLACE, SupplierReturn.STATUS_REMBOURSE, SupplierReturn.STATUS_CLOTURE}:
        if supplier_return.final_decision in {
            SupplierReturn.DECISION_FINALE_REMPLACE,
            SupplierReturn.DECISION_FINALE_REMBOURSE,
            SupplierReturn.DECISION_FINALE_AVOIR,
            SupplierReturn.DECISION_FINALE_REPARE,
            SupplierReturn.DECISION_FINALE_ACCEPTE,
        }:
            nc.close(
                decision={
                    SupplierReturn.DECISION_FINALE_REMPLACE: NonConformity.DECISION_REMPLACEMENT,
                    SupplierReturn.DECISION_FINALE_REMBOURSE: NonConformity.DECISION_REMBOURSEMENT,
                    SupplierReturn.DECISION_FINALE_AVOIR: NonConformity.DECISION_AVOIR,
                    SupplierReturn.DECISION_FINALE_REPARE: NonConformity.DECISION_REPARATION,
                    SupplierReturn.DECISION_FINALE_ACCEPTE: NonConformity.DECISION_ACCEPTATION_DEROGATOIRE,
                }.get(supplier_return.final_decision, nc.decision)
            )
        order_line.quantity_returned_total = max(order_line.quantity_returned_total, supplier_return.quantity)
        if supplier_return.final_decision == SupplierReturn.DECISION_FINALE_ACCEPTE:
            order_line.quantity_quarantine_total = max(order_line.quantity_quarantine_total - supplier_return.quantity, 0)
            order_line.quantity_accepted_total += supplier_return.quantity
        elif supplier_return.final_decision in {SupplierReturn.DECISION_FINALE_REMPLACE, SupplierReturn.DECISION_FINALE_REMBOURSE, SupplierReturn.DECISION_FINALE_AVOIR}:
            order_line.quantity_quarantine_total = max(order_line.quantity_quarantine_total - supplier_return.quantity, 0)

    _recompute_order(order)
    _log('purchase_order', order.id, 'Retour fournisseur mis à jour', f'Retour {supplier_return.id} - {supplier_return.status}')
    db.session.commit()
    flash('Retour fournisseur mis à jour.', 'success')
    return redirect(url_for('procurement.reception_detail', order_id=order.id))
