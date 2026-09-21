# ETS Safouene Daoud et Cie — Gestion des pièces automobiles KIA

Application métier distincte destinée à la gestion du stock de pièces automobiles et des outils d’atelier de l’entreprise ETS Safouene Daoud et Cie.

> La branche `main` conserve l'application de stock rapide. La branche
> `garage-plus` ajoute le portail DMS complet sans modifier le produit de stock
> déployé.

## Fonctionnalités

- Connexion par code PIN à 4 chiffres pour les profils **Management** et **Majdi**.
- Pièces automobiles consommables : sortie immédiate du stock.
- Outils d’atelier : emprunt, échéance et retour traçable.
- Réapprovisionnement, alertes de seuil, garantie, historique et rapports de gestion.
- Numéro de série enregistré avec les nouveaux articles et recherche par nom, code-barres ou numéro de série.
- Miroir Google Sheets facultatif du stock, de l’historique, des achats et des garanties.
- Interface tactile en français avec lecteur code-barres/QR.
- API FastAPI, PostgreSQL, jetons JWT et protection des opérations par rôle.

## Garage Plus (`garage-plus`)

Le portail `/garage.html` réutilise l'authentification et le stock existants et ajoute :

- Tableau de bord avec ordres actifs, véhicules prêts, chiffre facturé, créances et stock faible.
- Fiches clients et véhicules (immatriculation, VIN, kilométrage et historique futur).
- Équipe de mécaniciens, spécialités et taux horaires.
- Ordres de réparation avec priorité, affectation, diagnostic et cycle de statut.
- Planning atelier alimenté par les rendez-vous des ordres de réparation.
- Historique complet des interventions par véhicule.
- Lignes de main-d'œuvre, services et pièces; une pièce liée décrémente automatiquement le stock.
- Facturation depuis l'ordre de réparation, TVA, remise et règlements partiels ou complets.
- Facture A4 imprimable ou enregistrable en PDF depuis le navigateur.
- Fournisseurs, commandes d'achat et réception automatique dans le stock.
- Permissions : Management gère finance/achats/équipe; Majdi gère clients, véhicules et atelier.

Les nouvelles tables sont créées au démarrage par SQLAlchemy. Aucune table du
stock existant n'est supprimée ou renommée.

## Architecture locale

Docker Desktop exécute l'application et la base directement sur le PC du garage :

- FastAPI sert l’API sous `/api`.
- FastAPI sert également le frontend statique à la racine `/`.
- PostgreSQL conserve les données dans un volume local persistant.
- Le contrôle de santé est disponible sous `/health`.

Railway n'est pas requis. GitHub conserve le code; il ne stocke pas la base de
données locale. Les instructions Windows sont dans `INSTALLATION_LOCALE.md`.

Le code serveur utilisé en production se trouve dans `backend/app`. Les fichiers frontend actifs sont `index.html`, `garage.html`, `garage-invoice.html`, `garage.js`, `config.js`, `client.js`, `inventory.js`, `machine.js`, `store.js`, `keyboardScanner.js` et `renderer.js`.

## Variables obligatoires

- `DATABASE_URL`
- `JWT_SECRET` — valeur aléatoire longue, jamais enregistrée dans Git
- `ETS_ADMIN_PIN` — code PIN du profil Management
- `ETS_STOREKEEPER_PIN` — code PIN du profil Majdi
- `SEED_ON_STARTUP=true`

Variables facultatives : `CORS_ORIGINS`, `LEGACY_WEBAPP_URL`, `SHEET_SYNC_INTERVAL_MINUTES`, `SLACK_TRANSACTIONS_WEBHOOK_URL`, `SLACK_PURCHASE_WEBHOOK_URL`.

## Démarrage local rapide sous Windows

Installer et démarrer Docker Desktop, puis double-cliquer sur
`start-garage.cmd`. Au premier lancement, le programme demande les deux PIN à
quatre chiffres, génère les autres secrets et ouvre l'application.

## Démarrage local manuel

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
