# Préparer SamaService pour les stores

Le projet utilise Capacitor pour emballer l'interface web dans des applications Android et iOS. Le serveur Flask doit être déployé séparément et accessible en HTTPS.

## Déployer l'API avec Supabase et Render

Le backend utilise SQLite en local et PostgreSQL quand la variable `DATABASE_URL` est définie. Le fichier `render.yaml` prépare le service Flask sur Render; la base de données reste hébergée séparément sur Supabase.

1. Crée un projet Supabase et récupère son URI PostgreSQL depuis **Connect**. Utilise le pooler de session si l'accès direct n'est pas disponible depuis Render.
2. Dans Supabase, conserve le mot de passe de la base et l'URI privés. Ne les ajoute ni à `app.py`, ni au code mobile, ni au dépôt Git.
3. Pousse le projet sur GitHub, puis dans Render choisis **New → Blueprint** et connecte ce dépôt. Render lira `render.yaml` et te demandera la variable secrète `DATABASE_URL`.
4. Colle l'URI PostgreSQL de Supabase comme valeur de `DATABASE_URL`, puis lance le déploiement.
5. Après le premier déploiement, l'API est disponible à `https://sama-service-1.onrender.com/api`. Render fournit le HTTPS.

Les tables sont créées au démarrage sans ajouter d'annonces de démonstration. Au prochain redémarrage, les deux anciennes annonces de Modou Dépannage Auto seront désactivées; les demandes liées restent conservées. La base SQLite du PC n'est pas copiée automatiquement : exporte-la avant le déploiement si elle contient des comptes ou des demandes à conserver.

L'API limite CORS aux origines Capacitor locales définies par `CORS_ORIGINS`. Si une interface web est hébergée sur un autre domaine, ajoute son origine HTTPS exacte à cette variable dans Render, séparée par une virgule. CORS ne remplace pas l'authentification de l'API.

Le Blueprint utilise le plan gratuit Render pour faciliter les essais; le serveur peut se mettre en veille. Il faut choisir un plan sans mise en veille avant un lancement où la disponibilité est attendue. Supabase conserve ses propres conditions de disponibilité et de sauvegarde, à vérifier dans le plan choisi.

### Lancement d'une bêta limitée

Pour tester gratuitement, garde `plan: free` et limite d'abord l'accès à un petit groupe. Avant de partager le lien :

1. Vérifie dans Render que `DATABASE_URL` pointe vers le projet PostgreSQL Supabase prévu pour la bêta. N'utilise pas SQLite sur Render : son disque peut être effacé au redémarrage ou à la mise en veille.
2. Vérifie les limites de disponibilité et de sauvegarde du plan Supabase choisi. Configure aussi Cloudinary si les photos de profil doivent être utilisées.
3. Après le déploiement, ouvre `/api/metadonnees`, puis teste une inscription, une connexion, une publication, une demande client et la consultation des demandes par l'artisan.
4. Préviens les testeurs que la première requête après une période d'inactivité peut attendre environ une minute. Render peut aussi redémarrer une instance gratuite à tout moment.

Un ping externe toutes les 10 minutes peut éviter la mise en veille due à l'inactivité, mais ne garantit pas que l'instance reste disponible. Un cron Render est facturé selon son temps d'exécution; il n'est pas ajouté au Blueprint gratuit. Pour une bêta sans frais imprévus, accepte plutôt le réveil à froid.

## Photos de profil Cloudinary

1. Dans le tableau de bord Cloudinary, récupère `Cloud Name`, `API Key` et `API Secret`.
2. Dans Render, ouvre le service `samaservice-api`, puis **Environment**. Ajoute `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` et `CLOUDINARY_API_SECRET` avec les valeurs correspondantes. Ne les colle jamais dans le dépôt Git ni dans l'application mobile.
3. `FLASK_SECRET_KEY` est générée par le Blueprint. Cette clé signe les jetons temporaires utilisés pour modifier les photos; conserve-la stable entre les déploiements.
4. Redéploie le service Render. Les photos JPEG, PNG et WebP jusqu'à 5 Mo seront stockées dans le dossier Cloudinary `samaservice/profiles`.

La photo d'inscription est facultative. Si Cloudinary n'est pas configuré, l'inscription normale reste disponible, mais l'envoi, le remplacement et la suppression d'une photo sont désactivés.

Si les logs Render affichent `Using Erlang` ou `Using Elixir`, le service actif est encore configuré avec le mauvais runtime. Dans les paramètres du service, sélectionne **Python**, puis relance un déploiement. Les logs du build doivent montrer `pip install -r requirements.txt`; ceux du démarrage doivent lancer Gunicorn sur le port `$PORT`. Le Blueprint ci-dessus configure déjà ces valeurs.

## Préparer les fichiers web

Dans PowerShell, après le déploiement du serveur :

```powershell
npm.cmd install
npm.cmd run mobile:web
```

Le script utilise par défaut `https://sama-service-1.onrender.com/api`. Pour un autre serveur, définissez `SAMASERVICE_API_URL` avant de lancer le script. L'URL doit être en HTTPS et se terminer par `/api`; n'utilisez pas `127.0.0.1` sur un téléphone.

## Android

Sur Windows, installez Android Studio et le SDK Android, puis :

```powershell
npm.cmd run mobile:sync
npm.cmd run android
```

Android Studio permet ensuite de tester l'application et de générer un paquet de publication signé pour Google Play.

## iOS

La cible iOS doit être générée, compilée et signée sur macOS avec Xcode :

```sh
npm install
npm run mobile:sync
npm run ios
```

Avant une première publication, confirmez l'identifiant `sn.samaservice.dakar` dans `capacitor.config.ts` et remplacez-le si nécessaire. Les comptes développeur Apple et Google, les visuels des stores, la politique de confidentialité et les informations de publication sont également nécessaires.