// physics.js
// Fixed, robust Planck.js physics wrapper for knockout-style pieces.
// - Uses Box2D/Planck linearDamping for stable, direction-preserving slowdown.
// - Removes manual per-step velocity surgery.
// - Defensive NaN checking and safe velocity application.
// - Provides id-based piece tracking and helper to remove out-of-bounds bodies.
// - Fires optional onStopped callbacks when simulation halts.

export class KnockoutPhysics {
  constructor({
    timeStep = 1 / 480,
    velocityIterations = 8,
    positionIterations = 3,
    defaultLinearDamping = 1,
    defaultAngularDamping = 2,
    defaultDensity = 0.5,
    defaultRestitution = 0.9
  } = {}) {
    if (!window.planck) throw new Error("planck is required on window (include planck.min.js)");
    this.pl = window.planck;
    this.world = new this.pl.World(this.pl.Vec2(0, 0));

    this.timeStep = timeStep;
    this.velocityIterations = velocityIterations;
    this.positionIterations = positionIterations;

    this.bodies = []; // entries: { pieceid, body, color, radius }
    this._idCounter = 1;
    this.running = false;

    // Defaults (tweak these if you want different feel)
    this.defaultLinearDamping = defaultLinearDamping;
    this.defaultAngularDamping = defaultAngularDamping;
    this.defaultDensity = defaultDensity;
    this.defaultRestitution = defaultRestitution;

    // Stopped detection
    this._stopThreshold = 0.2; // world units / second
    this.onStoppedCallbacks = [];
  }

  // Register callback called when simulation stops (all pieces below threshold)
  onStopped(cb) {
    if (typeof cb === "function") this.onStoppedCallbacks.push(cb);
  }

  // Destroy all bodies and clear list
  clearPieces() {
    for (const entry of this.bodies) {
      try { this.world.destroyBody(entry.body); } catch (e) { /* ignore */ }
    }
    this.bodies = [];
  }

  // Add a piece; returns assigned id
  addPiece(x, y, pieceid, radius = 30, color = "red", opts = {}) {
    const pl = this.pl;

    if (!isFinite(x) || !isFinite(y)) {
      console.warn("Skipping piece with invalid coordinates", { x, y });
      return null;
    }
    if (!isFinite(radius) || radius <= 0) {
      console.warn("Skipping piece with invalid radius", { radius });
      return null;
    }
    
    
    let pos = {x: 0,y: 0};

    try{
        pos = {x: x, y: y};     
    }catch(e){
        console.log("failed to load velocity", x, y, pos); 
        //throw "VelocityException";   
    }
    
    const body = this.world.createBody({
      type: "dynamic",
      position: pos,
      bullet: !!opts.bullet || false,
      linearDamping: typeof opts.linearDamping === "number" ? opts.linearDamping : this.defaultLinearDamping,
      angularDamping: typeof opts.angularDamping === "number" ? opts.angularDamping : this.defaultAngularDamping
    });

    body.createFixture(pl.Circle(radius), {
      density: typeof opts.density === "number" ? opts.density : this.defaultDensity,
      restitution: typeof opts.restitution === "number" ? opts.restitution : this.defaultRestitution,
      friction: typeof opts.friction === "number" ? opts.friction : 0
    });

    this.bodies.push({ pieceid, body, color, radius });
    return pieceid;
  }

  // Apply linear velocity. Accepts either a Planck Body or a piece id.
  applyVelocity(bodyOrId, vx, vy) {
    let body = null;
    if (!isFinite(vx) || !isFinite(vy)) {
      console.warn("applyVelocity called with non-finite vx/vy", { vx, vy });
      return false;
    }

    if (typeof bodyOrId === "number") {
      const entry = this.bodies.find(e => e.pieceid === bodyOrId);
      if (!entry) {
        console.warn("applyVelocity: unknown id", bodyOrId);
        return false;
      }
      body = entry.body;
    } else if (bodyOrId && typeof bodyOrId.setLinearVelocity === "function") {
      body = bodyOrId;
    } else {
      console.warn("applyVelocity: invalid bodyOrId:", bodyOrId);
      return false;
    }

    // Final safety guard
    if (!isFinite(vx) || !isFinite(vy)) {
      body.setLinearVelocity(this.pl.Vec2(0, 0));
      return false;
    }
    body.setLinearVelocity(this.pl.Vec2(vx, vy));
    return true;
  }

