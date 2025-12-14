// Import shared variables from ui.js (must be a module)
import { gameId, playerId, players} from "./ui.js";

const API_BASE = "/games/api";
const UPDATE_INTERVAL = 60000; // 1 minute between updates

export function renderLeaderboard(container) {
  const leaderboard = document.createElement("div");
  leaderboard.id = "game-leaderboard";
  Object.assign(leaderboard.style, {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  });
  container.appendChild(leaderboard);

  
  let pieces = null;
  let playersWaiting = {};

  async function updatePlayers(repeatCount = 1) {
    for (let attempt = 1; attempt <= repeatCount; attempt++) {
      try {
        const res = await fetch(`${API_BASE}/game_state?game_id=${gameId}`);
        if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
        const data = await res.json();

        // Mutate the existing players object instead of replacing it
          Object.keys(players).forEach(k => delete players[k]);       // clear
          Object.assign(players, data.players || {});                 // repopulate


        pieces = data.pieces || [];
        playersWaiting = {};
        for (const pid in players) {
          if (players[pid].submitted_turn === "waiting") {
            playersWaiting[pid] = true;
          }
        }
        updateLeaderboard();
      } catch (err) {
        console.error("Failed to update players:", err);
      }
      if (attempt < repeatCount) {
        await new Promise(resolve => setTimeout(resolve, UPDATE_INTERVAL));
      }
    }
  }

  function updateLeaderboard() {
    if (!players) return;
    leaderboard.textContent = "";

    const header = document.createElement("h3");
    header.textContent = "Leaderboard";
    header.style.margin = "0 0 8px 0";
    leaderboard.appendChild(header);

    const pieceCounts = {};
    
    if (Array.isArray(pieces)) {
      pieces.forEach(piece => {
        const ownerId = piece.owner;
        if (piece.status != "out"){
            pieceCounts[ownerId] = (pieceCounts[ownerId] || 0) + 1;
        }
        
      });
    }
    


    

    for (const pid in players) {
      const player = players[pid];
      const score = pieceCounts[pid] || 0;
      const row = document.createElement("div");
      row.textContent = `${playersWaiting[pid] ? "⏳ " : ""}${player.name}: ${score} pieces ${pid === playerId ? "(you)" : ""}`;

      const colorBox = document.createElement("span");
      Object.assign(colorBox.style, {
        display: "inline-block",
        width: "12px",
        height: "12px",
        borderRadius: "2px",
        background: player.color || "gray",
        marginRight: "4px",
      });
      row.prepend(colorBox);

      leaderboard.appendChild(row);
    }
  }

  updatePlayers(20);
}
