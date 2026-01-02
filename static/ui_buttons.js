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
      alert("Press ok to run game \nIf you did not mean to skip to next turn, refresh or close this tab.");
      
      const response = await fetch(`${API_BASE}/apply_moves_and_run_game`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_id: gameId, player_id: playerId })
      });
      const data = await response.json();
      if (response.ok) {
        alert("Success, reload page to see results");
      } else {
        alert(`Error: ${data.error || 'Unknown error'}`);
      }
      console.log("Apply moves and run game:", data);
    } catch (err) {
      console.error("Error:", err);
    }
  });

  panel.appendChild(btnOther);
  panel.appendChild(btnReset);
  panel.appendChild(btnRunTurn);

  container.appendChild(panel);
}
