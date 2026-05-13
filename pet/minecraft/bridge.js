/**
 * Pepper Minecraft Bridge
 *
 * Runs on the host (Node.js). Exposes an HTTP API that the brain loop calls
 * to control a Mineflayer bot connected to a Minecraft Java server.
 * Also pushes live game state to the simulator every few seconds.
 *
 * Usage:
 *   cd minecraft && npm install && node bridge.js
 *
 * Environment variables:
 *   MC_BRIDGE_PORT   18090          HTTP API port
 *   SIMULATOR_URL    http://localhost:18080   Simulator base URL
 *   MC_USERNAME      Pepper         Bot username (offline-mode servers)
 */

const express  = require('express');
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');

const PORT          = parseInt(process.env.MC_BRIDGE_PORT || '18090');
const SIMULATOR_URL = process.env.SIMULATOR_URL || 'http://localhost:18080';
const DEFAULT_USER  = process.env.MC_USERNAME || 'Pepper';

const app = express();
app.use(express.json());

let bot = null;
let stateInterval = null;

// ── State snapshot ─────────────────────────────────────────────────────────

function nearbyEntities() {
  if (!bot) return [];
  return Object.values(bot.entities)
    .filter(e => e !== bot.entity)
    .map(e => ({
      name: e.name || e.username || e.type || 'unknown',
      type: e.type,
      distance: Math.round(e.position.distanceTo(bot.entity.position)),
    }))
    .filter(e => e.distance < 20)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 10);
}

function nearbyBlocks() {
  if (!bot) return {};
  const pos = bot.entity.position.floored();
  const counts = {};
  for (let dx = -6; dx <= 6; dx++)
    for (let dy = -3; dy <= 3; dy++)
      for (let dz = -6; dz <= 6; dz++) {
        const b = bot.blockAt(pos.offset(dx, dy, dz));
        if (b && b.name !== 'air') counts[b.name] = (counts[b.name] || 0) + 1;
      }
  return counts;
}

function snapshot() {
  if (!bot) return { connected: false };
  const p = bot.entity.position;
  return {
    connected:       true,
    username:        bot.username,
    position:        { x: Math.round(p.x), y: Math.round(p.y), z: Math.round(p.z) },
    health:          Math.round(bot.health ?? 0),
    food:            Math.round(bot.food ?? 0),
    game_mode:       bot.game?.gameMode ?? 'unknown',
    time_of_day:     bot.time?.timeOfDay ?? 0,
    nearby_entities: nearbyEntities(),
    nearby_blocks:   nearbyBlocks(),
    inventory:       bot.inventory.items().map(i => ({ name: i.name, count: i.count })),
  };
}

// ── Push state to simulator ────────────────────────────────────────────────

async function pushState() {
  try {
    await fetch(`${SIMULATOR_URL}/mc/state`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(snapshot()),
    });
  } catch { /* simulator may not be running */ }
}

// ── Bot lifecycle ──────────────────────────────────────────────────────────

function createBot(host, port, username, onReady, onError) {
  const b = mineflayer.createBot({ host, port: parseInt(port), username, hideErrors: true });
  b.loadPlugin(pathfinder);

  b.once('spawn', () => {
    const moves = new Movements(b);
    b.pathfinder.setMovements(moves);
    stateInterval = setInterval(pushState, 5000);
    pushState();
    onReady(b);
  });

  b.on('chat', (username, message) => {
    console.log(`[chat] <${username}> ${message}`);
    // forward in-game chat to simulator as transcript
    fetch(`${SIMULATOR_URL}/hardware/transcript`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ text: `[MC] <${username}> ${message}` }),
    }).catch(() => {});
  });

  b.on('death', () => console.log('[bot] died — respawning'));

  b.on('error', err => {
    console.error('[bot] error:', err.message);
    onError(err);
  });

  b.on('end', () => {
    console.log('[bot] disconnected');
    clearInterval(stateInterval);
    bot = null;
    fetch(`${SIMULATOR_URL}/mc/state`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ connected: false }),
    }).catch(() => {});
  });

  return b;
}

