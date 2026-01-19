

import {
  canvas,
  physics,
  pendingArrows,
  clientToWorld,
  arrowToVelocity,
  PIECE_RADIUS,
  submitMoves
} from "./ui.js";

const MAX_DRAG_DISTANCE = 600;

// --- Interaction state ---
let draggingPiece = null;
let dragStart = null;
let dragEnd = null;

// --- Mouse events ---
canvas.addEventListener("mousedown", e => {
  if (physics.running) return;
  const { x: mx, y: my } = clientToWorld(e.clientX, e.clientY);

  for (const { body, color, pieceid} of physics.bodies) {
    const dx = body.getPosition().x - mx;
    const dy = body.getPosition().y - my;
    if (Math.hypot(dx, dy) < PIECE_RADIUS) {

      console.log("Started dragging piece", pieceid);
      console.log(pendingArrows);
      console.log(physics.bodies);
        
      // If an arrow already exists for this piece, remove it (toggle-off behavior)
      const existingIndex = pendingArrows.findIndex(a => a.pieceid === pieceid);
      if (existingIndex !== -1) {
        pendingArrows.splice(existingIndex, 1);
        draggingPiece = null;
      }
        

      // Start a new arrow for this piece
      const arrow = {
        body,
        pieceid: pieceid,
        dragStart: { x: body.getPosition().x, y: body.getPosition().y },
        dragEnd: { x: body.getPosition().x, y: body.getPosition().y },
        color
      };

      pendingArrows.push(arrow);
      draggingPiece = arrow; // current active drag
      break;
    }
  }
});

canvas.addEventListener("mousemove", e => {
  if (!draggingPiece || physics.running) return;
  const { x: mx, y: my } = clientToWorld(e.clientX, e.clientY);

  let dx = mx - draggingPiece.dragStart.x;
  let dy = my - draggingPiece.dragStart.y;

  // Clamp to max drag distance
  const len = Math.hypot(dx, dy);
  if (len > MAX_DRAG_DISTANCE) {
    const scale = MAX_DRAG_DISTANCE / len;
    dx *= scale;
    dy *= scale;
  }

  draggingPiece.dragEnd = {
    x: draggingPiece.dragStart.x + dx,
    y: draggingPiece.dragStart.y + dy
  };
});

canvas.addEventListener("mouseup", e => {
  if (!draggingPiece || physics.running) return;

  const { x: vx, y: vy } = arrowToVelocity({
    x: draggingPiece.dragEnd.x - draggingPiece.dragStart.x,
    y: draggingPiece.dragEnd.y - draggingPiece.dragStart.y
  });
  
  


  physics.applyVelocity(draggingPiece.body, vx, vy);
  console.log(physics.bodies);

  // Keep arrow on screen until simulation starts
  draggingPiece = null;
  console.log(pendingArrows);
});

// Touch event handlers
canvas.addEventListener("touchstart", e => {
    e.preventDefault(); // Prevent scrolling
    if (physics.running) return;
    
    const touch = e.touches[0];
    const { x: mx, y: my } = clientToWorld(touch.clientX, touch.clientY);
    
    // Use same logic as mousedown
    for (const { body, color, pieceid } of physics.bodies) {
        const dx = body.getPosition().x - mx;
        const dy = body.getPosition().y - my;
        if (Math.hypot(dx, dy) < PIECE_RADIUS) {
            const existingIndex = pendingArrows.findIndex(a => a.pieceid === pieceid);
            if (existingIndex !== -1) {
                pendingArrows.splice(existingIndex, 1);
                draggingPiece = null;
            }

            const arrow = {
                body,
                pieceid,
                dragStart: { x: body.getPosition().x, y: body.getPosition().y },
                dragEnd: { x: body.getPosition().x, y: body.getPosition().y },
                color
            };

            pendingArrows.push(arrow);
            draggingPiece = arrow;
            break;
        }
    }
}, { passive: false });

canvas.addEventListener("touchmove", e => {
    e.preventDefault();
    if (!draggingPiece || physics.running) return;
    
    const touch = e.touches[0];
    const { x: mx, y: my } = clientToWorld(touch.clientX, touch.clientY);
    
    let dx = mx - draggingPiece.dragStart.x;
    let dy = my - draggingPiece.dragStart.y;
    
    const len = Math.hypot(dx, dy);
    if (len > MAX_DRAG_DISTANCE) {
        const scale = MAX_DRAG_DISTANCE / len;
        dx *= scale;
        dy *= scale;
    }
    
    draggingPiece.dragEnd = {
        x: draggingPiece.dragStart.x + dx,
        y: draggingPiece.dragStart.y + dy
    };
}, { passive: false });

canvas.addEventListener("touchend", e => {
  e.preventDefault();
  if (!draggingPiece || physics.running) return;

  const { x: vx, y: vy } = arrowToVelocity({
    x: draggingPiece.dragEnd.x - draggingPiece.dragStart.x,
    y: draggingPiece.dragEnd.y - draggingPiece.dragStart.y
  });

  physics.applyVelocity(draggingPiece.body, vx, vy);
  draggingPiece = null;
}, { passive: false });


// --- Start physics on Enter ---
document.addEventListener("keydown", async e => {
  if (e.key === "Enter") {
    physics.running = true;
    pendingArrows.length = 0; // clear all arrows
  }

  // Submit to server when pressing "s"
  if (e.key.toLowerCase() === "s") {
    submitMoves();
  }
  if (e.key === "p"){
    physics.running=false;
  }

});
