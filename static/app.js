/**
 * ---------------------------------------------------------
 *  RECHERCHE ET AFFICHAGE DES MORCEAUX
 * ---------------------------------------------------------
 */
async function doSearch() {
    try {
        const query = document.getElementById("searchInput").value;
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
                <button class="play-btn" onclick="play(${song.id})">▶</button>
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
 *  COMMANDES SERVEUR
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
const slider = document.getElementById("progressSlider");

slider.addEventListener("mousedown", () => {
    isDragging = true;
});

slider.addEventListener("mouseup", async (e) => {
    isDragging = false;
    const newPos = Number(e.target.value);
    await fetch(`/setpos/${newPos}`);
});

slider.addEventListener("input", (e) => {
    const currentTxt = document.getElementById("currentTime");
    currentTxt.innerText = formatTime(Number(e.target.value));
});

/**
 * ---------------------------------------------------------
 *  SYNCHRONISATION AVEC MPV
 * ---------------------------------------------------------
 */
async function updateStatus() {
    try {
        const response = await fetch(`/status`);
        const data = await response.json();

        const currentTxt = document.getElementById("currentTime");
        const totalTxt = document.getElementById("totalTime");
        const btn = document.getElementById("pauseBtn");

        if (data.duration > 0) {
            slider.max = Math.floor(data.duration);
            totalTxt.innerText = formatTime(data.duration);
        }

        if (!isDragging) {
            slider.value = Math.floor(data.pos);
            currentTxt.innerText = formatTime(data.pos);
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
 *  EXPOSITION GLOBALE
 * ---------------------------------------------------------
 */
window.play = play;
window.stopMusic = stopMusic;
window.doSearch = doSearch;
window.changeVolume = changeVolume;
window.togglePause = togglePause;
window.seek = seek;

window.onload = doSearch;
