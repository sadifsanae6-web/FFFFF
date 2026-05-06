REQUEST_STATUS_LABELS = {
    "brouillon": "Brouillon",
    "en_attente_approbation": "En attente d'approbation",
    "validee": "Validée",
    "refusee": "Refusée",
    "en_consultation": "Consultation fournisseurs",
    "offre_selectionnee": "Offre sélectionnée",
    "commandee": "Commande créée",
    "recue": "Réception enregistrée",
    "facturee": "Facturée",
    "payee": "Payée",
    "archivee": "Archivée",
}

ORDER_STATUS_LABELS = {
    "commandee": "Commandée",
    "en_reception": "Réception en cours",
    "reception_partielle": "Réception partielle",
    "attente_decision_qualite": "Décision qualité attendue",
    "partiellement_acceptee": "Partiellement acceptée",
    "reception_conforme": "Réception conforme",
    "reception_avec_reserve": "Réception avec réserve",
    "quarantaine": "Quarantaine",
    "non_conforme": "Non conforme",
    "reception_refusee": "Réception refusée",
    "litige_fournisseur": "Litige fournisseur",
    "retour_en_cours": "Retour en cours",
    "retour_cloture": "Retour clôturé",
    "soldee": "Soldée",
    "archivee": "Archivée",
    "annulee": "Annulée",
    "acceptee": "Acceptée",
    "acceptee_avec_reserve": "Acceptée avec réserve",
    "rejetee": "Rejetée",
    "rejetee_partiellement": "Rejet partiel",
}

RECEPTION_STATUS_LABELS = {
    "brouillon": "Brouillon",
    "qualite_a_traiter": "Qualité à traiter",
    "cloturee": "Clôturée",
    "complete": "Complète",
    "partielle": "Partielle",
    "avec_reserve": "Avec réserve",
    "refus_partiel": "Refus partiel",
    "refus_total": "Refus total",
    "saisie_logistique": "Saisie logistique",
    "a_controler": "À contrôler",
    "accepter": "Accepter",
    "accepter_avec_reserve": "Accepter avec réserve",
    "quarantaine": "Quarantaine",
    "rejeter": "Rejeter",
    "ouvrir_non_conformite": "Ouvrir une non-conformité",
    "refus_a_quai": "Refus à quai",
}

NC_STATUS_LABELS = {
    "ouverte": "Ouverte",
    "en_analyse": "En analyse",
    "action_fournisseur": "Action fournisseur",
    "en_cours": "En cours",
    "resolue": "Résolue",
    "cloturee": "Clôturée",
    "mineure": "Mineure",
    "majeure": "Majeure",
    "critique": "Critique",
    "produit_conforme": "Produit conforme",
    "remplacement": "Remplacement",
    "avoir": "Avoir",
    "reparation": "Réparation",
    "acceptation_derogatoire": "Acceptation dérogatoire",
    "retour_fournisseur": "Retour fournisseur",
    "a_definir": "À définir",
    "expedie": "Expédié",
    "recu_par_fournisseur": "Reçu par fournisseur",
    "remplace": "Remplacé",
    "rembourse": "Remboursé",
    "cloture": "Clôturé",
    "remplacement_effectif": "Remplacement effectué",
    "remboursement_effectif": "Remboursement effectué",
    "avoir_emis": "Avoir émis",
    "reparation_effective": "Réparation effectuée",
}

INVOICE_STATUS_LABELS = {
    "a_payer": "À payer",
    "a_verifier": "À vérifier",
    "modifiee": "Modifiée",
    "partiellement_payee": "Partiellement payée",
    "payee": "Payée",
    "archivee": "Archivée",
    "rapprochee": "Rapprochée",
    "non_rapprochee": "Non rapprochée",
    "depasse_quantites_acceptees": "Dépasse les quantités acceptées",
}

PAYMENT_STATUS_LABELS = {
    "enregistre": "Enregistré",
    "effectue": "Payé",
    "annule": "Annulé",
}

BADGE_CLASS = {
    "brouillon": "slate",
    "en_attente_approbation": "warning",
    "validee": "info",
    "refusee": "danger",
    "en_consultation": "info",
    "offre_selectionnee": "success",
    "commandee": "info",
    "en_reception": "info",
    "annulee": "danger",
    "recue": "success",
    "reception_conforme": "success",
    "reception_partielle": "warning",
    "attente_decision_qualite": "warning",
    "partiellement_acceptee": "warning",
    "reception_avec_reserve": "warning",
    "quarantaine": "warning",
    "non_conforme": "danger",
    "reception_refusee": "danger",
    "litige_fournisseur": "danger",
    "retour_en_cours": "warning",
    "retour_cloture": "success",
    "soldee": "success",
    "facturee": "warning",
    "a_payer": "warning",
    "a_verifier": "warning",
    "modifiee": "info",
    "partiellement_payee": "warning",
    "payee": "success",
    "archivee": "slate",
    "effectue": "success",
    "annule": "danger",
    "ouverte": "danger",
    "en_analyse": "warning",
    "action_fournisseur": "warning",
    "en_cours": "warning",
    "resolue": "info",
    "cloturee": "success",
    "mineure": "info",
    "majeure": "warning",
    "critique": "danger",
    "complete": "success",
    "partielle": "warning",
    "avec_reserve": "warning",
    "refus_partiel": "danger",
    "refus_total": "danger",
    "acceptee": "success",
    "acceptee_avec_reserve": "warning",
    "rejetee": "danger",
    "rejetee_partiellement": "warning",
    "a_controler": "warning",
    "refus_a_quai": "danger",
    "produit_conforme": "success",
    "rapprochee": "success",
    "non_rapprochee": "warning",
    "depasse_quantites_acceptees": "danger",
}

def display_status(value: str) -> str:
    maps = [
        REQUEST_STATUS_LABELS,
        ORDER_STATUS_LABELS,
        RECEPTION_STATUS_LABELS,
        NC_STATUS_LABELS,
        INVOICE_STATUS_LABELS,
        PAYMENT_STATUS_LABELS,
    ]
    for mapping in maps:
        if value in mapping:
            return mapping[value]
    return (value or "").replace("_", " ").capitalize()


def badge_class(value: str) -> str:
    return BADGE_CLASS.get(value, "slate")


def format_priority(value: float) -> str:
    return f"{value:.1f}/100"