  // Remove and destroy pieces that are outside the provided square board bounds
  // boardHalfSize is half the side length in world units
  removePiecesOutside(boardHalfSize = null) {
    if (boardHalfSize == null) return;
    const toRemove = [];
    for (const entry of this.bodies) {
      const p = entry.body.getPosition();
      if (
        p.x < -boardHalfSize || p.x > boardHalfSize ||
        p.y < -boardHalfSize || p.y > boardHalfSize
      ) {
        toRemove.push(entry.pieceid);
      }
    }
    if (toRemove.length === 0) return;
    this.bodies = this.bodies.filter(entry => {
      if (toRemove.includes(entry.pieceid)) {
        try { this.world.destroyBody(entry.body); } catch (e) { /* ignore */ }
        return false;
      }
      return true;
    });
  }

  // Single-step update: steps the world. No manual velocity surgery here.
  update() {
    if (!this.running) return;

    const dt = this.timeStep;

    // Pre-step sanity check
    for (const entry of this.bodies) {
      const body = entry.body;
      const pos = body.getPosition();
      const vel = body.getLinearVelocity();
      if (!isFinite(pos.x) || !isFinite(pos.y) || !isFinite(vel.x) || !isFinite(vel.y)) {
        console.error("NaN detected in body BEFORE step()", { pieceid: entry.pieceid, pos, vel, entry });
        this.running = false;
        return;
      }
    }

    // Step the world (Box2D handles damping and collisions)
    try {
      for(let i=0; i<8; i++){
        this.world.step(dt, this.velocityIterations, this.positionIterations);
      }
      
    } catch (err) {
      console.error("world.step error", err);
      this.running = false;
      return;
    }

    // Post-step sanity check
    for (const entry of this.bodies) {
      const body = entry.body;
      const pos = body.getPosition();
      const vel = body.getLinearVelocity();
      if (!isFinite(pos.x) || !isFinite(pos.y) || !isFinite(vel.x) || !isFinite(vel.y)) {
        console.error("NaN detected in body AFTER step()", { pieceid: entry.pieceid, pos, vel, entry });
        this.running = false;
        return;
      }
    }
  }

  // Stop detection: if all bodies are below threshold, stop simulation and notify callbacks
  stopIfStill() {
    if (this.bodies.length === 0) {
      this.running = false;
      return;
    }

    
    const allStill = this.bodies.every(({ body }) => {
      const v = body.getLinearVelocity();
      const mag = Math.hypot(v.x, v.y);
      return mag < this._stopThreshold;
    });

    if (allStill && this.running) {
      this.running = false;
      // zero out tiny velocities and angular velocities to avoid jitter
      for (const { body } of this.bodies) {
        try {
          body.setLinearVelocity(this.pl.Vec2(0, 0));
          body.setAngularVelocity(0);
        } catch (e) { /* ignore */ }
      }
      // call callbacks
      for (const cb of this.onStoppedCallbacks) {
        try { cb(); } catch (e) { console.error("onStopped callback error", e); }
      }
    }
  }

  // Helper: get snapshot of bodies (positions/velocities) for debug or rendering
  getBodiesSnapshot() {
    return this.bodies.map(({ pieceid, body, color, radius }) => {
      const p = body.getPosition();
      const v = body.getLinearVelocity();
      return { pieceid, x: p.x, y: p.y, vx: v.x, vy: v.y, color, radius };
    });
  }
}
