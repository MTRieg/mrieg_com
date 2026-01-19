import { KnockoutPhysics } from "./physics.js";



const url = new URL(import.meta.url);
const background = url.searchParams.get("background") === "true";

if (background) {
    console.log("trying to load conway");
    import("/static/ui_conway.js")
    //reminder to self: do not await this load. This file needs to finish loading before conway can load


} else {
    import("/static/ui_inputs.js")
}

const API_BASE = "https://mrieg.com/games/api";
const urlParams = new URLSearchParams(window.location.search);

// Game constants
const DEFAULT_BOARD_SIZE = 800;
const DEFAULT_DISPLAY_SIZE = 1000; // the size used for scaling calclations (always larger than board size)
const DEFAULT_BOARD_SHRINK = 50;
const COLORS = ["red", "blue", "green", "yellow", "grey", "maroon", "purple", "orange", "magenta", "gold"];
const PIECE_RADIUS = 30;

// Game state
let board_size = DEFAULT_BOARD_SIZE;
let board_shrink = DEFAULT_BOARD_SHRINK;
// Prefer explicit player_id from URL first; do NOT default to localStorage anymore.
// We'll try URL, and only after we know gameId we'll try the cookie via getPlayerIdFromCookie.
let playerId = urlParams.get("player_id") || null;
let currentTurn = 0;
const pendingArrows = [];

let players = {};

function setPlayerId(pid){
    playerId = pid;
}

// Getter for board size so other modules can read the current value.
function getBoardSize() {
  return board_size;
}

// Canvas setup
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

// Display state
let devicePixelRatio = window.devicePixelRatio || 1;
let displayScale = 1; //will be overwritten in resizeCanvas
let CENTER_X = 0;
let CENTER_Y = 0;
let WIDTH = 0;
let HEIGHT = 0;

// Physics
const physics = new KnockoutPhysics();

//when loading a replay, this is to help make adjustments from what the local simulation calculated to what the server calculated.
//should be negligeble, but important nonetheless, and if it's not negligeble then we have bigger problems.

let server_pieces = null;
let server_players = null;


   //removing this because it'll be easier to just store everything in cookies
// Persist player ID if provided in URL
if (urlParams.get("player_id")) {
    localStorage.setItem("player_id", playerId);
}


// --- Arrow <-> velocity conversion ---
// tweak this factor after testing with the physics engine


const ARROW_TO_VEL_FACTOR = 1; // tune this

function arrowToVelocity(d) {

  return { x: ARROW_TO_VEL_FACTOR*d.x, y: ARROW_TO_VEL_FACTOR*d.y};
}



function velocityToArrow(v) {

  return { x: v.x/ARROW_TO_VEL_FACTOR, y: v.y*ARROW_TO_VEL_FACTOR};
}



// Canvas resize handling
function resizeCanvas() {
    try {
        devicePixelRatio = window.devicePixelRatio || 1;
        
        // Force a layout recalculation
        document.body.style.height = window.innerHeight + 'px';
        
        // Get actual viewport size (important for mobile)
        const cssWidth = document.documentElement.clientWidth;
        const cssHeight = document.documentElement.clientHeight;
        
        // Set CSS size first
        canvas.style.width = cssWidth + "px";
        canvas.style.height = cssHeight + "px";
        
        // Then set backing store size
        canvas.width = Math.round(cssWidth * devicePixelRatio);
        canvas.height = Math.round(cssHeight * devicePixelRatio);
        
        WIDTH = canvas.width;
        HEIGHT = canvas.height;
        CENTER_X = WIDTH / 2;
        CENTER_Y = HEIGHT / 2;
        
        
        // ------ NEW SCALING LOGIC ------
        // Determine the maximum allowed rendered board size:
        const maxRenderSize = Math.min(WIDTH, HEIGHT);

        // Compute scale so the logical board_size fits into maxRenderSize
        displayScale = maxRenderSize / (DEFAULT_DISPLAY_SIZE);
        // --------------------------------

        
        
    } catch (err) {
        console.error("Resize error:", err);
    }
}

// Coordinate conversion helper
function clientToWorld(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const deviceX = (clientX - rect.left) * devicePixelRatio;
    const deviceY = (clientY - rect.top) * devicePixelRatio;
    return {
        x: (deviceX - CENTER_X) / displayScale,
        y: (deviceY - CENTER_Y) / displayScale
    };
}

// Initialize canvas size
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

// --- Game logic ---

// Assuming the game ID is in the URL (e.g., ?id=ABC123)
const gameId = urlParams.get("game_id");

