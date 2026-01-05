/**
 * ---------------------------------------------------------
 * RECHERCHE ET AFFICHAGE DES MORCEAUX
 * ---------------------------------------------------------
 */
let currentSearchMode = 'title'; 

function setSearchMode(mode) {
    currentSearchMode = mode;
    const input = document.getElementById("searchInput");
    
    // Optimisation : Utilisation d'un dictionnaire pour le texte
    const labels = { 'artist': 'artiste', 'album': 'album', 'title': 'titre' };
    input.placeholder = `Rechercher ${labels[mode] || 'titre'}...`;

    // Gestion visuelle des icônes
    document.querySelectorAll('.search-icon-btn').forEach(img => {
        img.classList.toggle('active', img.src.includes(mode));
    });

    doSearch();
}

async function doSearch() {
    try {
        const query = document.getElementById("searchInput").value || "";
        // On envoie le mode au serveur
        const url = `/search?q=${encodeURIComponent(query)}&mode=${currentSearchMode}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error("Erreur serveur");
        const data = await response.json();
        const list = document.getElementById("songList");

        list.innerHTML = "";

        if (!data.songs || data.songs.length === 0) {
            list.innerHTML = `<div style="text-align:center; padding:20px;">Aucune musique trouvée 🎸</div>`;
            return;
        }

            data.songs.forEach(song => {
    const card = document.createElement("div");
    const isGroupMode = (currentSearchMode === 'artist' || currentSearchMode === 'album');
    card.className = isGroupMode ? "song-card album-card-container" : "song-card";

    const cleanTitle = song.title.replace(/"/g, '&quot;').replace(/'/g, "\\'");
    const cleanArtist = song.artist.replace(/"/g, '&quot;').replace(/'/g, "\\'");
    const cleanAlbum = (song.album || "").replace(/"/g, '&quot;').replace(/'/g, "\\'");

    if (isGroupMode) {
    const albumCoverUrl = `/cover/${song.id}`;
    
    card.innerHTML = `
    <div class="album-card-content" style="display: flex; flex-direction: column; width: 100%;">
        <div class="album-header" style="display: flex; align-items: center; padding: 12px;">
            
            <span class="expand-icon" 
                  style="cursor:pointer; margin-right:15px; font-size:1.2em; color:#1db954; flex-shrink: 0;" 
                  onclick="toggleAlbum('${cleanAlbum}', '${cleanArtist}', this)">▶</span>
            
            <div class="cover-slot" style="width: 100px; height: 100px; margin-right: 20px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;">
            </div>

            <div class="album-identity" style="display: flex; flex-direction: column; flex-grow: 1;">
                
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 2px;">
                    <span style="font-size: 0.9em;">💿</span>
                    <div class="song-title" style="color: #1db954; font-weight: bold; font-size: 1.1em;">
                        ${song.album}
                    </div>
                    
                    <button class="play-album-fast-btn" 
                            title="Écouter cet album maintenant"
                            style="background: #1db954; border: none; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: white;"
                            onclick="playFullAlbumNow('${cleanAlbum}', '${cleanArtist}')">
                        <span style="font-size: 0.8em; margin-left: 2px;">▶</span>
                    </button>
                </div>

                <div class="song-subtext" style="color: #b3b3b3; margin-bottom: 10px; font-size: 0.9em;">
                    ${song.artist}
                </div>
                
                <button class="add-album-btn" 
                        style="width: fit-content; background:#1db954; color:white; border:none; border-radius:20px; padding:5px 15px; font-size:0.75em; font-weight:bold; cursor:pointer; display: flex; align-items: center; text-transform: uppercase;"
                        onclick="addFullAlbum('${cleanAlbum}', '${cleanArtist}')">
                    <span style="margin-right:5px; font-size: 1.2em;">+</span> TOUT AJOUTER
                </button>
                
            </div>
        </div>
        <div class="album-details" style="display: none; width: 100%;"></div>
    </div>`;

    // On tente de charger l'image
    const imgTest = new Image();
    imgTest.src = albumCoverUrl;
    
    imgTest.onload = function() {
        const slot = card.querySelector('.cover-slot');
        if (slot) {
            // On injecte l'image seulement si elle existe
            slot.innerHTML = `<img src="${albumCoverUrl}" 
                                   style="width: 100%; height: 100%; border-radius: 4px; object-fit: cover; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">`;
        }
    };

    // Si erreur (404), on ne fait rien : le cover-slot reste une zone de 70px vide et invisible.


   
    } else {
        const albumInfo = song.album ? ` > ${song.album}` : "";
        card.innerHTML = `
            <div class="song-info">
                <div class="song-title">${song.title}</div>
                <div class="song-subtext">
                    <span class="song-artist">${song.artist}</span>
                    <span class="song-album">${albumInfo}</span>
                </div>
            </div>
            <div class="song-actions">
                <button class="add-to-playlist-btn" 
                    data-id="${song.id}" 
                    data-title="${cleanTitle}" 
                    data-artist="${cleanArtist}" 
                    data-album="${cleanAlbum}">➕</button>
                <button class="play-btn" data-id="${song.id}">▶</button>
            </div>`;
    }
    list.appendChild(card);
});

    } catch (err) {
        console.error(err);
        document.getElementById("songList").innerHTML = 
            `<div style="color:red; text-align:center; padding:20px;">Impossible de joindre le Jukebox.</div>`;
    }
}


async function toggleAlbum(albumName, artistName, element) {
    const detailDiv = element.closest('.album-card-container').querySelector('.album-details');
    
    if (detailDiv.style.display === 'block') {
        detailDiv.style.display = 'none';
        element.innerText = '▶';
        return;
    }

    if (detailDiv.innerHTML.trim() === "") {
        try {
            const url = `/album_tracks?album=${encodeURIComponent(albumName)}&artist=${encodeURIComponent(artistName)}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.tracks && data.tracks.length > 0) {
                let html = "";
                data.tracks.forEach(track => {
    const cleanT = track.title.replace(/"/g, '&quot;').replace(/'/g, "\\'");
    
    html += `
        <div class="track-item" style="padding: 10px 30px 10px 10px; border-bottom: 1px solid #222; display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #ccc;">${track.title}</span>
            
            <div class="song-actions" style="display: flex; gap: 10px;">
                <button class="add-to-playlist-btn" 
                        data-id="${track.id}" 
                        data-title="${cleanT}" 
                        data-artist="${artistName.replace(/'/g, "\\'")}" 
                        data-album="${albumName.replace(/'/g, "\\'")}">➕</button>
                
                <button class="play-btn" data-id="${track.id}">▶</button>
            </div>
        </div>`;
});
                detailDiv.innerHTML = html;
            }
        } catch (err) {
            console.error("Erreur:", err);
        }
    }

    detailDiv.style.display = 'block';
    element.innerText = '▼';
}
async function addFullAlbum(albumName, artistName) {
    console.log(`Préparation de l'ajout global : ${albumName}`);
    
    try {
        // 1. On utilise ta route existante pour lister les titres
        const response = await fetch(`/album_tracks?album=${encodeURIComponent(albumName)}&artist=${encodeURIComponent(artistName)}`);
        const data = await response.json();
        
        if (data.tracks && data.tracks.length > 0) {
            // 2. On boucle sur chaque piste reçue
            for (const track of data.tracks) {
                // On utilise ta route existante pour ajouter UN titre
                // Le "await" ici est crucial : il attend que le Python ait fini l'insertion 
                // avant de demander la suivante, évitant de bloquer ta base de données.
                await fetch(`/playlist/add/${track.id}`, { method: "POST" });
            }
            
            // 3. Une fois la boucle terminée, on rafraîchit la playlist à droite
            loadPlaylistFromServer();
            
            // 4. On affiche l'alerte
            alert(`L'album "${albumName}" a été ajouté à la playlist.`);
        }
    } catch (err) {
        console.error("Erreur lors de l'ajout groupé :", err);
    }
}
/**
 * ---------------------------------------------------------
 * COMMANDES SERVEUR & GESTION AUDIO DYNAMIQUE
 * ---------------------------------------------------------
 */
