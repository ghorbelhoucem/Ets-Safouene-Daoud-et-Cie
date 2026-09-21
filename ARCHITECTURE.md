# Architecture — ETS Safouene Daoud & Cie

Application autonome de gestion du stock de pièces et d’outillage automobile KIA.

## Déploiement

Un conteneur local sert l’API FastAPI et l’interface web. Un second conteneur
PostgreSQL conserve les utilisateurs, clients, véhicules, ordres, factures,
articles, mouvements, emprunts, retours et déclarations de garantie. Docker
Compose injecte les secrets générés localement et conserve la base dans un volume
persistant sur le PC du garage. Railway n'est pas utilisé.

## Composants

- `backend/app` : API, authentification JWT, permissions et logique métier.
- `index.html` et modules JavaScript : interface tactile responsive en français.
- `backend/app/services/inventory.py` : retraits, retours, réceptions et ajustements.
- `backend/app/routers/reports.py` : tableau de bord et export Excel réservés à la direction.
- `backend/app/services/sheets_sync.py` : miroir Google Sheets facultatif du stock automobile.
- `backend/app/services/slack_notify.py` : notifications facultatives de mouvements et seuils bas.
- `backend/app/routers/garage.py` : clients, véhicules, atelier, facturation, achats et KPI.
- `backend/app/garage_schemas.py` : validation Pydantic du domaine Garage Plus.
- `garage.html` et `garage.js` : portail DMS responsive séparé du kiosque de stock.
- `kiosk.spec.js` : tests Playwright des parcours principaux.

## Domaines Garage Plus

```text
Customer ──< Vehicle ──< RepairOrder ──< RepairOrderLine
                              │
                              └── Invoice ──< Payment

Supplier ──< PurchaseOrder ──< PurchaseOrderLine >── InventoryItem
RepairOrderLine >──────────────────────────────────── InventoryItem
```

Une ligne de pièce liée à `InventoryItem` consomme le stock lors de son ajout à
un ordre. Une réception de commande fournisseur augmente ce même stock et écrit
un mouvement traçable. La facture est calculée depuis les lignes de l'ordre et
les règlements mettent à jour son solde et son état.

## Sécurité

Deux profils actifs seulement : `Management` et `Majdi`. Chaque connexion exige un
PIN à quatre chiffres. Le serveur signe un jeton JWT à durée limitée et recharge
l’utilisateur depuis la base à chaque requête protégée. Les actions et les auteurs
des journaux sont dérivés du jeton, jamais des valeurs envoyées par le navigateur.
Les deux profils peuvent consulter les rapports et gérer l'activité atelier.
Les réceptions manuelles, garanties, mécaniciens, factures, règlements,
fournisseurs et achats restent réservés à `Management`.

Les anciennes valeurs techniques de catégorie restent reconnues uniquement pour
la compatibilité des données PostgreSQL existantes; elles ne constituent pas des
espaces ou profils visibles dans le produit.
