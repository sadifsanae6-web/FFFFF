from datetime import date
from flask import Blueprint, render_template, session
from ..utils.auth_helpers import login_required
from ..models import PurchaseRequest

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def index():
    requests_list = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all()
    today = date.today()
    stats = {
        "retard": sum(1 for r in requests_list if r.need_date and r.need_date < today and r.status not in ["recue", "payee", "cloturee"]),
        "aujourdhui": sum(1 for r in requests_list if r.need_date == today),
        "avenir": sum(1 for r in requests_list if r.need_date and r.need_date > today),
        "total": len(requests_list),
        "en_attente": sum(1 for r in requests_list if r.status == "en_attente_approbation"),
        "alertes_budget": sum(1 for r in requests_list if (r.available_budget or 0) < r.estimated_amount),
    }
    role = session.get("user", {}).get("role")
    title = "Validation" if role == "approbateur" else "Tableau de bord"
    subtitle = "Gestion intelligente des achats, validations et budgets."
    return render_template("dashboard/index.html", requests_list=requests_list[:8], stats=stats, title=title, subtitle=subtitle)