let isLaunching = false;
// On récupère le dernier device utilisé ou "auto" par défaut
let selectedDevice = localStorage.getItem("selectedAudioDevice") || "auto";

async function play(id) {
    if (isLaunching) return;
    isLaunching = true;

    
    // On encode le device pour gérer les espaces et caractères spéciaux du FriendlyName
    const deviceParam = encodeURIComponent(selectedDevice);
    await fetch(`/play/${id}?device=${deviceParam}`);

    setTimeout(() => {
        isLaunching = false;
    }, 500); 
}

async function stopMusic() {
    await fetch(`/stop`);
}

async function togglePause() {
    await fetch(`/pause`);
}

// Variable locale pour éviter que le curseur ne saute pendant qu'on le bouge
let isDraggingVolume = false;

async function changeVolume(level) {
    // On met à jour le volume sur le serveur
    await fetch(`/volume/${level}`);
    
    // Optionnel : on peut stocker aussi dans le navigateur pour un backup
    localStorage.setItem("lastVolume", level);
}

async function seek(seconds) {
    await fetch(`/seek/${seconds}`);
}

async function playNext() {
    if (!currentTrackId) return;
    const res = await fetch(`/next?current_id=${currentTrackId}`);
    const data = await res.json();
    if (data.id) play(data.id);
}

