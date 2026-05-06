from collections import defaultdict

SERVICE_ORDER = ['Microbiologie', 'Physico-chimie', 'Contrôle qualité', 'Maintenance & métrologie', 'Logistique & stock', 'Administration']
SERVICE_ALIASES = {
    'Finance': 'Administration',
    'Production': 'Maintenance & métrologie',
    'Logistique': 'Logistique & stock',
    'IT': 'Maintenance & métrologie',
}
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import current_app
from pathlib import Path

def generate_pilotage_charts(requests, invoices, payments):
    static_dir = Path(current_app.root_path) / "static"
    charts_dir = static_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    by_department = defaultdict(float)
    for req in requests:
        service = SERVICE_ALIASES.get(req.department, req.department)
        if service in SERVICE_ORDER:
            by_department[service] += req.estimated_amount

    paid = sum(p.amount for p in payments)
    total_invoice = sum(i.amount for i in invoices)
    remaining = max(total_invoice - paid, 0)

    # bar chart
    fig = plt.figure(figsize=(8, 4.2))
    # Afficher toujours tous les services de la liste officielle, même si leur montant est 0.
    labels = SERVICE_ORDER
    values = [by_department.get(s, 0) for s in labels]
    plt.bar(labels, values)
    plt.title("Dépenses par service")
    plt.xlabel("Service")
    plt.ylabel("Montant (DH)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    dep_path = charts_dir / "depenses_par_service.png"
    plt.savefig(dep_path)
    plt.close(fig)

    # pie chart
    fig = plt.figure(figsize=(6, 4.2))
    values = [paid, remaining]
    labels = ["Payée", "À payer"]
    if sum(values) == 0:
        values = [1]
        labels = ["Aucune donnée"]
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title("Répartition des paiements")
    plt.tight_layout()
    pie_path = charts_dir / "repartition_paiements.png"
    plt.savefig(pie_path)
    plt.close(fig)

    return {
        "depenses_par_service": f"charts/{dep_path.name}",
        "repartition_paiements": f"charts/{pie_path.name}",
    }
