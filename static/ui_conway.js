// AUTOPLAY / DEMO UI INPUTS
// No real user input. Generates random moves for all pieces and animates them.

console.log("ui_conway start");



    import { canvas, physics, clientToWorld, arrowToVelocity, getBoardSize,
      PIECE_RADIUS, submitMoves, fetchGameState, pendingArrows} from "./ui.js?background=true";
  // ui.canvas, ui.physics, ui.clientToWorld, etc.

  console.log("loaded conway");

  let board_half_size = getBoardSize() / 2;

  // ---------------------------------------------------------------------------
  // CONFIGURATION
  // ---------------------------------------------------------------------------

  // How long arrows stay visible before physics starts
  const ARROW_SHOW_TIME = 2000;

  // How strong the random pushes are (in world units)
  const RANDOM_FORCE_MIN = 50;
  const RANDOM_FORCE_MAX = 500;

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
    board_half_size = getBoardSize() / 2;//in case board size changed

    for (const { body, color, pieceid } of physics.bodies) {
      const pos = body.getPosition();
      // Pick random displacement for arrow
      let v = randomVector(RANDOM_FORCE_MIN, RANDOM_FORCE_MAX);
      
      
      // If pos + v is outside the board, try again, to discourage YOLOing
      const max = board_half_size + 100; //extra 100 so that they might actually go off-board
      const board_size = getBoardSize();
      let endX = pos.x + v.x;
      let endY = pos.y + v.y;

      while (
        ((endX < -max) || (endX > max) || (endY < -max) || (endY > max) 
          || (endX + endY < -board_size) || (endX + endY > board_size)
          || (endX - endY < -board_size) || (endX - endY > board_size))
        //the last 4 checks are because, for a simulation, there's practically no reason to aim that far into the corner. 
      ) {
        v = randomVector(RANDOM_FORCE_MIN, RANDOM_FORCE_MAX);
        endX = pos.x + v.x;
        endY = pos.y + v.y;
      }



      pendingArrows.push({
        body,
        pieceid,
        dragStart: { x: pos.x, y: pos.y },
        dragEnd:   { x: endX, y: endY},
        color
      });
    }
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
    if (physics.bodies.length === 0) return true; //if there are no pieces, then all 0 pieces are the same color
    const first = physics.bodies[0].color;
    return physics.bodies.every(b => b.color === first);
  }

  async function animateMoves(colorDisplayed = null) { //if colorDisplayed is set, only animate arrows of that color
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
        if (colorDisplayed == null || arrow.color === colorDisplayed){
          const dx = arrow.dragEnd.x - arrow.dragStart.x;
          const dy = arrow.dragEnd.y - arrow.dragStart.y;
          pendingArrows.push({
            body: arrow.body,
            pieceid: arrow.pieceid,
            dragStart: { x: arrow.dragStart.x, y: arrow.dragStart.y },
            dragEnd:   { x: arrow.dragStart.x + dx * i/100, y: arrow.dragStart.y + dy * i/100 },
            color: arrow.color
          });
        }
        
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

    let possibleColors = new Set(physics.bodies.map(b => b.color));
    let displayColor = possibleColors.size > 0 ? [...possibleColors][Math.floor(Math.random() * possibleColors.size)] : null;
    //pick a random color to be "your color" for this demo
    //I originally had this as always "red", but that might make people assume red pieces are always theirs

    while (true) {
      // 1. Assign random moves to all pieces
      assignRandomMoves();

      
      //only do the next line if there are pieces of the special color to display:
      if(physics.bodies.some(b => b.color === displayColor)){
        let oldPendingArrows = pendingArrows.map(a => ({...a})); //deep copy

        await animateMoves(displayColor); //show special color arrows first
        //to simulate one player making their moves before they see everyone else's moves
        //color choice is arbitrary here

        await new Promise(r => setTimeout(r, ARROW_SHOW_TIME));

        pendingArrows.length = 0;
        for (const arrow of oldPendingArrows) {
          pendingArrows.push({...arrow});
        }
      }else{
        console.log("no red pieces to display first");
      }
        
      
      

      await animateMoves(null);

      
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

      


