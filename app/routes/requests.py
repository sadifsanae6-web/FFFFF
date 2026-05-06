from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app, abort
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

from ..db import db
from ..models import PurchaseRequest, PurchaseRequestLine, Attachment, ProductCatalog
from ..services.priority import compute_priority
from ..utils.auth_helpers import login_required, role_required
from ..utils.exports import export_requests_to_excel, export_requests_to_pdf
from ..utils.codes import next_code
from sqlalchemy import func

requests_bp = Blueprint('requests', __name__, url_prefix='/demandes')

PURCHASE_TYPES = ['Matières premières', 'Fournitures', 'Services']
DEPARTMENTS = ['Microbiologie', 'Physico-chimie', 'Contrôle qualité', 'Maintenance & métrologie', 'Logistique & stock', 'Administration']
LINE_TYPES = ['article', 'service']

DEFAULT_PROJECT_OPTIONS = [
    'Microbiologie des aliments',
    'Microbiologie des eaux',
    'Physico-chimie des eaux',
    'Physico-chimie des aliments',
    'Contrôle qualité interne',
    'Maintenance laboratoire',
]
EXCLUDED_PROJECT_OPTIONS = {
    'Achat écran interactif',
    'Maintenance serveurs',
    'Papier bureautique',
    'Transport logistique',
}

DEFAULT_PRODUCT_OPTIONS = [
    'PL1 Boite de Petri 55 contact',
    'PL2 Boites de Petri 60',
    'PL3 Boites de Petri 90',
    'PL4 Boites de Petri 140',
    'PL5 Étaleur Digralsky jetable stérile',
    'PL6 Pipettes plastique jetables stériles 1 mL',
]



def _project_options():
    existing = [row[0] for row in db.session.query(PurchaseRequest.project_name).distinct().order_by(PurchaseRequest.project_name.asc()).all() if row[0] and row[0] not in EXCLUDED_PROJECT_OPTIONS]
    options = list(DEFAULT_PROJECT_OPTIONS)
    for name in existing:
        if name not in options:
            options.append(name)
    return options

def _product_options():
    products = ProductCatalog.query.order_by(ProductCatalog.name.asc()).all()
    if not products:
        return DEFAULT_PRODUCT_OPTIONS
    return [p.name for p in products]


def _remember_new_articles(lines_data):
    """Enregistre automatiquement les nouveaux articles saisis manuellement."""
    for line in lines_data:
        if line.get('line_type') != 'article':
            continue
        name = (line.get('item_name') or '').strip()
        if not name:
            continue
        exists = ProductCatalog.query.filter(func.lower(ProductCatalog.name) == name.lower()).first()
        if not exists:
            db.session.add(ProductCatalog(name=name, reference=line.get('item_reference') or '', uom=line.get('uom') or 'Unité'))


def _current_user_id():
    return session['user']['id']


def _can_access(req):
    user = session.get('user')
    return user and (user['role'] != 'demandeur' or req.requester_id == user['id'])


def _save_attachment(uploaded_file, req_id):
    if not uploaded_file or not uploaded_file.filename:
        return
    filename = secure_filename(uploaded_file.filename)
    if not filename:
        return

    upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / f'request_{req_id}'
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    base = filepath.stem
    ext = filepath.suffix
    i = 1
    while filepath.exists():
        filepath = upload_dir / f'{base}_{i}{ext}'
        i += 1

    uploaded_file.save(filepath)
    db.session.add(Attachment(filename=filepath.name, filepath=str(filepath), request_id=req_id))


def _parse_request_lines(form):
    item_names = form.getlist('line_item_name[]')
    refs = form.getlist('line_item_reference[]')
    manufacturer_codes = form.getlist('line_manufacturer_code[]')
    line_types = form.getlist('line_type[]')
    uoms = form.getlist('line_uom[]')
    quantities = form.getlist('line_quantity[]')
    prices = form.getlist('line_estimated_unit_price[]')
    qc_flags = form.getlist('line_quality_control_required[]')
    delivery_sites = form.getlist('line_delivery_site[]')
    descriptions = form.getlist('line_description[]')

    lines = []
    errors = []
    for idx, name in enumerate(item_names, start=1):
        if not (name or '').strip():
            continue
        qty = float((quantities[idx - 1] or '0').replace(',', '.'))
        price = float((prices[idx - 1] or '0').replace(',', '.'))
        if qty <= 0:
            errors.append(f'Ligne {idx} : quantité invalide.')
        if price < 0:
            errors.append(f'Ligne {idx} : prix estimatif invalide.')
        lines.append({
            'line_no': idx,
            'item_name': name.strip(),
            'item_reference': (refs[idx - 1] or '').strip(),
            'manufacturer_code': (manufacturer_codes[idx - 1] if idx - 1 < len(manufacturer_codes) else '').strip(),
            'line_type': (line_types[idx - 1] if idx - 1 < len(line_types) else 'article').strip() or 'article',
            'uom': (uoms[idx - 1] or 'Unité').strip(),
            'quantity': qty,
            'estimated_unit_price': price,
            'quality_control_required': qc_flags[idx - 1] == '1',
            'delivery_site': (delivery_sites[idx - 1] or 'Dépôt principal').strip(),
            'description': (descriptions[idx - 1] or '').strip(),
        })
    if not lines:
        errors.append('Ajoute au moins une ligne de demande.')
    return lines, errors


