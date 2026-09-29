# Préparer SamaService pour les stores

Le projet utilise Capacitor pour emballer l'interface web dans des applications Android et iOS. Le serveur Flask doit être déployé séparément et accessible en HTTPS.

## Déployer l'API avec Supabase et Render

Le backend utilise SQLite en local et PostgreSQL quand la variable `DATABASE_URL` est définie. Le fichier `render.yaml` prépare le service Flask sur Render; la base de données reste hébergée séparément sur Supabase.

1. Crée un projet Supabase et récupère son URI PostgreSQL depuis **Connect**. Utilise le pooler de session si l'accès direct n'est pas disponible depuis Render.
2. Dans Supabase, conserve le mot de passe de la base et l'URI privés. Ne les ajoute ni à `app.py`, ni au code mobile, ni au dépôt Git.
3. Pousse le projet sur GitHub, puis dans Render choisis **New → Blueprint** et connecte ce dépôt. Render lira `render.yaml` et te demandera la variable secrète `DATABASE_URL`.
4. Colle l'URI PostgreSQL de Supabase comme valeur de `DATABASE_URL`, puis lance le déploiement.
5. Après le premier déploiement, l'API est disponible à `https://sama-service.onrender.com/api`. Render fournit le HTTPS.

Les tables sont créées au démarrage sans ajouter d'annonces de démonstration. Au prochain redémarrage, les deux anciennes annonces de Modou Dépannage Auto seront désactivées; les demandes liées restent conservées. La base SQLite du PC n'est pas copiée automatiquement : exporte-la avant le déploiement si elle contient des comptes ou des demandes à conserver.

Le Blueprint utilise le plan gratuit Render pour faciliter les essais; le serveur peut se mettre en veille. Supabase conserve ses propres conditions de disponibilité et de sauvegarde, à vérifier dans le plan choisi.

Si les logs Render affichent `Using Erlang` ou `Using Elixir`, le service actif est encore configuré avec le mauvais runtime. Dans les paramètres du service, sélectionne **Python**, puis relance un déploiement. Les logs du build doivent montrer `pip install -r requirements.txt`; ceux du démarrage doivent lancer Gunicorn sur le port `$PORT`. Le Blueprint ci-dessus configure déjà ces valeurs.

## Préparer les fichiers web

Dans PowerShell, après le déploiement du serveur :

```powershell
npm.cmd install
npm.cmd run mobile:web
```

Le script utilise par défaut `https://sama-service.onrender.com/api`. Pour un autre serveur, définissez `SAMASERVICE_API_URL` avant de lancer le script. L'URL doit être en HTTPS et se terminer par `/api`; n'utilisez pas `127.0.0.1` sur un téléphone.

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