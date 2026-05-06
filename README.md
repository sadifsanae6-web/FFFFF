# SmartPurchase refactorisé

Application Flask / SQLAlchemy de gestion des achats avec workflow professionnel :
- demande d'achat multi-lignes,
- consultation fournisseur,
- commande multi-lignes,
- réception en 2 étapes (logistique puis qualité),
- non-conformité et retour fournisseur,
- rapprochement facture / réception / paiement.

## Démarrage

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

L'application recrée automatiquement la base SQLite avec le nouveau schéma au premier lancement.

## Comptes de démonstration

- demandeur@sp.local / 1234
- approbateur@sp.local / 1234
- acheteur@sp.local / 1234
- magasinier@sp.local / 1234
- qualite@sp.local / 1234
- comptable@sp.local / 1234

## Refactoring livré

### Procurement
- séparation claire entre réception logistique, qualité et litige fournisseur,
- suivi quantitatif par ligne : commandé, livré, accepté, quarantaine, rejeté, retourné, restant,
- cycle de vie de non-conformité et de retour fournisseur,
- mise à jour automatique des statuts commande / ligne / réception,
- blocage stock et paiement selon la gravité et l'état du litige.

### Finance
- rapprochement commande / réception / facture,
- alerte si facture au-dessus des quantités acceptées,
- paiement limité à la partie payable,
- gestion crédible du partiel en cas de réception partielle ou litige.

### Demandes et commandes
- chaîne multi-lignes cohérente de bout en bout,
- reprise des lignes de demande vers la commande.
