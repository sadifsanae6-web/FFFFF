from datetime import date, timedelta
from pathlib import Path
from flask import current_app
from ..db import db
from ..models import (
    User, PurchaseRequest, PurchaseRequestLine, SupplierOffer, PurchaseOrder, PurchaseOrderLine,
    Reception, ReceptionLine, Invoice, Payment, Attachment, AuditLog,
    NonConformity, SupplierReturn, SupplierDirectory, ProductCatalog
)
from .priority import compute_priority


def _make_request(code, requester_id, project, department, ptype, budget, need_offset, urgency, criticality, status, description=''):
    req = PurchaseRequest(
        code=code,
        project_name=project,
        department=department,
        purchase_type=ptype,
        estimated_amount=0,
        available_budget=budget,
        need_date=date.today() + timedelta(days=need_offset),
        urgency=urgency,
        criticality=criticality,
        description=description,
        status=status,
        requester_id=requester_id,
    )
    return req


def seed_database():
    if User.query.first():
        return

    users = [
        ('Sara Demandeur', 'demandeur@sp.local', '1234', 'demandeur'),
        ('Youssef Approbateur', 'approbateur@sp.local', '1234', 'approbateur'),
        ('Nadia Acheteur', 'acheteur@sp.local', '1234', 'acheteur'),
        ('Meryem Magasin', 'magasinier@sp.local', '1234', 'magasinier'),
        ('Amine Qualité', 'qualite@sp.local', '1234', 'controle_qualite'),
        ('Youssef Comptable', 'comptable@sp.local', '1234', 'comptable'),
    ]
    saved = []
    for name, email, pwd, role in users:
        u = User(full_name=name, email=email, role=role)
        u.set_password(pwd)
        db.session.add(u)
        saved.append(u)
    db.session.flush()
    requester = saved[0]

    supplier_rows = [
        SupplierDirectory(name='Test Réactifs', email='testreactifs@hotmail.com ; assistente.fatima@test-reactifs.com', phone='0537855756 / 62', address='13 bd Lalla Asmaa résid. Chams n°4, fabrique t, Salé 11000', service='Matériel de laboratoire, consommables, MC, réactifs chimiques'),
        SupplierDirectory(name='Biolab Diagnostics', email='info.biolabdiagnostics@gmail.com', phone='0522600506 / 07', address='12 Bd Hassan Al Alaoui, Rés Nissrine, Ain Borja, Casablanca', service='Matériel de laboratoire, réactifs et produits chimiques, consommables et MC'),
        SupplierDirectory(name='Normalab', email='normalabsarl@gmail.com', phone='0522661350 / 52', address="N°9 Allée des orangers, Lot du départ, Ain Sbaa, Casablanca", service='Matériel de laboratoire, réactifs et produits chimiques, consommables'),
        SupplierDirectory(name='Isolab', email='isolab@isolabmaroc.com', phone='0522592306 / 07 / 8 / 9', address='Lot N° 30, parc industriel CFCIM, Bouskoura, 27182 Bouskoura', service='Équipements, matériel de laboratoire, consommables'),
    ]
    db.session.add_all(supplier_rows)

    product_rows = [
        ProductCatalog(name='PL1 Boite de Petri 55 contact'),
        ProductCatalog(name='PL2 Boites de Petri 60'),
        ProductCatalog(name='PL3 Boites de Petri 90'),
        ProductCatalog(name='PL4 Boites de Petri 140'),
        ProductCatalog(name='PL5 Étaleur Digralsky jetable stérile'),
        ProductCatalog(name='PL6 Pipettes plastique jetables stériles 1 mL'),
    ]
    db.session.add_all(product_rows)

    req14 = _make_request('REQ-2026-014', requester.id, 'Contrôle qualité interne', 'Contrôle qualité', 'Fournitures', 3000, 2, 2, 2, 'commandee', description='Écran réunion salle comité')
    req13 = _make_request('REQ-2026-013', requester.id, 'Physico-chimie des aliments', 'Administration', 'Fournitures', 500, 3, 1, 1, 'en_consultation')
    req12 = _make_request('REQ-2026-012', requester.id, 'Maintenance laboratoire', 'Maintenance & métrologie', 'Fournitures', 4000, 5, 3, 4, 'payee')
    req11 = _make_request('REQ-2026-011', requester.id, 'Microbiologie des eaux', 'Logistique & stock', 'Services', 1500, 6, 2, 3, 'facturee')
    req10 = _make_request('REQ-2026-010', requester.id, 'Maintenance laboratoire', 'Maintenance & métrologie', 'Services', 2500, 8, 4, 3, 'facturee')
    reqs = [req14, req13, req12, req11, req10]
    db.session.add_all(reqs)
    db.session.flush()

    def add_req_lines(req, rows):
        for idx, row in enumerate(rows, start=1):
            db.session.add(PurchaseRequestLine(request_id=req.id, line_no=idx, **row))
        db.session.flush()
        req.recompute_estimated_amount()
        req.priority_score = compute_priority(req.urgency, req.criticality, req.estimated_amount)

    add_req_lines(req14, [
        dict(item_name='Écran interactif 75 pouces', item_reference='ART-ECRAN-75', line_type='article', uom='Pièce', quantity=2, estimated_unit_price=850, quality_control_required=True, delivery_site='Magasin central - Rabat', description='Écran tactile'),
        dict(item_name='Support mural renforcé', item_reference='ART-SUP-01', line_type='article', uom='Pièce', quantity=2, estimated_unit_price=120, quality_control_required=False, delivery_site='Magasin central - Rabat', description='Accessoire fixation'),
    ])
    add_req_lines(req13, [
        dict(item_name='Papier A4', item_reference='PAP-A4', line_type='article', uom='Ramette', quantity=20, estimated_unit_price=5, quality_control_required=False, delivery_site='Administration', description='Papier bureautique'),
    ])
    add_req_lines(req12, [
        dict(item_name='Presse hydraulique', item_reference='PRS-01', line_type='article', uom='Pièce', quantity=1, estimated_unit_price=1200, quality_control_required=True, delivery_site='Dépôt usine', description='Équipement atelier'),
        dict(item_name='Kit sécurité', item_reference='KIT-SEC', line_type='article', uom='Kit', quantity=4, estimated_unit_price=200, quality_control_required=False, delivery_site='Dépôt usine', description='Sécurité opérateur'),
    ])
    add_req_lines(req11, [
        dict(item_name='Prestation transport', item_reference='TRP-001', line_type='service', uom='Mission', quantity=3, estimated_unit_price=300, quality_control_required=False, delivery_site='Plateforme logistique', description='Transport interne'),
    ])
    add_req_lines(req10, [
        dict(item_name='Intervention maintenance', item_reference='MAINT-2026', line_type='service', uom='Prestation', quantity=1, estimated_unit_price=1200, quality_control_required=True, delivery_site='Salle serveurs', description='Maintenance annuelle'),
    ])

    upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / f'request_{req14.id}'
    upload_dir.mkdir(parents=True, exist_ok=True)
    sample_file = upload_dir / 'devis_ecran.txt'
    sample_file.write_text("Devis fournisseur pour achat écran interactif")
    db.session.add(Attachment(filename=sample_file.name, filepath=str(sample_file), request_id=req14.id, entity_type='purchase_request', entity_id=req14.id, author_name='Sara Demandeur'))

    def add_offer(req, name, amount, notes, selected=False, email='', phone='', plan_b=False, address='', contact_person='', supplier_reference=''):
        off = SupplierOffer(supplier_name=name, supplier_email=email, supplier_phone=phone, supplier_address=address, contact_person=contact_person, supplier_reference=supplier_reference, amount=amount, notes=notes, request_id=req.id, is_selected=selected, is_plan_b_offer=plan_b, delay_days=5)
        db.session.add(off)
        return off

    req13.status = 'en_consultation'
    add_offer(req13, 'OfficePaper', 100, 'Livraison 48h', email='contact@officepaper.test', phone='0600000011', address='Casablanca', contact_person='Mme Amal', supplier_reference='OP-2026')
    add_offer(req13, 'PaperPro', 110, 'Livraison 24h', email='commercial@paperpro.test', phone='0600000012', plan_b=True, address='Rabat', contact_person='M. Rachid', supplier_reference='PP-2026')

    off1 = add_offer(req14, 'RenSTORE', req14.estimated_amount, 'Offre principale', selected=True, email='sales@renstore.test', phone='0600000001', address='Marrakech', contact_person='Service commercial', supplier_reference='REN-75')
    add_offer(req14, 'TechStore SARL', req14.estimated_amount, 'Offre plan B', email='contact@techstore.test', phone='0600000002', plan_b=True, address='Casablanca', contact_person='Mme Sofia', supplier_reference='TS-2026')
    cmd_active = PurchaseOrder(code='CMD-2026-018', supplier_name=off1.supplier_name, supplier_email=off1.supplier_email, supplier_phone=off1.supplier_phone, amount=off1.amount, status='commandee', request_id=req14.id, selected_offer=off1, reception_site='Magasin central - Rabat')
    db.session.add(cmd_active)
    db.session.flush()
    for line in req14.lines:
        db.session.add(PurchaseOrderLine(order_id=cmd_active.id, request_line_id=line.id, item_name=line.item_name, item_reference=line.item_reference, uom=line.uom, quantity_ordered=line.quantity, unit_price=line.estimated_unit_price, quality_control_required=line.quality_control_required, delivery_site=line.delivery_site))
    db.session.add(AuditLog(entity_type='purchase_order', entity_id=cmd_active.id, action='Création commande', actor_name='Nadia Acheteur', details='Commande créée et en attente de réception'))

    off2 = add_offer(req12, 'TechStore SARL', req12.estimated_amount, 'Équipements atelier', selected=True, email='contact@techstore.test', phone='0600000002', address='Casablanca', contact_person='Mme Sofia', supplier_reference='TS-AT-01')
    cmd_ok = PurchaseOrder(code='CMD-2026-015', supplier_name=off2.supplier_name, supplier_email=off2.supplier_email, supplier_phone=off2.supplier_phone, amount=off2.amount, status='reception_conforme', request_id=req12.id, selected_offer=off2, reception_site='Dépôt usine')
    db.session.add(cmd_ok)
    db.session.flush()
    line_ok1 = PurchaseOrderLine(order_id=cmd_ok.id, request_line_id=req12.lines[0].id, item_name='Presse hydraulique', item_reference='PRS-01', uom='Pièce', quantity_ordered=1, unit_price=1200, quantity_delivered_total=1, quantity_accepted_total=1, status='acceptee', quality_control_required=True, delivery_site='Dépôt usine')
    line_ok2 = PurchaseOrderLine(order_id=cmd_ok.id, request_line_id=req12.lines[1].id, item_name='Kit sécurité', item_reference='KIT-SEC', uom='Kit', quantity_ordered=4, unit_price=200, quantity_delivered_total=4, quantity_accepted_total=4, status='acceptee', delivery_site='Dépôt usine')
    db.session.add_all([line_ok1, line_ok2])
    db.session.flush()
    rec_ok = Reception(code='REC-2026-010', order_id=cmd_ok.id, logistic_status='complete', status='cloturee', observations='Réception conforme', received_by_name='Meryem Magasin', quality_decided_by_name='Amine Qualité', quality_decision_date=date.today())
    db.session.add(rec_ok)
    db.session.flush()
    db.session.add_all([
        ReceptionLine(reception_id=rec_ok.id, order_line_id=line_ok1.id, quantity_ordered=1, quantity_delivered_before=0, quantity_delivered_now=1, quantity_accepted=1, quantity_remaining=0, status='acceptee', quality_decision='accepter'),
        ReceptionLine(reception_id=rec_ok.id, order_line_id=line_ok2.id, quantity_ordered=4, quantity_delivered_before=0, quantity_delivered_now=4, quantity_accepted=4, quantity_remaining=0, status='acceptee', quality_decision='accepter'),
    ])

    off3 = add_offer(req11, 'MagiqueStore SARL', req11.estimated_amount, 'Transport interne', selected=True, email='ops@magique.test', phone='0600000003', address='Marrakech', contact_person='M. Karim', supplier_reference='MG-TRP')
    cmd_partial = PurchaseOrder(code='CMD-2026-011', supplier_name=off3.supplier_name, supplier_email=off3.supplier_email, supplier_phone=off3.supplier_phone, amount=off3.amount, status='reception_partielle', request_id=req11.id, selected_offer=off3, reception_site='Plateforme logistique')
    db.session.add(cmd_partial)
    db.session.flush()
    line_partial = PurchaseOrderLine(order_id=cmd_partial.id, request_line_id=req11.lines[0].id, item_name='Prestation transport', item_reference='TRP-001', uom='Mission', quantity_ordered=3, unit_price=300, quantity_delivered_total=2, quantity_accepted_total=2, status='reception_partielle', quality_control_required=False, delivery_site='Plateforme logistique')
    db.session.add(line_partial)
    db.session.flush()
    rec_partial = Reception(code='REC-2026-011', order_id=cmd_partial.id, logistic_status='partielle', status='cloturee', observations='2 missions livrées sur 3', received_by_name='Meryem Magasin', quality_decided_by_name='Meryem Magasin', quality_decision_date=date.today(), is_final=False)
    db.session.add(rec_partial)
    db.session.flush()
    db.session.add(ReceptionLine(reception_id=rec_partial.id, order_line_id=line_partial.id, quantity_ordered=3, quantity_delivered_before=0, quantity_delivered_now=2, quantity_accepted=2, quantity_remaining=1, status='acceptee', quality_decision='accepter'))

    off4 = add_offer(req10, 'TechStore SARL', req10.estimated_amount, 'Maintenance annuelle', selected=True, email='contact@techstore.test', phone='0600000002', address='Casablanca', contact_person='Mme Sofia', supplier_reference='TS-MNT')
    cmd_issue = PurchaseOrder(code='CMD-2026-017', supplier_name=off4.supplier_name, supplier_email=off4.supplier_email, supplier_phone=off4.supplier_phone, amount=off4.amount, status='reception_avec_reserve', request_id=req10.id, selected_offer=off4, reception_site='Salle serveurs', payment_blocked=True, stock_blocked=True)
    db.session.add(cmd_issue)
    db.session.flush()
    line_issue = PurchaseOrderLine(order_id=cmd_issue.id, request_line_id=req10.lines[0].id, item_name='Intervention maintenance', item_reference='MAINT-2026', uom='Prestation', quantity_ordered=1, unit_price=1200, quantity_delivered_total=1, quantity_accepted_total=0.8, quantity_rejected_total=0.2, status='acceptee_avec_reserve', quality_control_required=True, delivery_site='Salle serveurs')
    db.session.add(line_issue)
    db.session.flush()
    rec_issue = Reception(code='REC-2026-012', order_id=cmd_issue.id, logistic_status='avec_reserve', status='cloturee', observations='Intervention réalisée avec anomalies', received_by_name='Amine Qualité', quality_decided_by_name='Amine Qualité', quality_decision_date=date.today(), delivery_note_number='BL-445')
    db.session.add(rec_issue)
    db.session.flush()
    rec_line_issue = ReceptionLine(reception_id=rec_issue.id, order_line_id=line_issue.id, quantity_ordered=1, quantity_delivered_before=0, quantity_delivered_now=1, quantity_accepted=0.8, quantity_rejected=0.2, quantity_remaining=0, status='acceptee_avec_reserve', quality_decision='accepter_avec_reserve', defect_reason='Rapport incomplet', comment='Pièces justificatives manquantes')
    db.session.add(rec_line_issue)
    db.session.flush()
    nc = NonConformity(reception_id=rec_issue.id, reception_line_id=rec_line_issue.id, order_line_id=line_issue.id, reason='Rapport incomplet', comment='Blocage paiement jusqu’à régularisation', severity='majeure', decision='avoir', status='action_fournisseur', payment_blocked=True, stock_blocked=False)
    db.session.add(nc)
    db.session.flush()
    db.session.add(SupplierReturn(non_conformity_id=nc.id, return_type='avoir', quantity=0.2, status='en_cours', decision_comment='Avoir demandé', payment_impact='paiement_bloque', stock_impact='stock_non_integre'))

    db.session.flush()
    invoices = [
        Invoice(code='FAC-2026-006', supplier_name=cmd_ok.supplier_name, amount=2000, status='payee', order_id=cmd_ok.id, due_date=date.today()+timedelta(days=10)),
        Invoice(code='FAC-2026-007', supplier_name=cmd_partial.supplier_name, amount=600, status='a_payer', order_id=cmd_partial.id, due_date=date.today()+timedelta(days=7)),
        Invoice(code='FAC-2026-008', supplier_name=cmd_issue.supplier_name, amount=1200, status='a_verifier', order_id=cmd_issue.id, due_date=date.today()+timedelta(days=5), warning_message='La facture dépasse la partie actuellement acceptable.'),
    ]
    db.session.add_all(invoices)
    db.session.flush()
    db.session.add(Payment(amount=2000, method='Virement', reference='PAY-2000', invoice_id=invoices[0].id))

    db.session.add_all([
        AuditLog(entity_type='purchase_order', entity_id=cmd_ok.id, action='Réception conforme', actor_name='Meryem Magasin', details='Commande réceptionnée sans écart'),
        AuditLog(entity_type='purchase_order', entity_id=cmd_partial.id, action='Réception partielle', actor_name='Meryem Magasin', details='Reste 1 mission en attente'),
        AuditLog(entity_type='purchase_order', entity_id=cmd_issue.id, action='Réception avec réserve', actor_name='Amine Qualité', details='Blocage paiement pour non-conformité'),
    ])

    db.session.commit()
