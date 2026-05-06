from __future__ import annotations

from datetime import datetime, date
from .db import db
from werkzeug.security import generate_password_hash, check_password_hash


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(db.Model, TimestampMixin):
    __tablename__ = "user"

    ROLE_DEMANDEUR = "demandeur"
    ROLE_APPROBATEUR = "approbateur"
    ROLE_ACHETEUR = "acheteur"
    ROLE_MAGASINIER = "magasinier"
    ROLE_QUALITE = "controle_qualite"
    ROLE_COMPTABLE = "comptable"
    ROLE_ADMIN = "administrateur"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, index=True)

    requests = db.relationship("PurchaseRequest", backref="requester", lazy=True, cascade="all, delete-orphan")

    __mapper_args__ = {"polymorphic_on": role, "polymorphic_identity": "user"}

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles


class Demandeur(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_DEMANDEUR}


class Approbateur(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_APPROBATEUR}


class Acheteur(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_ACHETEUR}


class Magasinier(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_MAGASINIER}


class ControleQualite(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_QUALITE}


class Comptable(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_COMPTABLE}


class Administrateur(User):
    __mapper_args__ = {"polymorphic_identity": User.ROLE_ADMIN}


class SupplierDirectory(db.Model, TimestampMixin):
    __tablename__ = "supplier_directory"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), default="", nullable=False)
    phone = db.Column(db.String(80), default="", nullable=False)
    address = db.Column(db.String(255), default="", nullable=False)
    service = db.Column(db.String(255), default="", nullable=False)




class ProductCatalog(db.Model, TimestampMixin):
    __tablename__ = "product_catalog"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), unique=True, nullable=False, index=True)
    reference = db.Column(db.String(80), default="", nullable=False)
    uom = db.Column(db.String(30), default="Unité", nullable=False)


