from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date

from ..db import db
from ..models import PurchaseOrder, Invoice, Payment, AuditLog
from ..utils.auth_helpers import login_required, role_required
from ..utils.codes import next_code

finance_bp = Blueprint('finance', __name__)


def _parse_float(value, default=0.0):
    raw = (value or '').replace(',', '.').strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def _sync_request_status_after_invoice_change(invoice: Invoice) -> None:
    order = invoice.purchase_order
    req = order.purchase_request if order else None
    if not req:
        return

    remaining_invoices = []
    for req_order in req.orders:
        remaining_invoices.extend([req_invoice for req_invoice in req_order.invoices if req_invoice.status != Invoice.STATUS_ARCHIVEE])

    if remaining_invoices:
        req.mark_as_invoiced()
    elif any(req_order.qty_accepted_total > 0 for req_order in req.orders):
        req.mark_as_received()


def _log(entity_type, entity_id, action, details=''):
    db.session.add(AuditLog(entity_type=entity_type, entity_id=entity_id, action=action, actor_name='Finance', details=details))


@finance_bp.route('/factures')
@login_required
def invoices():
    invoices_list = Invoice.query.filter(Invoice.status != Invoice.STATUS_ARCHIVEE).order_by(Invoice.created_at.desc()).all()
    total = len(invoices_list)
    reste = sum(i.remaining_amount for i in invoices_list)
    return render_template('finance/invoices.html', invoices_list=invoices_list, total=total, reste=reste)


@finance_bp.route('/factures/archives')
@login_required
def archived_invoices():
    invoices_list = Invoice.query.filter(Invoice.status == Invoice.STATUS_ARCHIVEE).order_by(Invoice.created_at.desc()).all()
    total = len(invoices_list)
    reste = sum(i.remaining_amount for i in invoices_list)
    return render_template('finance/archived_invoices.html', invoices_list=invoices_list, total=total, reste=reste)


@finance_bp.route('/factures/nouvelle', methods=['GET', 'POST'])
@role_required('comptable')
def new_invoice():
    orders = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_([
            PurchaseOrder.STATUS_CONFORME,
            PurchaseOrder.STATUS_RECEPTION_PARTIELLE,
            PurchaseOrder.STATUS_PARTIELLEMENT_ACCEPTEE,
            PurchaseOrder.STATUS_RESERVE,
            PurchaseOrder.STATUS_QUARANTAINE,
            PurchaseOrder.STATUS_NON_CONFORME,
            PurchaseOrder.STATUS_RETOUR_EN_COURS,
            PurchaseOrder.STATUS_RETOUR_CLOTURE,
        ])
    ).order_by(PurchaseOrder.created_at.desc()).all()

    if request.method == 'POST':
        order = PurchaseOrder.query.get_or_404(int(request.form.get('order_id')))
        amount = _parse_float(request.form.get('amount'))
        warning_message = ''
        if amount <= 0:
            flash('Le montant de facture doit être positif.', 'danger')
            return redirect(url_for('finance.new_invoice'))
        payable_now = order.payable_amount_now
        if amount > payable_now:
            flash(f'Le montant de facture ({amount:.2f} DH) dépasse le reste facturable disponible ({payable_now:.2f} DH).', 'danger')
            return redirect(url_for('finance.new_invoice'))

        invoice = Invoice(
            code=next_code(Invoice, 'FAC'),
            supplier_name=request.form.get('supplier_name', order.supplier_name),
            amount=amount,
            order_id=order.id,
            invoice_date=_parse_date(request.form.get('invoice_date')) or date.today(),
            due_date=_parse_date(request.form.get('due_date')),
            warning_message=warning_message,
        )

        invoice.refresh_status_from_payments()
        order.purchase_request.mark_as_invoiced()
        db.session.add(invoice)
        _log('purchase_order', order.id, 'Facture créée', f'{invoice.code} - montant {amount:.2f} DH')
        db.session.commit()
        flash('Facture enregistrée.' + (f' Avertissement : {warning_message}' if warning_message else ''), 'warning' if warning_message else 'success')
        return redirect(url_for('finance.invoices'))

    return render_template('finance/new_invoice.html', orders=orders)