// New function: get player id from server-set cookie "game_info" with format "game_id:player_id[,game_id:player_id...]"
function getPlayerIdFromCookie(gid) {
    if (!gid) return null;
    const cookies = document.cookie ? document.cookie.split("; ") : [];
    const kv = cookies.find(c => c.startsWith("game_info="));
    if (!kv) return null;
    const raw = decodeURIComponent(kv.split("=").slice(1).join("="));
    // raw may be "game1:player1,game2:player2"
    const pairs = raw.split(",");
    for (const p of pairs) {
        const [g, pid] = p.split(":");
        if (g === gid) return pid || null;
    }
    return null;
}

// Only call cookie lookup after the existing checks for game_id in the URL (per request)
if (!playerId && gameId) {
    const pid = getPlayerIdFromCookie(gameId);
    if (pid) {
        playerId = pid;
    }
}

console.log(playerId)

async function fetchGameState(ReplayLastTurn=false) {
  const res = await fetch(`${API_BASE}/game_state?game_id=${gameId}`);
  const data = await res.json();

  console.log("ReplayLastTurn:", ReplayLastTurn, " old_pieces:", Boolean(data.pieces_old && data.pieces_old.length > 0));

  // Extract values from nested structure
  const turn_number = data.state?.turn_number;
  const board_size_new = data.settings?.board_size;
  const board_shrink_new = data.settings?.board_shrink;
  const pieces_old = data.pieces_old || [];
  const pieces = data.pieces || [];
  const players_data = data.players || {};

  // store current turn for submissions
  if (typeof turn_number === "number") currentTurn = turn_number;
  if (typeof board_size_new === "number") board_size = board_size_new;
  if (typeof board_shrink_new === "number") board_shrink = board_shrink_new;

  // Convert players structure to format expected by place_pieces
  const players_formatted = {};
  for (const [playerId, playerData] of Object.entries(players_data)) {
    players_formatted[playerId] = {
      color: playerData.color
    };
  }

  if (pieces_old && pieces_old.length > 0 && ReplayLastTurn) {
    board_size += board_shrink;
    // Convert piece structure to format expected by place_pieces
    const pieces_old_formatted = pieces_old.map(p => ({
      ...p,
      owner: p.owner_player_id,
      pieceid: p.piece_id
    }));
    await place_pieces(pieces_old_formatted, players_formatted);
    console.log(`Loaded ${pieces_old.length} old pieces from server, will start physics shortly`);
    // wait 3 seconds, then start physics
    setTimeout(() => {
        pendingArrows.length = 0;
        physics.running = true;
    }, 3000);
    //once physics stops, clear the board and place the new pieces
    
    const pieces_formatted = pieces.map(p => ({
      ...p,
      owner: p.owner_player_id,
      pieceid: p.piece_id
    }));
    server_pieces = pieces_formatted;
    server_players = players_formatted;
    
    return;
  } 
  if (pieces && pieces.length > 0) {
    while (physics.running) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    // Convert piece structure to format expected by place_pieces
    const pieces_formatted = pieces.map(p => ({
      ...p,
      owner: p.owner_player_id,
      pieceid: p.piece_id
    }));
    place_pieces(pieces_formatted, players_formatted);
    console.log(`Loaded ${pieces.length} pieces from server`);
    return;
  } 
  defaultLoad();
}

// Place pieces into physics engine
// does not clear existing pieces, or arrows
async function place_pieces(pieces, players){
    physics.clearPieces();
  console.log("Placing pieces:", pieces, " with players:", players);

   pieces.forEach(p => {
      if (p.status && p.status === "out") {
        return; // skip pieces that are out
      }
      const ownerColor =
        players?.[p.owner]?.color || "#FFFF00"; // fallback if missing
      physics.addPiece(p.x, p.y, p.pieceid, PIECE_RADIUS, ownerColor);
      const body = physics.bodies[physics.bodies.length - 1].body;      
      const color = ownerColor;
      const d = velocityToArrow({ x: p.vx, y: p.vy });
      if(d.x != 0 || d.y != 0){
        const arrow = {
          body,
          dragStart: { x: p.x, y: p.y },
          dragEnd: { x: p.x + d.x, y: p.y + d.y },
          pieceid: p.pieceid,
          color
        };
        pendingArrows.push(arrow);
      }
      

      const piece = physics.bodies[physics.bodies.length - 1];
      if (piece && piece.body) {
        physics.applyVelocity(piece.body, p.vx, p.vy);
      }else{
        console.warn(`Piece with id ${p.id} not found in physics bodies.`);
      }
    });
}

fetchGameState(true);