async function playPrevious() {
    if (!currentTrackId) return;
    const res = await fetch(`/previous?current_id=${currentTrackId}`);
    const data = await res.json();
    if (data.id) play(data.id);
}

/**
 * ---------------------------------------------------------
 * SÉLECTEUR DE SORTIE AUDIO (MODALE)
 * ---------------------------------------------------------
 */
const speakerBtn = document.getElementById("speakerBtn");
if (speakerBtn) {
    speakerBtn.addEventListener("click", openDeviceModal);
}

async function openDeviceModal() {
    const modal = document.getElementById("deviceModal");
    const list = document.getElementById("deviceList");
    
    modal.style.display = "flex";
    list.innerHTML = "<p style='color: #888;'>Recherche des périphériques...</p>";

    try {
        const resp = await fetch("/audio-devices");
        const data = await resp.json();
        
        list.innerHTML = ""; // On vide le message de chargement

        if (data.devices && data.devices.length > 0) {
            data.devices.forEach(name => {
                const fullDeviceString = `wasapi/${name}`;
                const div = document.createElement("div");
                div.className = "device-item";
                
                // Si c'est le device actuel, on ajoute une classe visuelle
                if (selectedDevice === fullDeviceString) {
                    div.classList.add("active");
                }
                
                div.innerText = name;
                div.onclick = () => {
                    selectedDevice = fullDeviceString;
                    localStorage.setItem("selectedAudioDevice", selectedDevice);
                    console.log("Sortie audio définie sur :", selectedDevice);
                    closeDeviceModal();
                    
                    // Optionnel : petit feedback visuel
                    alert(`Sortie configurée : ${name}\nPrendra effet au prochain morceau.`);
                };
                list.appendChild(div);
            });
        } else {
            list.innerHTML = "<p>Aucun périphérique trouvé.</p>";
        }
    } catch (err) {
        list.innerHTML = "<p>Erreur lors de la récupération des périphériques.</p>";
        console.error(err);
    }
}

function closeDeviceModal() {
    document.getElementById("deviceModal").style.display = "none";
}

// Fermer la modale si on clique en dehors du cadre
window.onclick = function(event) {
    const modal = document.getElementById("deviceModal");
    if (event.target == modal) {
        closeDeviceModal();
    }
}

/**
 * ---------------------------------------------------------
 *  FORMATAGE DU TEMPS
 * ---------------------------------------------------------
 */
