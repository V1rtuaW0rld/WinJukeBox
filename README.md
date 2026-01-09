Structure du projet
Le projet est une application de lecteur audio (jukebox) avec une interface web qui permet de gérer une bibliothèque musicale. La structure comprend :

Un script d'indexation de la bibliothèque musicale (indexMusicinDB.py)
Un serveur web avec FastAPI (server.py)
Une interface utilisateur web avec HTML/CSS/JS (static/)
Des dépendances nécessaires (requirements.txt)
Fonctionnalités principales
1. Indexation de la bibliothèque musicale
indexMusicinDB.py : Script qui scanne un dossier réseau contenant des fichiers MP3
Recherche automatique des pochettes d'albums dans les dossiers
Extraction des tags ID3 (titre, artiste, album)
Stockage dans une base de données SQLite
Gestion des tables :
tracks : Morceaux de musique
playlist : Playlist de lecture en cours
shuffled_playlist : Playlist aléatoire
playlist_album : Lecture immédiate d'un album
saved_playlists_info : Noms des playlists sauvegardées
saved_playlists_content : Contenu des playlists sauvegardées
2. Interface utilisateur web
Interface responsive avec HTML/CSS/JS
Affichage des informations de lecture en cours
Contrôles de lecture (pause, avancer, reculer)
Barre de progression et volume
Recherche par titre, artiste ou album
Explorateur de fichiers
Gestion de playlists (création, lecture, mélange, suppression)
3. Serveur web
Utilisation de FastAPI pour l'API REST
Intégration avec MPV (media player) pour la lecture audio
Gestion des contrôles audio (pause, lecture, volume)
Interface de gestion des playlists
Gestion des périphériques audio
Architecture technique
Dépendances principales :
mutagen : Lecture des tags MP3
fastapi : Framework web
uvicorn : Serveur ASGI
python-mpv-jsonipc : Contrôle du lecteur MPV
tqdm : Barre de progression
Base de données :
SQLite avec gestion des clés étrangères
Structure optimisée pour la gestion de playlists
Sauvegarde des playlists personnalisées
Fonctionnalités spécifiques
Scan automatique : Recherche des fichiers MP3 dans un dossier réseau
Recherche avancée : Par titre, artiste ou album
Gestion de playlists : Création, sauvegarde, lecture aléatoire
Interface utilisateur : Design moderne avec contrôles intuitifs
Gestion audio : Contrôle du volume, changement de périphérique audio
Points forts du projet
Architecture modulaire et bien structurée
Interface utilisateur intuitive et complète
Gestion avancée des playlists
Support pour les pochettes d'albums
Intégration avec un lecteur audio externe (MPV)
Système de sauvegarde des playlists personnalisées
Comment utiliser le projet
Installer les dépendances avec pip install -r requirements.txt
Exécuter le script d'indexation pour scanner la bibliothèque musicale : python indexMusicinDB.py
Démarrer le serveur web : uvicorn server:app --reload
Accéder à l'interface via un navigateur web
Le projet est conçu pour fonctionner sur un réseau local avec un dossier partagé contenant la bibliothèque musicale.
