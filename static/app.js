/**
 * FONCTION DE RECHERCHE ET D'AFFICHAGE
 * Cette fonction récupère les morceaux depuis le serveur et crée les "cartes" HTML.
 */
async function doSearch() {
    console.log("🔍 Recherche en cours...");
    try {
        // 1. On récupère la valeur saisie dans la barre de recherche
        const query = document.getElementById('searchInput').value;
        
        // 2. On appelle l'API du serveur (FastAPI)
        // encodeURIComponent permet de gérer les espaces et caractères spéciaux dans la recherche
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
        
        // 3. Si le serveur répond une erreur (ex: 500), on déclenche une alerte
        if (!response.ok) throw new Error("Erreur serveur : " + response.status);
        
        // 4. On transforme la réponse en objet JSON (celui qui contient la clé "songs")
        const data = await response.json();
        const list = document.getElementById('songList');
        
        // 5. Si la liste est vide, on affiche un petit message sympa
        if (!data.songs || data.songs.length === 0) {
            list.innerHTML = '<div style="text-align:center; padding:20px;">Aucune musique trouvée. 🎸</div>';
            return;
        }

        // 6. On vide la liste actuelle (efface le "Chargement...") avant de la remplir
        list.innerHTML = ''; 

        // 7. On boucle sur chaque chanson reçue pour créer le HTML
        data.songs.forEach(song => {
            const card = document.createElement('div');
            card.className = 'song-card';
            card.innerHTML = `
                <div class="song-info">
                    <strong>${song.title}</strong><br>
                    <small style="color: #b3b3b3">${song.artist}</small>
                </div>
                <button class="play-btn" onclick="play(${song.id})">▶</button>
            `;
            list.appendChild(card);
        });
    } catch (error) {
        // En cas de gros plantage, on affiche l'erreur dans la console F12 et sur l'écran
        console.error("❌ Erreur détaillée:", error);
        document.getElementById('songList').innerHTML = 
            '<div style="color:red; text-align:center; padding:20px;">Impossible de joindre le Jukebox.</div>';
    }
}

/**
 * FONCTIONS DE COMMANDE
 * Ces fonctions envoient des ordres simples au serveur.
 */

// Lancer une chanson par son ID
async function play(id) {
    console.log("🎵 Lecture demandée pour l'ID :", id);
    await fetch(`/play/${id}`);
}

// Arrêter la musique
async function stopMusic() {
    console.log("🛑 Arrêt de la musique");
    await fetch('/stop');
}

// Changer le volume (appelé par le curseur range)
async function updateVolume(level) {
    console.log("🔊 Volume réglé sur :", level);
    await fetch(`/volume/${level}`);
}

// --- LOGIQUE DU LECTEUR ---

async function togglePause() {
    await fetch('/pause');
    // On change l'icône visuellement pour un retour immédiat
    const btn = document.getElementById('pauseBtn');
    btn.innerText = (btn.innerText === "⏸") ? "▶" : "⏸";
}

async function seek(seconds) {
    await fetch(`/seek/${seconds}`);
}

// Fonction pour le volume (déjà fonctionnelle chez toi, mais on s'assure de l'appel)
async function changeVolume(level) {
    await fetch(`/volume/${level}`);
}

// Pour éviter que la barre de recherche ne soit trop large, 
// on a utilisé grid-template-columns: 1fr 2fr 1fr;

/**
 * EXPOSITION GLOBALE ET INITIALISATION
 * Indispensable pour que le HTML (onclick) puisse trouver les fonctions.
 */

// On attache nos fonctions à l'objet 'window' (le navigateur)
window.play = play;
window.stopMusic = stopMusic;
window.updateVolume = updateVolume;
window.doSearch = doSearch;

// Dès que la page est totalement chargée, on lance une première recherche (vide)
// pour afficher tous les morceaux par défaut.
window.onload = doSearch;

// Barre de temps

const btn = document.getElementById('pauseBtn');
if (data.paused) {
    btn.className = 'playing'; // MPV en pause -> on montre le bouton PLAY
} else {
    btn.className = 'paused';  // MPV joue -> on montre le bouton PAUSE
}

// Fonction pour transformer les secondes en format 0:00
function formatTime(seconds) {
    if (!seconds) return "0:00";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec < 10 ? '0' : ''}${sec}`;
}

async function updateStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();

        if (data.duration > 0) {
            const slider = document.getElementById('progressSlider');
            const currentTxt = document.getElementById('currentTime');
            const totalTxt = document.getElementById('totalTime');
            const btn = document.getElementById('pauseBtn');

            // 1. On fait bouger le curseur vert
            slider.max = Math.floor(data.duration);
            slider.value = Math.floor(data.pos);

            // 2. On met à jour les chiffres du temps
            currentTxt.innerText = formatTime(data.pos);
            totalTxt.innerText = formatTime(data.duration);

            // 3. On synchronise l'icône du bouton
            if (data.paused) {
                btn.className = 'playing'; // Affiche Play si MPV est en pause
            } else {
                btn.className = 'paused';  // Affiche Pause si la musique joue
            }
        }
    } catch (e) { console.error("Erreur de synchro"); }
}

// Lancement automatique toutes les secondes
setInterval(updateStatus, 1000);

document.getElementById('progressSlider').addEventListener('input', async (e) => {
    const newPos = e.target.value;
    await fetch(`/seek?pos=${newPos}`);
});