class PurchaseRequest(db.Model, TimestampMixin):
    __tablename__ = "purchase_request"

    STATUS_BROUILLON = "brouillon"
    STATUS_EN_ATTENTE = "en_attente_approbation"
    STATUS_VALIDEE = "validee"
    STATUS_REFUSEE = "refusee"
    STATUS_EN_CONSULTATION = "en_consultation"
    STATUS_OFFRE_SELECTIONNEE = "offre_selectionnee"
    STATUS_COMMANDEE = "commandee"
    STATUS_RECUE = "recue"
    STATUS_FACTUREE = "facturee"
    STATUS_PAYEE = "payee"
    STATUS_ARCHIVEE = "archivee"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    project_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    purchase_type = db.Column(db.String(80), nullable=False)
    estimated_amount = db.Column(db.Float, nullable=False)
    available_budget = db.Column(db.Float, nullable=True)
    need_date = db.Column(db.Date, nullable=True)
    urgency = db.Column(db.Integer, default=1, nullable=False)
    criticality = db.Column(db.Integer, default=1, nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    priority_score = db.Column(db.Float, default=0, nullable=False)
    status = db.Column(db.String(40), default=STATUS_BROUILLON, nullable=False, index=True)
    approver_comment = db.Column(db.Text, default="", nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    attachments = db.relationship("Attachment", backref="purchase_request", cascade="all, delete-orphan", lazy=True)
    offers = db.relationship("SupplierOffer", backref="purchase_request", cascade="all, delete-orphan", lazy=True, order_by="SupplierOffer.amount.asc()")
    orders = db.relationship("PurchaseOrder", backref="purchase_request", cascade="all, delete-orphan", lazy=True, order_by="PurchaseOrder.created_at.desc()")
    lines = db.relationship("PurchaseRequestLine", backref="purchase_request", cascade="all, delete-orphan", lazy=True, order_by="PurchaseRequestLine.id.asc()")

    def submit_for_approval(self) -> None:
        self.status = self.STATUS_EN_ATTENTE

    def resubmit_after_rejection(self) -> None:
        self.approver_comment = ""
        self.status = self.STATUS_EN_ATTENTE

    def approve(self, comment: str = "") -> None:
        self.approver_comment = comment or ""
        self.status = self.STATUS_VALIDEE

    def reject(self, comment: str = "") -> None:
        self.approver_comment = comment or ""
        self.status = self.STATUS_REFUSEE

    def open_supplier_consultation(self) -> None:
        self.status = self.STATUS_EN_CONSULTATION

    def mark_offer_selected(self) -> None:
        self.status = self.STATUS_OFFRE_SELECTIONNEE

    def mark_as_ordered(self) -> None:
        self.status = self.STATUS_COMMANDEE

    def mark_as_received(self) -> None:
        self.status = self.STATUS_RECUE

    def mark_as_invoiced(self) -> None:
        self.status = self.STATUS_FACTUREE

    def mark_as_paid(self) -> None:
        self.status = self.STATUS_PAYEE

    def mark_as_archived(self) -> None:
        self.status = self.STATUS_ARCHIVEE

    def restore_from_archive(self) -> None:
        if self.orders:
            self.status = self.STATUS_COMMANDEE
        elif self.offers:
            self.status = self.STATUS_OFFRE_SELECTIONNEE if self.get_selected_offer() else self.STATUS_EN_CONSULTATION
        else:
            self.status = self.STATUS_EN_ATTENTE

    def can_be_edited_by_requester(self) -> bool:
        return self.status in {self.STATUS_BROUILLON, self.STATUS_EN_ATTENTE, self.STATUS_REFUSEE}

    def get_selected_offer(self):
        return next((offer for offer in self.offers if offer.is_selected), None)

    def recompute_estimated_amount(self) -> float:
        self.estimated_amount = round(sum(line.estimated_total_amount for line in self.lines), 2)
        return self.estimated_amount


class PurchaseRequestLine(db.Model, TimestampMixin):
    """Ligne de demande d'achat pour permettre une chaîne multi-lignes cohérente."""

    __tablename__ = "purchase_request_line"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("purchase_request.id"), nullable=False)
    line_no = db.Column(db.Integer, default=1, nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    item_reference = db.Column(db.String(80), default="", nullable=False)
    manufacturer_code = db.Column(db.String(80), default="", nullable=False)
    line_type = db.Column(db.String(20), default="article", nullable=False)
    uom = db.Column(db.String(30), default="Unité", nullable=False)
    quantity = db.Column(db.Float, default=1, nullable=False)
    estimated_unit_price = db.Column(db.Float, default=0, nullable=False)
    quality_control_required = db.Column(db.Boolean, default=False, nullable=False)
    delivery_site = db.Column(db.String(120), default="Dépôt principal", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(40), default="brouillon", nullable=False)

    @property
    def estimated_total_amount(self) -> float:
        return round((self.quantity or 0) * (self.estimated_unit_price or 0), 2)


class Attachment(db.Model, TimestampMixin):
    __tablename__ = "attachment"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    attachment_type = db.Column(db.String(40), default="document", nullable=False)
    entity_type = db.Column(db.String(40), default="purchase_request", nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    author_name = db.Column(db.String(120), default="", nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("purchase_request.id"), nullable=True)


class SupplierOffer(db.Model, TimestampMixin):
    __tablename__ = "supplier_offer"

    id = db.Column(db.Integer, primary_key=True)
    supplier_name = db.Column(db.String(120), nullable=False)
    supplier_email = db.Column(db.String(120), default="", nullable=False)
    supplier_phone = db.Column(db.String(40), default="", nullable=False)
    supplier_address = db.Column(db.String(255), default="", nullable=False)
    supplier_service = db.Column(db.String(255), default="", nullable=False)
    contact_person = db.Column(db.String(120), default="", nullable=False)
    supplier_reference = db.Column(db.String(120), default="", nullable=False)
    amount = db.Column(db.Float, default=0, nullable=False)
    delay_days = db.Column(db.Integer, default=0, nullable=False)
    notes = db.Column(db.Text, default="", nullable=False)
    remarks = db.Column(db.Text, default="", nullable=False)
    is_selected = db.Column(db.Boolean, default=False, nullable=False)
    is_plan_b_offer = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("purchase_request.id"), nullable=False)
    lines = db.relationship("SupplierOfferLine", backref="supplier_offer", cascade="all, delete-orphan", lazy=True, order_by="SupplierOfferLine.id.asc()")

    def recompute_amount(self) -> float:
        self.amount = round(sum(line.total_ht for line in self.lines), 2)
        return self.amount

    def select(self) -> None:
        if self.purchase_request:
            for offer in self.purchase_request.offers:
                if not offer.is_archived:
                    offer.is_selected = False
            self.purchase_request.mark_offer_selected()
        self.is_selected = True
        self.is_archived = False

    def archive(self) -> None:
        self.is_archived = True
        self.is_selected = False

    def restore(self) -> None:
        self.is_archived = False


class SupplierOfferLine(db.Model, TimestampMixin):
    __tablename__ = "supplier_offer_line"

    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey("supplier_offer.id"), nullable=False)
    request_line_id = db.Column(db.Integer, db.ForeignKey("purchase_request_line.id"), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    quantity_ordered = db.Column(db.Float, default=1, nullable=False)
    price_ht = db.Column(db.Float, default=0, nullable=False)

    request_line = db.relationship("PurchaseRequestLine", foreign_keys=[request_line_id])

    @property
    def total_ht(self) -> float:
        return round((self.quantity_ordered or 0) * (self.price_ht or 0), 2)


class PurchaseOrder(db.Model, TimestampMixin):
    __tablename__ = "purchase_order"

    STATUS_COMMANDEE = "commandee"
    STATUS_EN_RECEPTION = "en_reception"
    STATUS_RECEPTION_PARTIELLE = "reception_partielle"
    STATUS_ATTENTE_QUALITE = "attente_decision_qualite"
    STATUS_PARTIELLEMENT_ACCEPTEE = "partiellement_acceptee"
    STATUS_CONFORME = "reception_conforme"
    STATUS_RESERVE = "reception_avec_reserve"
    STATUS_QUARANTAINE = "quarantaine"
    STATUS_NON_CONFORME = "non_conforme"
    STATUS_REFUSEE = "reception_refusee"
    STATUS_LITIGE = "litige_fournisseur"
    STATUS_RETOUR_EN_COURS = "retour_en_cours"
    STATUS_RETOUR_CLOTURE = "retour_cloture"
    STATUS_SOLDEE = "soldee"
    STATUS_ARCHIVEE = "archivee"
    STATUS_ANNULEE = "annulee"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    supplier_name = db.Column(db.String(120), nullable=False)
    supplier_email = db.Column(db.String(120), default="", nullable=False)
    supplier_phone = db.Column(db.String(40), default="", nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(40), default=STATUS_COMMANDEE, nullable=False, index=True)
    cancellation_reason = db.Column(db.String(255), default="", nullable=False)
    previous_order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=True)
    reception_site = db.Column(db.String(120), default="Dépôt principal", nullable=False)
    stock_blocked = db.Column(db.Boolean, default=False, nullable=False)
    payment_blocked = db.Column(db.Boolean, default=False, nullable=False)

    request_id = db.Column(db.Integer, db.ForeignKey("purchase_request.id"), nullable=False)
    selected_offer_id = db.Column(db.Integer, db.ForeignKey("supplier_offer.id"), nullable=True)

    selected_offer = db.relationship("SupplierOffer", foreign_keys=[selected_offer_id])
    previous_order = db.relationship("PurchaseOrder", remote_side=[id], uselist=False)
    lines = db.relationship("PurchaseOrderLine", backref="purchase_order", cascade="all, delete-orphan", lazy=True, order_by="PurchaseOrderLine.id.asc()")
    receptions = db.relationship("Reception", backref="purchase_order", cascade="all, delete-orphan", lazy=True, order_by="Reception.created_at.desc()")
    invoices = db.relationship("Invoice", backref="purchase_order", cascade="all, delete-orphan", lazy=True)

    @property
    def latest_reception(self):
        return self.receptions[0] if self.receptions else None

    @property
    def has_open_issue(self):
        return any(nc.is_open for line in self.lines for nc in line.non_conformities)

    @property
    def qty_ordered_total(self) -> float:
        return round(sum(line.quantity_ordered for line in self.lines), 2)

    @property
    def qty_delivered_total(self) -> float:
        return round(sum(line.quantity_delivered_total for line in self.lines), 2)

    @property
    def qty_accepted_total(self) -> float:
        return round(sum(line.quantity_accepted_total for line in self.lines), 2)

    @property
    def qty_quarantine_total(self) -> float:
        return round(sum(line.quantity_quarantine_total for line in self.lines), 2)

    @property
    def qty_rejected_total(self) -> float:
        return round(sum(line.quantity_rejected_total for line in self.lines), 2)

    @property
    def qty_returned_total(self) -> float:
        return round(sum(line.quantity_returned_total for line in self.lines), 2)

    @property
    def qty_remaining_total(self) -> float:
        if self.status == self.STATUS_ANNULEE:
            return 0
        return round(sum(line.quantity_remaining_to_deliver for line in self.lines), 2)

    @property
    def accepted_amount(self) -> float:
        return round(sum(line.accepted_amount for line in self.lines), 2)

    @property
    def ordered_amount(self) -> float:
        return round(sum(line.ordered_amount for line in self.lines), 2)

    @property
    def already_invoiced_amount(self) -> float:
        return round(sum(inv.amount for inv in self.invoices if inv.status != Invoice.STATUS_ARCHIVEE), 2)

    @property
    def payable_amount_now(self) -> float:
        """Montant payable crédible : quantités acceptées moins montants déjà facturés/clos."""
        if self.status == self.STATUS_ANNULEE:
            return 0
        return max(round(self.accepted_amount - self.already_invoiced_amount, 2), 0)

    def cancel_for_plan_b(self, reason: str = "") -> None:
        self.status = self.STATUS_ANNULEE
        self.cancellation_reason = reason or "Commande remplacée par un plan B fournisseur"
        self.payment_blocked = True
        self.stock_blocked = False

    def archive(self) -> None:
        self.status = self.STATUS_ARCHIVEE
        self.payment_blocked = False
        self.stock_blocked = False

    def restore(self) -> None:
        if self.receptions:
            self.refresh_status_from_lines()
        else:
            self.status = self.STATUS_COMMANDEE

    @property
    def has_finance_activity(self) -> bool:
        return any(inv.status != Invoice.STATUS_ARCHIVEE for inv in self.invoices)

    @property
    def is_fully_paid(self) -> bool:
        active_invoices = [inv for inv in self.invoices if inv.status != Invoice.STATUS_ARCHIVEE]
        return bool(active_invoices) and all(inv.status == Invoice.STATUS_PAYEE for inv in active_invoices)

    @property
    def reception_action_label(self) -> str:
        if self.status in {self.STATUS_CONFORME, self.STATUS_ANNULEE}:
            return "Voir"
        if self.status == self.STATUS_COMMANDEE:
            return "Saisir"
        return "Compléter"

    def refresh_status_from_lines(self) -> str:
        if self.status in {self.STATUS_ANNULEE, self.STATUS_ARCHIVEE}:
            return self.status
        if not self.lines:
            self.status = self.STATUS_COMMANDEE
            return self.status

        if any(rec.status == Reception.STATUS_QUALITE_A_TRAITER for rec in self.receptions):
            self.status = self.STATUS_ATTENTE_QUALITE
        elif self.qty_delivered_total <= 0:
            self.status = self.STATUS_COMMANDEE
        else:
            open_ncs = [nc for line in self.lines for nc in line.non_conformities if nc.is_open]
            if any(nc.decision == NonConformity.DECISION_REMPLACEMENT for nc in open_ncs):
                self.status = self.STATUS_RECEPTION_PARTIELLE
            elif any(nc.decision == NonConformity.DECISION_REJETER for nc in open_ncs):
                self.status = self.STATUS_RECEPTION_PARTIELLE
            elif self.qty_accepted_total > 0 and self.qty_rejected_total == 0 and self.qty_quarantine_total == 0:
                self.status = self.STATUS_CONFORME if self.qty_remaining_total <= 0 else self.STATUS_RECEPTION_PARTIELLE
            elif self.qty_remaining_total > 0:
                self.status = self.STATUS_RECEPTION_PARTIELLE if self.qty_accepted_total > 0 else self.STATUS_EN_RECEPTION
            elif self.qty_rejected_total >= self.qty_ordered_total and self.qty_accepted_total <= 0:
                self.status = self.STATUS_REFUSEE
            elif self.qty_accepted_total > 0:
                self.status = self.STATUS_RECEPTION_PARTIELLE
            else:
                self.status = self.STATUS_PARTIELLEMENT_ACCEPTEE

        self.stock_blocked = self.qty_quarantine_total > 0 or any(nc.stock_blocked for line in self.lines for nc in line.non_conformities if nc.is_open)
        open_ncs = [nc for line in self.lines for nc in line.non_conformities if nc.is_open]
        if self.status == self.STATUS_REFUSEE:
            self.payment_blocked = True
        elif any(nc.decision == NonConformity.DECISION_REMPLACEMENT for nc in open_ncs):
            self.payment_blocked = False
        else:
            blocking_ncs = [nc for nc in open_ncs if nc.decision == NonConformity.DECISION_REJETER]
            self.payment_blocked = any(nc.severity in {NonConformity.SEVERITY_MAJEURE, NonConformity.SEVERITY_CRITIQUE} for nc in blocking_ncs)
        return self.status


class PurchaseOrderLine(db.Model, TimestampMixin):
    __tablename__ = "purchase_order_line"

    STATUS_EN_ATTENTE = "en_attente"
    STATUS_RECEPTION_PARTIELLE = "reception_partielle"
    STATUS_ATTENTE_QUALITE = "attente_decision_qualite"
    STATUS_ACCEPTEE = "acceptee"
    STATUS_ACCEPTEE_AVEC_RESERVE = "acceptee_avec_reserve"
    STATUS_QUARANTAINE = "quarantaine"
    STATUS_REJETEE_PARTIELLEMENT = "rejetee_partiellement"
    STATUS_REJETEE = "rejetee"
    STATUS_CLOTUREE = "cloturee"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    request_line_id = db.Column(db.Integer, db.ForeignKey("purchase_request_line.id"), nullable=True)
    item_name = db.Column(db.String(150), nullable=False)
    item_reference = db.Column(db.String(80), default="", nullable=False)
    manufacturer_code = db.Column(db.String(80), default="", nullable=False)
    uom = db.Column(db.String(30), default="Unité", nullable=False)
    quantity_ordered = db.Column(db.Float, default=1, nullable=False)
    unit_price = db.Column(db.Float, default=0, nullable=False)
    quantity_delivered_total = db.Column(db.Float, default=0, nullable=False)
    quantity_accepted_total = db.Column(db.Float, default=0, nullable=False)
    quantity_quarantine_total = db.Column(db.Float, default=0, nullable=False)
    quantity_rejected_total = db.Column(db.Float, default=0, nullable=False)
    quantity_returned_total = db.Column(db.Float, default=0, nullable=False)
    status = db.Column(db.String(40), default=STATUS_EN_ATTENTE, nullable=False, index=True)
    quality_control_required = db.Column(db.Boolean, default=False, nullable=False)
    delivery_site = db.Column(db.String(120), default="Dépôt principal", nullable=False)

    request_line = db.relationship("PurchaseRequestLine", foreign_keys=[request_line_id])
    reception_lines = db.relationship("ReceptionLine", backref="order_line", lazy=True)
    non_conformities = db.relationship("NonConformity", backref="order_line", lazy=True)

    @property
    def ordered_amount(self) -> float:
        return round((self.quantity_ordered or 0) * (self.unit_price or 0), 2)

    @property
    def accepted_amount(self) -> float:
        return round((self.quantity_accepted_total or 0) * (self.unit_price or 0), 2)

    @property
    def quantity_physical_net(self) -> float:
        return max(round(self.quantity_delivered_total - self.quantity_returned_total, 2), 0)

    @property
    def quantity_remaining_to_deliver(self) -> float:
        if self.purchase_order and self.purchase_order.status == PurchaseOrder.STATUS_ANNULEE:
            return 0
        return max(round(self.quantity_ordered - self.quantity_delivered_total, 2), 0)

    @property
    def quantity_pending_quality(self) -> float:
        pending = self.quantity_delivered_total - self.quantity_accepted_total - self.quantity_quarantine_total - self.quantity_rejected_total
        return max(round(pending, 2), 0)

    @property
    def quantity_pending(self):
        return self.quantity_remaining_to_deliver

    def recompute_status(self) -> str:
        if self.quantity_pending_quality > 0:
            self.status = self.STATUS_ATTENTE_QUALITE
        elif self.quantity_accepted_total >= self.quantity_ordered and self.quantity_quarantine_total == 0 and self.quantity_rejected_total == 0:
            self.status = self.STATUS_ACCEPTEE
        elif self.quantity_quarantine_total > 0:
            self.status = self.STATUS_QUARANTAINE
        elif self.quantity_rejected_total >= self.quantity_ordered and self.quantity_accepted_total <= 0:
            self.status = self.STATUS_REJETEE
        elif self.quantity_rejected_total > 0 and self.quantity_accepted_total > 0:
            self.status = self.STATUS_ACCEPTEE_AVEC_RESERVE
        elif self.quantity_delivered_total > 0 and self.quantity_remaining_to_deliver > 0:
            self.status = self.STATUS_RECEPTION_PARTIELLE
        elif self.quantity_delivered_total > 0:
            self.status = self.STATUS_CLOTUREE
        else:
            self.status = self.STATUS_EN_ATTENTE
        return self.status


class Reception(db.Model, TimestampMixin):
    __tablename__ = "reception"

    STATUS_BROUILLON = "brouillon"
    STATUS_QUALITE_A_TRAITER = "qualite_a_traiter"
    STATUS_CLOTUREE = "cloturee"

    LOGISTIC_COMPLETE = "complete"
    LOGISTIC_PARTIAL = "partielle"
    LOGISTIC_WITH_RESERVE = "avec_reserve"
    LOGISTIC_REFUSED_PARTIAL = "refus_partiel"
    LOGISTIC_REFUSED_TOTAL = "refus_total"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    reception_date = db.Column(db.Date, default=date.today, nullable=False)
    delivery_note_number = db.Column(db.String(80), default="", nullable=False)
    delivery_note_date = db.Column(db.Date, nullable=True)
    carrier = db.Column(db.String(120), default="", nullable=False)
    reception_site = db.Column(db.String(120), default="Dépôt principal", nullable=False)
    warehouse = db.Column(db.String(120), default="Magasin central", nullable=False)
    logistic_status = db.Column(db.String(40), default=LOGISTIC_COMPLETE, nullable=False)
    status = db.Column(db.String(40), default=STATUS_QUALITE_A_TRAITER, nullable=False, index=True)
    transport_reservations = db.Column(db.Text, default="", nullable=False)
    refusal_reason = db.Column(db.String(255), default="", nullable=False)
    observations = db.Column(db.Text, default="", nullable=False)
    received_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    received_by_name = db.Column(db.String(120), default="", nullable=False)
    quality_decided_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    quality_decided_by_name = db.Column(db.String(120), default="", nullable=False)
    quality_decision_date = db.Column(db.Date, nullable=True)
    is_final = db.Column(db.Boolean, default=False, nullable=False)

    lines = db.relationship("ReceptionLine", backref="reception", cascade="all, delete-orphan", lazy=True)
    non_conformities = db.relationship("NonConformity", backref="reception", cascade="all, delete-orphan", lazy=True)


class ReceptionLine(db.Model, TimestampMixin):
    __tablename__ = "reception_line"

    STATUS_SAISIE_LOGISTIQUE = "saisie_logistique"
    STATUS_A_CONTROLER = "a_controler"
    STATUS_ACCEPTEE = "acceptee"
    STATUS_ACCEPTEE_AVEC_RESERVE = "acceptee_avec_reserve"
    STATUS_QUARANTAINE = "quarantaine"
    STATUS_REJETEE = "rejetee"
    STATUS_REFUS_QUAI = "refus_a_quai"

    DECISION_ACCEPT = "accepter"
    DECISION_ACCEPT_WITH_RESERVE = "accepter_avec_reserve"
    DECISION_QUARANTINE = "quarantaine"
    DECISION_REJECT = "rejeter"
    DECISION_OPEN_NC = "ouvrir_non_conformite"

    id = db.Column(db.Integer, primary_key=True)
    reception_id = db.Column(db.Integer, db.ForeignKey("reception.id"), nullable=False)
    order_line_id = db.Column(db.Integer, db.ForeignKey("purchase_order_line.id"), nullable=False)
    quantity_ordered = db.Column(db.Float, default=0, nullable=False)
    quantity_delivered_before = db.Column(db.Float, default=0, nullable=False)
    quantity_delivered_now = db.Column(db.Float, default=0, nullable=False)
    quantity_refused_dock = db.Column(db.Float, default=0, nullable=False)
    quantity_accepted = db.Column(db.Float, default=0, nullable=False)
    quantity_quarantine = db.Column(db.Float, default=0, nullable=False)
    quantity_rejected = db.Column(db.Float, default=0, nullable=False)
    quantity_returned = db.Column(db.Float, default=0, nullable=False)
    quantity_remaining = db.Column(db.Float, default=0, nullable=False)
    status = db.Column(db.String(40), default=STATUS_A_CONTROLER, nullable=False, index=True)
    quality_decision = db.Column(db.String(40), default="", nullable=False)
    defect_reason = db.Column(db.String(255), default="", nullable=False)
    comment = db.Column(db.Text, default="", nullable=False)
    lot_number = db.Column(db.String(80), default="", nullable=False)
    serial_number = db.Column(db.String(80), default="", nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    storage_location = db.Column(db.String(120), default="", nullable=False)

    non_conformities = db.relationship("NonConformity", backref="reception_line", lazy=True)


class NonConformity(db.Model, TimestampMixin):
    __tablename__ = "non_conformity"

    STATUS_OUVERTE = "ouverte"
    STATUS_EN_ANALYSE = "en_analyse"
    STATUS_ACTION_FOURNISSEUR = "action_fournisseur"
    STATUS_EN_COURS = "en_cours"
    STATUS_RESOLUE = "resolue"
    STATUS_CLOTUREE = "cloturee"

    SEVERITY_PRODUIT_CONFORME = "produit_conforme"
    SEVERITY_MINEURE = "mineure"
    SEVERITY_MAJEURE = "majeure"
    SEVERITY_CRITIQUE = "critique"

    DECISION_PRODUIT_CONFORME = "produit_conforme"
    DECISION_ACCEPTER = "accepter"
    DECISION_REMPLACEMENT = "remplacement"
    DECISION_REJETER = "rejeter"
    DECISION_AVOIR = "avoir"
    DECISION_REPARATION = "reparation"
    DECISION_ACCEPTATION_DEROGATOIRE = "acceptation_derogatoire"
    DECISION_RETOUR_FOURNISSEUR = "retour_fournisseur"
    DECISION_AUCUNE = "a_definir"

    id = db.Column(db.Integer, primary_key=True)
    reception_id = db.Column(db.Integer, db.ForeignKey("reception.id"), nullable=False)
    reception_line_id = db.Column(db.Integer, db.ForeignKey("reception_line.id"), nullable=False)
    order_line_id = db.Column(db.Integer, db.ForeignKey("purchase_order_line.id"), nullable=False)
    status = db.Column(db.String(40), default=STATUS_OUVERTE, nullable=False, index=True)
    severity = db.Column(db.String(20), default=SEVERITY_MAJEURE, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    comment = db.Column(db.Text, default="", nullable=False)
    decision = db.Column(db.String(40), default=DECISION_AUCUNE, nullable=False)
    payment_blocked = db.Column(db.Boolean, default=True, nullable=False)
    stock_blocked = db.Column(db.Boolean, default=True, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    return_case = db.relationship("SupplierReturn", backref="non_conformity", uselist=False, cascade="all, delete-orphan")

    @property
    def is_open(self) -> bool:
        return self.status not in {self.STATUS_RESOLUE, self.STATUS_CLOTUREE}

    def close(self, decision: str | None = None) -> None:
        if decision:
            self.decision = decision
        self.status = self.STATUS_CLOTUREE
        self.payment_blocked = False
        self.stock_blocked = False
        self.closed_at = datetime.utcnow()


class SupplierReturn(db.Model, TimestampMixin):
    __tablename__ = "supplier_return"

    STATUS_EN_COURS = "en_cours"
    STATUS_EXPEDIE = "expedie"
    STATUS_RECU_FOURNISSEUR = "recu_par_fournisseur"
    STATUS_REMPLACE = "remplace"
    STATUS_REMBOURSE = "rembourse"
    STATUS_CLOTURE = "cloture"

    DECISION_FINALE_REMPLACE = "remplacement_effectif"
    DECISION_FINALE_REMBOURSE = "remboursement_effectif"
    DECISION_FINALE_AVOIR = "avoir_emis"
    DECISION_FINALE_REPARE = "reparation_effective"
    DECISION_FINALE_ACCEPTE = "acceptation_derogatoire"

    id = db.Column(db.Integer, primary_key=True)
    non_conformity_id = db.Column(db.Integer, db.ForeignKey("non_conformity.id"), nullable=False)
    return_type = db.Column(db.String(40), nullable=False)
    quantity = db.Column(db.Float, default=0, nullable=False)
    status = db.Column(db.String(40), default=STATUS_EN_COURS, nullable=False, index=True)
    shipped_at = db.Column(db.Date, nullable=True)
    resolved_at = db.Column(db.Date, nullable=True)
    final_decision = db.Column(db.String(60), default="", nullable=False)
    decision_comment = db.Column(db.Text, default="", nullable=False)
    stock_impact = db.Column(db.String(60), default="stock_bloque", nullable=False)
    payment_impact = db.Column(db.String(60), default="paiement_bloque", nullable=False)


class AuditLog(db.Model, TimestampMixin):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(120), nullable=False)
    actor_name = db.Column(db.String(120), default="", nullable=False)
    details = db.Column(db.Text, default="", nullable=False)


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoice"

    STATUS_A_PAYER = "a_payer"
    STATUS_A_VERIFIER = "a_verifier"
    STATUS_MODIFIEE = "modifiee"
    STATUS_PARTIELLEMENT_PAYEE = "partiellement_payee"
    STATUS_PAYEE = "payee"
    STATUS_ARCHIVEE = "archivee"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    supplier_name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(40), default=STATUS_A_PAYER, nullable=False, index=True)
    invoice_date = db.Column(db.Date, default=date.today, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey("purchase_order.id"), nullable=False)
    warning_message = db.Column(db.Text, default="", nullable=False)

    payments = db.relationship("Payment", backref="invoice", cascade="all, delete-orphan", lazy=True, order_by="Payment.created_at.desc()")

    @property
    def active_payments(self):
        return [payment for payment in self.payments if payment.status != Payment.STATUS_ANNULE]

    @property
    def paid_total(self) -> float:
        return round(sum(payment.amount for payment in self.active_payments), 2)

    @property
    def remaining_amount(self) -> float:
        return max(round(self.amount - self.paid_total, 2), 0)

    @property
    def accepted_amount_reference(self) -> float:
        return self.purchase_order.accepted_amount if self.purchase_order else 0.0

    @property
    def match_status(self) -> str:
        if self.amount <= self.accepted_amount_reference:
            return "rapprochee"
        if self.accepted_amount_reference <= 0:
            return "non_rapprochee"
        return "depasse_quantites_acceptees"

    @property
    def max_payable_now(self) -> float:
        if not self.purchase_order:
            return self.remaining_amount
        if self.purchase_order.status == PurchaseOrder.STATUS_ANNULEE:
            return 0
        cap = max(min(self.amount, self.purchase_order.accepted_amount) - self.paid_total, 0)
        return round(cap, 2)

    def mark_as_modified(self) -> None:
        self.status = self.STATUS_MODIFIEE

    def mark_as_unpaid(self) -> None:
        self.status = self.STATUS_A_PAYER if self.match_status == "rapprochee" else self.STATUS_A_VERIFIER
        if self.purchase_order:
            self.purchase_order.purchase_request.mark_as_invoiced()

    def mark_as_paid(self) -> None:
        self.status = self.STATUS_PAYEE

    def mark_as_archived(self) -> None:
        self.status = self.STATUS_ARCHIVEE

    def refresh_status_from_payments(self) -> str:
        if self.status == self.STATUS_ARCHIVEE:
            return self.status
        if self.paid_total <= 0:
            self.mark_as_unpaid()
        elif self.paid_total < self.amount:
            self.status = self.STATUS_PARTIELLEMENT_PAYEE
            if self.purchase_order:
                self.purchase_order.purchase_request.mark_as_invoiced()
        else:
            self.mark_as_paid()
        return self.status

    def is_payable(self) -> bool:
        return self.remaining_amount > 0 and self.status != self.STATUS_ARCHIVEE and self.max_payable_now > 0


class Payment(db.Model, TimestampMixin):
    __tablename__ = "payment"

    STATUS_ENREGISTRE = "enregistre"
    STATUS_EFFECTUE = "effectue"
    STATUS_ANNULE = "annule"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=date.today, nullable=False)
    method = db.Column(db.String(40), default="Espèces", nullable=False)
    reference = db.Column(db.String(120), default="", nullable=False)
    status = db.Column(db.String(40), default=STATUS_EFFECTUE, nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)

    def apply(self) -> None:
        if self.invoice:
            self.invoice.refresh_status_from_payments()

    def cancel(self) -> None:
        self.status = self.STATUS_ANNULE
        if self.invoice:
            self.invoice.refresh_status_from_payments()
