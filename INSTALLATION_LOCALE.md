# Installation locale — Garage Plus

Garage Plus fonctionne sur le PC du garage. Railway n'est pas utilisé. GitHub
conserve uniquement le code et l'historique des versions; les données clients,
véhicules, réparations, factures et stocks restent dans PostgreSQL sur ce PC.

## Windows — première installation

1. Installer et démarrer Docker Desktop.
2. Télécharger ou cloner la branche `garage-plus` de ce dépôt.
3. Double-cliquer sur `start-garage.cmd`.
4. Choisir un PIN Management et un PIN Majdi, chacun composé de quatre chiffres.
5. Attendre l'ouverture automatique de <http://localhost:61938>.

Le premier démarrage crée un fichier `.env` local avec des secrets aléatoires.
Ce fichier et les données PostgreSQL ne sont jamais envoyés sur GitHub.

## Utilisation quotidienne

- Démarrer : `start-garage.cmd`
- Arrêter : `stop-garage.cmd`
- Sauvegarder : `backup-garage.cmd`
- Ouvrir manuellement : <http://localhost:61938>

Les sauvegardes SQL sont placées dans le dossier `backups`, ignoré par Git.
Copier régulièrement ce dossier vers une clé USB ou un disque externe.

## Accès depuis d'autres PC du garage

L'application écoute seulement sur le PC local par défaut. Pour un réseau local
de confiance, ajouter `APP_HOST=0.0.0.0` au fichier `.env`, redémarrer, autoriser
le port TCP 61938 dans le pare-feu Windows, puis ouvrir
`http://ADRESSE-IP-DU-PC:61938` depuis les autres postes.

Ne pas exposer directement ce port sur Internet. Un accès distant nécessitera
un VPN privé ou une couche HTTPS et une configuration de sécurité dédiée.

## Google Sheets

Le système principal reste utilisable hors ligne. Si une URL Google Apps Script
est configurée dans `LEGACY_WEBAPP_URL`, le miroir Google Sheets reprend dès que
la connexion Internet est disponible.
