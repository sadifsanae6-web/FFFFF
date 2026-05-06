from flask import Blueprint, render_template
from ..utils.auth_helpers import login_required
from ..models import PurchaseRequest, Invoice, Payment
from ..services.charts import generate_pilotage_charts

pilotage_bp = Blueprint("pilotage", __name__)

@pilotage_bp.route("/pilotage")
@login_required
def index():
    requests_list = PurchaseRequest.query.all()
    invoices = Invoice.query.all()
    payments = Payment.query.all()
    charts = generate_pilotage_charts(requests_list, invoices, payments)
    total_achats = sum(r.estimated_amount for r in requests_list)
    total_factures = sum(i.amount for i in invoices)
    total_paye = sum(p.amount for p in payments)
    reste = max(total_factures - total_paye, 0)
    stats = {"demandes": len(requests_list), "montant_achats": total_achats, "montant_factures": total_factures, "paye": total_paye, "reste": reste}
    return render_template("pilotage/index.html", stats=stats, charts=charts)