@finance_bp.route('/factures/<int:invoice_id>/modifier', methods=['GET', 'POST'])
@role_required('comptable')
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    orders = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()

    if request.method == 'POST':
        invoice.supplier_name = request.form.get('supplier_name', invoice.supplier_name)
        invoice.amount = _parse_float(request.form.get('amount'), invoice.amount)
        if request.form.get('order_id'):
            invoice.order_id = int(request.form.get('order_id'))
        invoice.invoice_date = _parse_date(request.form.get('invoice_date')) or invoice.invoice_date
        invoice.due_date = _parse_date(request.form.get('due_date'))
        invoice.warning_message = ''
        if invoice.purchase_order:
            other_invoiced = sum(inv.amount for inv in invoice.purchase_order.invoices if inv.id != invoice.id and inv.status != Invoice.STATUS_ARCHIVEE)
            payable_limit = max(round(invoice.purchase_order.accepted_amount - other_invoiced, 2), 0)
            if invoice.amount > payable_limit:
                invoice.warning_message = f'Le montant de facture dépasse le reste facturable disponible ({payable_limit:.2f} DH).'
        invoice.mark_as_modified()
        invoice.refresh_status_from_payments()
        _log('purchase_order', invoice.order_id, 'Facture modifiée', f'{invoice.code} - montant {invoice.amount:.2f} DH')
        db.session.commit()
        flash('Facture modifiée.', 'success')
        return redirect(url_for('finance.invoices'))

    return render_template('finance/edit_invoice.html', invoice=invoice, orders=orders)


@finance_bp.route('/factures/<int:invoice_id>/archiver', methods=['POST'])
@role_required('comptable')
def archive_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.mark_as_archived()
    _sync_request_status_after_invoice_change(invoice)
    _log('purchase_order', invoice.order_id, 'Facture archivée', invoice.code)
    db.session.commit()
    flash('Facture archivée.', 'info')
    return redirect(url_for('finance.invoices'))


@finance_bp.route('/factures/<int:invoice_id>/restaurer', methods=['POST'])
@role_required('comptable')
def restore_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    invoice.refresh_status_from_payments()
    if invoice.purchase_order and invoice.purchase_order.purchase_request:
        invoice.purchase_order.purchase_request.mark_as_invoiced()
    db.session.commit()
    flash('Facture restaurée.', 'success')
    return redirect(url_for('finance.archived_invoices'))


@finance_bp.route('/paiements')
@login_required
def payments():
    invoices = Invoice.query.filter(Invoice.status != Invoice.STATUS_ARCHIVEE).order_by(Invoice.created_at.desc()).all()
    for invoice in invoices:
        invoice.refresh_status_from_payments()
    db.session.commit()
    payments_list = Payment.query.join(Invoice).filter(Invoice.status != Invoice.STATUS_ARCHIVEE).order_by(Payment.created_at.desc()).all()
    return render_template('finance/payments.html', invoices=invoices, payments_list=payments_list)


@finance_bp.route('/paiements/<int:invoice_id>/payer', methods=['GET', 'POST'])
@role_required('comptable')
def new_payment(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    remaining = invoice.remaining_amount
    payable_now = invoice.max_payable_now

    if request.method == 'POST':
        if not invoice.is_payable():
            flash("Cette facture n'est pas payable à ce stade.", 'info')
            return redirect(url_for('finance.payments'))

        raw_amount = (request.form.get('amount') or '').replace(',', '.').strip()
        amount = float(raw_amount) if raw_amount else min(remaining, payable_now)
        if amount <= 0:
            amount = min(remaining, payable_now)

        if amount > payable_now:
            flash(f"Paiement limité à la partie payable ({payable_now:.2f} DH) selon les quantités acceptées.", 'warning')
            amount = payable_now

        payment = Payment(
            amount=amount,
            method=request.form.get('method', 'Espèces'),
            reference=request.form.get('reference', ''),
            invoice_id=invoice.id,
            status=Payment.STATUS_EFFECTUE,
        )
        db.session.add(payment)
        db.session.flush()
        payment.apply()
        _log('purchase_order', invoice.order_id, 'Paiement enregistré', f'{invoice.code} - {amount:.2f} DH')
        db.session.commit()
        flash('Paiement enregistré.', 'success')
        return redirect(url_for('finance.payments'))

    return render_template('finance/new_payment.html', invoice=invoice, remaining=remaining, payable_now=payable_now)
