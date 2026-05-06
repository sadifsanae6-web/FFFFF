class Utilisateur:
    def __init__(self, nom: str, email: str):
        self.__nom = nom
        self.__email = email

    def get_nom(self) -> str:
        return self.__nom

    def set_nom(self, nom: str) -> None:
        if nom and nom.strip():
            self.__nom = nom.strip()

    def get_email(self) -> str:
        return self.__email

    def set_email(self, email: str) -> None:
        if "@" in email:
            self.__email = email

    def se_connecter(self) -> str:
        return f"{self.__nom} s'est connecté."


class Demandeur(Utilisateur):
    def creer_demande(self) -> str:
        return "Le demandeur crée une demande d'achat."


class Approbateur(Utilisateur):
    def valider_demande(self) -> str:
        return "L'approbateur valide une demande."

    def refuser_demande(self) -> str:
        return "L'approbateur refuse une demande."


class Acheteur(Utilisateur):
    def creer_commande(self) -> str:
        return "L'acheteur crée une commande."

    def activer_plan_b(self) -> str:
        return "L'acheteur active un plan B fournisseur."


class Comptable(Utilisateur):
    def enregistrer_facture(self) -> str:
        return "Le comptable enregistre une facture."

    def enregistrer_paiement(self) -> str:
        return "Le comptable enregistre un paiement."


class DemandeAchatPOO:
    def __init__(self, reference: str, projet: str, montant_estime: float):
        self.__reference = reference
        self.__projet = projet
        self.__montant_estime = 0.0
        self.set_montant_estime(montant_estime)
        self.__statut = "Brouillon"

    def get_reference(self) -> str:
        return self.__reference

    def get_projet(self) -> str:
        return self.__projet

    def set_projet(self, projet: str) -> None:
        if projet and projet.strip():
            self.__projet = projet.strip()

    def get_montant_estime(self) -> float:
        return self.__montant_estime

    def set_montant_estime(self, montant: float) -> None:
        if montant >= 0:
            self.__montant_estime = float(montant)

    def get_statut(self) -> str:
        return self.__statut

    def set_statut(self, statut: str) -> None:
        valeurs_valides = {
            "Brouillon",
            "En attente d'approbation",
            "Validée",
            "Refusée",
            "En consultation",
            "Offre sélectionnée",
            "Commandée",
            "Reçue",
            "Facturée",
            "Payée",
        }
        if statut in valeurs_valides:
            self.__statut = statut


class FacturePOO:
    def __init__(self, code: str, montant: float):
        self.__code = code
        self.__montant = 0.0
        self.set_montant(montant)
        self.__statut = "À payer"

    def get_code(self) -> str:
        return self.__code

    def get_montant(self) -> float:
        return self.__montant

    def set_montant(self, montant: float) -> None:
        if montant > 0:
            self.__montant = float(montant)

    def get_statut(self) -> str:
        return self.__statut

    def marquer_payee(self) -> None:
        self.__statut = "Payée"


if __name__ == "__main__":
    demandeur = Demandeur("Sara Demandeur", "demandeur@sp.local")
    acheteur = Acheteur("Amine Acheteur", "acheteur@sp.local")
    facture = FacturePOO("FAC-001", 4500)

    print(demandeur.se_connecter())
    print(demandeur.creer_demande())
    print(acheteur.creer_commande())
    print(f"Facture {facture.get_code()} - statut initial : {facture.get_statut()}")
    facture.marquer_payee()
    print(f"Facture {facture.get_code()} - statut final : {facture.get_statut()}")
