/**
 * ---------------------------------------------------------
 *  RECHERCHE ET AFFICHAGE DES MORCEAUX
 * ---------------------------------------------------------
 * Utilise l'endpoint /search de server.py
 */
async function doSearch() {
    try {
        const query = document.getElementById("searchInput").value || "";
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error("Erreur serveur");

        const data = await response.json();
        const list = document.getElementById("songList");

        if (!data.songs || data.songs.length === 0) {
            list.innerHTML = `<div style="text-align:center; padding:20px;">
                Aucune musique trouvée 🎸
            </div>`;
            return;
        }

        list.innerHTML = "";
        data.songs.forEach(song => {
            const card = document.createElement("div");
            card.className = "song-card";

            // --- PRÉPARATION DU TEXTE DE L'ALBUM ---
            // Si song.album existe, on ajoute " > Nom de l'album", sinon rien.
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
                    <button
                        class="add-to-playlist-btn"
                        data-id="${song.id}"
                        data-title="${song.title.replace(/"/g, '&quot;')}"
                        data-artist="${song.artist.replace(/"/g, '&quot;')}"
                        data-album="${(song.album || "").replace(/"/g, '&quot;')}"
                    >➕</button>
                    <button class="play-btn" data-id="${song.id}">▶</button>
                </div>
            `;

            list.appendChild(card);
        });

    } catch (err) {
        console.error(err);
        document.getElementById("songList").innerHTML =
            `<div style="color:red; text-align:center; padding:20px;">
                Impossible de joindre le Jukebox.
            </div>`;
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

async function changeVolume(level) {
    await fetch(`/volume/${level}`);
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
            // On ne change l'image que si l'ID a vraiment changé pour éviter le clignotement
            if (data.track.id !== currentTrackId) {
                const elHeader = document.querySelector(".jukebox-header");
                const elCover = document.getElementById("current-cover");
                const nextSrc = `/cover/${data.track.id}`;
                const timestamp = new Date().getTime();
                const fullImageUrl = `url("${nextSrc}?t=${timestamp}")`;

                document.body.style.backgroundImage = fullImageUrl;
                if (elHeader) elHeader.style.backgroundImage = fullImageUrl;
                if (elCover) elCover.src = `${nextSrc}?t=${timestamp}`;

                // On met à jour l'ID global une fois que tout est fait
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
}

    } catch (err) {
        console.error("Erreur updateStatus:", err);
    }
}

// Lancement de la boucle de synchronisation (1 fois par seconde)
setInterval(updateStatus, 1000);

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
        
        // --- ÉTAPE CRUCIALE POUR LE HIGHLIGHT ---
        // On attache l'ID de la BDD directement à l'élément HTML
        li.dataset.id = song.id; 

        // Zone texte cliquable
        const textSpan = document.createElement("span");
        textSpan.textContent = `${song.title} — ${song.artist}`;
        textSpan.classList.add("playlist-text");
        
        textSpan.addEventListener("click", () => {
            const foundIndex = playlist.findIndex(s => s.id === song.id);
            if (foundIndex !== -1) {
                isPlaylistMode = true;
                currentPlaylistIndex = foundIndex;
                play(song.id);
            }
        });

        // Bouton corbeille (pour supprimer de la playlist)
        const trashBtn = document.createElement("button");
        trashBtn.textContent = "🗑";
        trashBtn.classList.add("remove-btn");
        trashBtn.addEventListener("click", (e) => {
            e.stopPropagation(); // Empêche de lancer la musique quand on veut juste supprimer
            removeFromPlaylist(song.id);
        });

        // Assemblage de la ligne
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
 *  INITIALISATION GLOBALE
 * ---------------------------------------------------------
 */
window.addEventListener("load", () => {
    initProgressBar();
    initPlaylistPanel();
    doSearch();
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