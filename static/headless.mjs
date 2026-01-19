// headless.mjs
// Refactored to use the same Planck settings/behaviour as the new physics.js wrapper
// - timeStep = 1/480
// - defaultLinearDamping = 1
// - defaultAngularDamping = 2
// - defaultDensity = 0.5
// - defaultRestitution = 0.9
// - each "update" performs 8 world.step(...) calls (so effective dt per loop = 1/60)
// - robust NaN checks before/after stepping
// Input/Output interface unchanged (read JSON from stdin, write JSON to stdout).

import planck from "planck";

// Utility: read all stdin as JSON with size limit
const readStdin = async (maxBytes = 200_000) => {
  const chunks = [];
  let total = 0;
  for await (const chunk of process.stdin) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buf.length;
    if (total > maxBytes) throw new Error("stdin too large");
    chunks.push(buf);
  }
  return JSON.parse(Buffer.concat(chunks).toString());
};

const sanitizeInput = (data) => {
  if (typeof data !== "object" || data === null) throw new Error("input must be an object");
  const pieces = data.pieces;
  if (!Array.isArray(pieces)) throw new Error("pieces must be an array");

  const MAX_PIECES = 1000;
  if (pieces.length > MAX_PIECES) throw new Error("too many pieces");

  const MAX_COORD = 10000;
  const MAX_SPEED = 5000;
  const MIN_RADIUS = 1;
  const MAX_RADIUS = 1000;

  return {
    pieces: pieces.map((p, i) => {
      if (typeof p !== "object" || p === null || Array.isArray(p))
        throw new Error(`piece[${i}] invalid`);

      const out = Object.create(null);
      const pieceid = Number(p.pieceid || 0);
      const x = Number(p.x || 0);
      const y = Number(p.y || 0);
      const vx = Number(p.vx || 0);
      const vy = Number(p.vy || 0);
      const radius = Number(p.radius ?? 30);
      const color = typeof p.color === "string" ? p.color.slice(0, 64).replace(/[\x00-\x1F\x7F]/g, "") : "gray";
      const owner = typeof p.owner === "string" ? p.owner.slice(0, 64) : null;

      if (!Number.isFinite(x) || !Number.isFinite(y))
        throw new Error(`piece[${i}] coords invalid`);
      if (!Number.isFinite(vx) || !Number.isFinite(vy))
        throw new Error(`piece[${i}] velocity invalid`);
      if (!Number.isFinite(radius))
        throw new Error(`piece[${i}] radius invalid`);

      out.x = Math.max(-MAX_COORD, Math.min(MAX_COORD, x));
      out.y = Math.max(-MAX_COORD, Math.min(MAX_COORD, y));
      out.vx = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, vx));
      out.vy = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, vy));
      out.radius = Math.max(MIN_RADIUS, Math.min(MAX_RADIUS, Math.abs(radius)));
      out.color = color;
      out.owner = owner;
      out.pieceid = pieceid;

      return out;
    }),
    boardBefore: Number.isFinite(data.boardBefore) ? data.boardBefore : 800,
    boardAfter: Number.isFinite(data.boardAfter) ? data.boardAfter : 700,
  };
};

async function main() {
  const data = await readStdin(200_000);
  let { pieces, boardBefore = 800, boardAfter = 700 } = sanitizeInput(data);

  const pl = planck;

  // Create world with no gravity
  const world = new pl.World(pl.Vec2(0, 0));

  const bodies = [];

  // Physics.js wrapper defaults
  const timeStep = 1 / 480; // as in KnockoutPhysics
  const stepsPerUpdate = 8; // wrapper calls world.step(dt) 8 times per update
  const velocityIterations = 8;
  const positionIterations = 3;
  const defaultLinearDamping = 1;
  const defaultAngularDamping = 2;
  const defaultDensity = 0.5;
  const defaultRestitution = 0.9;

  // Create dynamic bodies matching new wrapper settings
  for (const p of pieces) {
    if (p.x == null || p.y == null){continue;} 


    const body = world.createBody({
      type: "dynamic",
      position: pl.Vec2(p.x, p.y),
      linearDamping: defaultLinearDamping,
      angularDamping: defaultAngularDamping,
      bullet: true,
    });

    body.createFixture(pl.Circle(p.radius), {
      density: defaultDensity,
      restitution: defaultRestitution,
      friction: 0.0,
    });

    body.setLinearVelocity(pl.Vec2(p.vx, p.vy));

    bodies.push({ body, owner: p.owner ?? "gray", pieceid: p.pieceid, radius: p.radius });
  }

  // Simulation parameters
  const velocityThreshold = 0.05; // matches KnockoutPhysics._stopThreshold
  const maxSteps = 3000;
  let steps = 0;

  const halfBefore = boardBefore / 2;
  const halfAfter = boardAfter / 2;

  // Helper: sanity check that all bodies have finite pos & vel
  const sanityCheck = () => {
    for (const { body } of bodies) {
      const p = body.getPosition();
      const v = body.getLinearVelocity();
      if (!Number.isFinite(p.x) || !Number.isFinite(p.y) || !Number.isFinite(v.x) || !Number.isFinite(v.y)) {
        return false;
      }
    }
    return true;
  };

  // Run simulation loop
  while (steps < maxSteps) {
    // Pre-step sanity check
    if (!sanityCheck()) {
      // abort on NaN
      break;
    }

    try {
      for (let i = 0; i < stepsPerUpdate; i++) {
        world.step(timeStep, velocityIterations, positionIterations);
      }
    } catch (err) {
      // step error: abort simulation
      break;
    }

    // Post-step sanity check
    if (!sanityCheck()) {
      break;
    }

    // Remove bodies that leave boardAfter region (boardAfter is full side length; we use half for bounds)
    for (let i = bodies.length - 1; i >= 0; i--) {
      const b = bodies[i].body;
      const pos = b.getPosition();
      if (Math.abs(pos.x) > halfBefore || Math.abs(pos.y) > halfBefore) {
        try { world.destroyBody(b); } catch (e) { /* ignore */ }
        bodies.splice(i, 1);
      }
    }

    steps++;

    // Check if all pieces are nearly still according to new threshold
    const allStill = bodies.every(({ body }) => {
      const v = body.getLinearVelocity();
      return Math.hypot(v.x, v.y) < velocityThreshold;
    });

    if (allStill) {
      // zero out tiny velocities and angular velocities (like KnockoutPhysics.stopIfStill)
      for (const { body } of bodies) {
        try {
          body.setLinearVelocity(pl.Vec2(0, 0));
          body.setAngularVelocity(0);
        } catch (e) { /* ignore */ }
      }
      break;
    }
  }

  // Prepare results (same shape as before)
  const survivors = bodies.map(({ body, owner, pieceid}) => {
    const pos = body.getPosition();
    const vel = body.getLinearVelocity();

    const outOfBounds =
      Math.abs(pos.x) > halfAfter || Math.abs(pos.y) > halfAfter;

    if (outOfBounds) {
      return { x: null, y: null, owner, pieceid, status: "out" };
    }

    return {
      x: +pos.x.toFixed(2),
      y: +pos.y.toFixed(2),
      vx: +vel.x.toFixed(2),
      vy: +vel.y.toFixed(2),
      owner,
      pieceid,
      status: "in",
    };
  });

  pieces = survivors;

  console.log(JSON.stringify({ pieces }));
}

main().catch(err => {
  console.error(JSON.stringify({ error: String(err) }));
  process.exit(1);
});