@requests_bp.route('/')
@login_required
def index():
    user = session.get('user')
    query = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc())
    if user['role'] == 'demandeur':
        query = query.filter_by(requester_id=user['id'])
    requests_list = query.filter(PurchaseRequest.status != PurchaseRequest.STATUS_ARCHIVEE).all()
    return render_template('requests/index.html', requests_list=requests_list)


@requests_bp.route('/archives')
@login_required
def archived():
    user = session.get('user')
    query = PurchaseRequest.query.filter(PurchaseRequest.status == PurchaseRequest.STATUS_ARCHIVEE).order_by(PurchaseRequest.created_at.desc())
    if user['role'] == 'demandeur':
        query = query.filter_by(requester_id=user['id'])
    requests_list = query.all()
    return render_template('requests/archived.html', requests_list=requests_list)


@requests_bp.route('/nouvelle', methods=['GET', 'POST'])
@role_required('demandeur')
def new():
    if request.method == 'POST':
        lines_data, line_errors = _parse_request_lines(request.form)
        if line_errors:
            for err in line_errors:
                flash(err, 'danger')
            return render_template('requests/new.html', req=None, purchase_types=PURCHASE_TYPES, departments=DEPARTMENTS, line_types=LINE_TYPES, product_options=_product_options(), project_options=_project_options())

        estimated_amount = round(sum(line['quantity'] * line['estimated_unit_price'] for line in lines_data), 2)
        urgency = int(request.form.get('urgency') or 1)
        criticality = int(request.form.get('criticality') or 1)
        priority = compute_priority(urgency, criticality, estimated_amount)

        req = PurchaseRequest(
            code=next_code(PurchaseRequest, 'REQ'),
            project_name=request.form.get('project_name', '').strip() or 'Demande laboratoire',
            department=request.form.get('department', ''),
            purchase_type=request.form.get('purchase_type', ''),
            estimated_amount=estimated_amount,
            available_budget=0,
            need_date=datetime.strptime(request.form.get('need_date'), '%Y-%m-%d').date() if request.form.get('need_date') else None,
            urgency=urgency,
            criticality=criticality,
            description=request.form.get('description', ''),
            priority_score=priority,
            requester_id=_current_user_id(),
        )
        req.submit_for_approval()
        db.session.add(req)
        db.session.flush()
        _remember_new_articles(lines_data)
        for line in lines_data:
            db.session.add(PurchaseRequestLine(request_id=req.id, **line))
        for uploaded in request.files.getlist('attachments'):
            _save_attachment(uploaded, req.id)
        db.session.commit()
        flash('Demande créée avec succès.', 'success')
        return redirect(url_for('requests.index'))

    return render_template('requests/new.html', req=None, purchase_types=PURCHASE_TYPES, departments=DEPARTMENTS, line_types=LINE_TYPES, product_options=_product_options(), project_options=_project_options())


