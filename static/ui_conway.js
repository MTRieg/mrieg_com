// AUTOPLAY / DEMO UI INPUTS
// No real user input. Generates random moves for all pieces and animates them.

console.log("ui_conway start");


  const ui = await import("./ui.js?background=true"); 
  // ui.canvas, ui.physics, ui.clientToWorld, etc.

  console.log("loaded conway");

  const { canvas, physics, clientToWorld, arrowToVelocity, board_size,
          PIECE_RADIUS, submitMoves, fetchGameState, pendingArrows} = ui;

  const BOARD_HALF_SIZE = board_size / 2;

  // ---------------------------------------------------------------------------
  // CONFIGURATION
  // ---------------------------------------------------------------------------

  // How long arrows stay visible before physics starts
  const ARROW_SHOW_TIME = 2000;

  // How strong the random pushes are (in world units)
  const RANDOM_FORCE_MIN = 50;
  const RANDOM_FORCE_MAX = 300;

  // If true, auto-submit to server instead of purely running local demos
  const AUTO_SUBMIT = false;

  const MAX_DRAG_DISTANCE = 600;

  // ---------------------------------------------------------------------------
  // RANDOM MOVE GENERATION
  // ---------------------------------------------------------------------------

  // Generate a random velocity vector within bounds
  function randomVector(minLen, maxLen) {
    const angle = Math.random() * Math.PI * 2;
    const len = minLen + Math.random() * (maxLen - minLen);
    return {
      x: Math.cos(angle) * len,
      y: Math.sin(angle) * len
    };
  }

  // Build random arrows for every piece
  function assignRandomMoves() {
    pendingArrows.length = 0;

    for (const { body, color, pieceid } of physics.bodies) {
      const pos = body.getPosition();

      // Pick random displacement for arrow
      let v = randomVector(RANDOM_FORCE_MIN, RANDOM_FORCE_MAX);
      
      
      // If pos + v is outside the board, try again, to discourage YOLOing
      const max = BOARD_HALF_SIZE + 100;
      let endX = pos.x + v.x;
      let endY = pos.y + v.y;

      while (
        (endX < -max || endX > max || endY < -max || endY > max)
      ) {
        v = randomVector(RANDOM_FORCE_MIN, RANDOM_FORCE_MAX);
        endX = pos.x + v.x;
        endY = pos.y + v.y;
      }

      const arrowLength = Math.hypot(v.x, v.y);

      // Cap at MAX_DRAG_DISTANCE if needed
      let dx = v.x;
      let dy = v.y;
      if (arrowLength > MAX_DRAG_DISTANCE) {
        const scale = MAX_DRAG_DISTANCE / arrowLength;
        dx *= scale;
        dy *= scale;
      }

      pendingArrows.push({
        body,
        pieceid,
        dragStart: { x: pos.x, y: pos.y },
        dragEnd:   { x: pos.x + dx, y: pos.y + dy },
        color
      });
    }

    console.log("Random moves assigned:", pendingArrows);
  }

  // Apply velocities to pieces
  function applyArrowsToPhysics() {
    for (const arrow of pendingArrows) {
      const vxvy = arrowToVelocity({
        x: arrow.dragEnd.x - arrow.dragStart.x,
        y: arrow.dragEnd.y - arrow.dragStart.y
      });
      physics.applyVelocity(arrow.body, vxvy.x, vxvy.y);
    }
  }

  function allPiecesSameColor() {
    if (physics.bodies.length === 0) return false;
    const first = physics.bodies[0].color;
    return physics.bodies.every(b => b.color === first);
  }

  async function animateMoves() {
    const oldPendingArrows = pendingArrows.map(a => ({
      body: a.body,
      pieceid: a.pieceid,
      color: a.color,
      dragStart: { ...a.dragStart },
      dragEnd:   { ...a.dragEnd }
    }));
    
    for(let i=0; i<=100; i++){
      pendingArrows.length = 0;
      for (const arrow of oldPendingArrows){
        const dx = arrow.dragEnd.x - arrow.dragStart.x;
        const dy = arrow.dragEnd.y - arrow.dragStart.y;
        pendingArrows.push({
          body: arrow.body,
          pieceid: arrow.pieceid,
          dragStart: { x: arrow.dragStart.x, y: arrow.dragStart.y },
          dragEnd:   { x: arrow.dragEnd.x + dx * i/100, y: arrow.dragEnd.y + dy * i/100 },
          color: arrow.color
        });
      }
      await new Promise(r => setTimeout(r, 1));
    }



  }


  // ---------------------------------------------------------------------------
  // MAIN LOOP: continuous auto-play cycle
  // ---------------------------------------------------------------------------

  async function autoplayCycle() {
    // Wait for board to load at least once
    while (physics.bodies.length === 0) {
      await new Promise(r => setTimeout(r, 200));
      console.log("waiting on pieces");
    }

    while (true) {
      // 1. Assign random moves to all pieces
      assignRandomMoves();

      await animateMoves();

      
      // 2. Allow arrows to show briefly
      await new Promise(r => setTimeout(r, ARROW_SHOW_TIME));

      // 3. Apply to physics
      applyArrowsToPhysics();
      physics.running = true;
      pendingArrows.length = 0;

      if (AUTO_SUBMIT) {
        submitMoves();
      }

      // 4. Wait for physics to finish
      while (physics.running) {
        await new Promise(r => setTimeout(r, 100));
      }

      // 5. STOP HERE if all pieces are the same color
      if (allPiecesSameColor()) {
        console.log("Autoplay halted: all pieces share the same color.");
        return;  // exits autoplayCycle
      }

      // Otherwise loop continues for next demo round
      pendingArrows.length = 0;
    }
  }

  // Start autoplay
  autoplayCycle();

      


