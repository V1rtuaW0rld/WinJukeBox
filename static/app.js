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

            card.innerHTML = `
                <div class="song-info">
                    <strong>${song.title}</strong><br>
                    <small style="color:#b3b3b3">${song.artist}</small>
                </div>
                <div class="song-actions">
                    <button
                        class="add-to-playlist-btn"
                        data-id="${song.id}"
                        data-title="${song.title.replace(/"/g, '&quot;')}"
                        data-artist="${song.artist.replace(/"/g, '&quot;')}"
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
 *  COMMANDES SERVEUR (COHÉRENTES AVEC server.py)
 * ---------------------------------------------------------
 */
async function play(id) {
    await fetch(`/play/${id}`);
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
 *  SYNCHRONISATION AVEC MPV
 * ---------------------------------------------------------
 */
async function updateStatus() {
    try {
        const response = await fetch(`/status`);
        if (!response.ok) return;
        const data = await response.json();

        const currentTxt = document.getElementById("currentTime");
        const totalTxt = document.getElementById("totalTime");
        const btn = document.getElementById("pauseBtn");

        if (!slider) {
            slider = document.getElementById("progressSlider");
            if (!slider) return;
        }

        if (data.duration > 0) {
            slider.max = Math.floor(data.duration);
            totalTxt.innerText = formatTime(data.duration);
        }

        if (!isDragging) {
            slider.value = Math.floor(data.pos || 0);
            currentTxt.innerText = formatTime(data.pos || 0);
        }

        if (data.paused) {
            btn.classList.remove("paused");
            btn.classList.add("playing");
        } else {
            btn.classList.remove("playing");
            btn.classList.add("paused");
        }

    } catch (err) {
        console.error("Erreur updateStatus:", err);
    }
}

setInterval(updateStatus, 1000);

/**
 * ---------------------------------------------------------
 *  PLAYLIST (LOCALSTORAGE + PANNEAU SLIDE-IN)
 * ---------------------------------------------------------
 */
let playlist = [];

function loadPlaylistFromStorage() {
    try {
        const raw = localStorage.getItem("playlist");
        playlist = raw ? JSON.parse(raw) : [];
    } catch {
        playlist = [];
    }
}

function savePlaylistToStorage() {
    localStorage.setItem("playlist", JSON.stringify(playlist));
}

function refreshPlaylistUI() {
    const ul = document.getElementById("playlistItems");
    if (!ul) return;

    ul.innerHTML = "";
    playlist.forEach((song, index) => {
        const li = document.createElement("li");
        li.textContent = `${song.title} — ${song.artist}`;
        li.dataset.index = index;
        ul.appendChild(li);
    });
}

function addToPlaylistFromElement(target) {
    const id = Number(target.dataset.id);
    const title = target.dataset.title || "";
    const artist = target.dataset.artist || "";

    const song = { id, title, artist };
    playlist.push(song);
    savePlaylistToStorage();
    refreshPlaylistUI();
}

function initPlaylistPanel() {
    const playlistPanel = document.getElementById("playlistPanel");
    const openPlaylistBtn = document.getElementById("openPlaylistBtn");
    const closePlaylistBtn = document.getElementById("closePlaylistBtn");
    const playPlaylistBtn = document.getElementById("playPlaylistBtn");
    // Ouvrir / fermer via le bouton 🎵
    if (openPlaylistBtn && playlistPanel) {
        openPlaylistBtn.addEventListener("click", () => {
            playlistPanel.classList.toggle("open");
        });
    }
    // Fermer via le bouton ❌
    if (closePlaylistBtn && playlistPanel) {
        closePlaylistBtn.addEventListener("click", () => {
            playlistPanel.classList.remove("open");
        });
    }
    // Lire la playlist
    if (playPlaylistBtn) {
        playPlaylistBtn.addEventListener("click", () => {
            if (playlist.length > 0) {
                play(playlist[0].id);
            }
        });
    }
    // Click sur les boutons ➕ (délégation)
    document.addEventListener("click", (e) => {
        if (e.target && e.target.classList.contains("add-to-playlist-btn")) {
            addToPlaylistFromElement(e.target);
        }
        if (e.target && e.target.classList.contains("play-btn")) {
            const id = Number(e.target.dataset.id);
            if (id) play(id);
        }
    });
    loadPlaylistFromStorage();
    refreshPlaylistUI();
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