function formatTime(seconds) {
    if (!seconds || seconds < 0) return "0:00";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec < 10 ? "0" : ""}${sec}`;
}

/**
 * ---------------------------------------------------------
 *  BARRE DE PROGRESSION
 * ---------------------------------------------------------
 */
let isDragging = false;
let slider = null;

function initProgressBar() {
    slider = document.getElementById("progressSlider");
    if (!slider) return;

    slider.addEventListener("mousedown", () => {
        isDragging = true;
    });

    slider.addEventListener("touchstart", () => {
        isDragging = true;
    });

    slider.addEventListener("mouseup", async (e) => {
        isDragging = false;
        const newPos = Number(e.target.value);
        await fetch(`/setpos/${newPos}`);
    });

    slider.addEventListener("touchend", async () => {
        isDragging = false;
        const newPos = Number(slider.value);
        await fetch(`/setpos/${newPos}`);
        setTimeout(updateStatus, 300);
    });

    slider.addEventListener("input", (e) => {
        const currentTxt = document.getElementById("currentTime");
        currentTxt.innerText = formatTime(Number(e.target.value));
    });
}

/**
 * ---------------------------------------------------------
 * SYNCHRONISATION AVEC MPV & AFFICHAGE INFOS BDD
 * ---------------------------------------------------------
 */
async function updateStatus() {
    try {
        const response = await fetch(`/status`);
        if (!response.ok) return;
        const data = await response.json();

        // --- 1. MISE À JOUR DES INFOS (HEADER & TEXTES) ---
        if (data.track) {
            const elTitle = document.getElementById("trackTitle");
            const elArtist = document.getElementById("trackArtist");
            const elAlbum = document.getElementById("trackAlbum");
            
            // On vérifie si le texte affiché correspond au morceau réel
            // Si ça diffère, on force la mise à jour des textes
            if (elTitle && elTitle.innerText !== data.track.title) {
                elTitle.innerText = data.track.title || "---";
                if (elArtist) elArtist.innerText = data.track.artist || "---";
                if (elAlbum) elAlbum.innerText = data.track.album || "";
            }

            // MISE À JOUR DE L'AMBIANCE VISUELLE (Image)
if (data.track && data.track.id !== currentTrackId) {
    const elHeader = document.querySelector(".jukebox-header");
    const elCover = document.getElementById("current-cover");
    const nextSrc = `/cover/${data.track.id}?t=${new Date().getTime()}`;

    // On crée un testeur d'image "fantôme"
    const imgTester = new Image();
    imgTester.src = nextSrc;

    // CAS 1 : L'image existe et charge avec succès
    imgTester.onload = () => {
        const urlFormat = `url("${nextSrc}")`;
        document.body.style.backgroundImage = urlFormat;
        if (elHeader) elHeader.style.backgroundImage = urlFormat;
        if (elCover) {
            elCover.style.display = "block";
            elCover.src = nextSrc;
        }
    };

    // CAS 2 : L'image est absente (Erreur 404 ou 500)
    imgTester.onerror = () => {
        console.log("Pochette absente pour ce titre, passage en mode neutre.");
        // Au lieu d'une image, on met un dégradé stylé pour le fond
        const neutralBg = "linear-gradient(135deg, #121212 0%, #282828 100%)";
        
        document.body.style.backgroundImage = neutralBg;
        if (elHeader) elHeader.style.backgroundImage = neutralBg;
        
        if (elCover) {
            // On cache la balise image cassée pour ne pas voir l'icône "image brisée"
            elCover.style.display = "none"; 
        }
    };

    currentTrackId = data.track.id;
}
        }

        // --- 2. GESTION DU HIGHLIGHT DANS LA PLAYLIST ---
        const allItems = document.querySelectorAll(".playlist-item");
        allItems.forEach(item => {
            const isCurrent = (data.track && Number(item.dataset.id) === data.track.id);
            item.classList.toggle("playing-now", isCurrent);
        });

        // --- 3. BARRE DE PROGRESSION & TEMPS ---
        const currentTxt = document.getElementById("currentTime");
        const totalTxt = document.getElementById("totalTime");
        
        if (!slider) slider = document.getElementById("progressSlider");

        if (slider) {
            if (data.duration > 0) {
                slider.max = Math.floor(data.duration);
                if (totalTxt) totalTxt.innerText = formatTime(data.duration);
            }
            if (!isDragging) {
                slider.value = Math.floor(data.pos || 0);
                if (currentTxt) currentTxt.innerText = formatTime(data.pos || 0);
            }
        }

        // --- 4. ÉTAT DU BOUTON PAUSE ---
        const btn = document.getElementById("pauseBtn");
        if (btn) {
         // Si data.paused est vrai, la musique est arrêtée : on affiche "Play"
        if (data.paused) {
        btn.classList.add("paused");
        btn.classList.remove("playing");
        } 
        // Sinon, la musique joue : on affiche "Pause"
        else {
        btn.classList.add("playing");
        btn.classList.remove("paused");
        }

        // --- 5. SYNCHRO DU SLIDER VOLUME ---
        const volSlider = document.getElementById("volumeSlider"); // Vérifie bien cet ID dans ton HTML
        if (volSlider && !isDraggingVolume) {
        // Si le serveur nous renvoie le volume dans le status
        if (data.volume !== undefined) {
        volSlider.value = data.volume;
        }
        }
}

    } catch (err) {
        console.error("Erreur updateStatus:", err);
    }
}

// Lancement de la boucle de synchronisation (1 fois par seconde)
setInterval(updateStatus, 1000);

// Lire un Album individuellement
// Variable globale pour savoir quelle table on lit
let currentMode = "playlist"; // ou "album"

async function playFullAlbumNow(albumName, artistName) {
    try {
        const response = await fetch('/api/play_album_now', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ album: albumName, artist: artistName })
        });
        
        const data = await response.json();
        
        if (data.first_id) {
            // On lance la lecture. Le serveur gérera le 'next' 
            // via la priorité playlist_album dans ta route /next
            play(data.first_id);
            console.log("Lecture de l'album lancée :", albumName);
        } else {
            console.error("Erreur : Aucun ID retourné par le serveur");
        }
    } catch (err) {
        console.error("Erreur lors de la requête album :", err);
    }
}


/**
 * ---------------------------------------------------------
 *  PLAYLIST (SQLITE + PANNEAU SLIDE-IN + ENCHAÎNEMENT)
 * ---------------------------------------------------------
 */

let playlist = [];
let currentPlaylistIndex = -1;
let isPlaylistMode = false;
let currentTrackId = null; // morceau actuellement joué




/* Charger la playlist depuis le serveur */
async function loadPlaylistFromServer() {
    try {
        const res = await fetch("/playlist");
        const data = await res.json();
        playlist = data.songs || [];
        refreshPlaylistUI();
    } catch (e) {
        console.warn("Erreur de chargement de la playlist", e);
    }
}

/* Ajouter une chanson à la playlist */
async function addToPlaylistFromElement(target) {
    const id = Number(target.dataset.id);
    if (!id) return;

    await fetch(`/playlist/add/${id}`, { method: "POST" });
    loadPlaylistFromServer();
}

/* Supprimer une chanson de la playlist */
async function removeFromPlaylist(id) {
    await fetch(`/playlist/remove/${id}`, { method: "DELETE" });
    loadPlaylistFromServer();
}

/* Rafraîchir l'affichage du panneau playlist */
function refreshPlaylistUI() {
    const ul = document.getElementById("playlistItems");
    if (!ul) return;

    ul.innerHTML = "";

    playlist.forEach((song, index) => {
        const li = document.createElement("li");
        li.classList.add("playlist-item");
        li.dataset.id = song.id; 

        // 1. Création du Slot pour la mini-cover (fixe à 32px)
        const coverSlot = document.createElement("div");
        coverSlot.style.width = "32px";
        coverSlot.style.height = "32px";
        coverSlot.style.marginRight = "12px";
        coverSlot.style.flexShrink = "0";
        coverSlot.style.borderRadius = "3px";
        coverSlot.style.overflow = "hidden";
        coverSlot.style.backgroundColor = "rgba(255,255,255,0.05)"; // Optionnel : léger fond gris
        coverSlot.style.display = "flex";
        coverSlot.style.alignItems = "center";
        coverSlot.style.justifyContent = "center";

        // 2. Test de l'image pour la mini-cover
        const miniImg = new Image();
        miniImg.src = `/cover/${song.id}`;
        miniImg.style.width = "100%";
        miniImg.style.height = "100%";
        miniImg.style.objectFit = "cover";

        miniImg.onload = () => {
            coverSlot.appendChild(miniImg);
        };
        // Si erreur (404), on ne fait rien : le slot reste vide (zone de vide propre)

        // 3. Zone texte cliquable
        const textSpan = document.createElement("span");
        textSpan.textContent = `${song.title} — ${song.artist}`;
        textSpan.classList.add("playlist-text");
        textSpan.style.flexGrow = "1"; // Pour que le texte occupe l'espace
        textSpan.style.fontSize = "0.85em";
        textSpan.style.whiteSpace = "nowrap";
        textSpan.style.overflow = "hidden";
        textSpan.style.textOverflow = "ellipsis";
        
        textSpan.addEventListener("click", () => {
            const foundIndex = playlist.findIndex(s => s.id === song.id);
            if (foundIndex !== -1) {
                isPlaylistMode = true;
                currentPlaylistIndex = foundIndex;
                play(song.id);
            }
        });

        // 4. Bouton corbeille
        const trashBtn = document.createElement("button");
        trashBtn.textContent = "🗑";
        trashBtn.classList.add("remove-btn");
        trashBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            removeFromPlaylist(song.id);
        });

        // Assemblage (Vignette + Texte + Poubelle)
        li.appendChild(coverSlot);
        li.appendChild(textSpan);
        li.appendChild(trashBtn);
        ul.appendChild(li);
    });
}


/* Initialisation du panneau playlist */
function initPlaylistPanel() {
    const playlistPanel = document.getElementById("playlistPanel");
    const openPlaylistBtn = document.getElementById("openPlaylistBtn");
    const closePlaylistBtn = document.getElementById("closePlaylistBtn");
    const playPlaylistBtn = document.getElementById("playPlaylistBtn");
    const shufflePlaylistBtn = document.getElementById("shufflePlaylistBtn");
    const nextBtn = document.getElementById("nextBtn");
    const prevBtn = document.getElementById("prevBtn");
    const clearPlaylistBtn = document.getElementById("clearPlaylistBtn");

    if (clearPlaylistBtn) {
    clearPlaylistBtn.addEventListener("click", async () => {
        await fetch("/playlist/clear", { method: "DELETE" });
        loadPlaylistFromServer();
    });
    }
    
    if (openPlaylistBtn && playlistPanel) {
        openPlaylistBtn.addEventListener("click", () => {
            // On ouvre le panneau et on notifie le body pour décaler la liste
            playlistPanel.classList.toggle("open");
            document.body.classList.toggle("playlist-is-open");
        });
    }

    if (closePlaylistBtn && playlistPanel) {
        closePlaylistBtn.addEventListener("click", () => {
            // On ferme le panneau et on retire le décalage
            playlistPanel.classList.remove("open");
            document.body.classList.remove("playlist-is-open");
        });
    }

    if (playPlaylistBtn) {
        playPlaylistBtn.addEventListener("click", () => {
            if (playlist.length > 0) {
                isPlaylistMode = true;
                currentPlaylistIndex = 0;
                play(playlist[0].id);
            }
        });
    }
    
    if (shufflePlaylistBtn) {
        shufflePlaylistBtn.addEventListener("click", () => {
            toggleShuffle();
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            playNext();
        });
    }
    
    if (prevBtn) {
        prevBtn.addEventListener("click", () => {
            playPrevious();
        });
    }

    // Gestion des clics délégués pour les boutons dans les cartes
    document.addEventListener("click", (e) => {
        // Pour l'ajout à la playlist
        const addBtn = e.target.closest(".add-to-playlist-btn");
        if (addBtn) {
            addToPlaylistFromElement(addBtn);
        }

        // Pour le bouton Play (hors playlist)
        const playBtn = e.target.closest(".play-btn");
        if (playBtn) {
            const id = Number(playBtn.dataset.id);
            if (id) {
                isPlaylistMode = false;
                play(id);
            }
        }
    });

    loadPlaylistFromServer();
    refreshShuffleStatus();
}

/* Ajout des helpers shuffle */
let shuffleActive = false;

async function refreshShuffleStatus() {
    try {
        const res = await fetch("/shuffle/status");
        const data = await res.json();
        shuffleActive = !!data.shuffle;
        updateShuffleButton();
    } catch (e) {
        console.warn("Erreur /shuffle/status", e);
    }
}

function updateShuffleButton() {
    const btn = document.getElementById("shufflePlaylistBtn");
    if (!btn) return;
    btn.classList.toggle("active", shuffleActive);
    btn.classList.toggle("inactive", !shuffleActive);
}

async function enableShuffle() {
    try {
        const res = await fetch("/shuffle/enable", { method: "POST" });
        const data = await res.json();
        shuffleActive = true;
        isPlaylistMode = true;        // on lit en mode "playlist"
        currentPlaylistIndex = -1;    // index local n'a plus de sens en shuffle
        updateShuffleButton();
    } catch (e) {
        console.warn("Erreur /shuffle/enable", e);
    }
}

async function disableShuffle() {
    try {
        await fetch("/shuffle/disable", { method: "POST" });
        shuffleActive = false;
        updateShuffleButton();
    } catch (e) {
        console.warn("Erreur /shuffle/disable", e);
    }
}

async function toggleShuffle() {
    if (shuffleActive) {
        await disableShuffle();
    } else {
        await enableShuffle();
    }
}


/**
 * ---------------------------------------------------------
 * INITIALISATION GLOBALE
 * ---------------------------------------------------------
 */
window.addEventListener("load", () => {
    initProgressBar();
    initPlaylistPanel();
    
    // On remplace doSearch() par setSearchMode pour 
    // allumer l'icône "titre" et préparer le terrain proprement.
    setSearchMode('title'); 
});

/**
 * ---------------------------------------------------------
 *  EXPOSITION GLOBALE (pour les attributs onclick HTML)
 * ---------------------------------------------------------
 */
window.play = play;
window.stopMusic = stopMusic;
window.doSearch = doSearch;
window.changeVolume = changeVolume;
window.togglePause = togglePause;
window.seek = seek;
window.playNext = playNext;
window.playPrevious = playPrevious;