@requests_bp.route('/<int:request_id>')
@login_required
def detail(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if not _can_access(req):
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('requests/detail.html', req=req)


@requests_bp.route('/<int:request_id>/modifier', methods=['GET', 'POST'])
@role_required('demandeur')
def edit(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if req.requester_id != _current_user_id():
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('requests.index'))
    if not req.can_be_edited_by_requester():
        flash("Cette demande ne peut plus être modifiée à ce stade.", 'warning')
        return redirect(url_for('requests.detail', request_id=req.id))

    if request.method == 'POST':
        lines_data, line_errors = _parse_request_lines(request.form)
        if line_errors:
            for err in line_errors:
                flash(err, 'danger')
            return render_template('requests/edit.html', req=req, purchase_types=PURCHASE_TYPES, departments=DEPARTMENTS, line_types=LINE_TYPES, product_options=_product_options(), project_options=_project_options())

        req.project_name = request.form.get('project_name', req.project_name).strip() or 'Demande laboratoire'
        req.department = request.form.get('department', req.department)
        req.purchase_type = request.form.get('purchase_type', req.purchase_type)
        req.available_budget = req.available_budget or 0
        req.need_date = datetime.strptime(request.form.get('need_date'), '%Y-%m-%d').date() if request.form.get('need_date') else req.need_date
        req.urgency = int(request.form.get('urgency') or req.urgency)
        req.criticality = int(request.form.get('criticality') or req.criticality)
        req.description = request.form.get('description', req.description)

        PurchaseRequestLine.query.filter_by(request_id=req.id).delete()
        _remember_new_articles(lines_data)
        for line in lines_data:
            db.session.add(PurchaseRequestLine(request_id=req.id, **line))

        req.recompute_estimated_amount()
        req.priority_score = compute_priority(req.urgency, req.criticality, req.estimated_amount)
        if req.status == PurchaseRequest.STATUS_REFUSEE:
            req.resubmit_after_rejection()

        for uploaded in request.files.getlist('attachments'):
            _save_attachment(uploaded, req.id)
        db.session.commit()
        flash('Demande modifiée.', 'success')
        return redirect(url_for('requests.detail', request_id=req.id))

    return render_template('requests/edit.html', req=req, purchase_types=PURCHASE_TYPES, departments=DEPARTMENTS, line_types=LINE_TYPES, product_options=_product_options(), project_options=_project_options())


@requests_bp.route('/<int:request_id>/archiver', methods=['POST'])
@role_required('demandeur')
def archive(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if req.requester_id != _current_user_id():
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('requests.index'))
    if req.status not in {PurchaseRequest.STATUS_BROUILLON, PurchaseRequest.STATUS_EN_ATTENTE, PurchaseRequest.STATUS_REFUSEE}:
        flash("Cette demande ne peut pas être archivée à ce stade.", 'warning')
        return redirect(url_for('requests.detail', request_id=req.id))
    req.mark_as_archived()
    db.session.commit()
    flash('Demande archivée.', 'info')
    return redirect(url_for('requests.index'))


@requests_bp.route('/<int:request_id>/restaurer', methods=['POST'])
@role_required('demandeur')
def restore(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if req.requester_id != _current_user_id():
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('requests.index'))
    if req.status != PurchaseRequest.STATUS_ARCHIVEE:
        flash("Cette demande n'est pas archivée.", 'warning')
        return redirect(url_for('requests.index'))
    req.restore_from_archive()
    db.session.commit()
    flash('Demande restaurée.', 'success')
    return redirect(url_for('requests.archived'))


@requests_bp.route('/pieces-jointes/<int:attachment_id>/telecharger')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    req = attachment.purchase_request
    if not _can_access(req):
        abort(403)
    return send_file(attachment.filepath, as_attachment=True, download_name=attachment.filename)


@requests_bp.route('/pieces-jointes/<int:attachment_id>/supprimer', methods=['POST'])
@role_required('demandeur')
def delete_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    req = attachment.purchase_request
    if req.requester_id != _current_user_id():
        flash('Accès non autorisé.', 'danger')
        return redirect(url_for('requests.index'))
    try:
        Path(attachment.filepath).unlink(missing_ok=True)
    except Exception:
        pass
    request_id = req.id
    db.session.delete(attachment)
    db.session.commit()
    flash('Pièce jointe supprimée.', 'info')
    return redirect(url_for('requests.detail', request_id=request_id))


@requests_bp.route('/export/excel')
@login_required
def export_excel():
    path = export_requests_to_excel(PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all())
    return send_file(path, as_attachment=True)


@requests_bp.route('/export/pdf')
@login_required
def export_pdf():
    path = export_requests_to_pdf(PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all())
    return send_file(path, as_attachment=True)


@requests_bp.route('/en-attente')
@role_required('approbateur')
def pending():
    requests_list = PurchaseRequest.query.filter_by(status=PurchaseRequest.STATUS_EN_ATTENTE).order_by(PurchaseRequest.priority_score.desc()).all()
    return render_template('requests/pending.html', requests_list=requests_list)


@requests_bp.route('/<int:request_id>/valider', methods=['POST'])
@role_required('approbateur')
def approve(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if req.status != PurchaseRequest.STATUS_EN_ATTENTE:
        flash("Cette demande n'est pas en attente d'approbation.", 'warning')
        return redirect(url_for('requests.detail', request_id=req.id))
    req.approve(comment=request.form.get('approver_comment', ''))
    db.session.commit()
    flash('Demande validée.', 'success')
    return redirect(url_for('requests.detail', request_id=req.id))


@requests_bp.route('/<int:request_id>/refuser', methods=['POST'])
@role_required('approbateur')
def reject(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    if req.status != PurchaseRequest.STATUS_EN_ATTENTE:
        flash("Cette demande n'est pas en attente d'approbation.", 'warning')
        return redirect(url_for('requests.detail', request_id=req.id))
    req.reject(comment=request.form.get('approver_comment', ''))
    db.session.commit()
    flash('Demande refusée.', 'info')
    return redirect(url_for('requests.detail', request_id=req.id))
