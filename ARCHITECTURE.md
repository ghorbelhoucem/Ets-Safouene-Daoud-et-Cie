# Architecture — ETS Safouene Daoud & Cie

Application autonome de gestion du stock de pièces et d’outillage automobile KIA.

## Déploiement

Un conteneur unique sert l’API FastAPI et l’interface web. PostgreSQL conserve les
utilisateurs, articles, mouvements, emprunts, retours et déclarations de garantie.
Railway fournit la base et injecte les secrets à l’exécution.

## Composants

- `backend/app` : API, authentification JWT, permissions et logique métier.
- `index.html` et modules JavaScript : interface tactile responsive en français.
- `backend/app/services/inventory.py` : retraits, retours, réceptions et ajustements.
- `backend/app/routers/reports.py` : tableau de bord et export Excel réservés à la direction.
- `backend/app/services/sheets_sync.py` : miroir Google Sheets facultatif du stock automobile.
- `backend/app/services/slack_notify.py` : notifications facultatives de mouvements et seuils bas.
- `kiosk.spec.js` : tests Playwright des parcours principaux.

## Sécurité

Deux profils actifs seulement : `Management` et `Majdi`. Chaque connexion exige un
PIN à quatre chiffres. Le serveur signe un jeton JWT à durée limitée et recharge
l’utilisateur depuis la base à chaque requête protégée. Les actions et les auteurs
des journaux sont dérivés du jeton, jamais des valeurs envoyées par le navigateur.
Les rapports, réceptions et garanties sont réservés à `Management`.

Les anciennes valeurs techniques de catégorie restent reconnues uniquement pour
la compatibilité des données PostgreSQL existantes; elles ne constituent pas des
espaces ou profils visibles dans le produit.
