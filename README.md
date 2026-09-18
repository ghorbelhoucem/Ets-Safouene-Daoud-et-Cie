# ETS Safouene Daoud et Cie — Gestion des pièces automobiles KIA

Application métier distincte destinée à la gestion du stock de pièces automobiles et des outils d’atelier de l’entreprise ETS Safouene Daoud et Cie.

## Fonctionnalités

- Connexion par code PIN à 4 chiffres pour les profils **Management** et **Majdi**.
- Pièces automobiles consommables : sortie immédiate du stock.
- Outils d’atelier : emprunt, échéance et retour traçable.
- Réapprovisionnement, alertes de seuil, garantie, historique et rapports de gestion.
- Numéro de série enregistré avec les nouveaux articles et recherche par nom, code-barres ou numéro de série.
- Miroir Google Sheets facultatif du stock, de l’historique, des achats et des garanties.
- Interface tactile en français avec lecteur code-barres/QR.
- API FastAPI, PostgreSQL, jetons JWT et protection des opérations par rôle.

## Architecture de production

Railway exécute un seul conteneur applicatif construit avec le `Dockerfile` racine :

- FastAPI sert l’API sous `/api`.
- FastAPI sert également le frontend statique à la racine `/`.
- PostgreSQL est un service Railway séparé.
- Le contrôle de santé est disponible sous `/health`.

Le code serveur utilisé en production se trouve dans `backend/app`. Les fichiers frontend actifs sont `index.html`, `config.js`, `client.js`, `inventory.js`, `machine.js`, `store.js`, `keyboardScanner.js` et `renderer.js`.

## Variables obligatoires

- `DATABASE_URL`
- `JWT_SECRET` — valeur aléatoire longue, jamais enregistrée dans Git
- `ETS_ADMIN_PIN` — code PIN du profil Management
- `ETS_STOREKEEPER_PIN` — code PIN du profil Majdi
- `SEED_ON_STARTUP=true`

Variables facultatives : `CORS_ORIGINS`, `LEGACY_WEBAPP_URL`, `SHEET_SYNC_INTERVAL_MINUTES`, `SLACK_TRANSACTIONS_WEBHOOK_URL`, `SLACK_PURCHASE_WEBHOOK_URL`.

## Démarrage local

Créer un fichier `.env` contenant au minimum :

```env
POSTGRES_PASSWORD=change-this-password
JWT_SECRET=change-this-long-random-secret
ETS_ADMIN_PIN=<code-management-à-4-chiffres>
ETS_STOREKEEPER_PIN=<code-majdi-à-4-chiffres>
```

Puis lancer :

```bash
docker compose up --build
```

Ouvrir <http://localhost:61938>.

## Vérifications

```bash
python -m compileall -q backend/app
npm install
npm test
docker compose config
```

Les identifiants, secrets JWT, webhooks et mots de passe de base de données ne doivent jamais être ajoutés au dépôt.