// ── HTTP API ───────────────────────────────────────────────────────────────

app.post('/join', (req, res) => {
  if (bot) return res.json({ error: 'already connected — call /leave first' });
  const { host = 'localhost', port = 25565, username = DEFAULT_USER } = req.body;
  console.log(`[bridge] connecting to ${host}:${port} as ${username}`);

  let responded = false;
  createBot(host, port, username,
    (b) => {
      bot = b;
      if (!responded) { responded = true; res.json({ ok: true, username: b.username, host, port }); }
    },
    (err) => {
      bot = null;
      if (!responded) { responded = true; res.json({ error: err.message }); }
    }
  );
});

app.post('/leave', (req, res) => {
  if (!bot) return res.json({ ok: true, message: 'not connected' });
  bot.quit('Pepper signing off');
  bot = null;
  clearInterval(stateInterval);
  res.json({ ok: true });
});

app.get('/state', (req, res) => res.json(snapshot()));

app.post('/chat', (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const text = String(req.body.text || '').slice(0, 256);
  bot.chat(text);
  res.json({ ok: true, text });
});

app.post('/move', async (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const { x, y, z } = req.body;
  try {
    await bot.pathfinder.goto(new goals.GoalNear(x, y, z, 2));
    const p = bot.entity.position;
    res.json({ ok: true, position: { x: Math.round(p.x), y: Math.round(p.y), z: Math.round(p.z) } });
  } catch (err) {
    res.json({ error: err.message });
  }
});

app.post('/mine', async (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const { block_type } = req.body;
  const block = bot.findBlock({ matching: b => b.name === block_type, maxDistance: 32 });
  if (!block) return res.json({ error: `no ${block_type} found within 32 blocks` });
  try {
    await bot.pathfinder.goto(new goals.GoalBlock(block.position.x, block.position.y, block.position.z));
    await bot.dig(block);
    res.json({ ok: true, mined: block_type, at: block.position });
  } catch (err) {
    res.json({ error: err.message });
  }
});

app.post('/place', async (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const { block_type, x, y, z } = req.body;
  const item = bot.inventory.findInventoryItem(bot.registry.itemsByName[block_type]?.id);
  if (!item) return res.json({ error: `${block_type} not in inventory` });
  const target = bot.blockAt(new bot.vec3(x, y - 1, z));
  if (!target) return res.json({ error: 'no surface to place on' });
  try {
    await bot.equip(item, 'hand');
    await bot.placeBlock(target, new bot.vec3(0, 1, 0));
    res.json({ ok: true, placed: block_type, at: { x, y, z } });
  } catch (err) {
    res.json({ error: err.message });
  }
});

app.post('/attack', (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const mobs = Object.values(bot.entities)
    .filter(e => e !== bot.entity && e.type === 'mob')
    .sort((a, b) => a.position.distanceTo(bot.entity.position) - b.position.distanceTo(bot.entity.position));
  if (!mobs.length) return res.json({ error: 'no mobs nearby' });
  const target = mobs[0];
  bot.attack(target);
  res.json({ ok: true, attacked: target.name, distance: Math.round(target.position.distanceTo(bot.entity.position)) });
});

app.listen(PORT, () => {
  console.log(`[bridge] Pepper Minecraft bridge listening on :${PORT}`);
  console.log(`[bridge] Simulator URL: ${SIMULATOR_URL}`);
  console.log('[bridge] POST /join  {host, port, username} — connect bot');
  console.log('[bridge] POST /leave                        — disconnect');
  console.log('[bridge] GET  /state                        — game state');
  console.log('[bridge] POST /chat  {text}                 — send chat');
  console.log('[bridge] POST /move  {x, y, z}             — pathfind');
  console.log('[bridge] POST /mine  {block_type}           — dig');
  console.log('[bridge] POST /attack                       — hit nearest mob');
});