function defaultLoad() {
  console.log("No pieces in game state. Insert default setup logic here.");

  let nextId = 1; // pieceid generator required by new engine

  COLORS.forEach((color, i) => {
    for (let j = 0; j < 4; j++) {
      let placed = false;
      const maxAttempts = 500;

      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const x = (Math.random() - 0.5) * (board_size - 2 * PIECE_RADIUS);
        const y = (Math.random() - 0.5) * (board_size - 2 * PIECE_RADIUS);

        // Collision check against existing bodies
        let tooClose = false;
        for (const entry of physics.bodies) {
          const pos = entry.body.getPosition();
          const dx = pos.x - x;
          const dy = pos.y - y;
          const dist = Math.hypot(dx, dy);
          if (dist < 2 * PIECE_RADIUS + 5) {
            tooClose = true;
            break;
          }
        }

        if (!tooClose) {
          const pieceid = nextId++;
          physics.addPiece(x, y, pieceid, PIECE_RADIUS, color);
          placed = true;
          break;
        }
      }

      if (!placed) {
        console.warn(`Could not place piece ${j + 1} for player ${i + 1} after ${maxAttempts} attempts`);
      }
    }
  });

  draw();
}





// Submit moves to server
async function submitMoves() {
  if (pendingArrows.length === 0) {
      console.log("No moves to submit.");
      return;
  }

  // Ensure we have a player id
  if (!playerId) {
    alert("No player_id found. Join the game first (player_id must be saved in localStorage).");
    return;
  }

  const moves = pendingArrows.map(a => {
    const { x, y } = arrowToVelocity({
      x: a.dragEnd.x - a.dragStart.x,
      y: a.dragEnd.y - a.dragStart.y
    });
    console.log(a);
    return {
      pieceid: a.pieceid,
      vx: x,
      vy: y
    };
  });



  try {
    const res = await fetch(`${API_BASE}/submit_turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        game_id: gameId,
        player_id: playerId,
        turn_number: currentTurn,
        actions: moves
      })
    });

    const data = await res.json();
    console.log("Move submitted:", data);
    console.log(physics.bodies);

    alert("Your moves have been submitted for this turn!");

    // Clear pending arrows
    pendingArrows.length = 0;

  } catch (err) {
    console.error("Error submitting moves:", err);
    alert("Failed to submit your moves. Try again.");
  }
};

// Drawing: set transform once, draw in world units
function draw() {
  ctx.resetTransform();
  ctx.clearRect(0, 0, WIDTH, HEIGHT);
  
  ctx.save();
  ctx.translate(CENTER_X, CENTER_Y);
  ctx.scale(displayScale, displayScale);
  
  // Draw board
  ctx.fillStyle = "white";
  ctx.fillRect(-board_size / 2, -board_size / 2, board_size, board_size);
  
  // Draw pieces
  for (const { body, color } of physics.bodies) {
      ctx.beginPath();
      
      ctx.arc(body.getPosition().x, body.getPosition().y, PIECE_RADIUS, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
  }
  
// Draw arrows
for (const arrow of pendingArrows) {
    const { x: x1, y: y1 } = arrow.dragStart;
    const { x: x2, y: y2 } = arrow.dragEnd;

    ctx.strokeStyle = arrow.color;
    ctx.lineWidth = 3;

    // Main line
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    // Arrowhead
    const headLength = 12;        // pixels
    const angle = Math.atan2(y2 - y1, x2 - x1);

    const leftAngle  = angle + Math.PI * 0.8;
    const rightAngle = angle - Math.PI * 0.8;

    const xLeft  = x2 + Math.cos(leftAngle)  * headLength;
    const yLeft  = y2 + Math.sin(leftAngle)  * headLength;
    const xRight = x2 + Math.cos(rightAngle) * headLength;
    const yRight = y2 + Math.sin(rightAngle) * headLength;

    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(xLeft, yLeft);
    ctx.lineTo(xRight, yRight);
    ctx.closePath();
    ctx.fillStyle = arrow.color;
    ctx.fill();
}
//sanity check results: a line from 0,0 to -396,0 (when board size is 800) goes from origin to pixels away from the left edge.
}

// --- Game loop ---
function loop() {
    if (physics.running) {
        physics.update();
        physics.stopIfStill();
        
        if (!physics.running) {
            board_size -= board_shrink;
            // reset canvas size
            resizeCanvas();
            if (server_pieces && server_players){
                physics.clearPieces();
                console.log("Placing new pieces:", server_pieces, server_players);
                place_pieces(server_pieces, server_players);
                server_pieces = null;
                server_players = null;            
            }
        }
        
        physics.removePiecesOutside(board_size / 2);


        
    }
    
    draw();
    requestAnimationFrame(loop);
}
loop();

// Helper to get current turn number (client-side view)
function getCurrentTurn() {
  return currentTurn;
}

// export shared symbols for ui_buttons.js and ui_leaderboard.js
export { canvas, pendingArrows, physics, gameId, playerId, PIECE_RADIUS, board_size, players, setPlayerId,
          getBoardSize, arrowToVelocity, clientToWorld, getPlayerIdFromCookie, submitMoves, fetchGameState, getCurrentTurn};


