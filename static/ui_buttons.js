// Import shared variables from ui.js (must be a module)
import { canvas, pendingArrows, players, physics, gameId, playerId, submitMoves, fetchGameState, setPlayerId} from "./ui.js";

const API_BASE = "/games/api";

// --- Control panel embedded in sidebar ---
export function createButtonPanel(container) {
  const panel = document.createElement("div");
  panel.id = "game-controls";
  Object.assign(panel.style, {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    padding: "8px",
  });

  const btnOther = document.createElement("button");
  btnOther.textContent = "Submit Moves";
  btnOther.addEventListener("click", async () => {
    submitMoves(pendingArrows);
  });

  const btnRejoin = document.createElement("button");
  btnRejoin.textContent = "Rejoin Game";
  btnRejoin.addEventListener("click", () => {
      const name = prompt("Enter your name:");
      if (!name) return;

      // Look for a matching player in the current players list
      let matchedPid = null;
      for (const pid in players) {
        if (players[pid].name === name) {
          matchedPid = pid;
          break;
        }
      }

      if (!matchedPid) {
        alert("No existing player with that name was found.");
        return;
      }

      // Update client-side playerId
      setPlayerId(matchedPid);

      // Update URL parameter so reload preserves identity
      const url = new URL(window.location.href);
      url.searchParams.set("player_id", playerId);
      window.history.replaceState({}, "", url);

      alert(`Rejoined as ${name}`);
      window.location.reload();
    });


  const btnReset = document.createElement("button");
  btnReset.textContent = "Show last turn";
  btnReset.addEventListener("click", () => {
    pendingArrows.length = 0;
    physics.clearPieces();
    fetchGameState(true);
    console.log("Game reset");
  });

  const btnRunTurn = document.createElement("button");
  btnRunTurn.textContent = "Fasttrack Next Turn (creator only)";
  btnRunTurn.addEventListener("click", async () => {
    try {
      const response = await fetch(`${API_BASE}/apply_submitted_moves`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameId, player_id: playerId })
      });
      const data = await response.json();
      if (response.ok) {
        alert("Press ok to run game \nIf you did not mean to skip to next turn, refresh or close this tab.");
        const nextResponse = await fetch(`${API_BASE}/start_or_run_game?game_id=${gameId}&player_id=${playerId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ game_id: gameId })
        });
        const nextData = await nextResponse.json();
        if (nextResponse.ok) {alert("Success, reload page to see results");}
        console.log("Next phase:", nextData);
      }else{
        alert(`Error: ${data.error || 'Unknown error'}`);
      }
      console.log("Apply moves:", data);
    } catch (err) {
      console.error("Error:", err);
    }
  });

  panel.appendChild(btnOther);
  panel.appendChild(btnReset);
  panel.appendChild(btnRejoin);
  panel.appendChild(btnRunTurn);

  container.appendChild(panel);
}
