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
const Vec3 = require('vec3');

const PORT          = parseInt(process.env.MC_BRIDGE_PORT || '18090');
const SIMULATOR_URL = process.env.SIMULATOR_URL || 'http://localhost:18080';
const DEFAULT_USER  = process.env.MC_USERNAME || 'Pepper';

const app = express();
app.use(express.json());

let bot = null;
let stateInterval = null;
let _lastHost = 'mcserver';
let _lastPort = 25565;
let _lastUser = DEFAULT_USER;

const net = require('net');

const RCON_HOST = process.env.MC_RCON_HOST || 'mcserver';
const RCON_PORT = parseInt(process.env.MC_RCON_PORT || '25575');
const RCON_PASS = process.env.MC_RCON_PASS || 'pepper123';

// Minimal RCON client — auth + one command
function rconCommand(cmd) {
  return new Promise((resolve, reject) => {
    const sock = net.connect(RCON_PORT, RCON_HOST);
    let buf = Buffer.alloc(0);
    let authed = false;
    let cmdId = 2;

    const pkt = (id, type, body) => {
      const b = Buffer.from(body + '\0\0', 'utf8');
      const p = Buffer.allocUnsafe(4 + 4 + 4 + b.length);
      p.writeInt32LE(8 + b.length, 0);
      p.writeInt32LE(id, 4);
      p.writeInt32LE(type, 8);
      b.copy(p, 12);
      return p;
    };

    sock.setTimeout(5000);
    sock.on('timeout', () => { sock.destroy(); reject(new Error('rcon timeout')); });
    sock.on('error', reject);

    sock.on('connect', () => sock.write(pkt(1, 3, RCON_PASS)));

    sock.on('data', chunk => {
      buf = Buffer.concat([buf, chunk]);
      while (buf.length >= 12) {
        const len = buf.readInt32LE(0) + 4;
        if (buf.length < len) break;
        const id = buf.readInt32LE(4);
        const body = buf.slice(12, len - 2).toString('utf8');
        buf = buf.slice(len);
        if (!authed) {
          if (id === -1) { sock.destroy(); return reject(new Error('rcon auth failed')); }
          authed = true;
          sock.write(pkt(cmdId, 2, cmd));
        } else {
          sock.destroy();
          resolve(body);
        }
      }
    });
  });
}

async function rconGive(player, item, count) {
  try {
    const result = await rconCommand(`give ${player} minecraft:${item} ${count}`);
    console.log(`[rcon] give ${player} ${item} ${count}: ${result}`);
  } catch (e) {
    console.error('[rcon] give failed:', e.message);
  }
}

// Mining loot table: what item a block actually drops
const MINE_DROPS = {
  stone:                'cobblestone',
  coal_ore:             'coal',
  deepslate_coal_ore:   'coal',
  iron_ore:             'raw_iron',
  deepslate_iron_ore:   'raw_iron',
  gold_ore:             'raw_gold',
  deepslate_gold_ore:   'raw_gold',
  diamond_ore:          'diamond',
  deepslate_diamond_ore:'diamond',
  redstone_ore:         'redstone',
  deepslate_redstone_ore:'redstone',
  lapis_ore:            'lapis_lazuli',
  deepslate_lapis_ore:  'lapis_lazuli',
  copper_ore:           'raw_copper',
  deepslate_copper_ore: 'raw_copper',
  gravel:               'gravel',
  sand:                 'sand',
};

// Rotating hotbar slot counter for creative-mode item grants (slots 36-44)
let _creativeMineSlot = 36;

// ── State snapshot ─────────────────────────────────────────────────────────

function nearbyEntities() {
  if (!bot || !bot.entity) return [];
  return Object.values(bot.entities)
    .filter(e => e !== bot.entity && e.position)
    .map(e => {
      const ep = e.position;
      const entry = {
        name: e.name || e.username || e.type || 'unknown',
        type: e.type,
        distance: Math.round(ep.distanceTo(bot.entity.position)),
      };
      // expose position for players so Pepper can navigate to them
      if (e.type === 'player') {
        entry.x = Math.round(ep.x);
        entry.y = Math.round(ep.y);
        entry.z = Math.round(ep.z);
      }
      return entry;
    })
    .filter(e => e.distance < 30)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 10);
}

function nearbyBlocks() {
  if (!bot || !bot.entity) return {};
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
  if (!bot || !bot.entity) return { connected: false };
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
    moves.canDig = false;   // off by default — mine endpoint enables it only for its own navigation
    b.pathfinder.setMovements(moves);
    stateInterval = setInterval(pushState, 5000);
    pushState();
    // Apply permanent invincibility to ALL players so items still drop naturally
    setTimeout(async () => {
      try {
        for (const effect of ['resistance', 'saturation', 'fire_resistance']) {
          await rconCommand(`effect give @a minecraft:${effect} 99999 255 true`);
        }
        console.log('[bot] invincibility effects applied to all players');
      } catch (e) {
        console.error('[bot] failed to apply effects:', e.message);
      }
    }, 2000);
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

  b.on('death', () => {
    console.log('[bot] died — respawning in 2s');
    setTimeout(() => { try { b.respawn(); } catch(e) { console.error('[bot] respawn failed:', e.message); } }, 2000);
  });

  b.on('error', err => {
    console.error('[bot] error:', err.message);
    // non-fatal errors — don't call onError so we don't kill the bot
  });

  b.on('end', () => {
    console.log('[bot] disconnected — waiting for manual rejoin');
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
  const { host = 'mcserver', port = 25565, username = DEFAULT_USER } = req.body;
  _lastHost = host; _lastPort = parseInt(port); _lastUser = username;
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

// Blocks that need a pickaxe to drop items in survival
const NEEDS_PICKAXE = new Set([
  'stone','cobblestone','granite','diorite','andesite','deepslate',
  'tuff','gravel','sandstone','coal_ore','iron_ore','gold_ore',
  'diamond_ore','redstone_ore','lapis_ore','copper_ore','netherrack',
  'deepslate_coal_ore','deepslate_iron_ore','deepslate_gold_ore',
  'deepslate_diamond_ore','deepslate_redstone_ore','deepslate_lapis_ore',
  'deepslate_copper_ore',
]);

app.post('/mine', async (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const { block_type } = req.body;
  const block = bot.findBlock({ matching: b => b.name === block_type, maxDistance: 32 });
  if (!block) return res.json({ error: `no ${block_type} found within 32 blocks` });

  // Warn early if a pickaxe is needed but not held
  if (NEEDS_PICKAXE.has(block_type)) {
    const pickaxe = bot.inventory.items().find(i => i.name.includes('pickaxe'));
    if (!pickaxe) {
      return res.json({ error: `need a pickaxe to mine ${block_type} — craft one first (wooden_pickaxe or stone_pickaxe)` });
    }
    await bot.equip(pickaxe, 'hand');
  }

  try {
    // Enable digging only for this mining operation so the pathfinder can reach buried blocks
    bot.pathfinder.movements.canDig = true;
    await bot.pathfinder.goto(new goals.GoalBlock(block.position.x, block.position.y, block.position.z));
    bot.pathfinder.movements.canDig = false;
    await bot.dig(block);
    const inv = bot.inventory.items().map(i => ({ name: i.name, count: i.count }));
    res.json({ ok: true, mined: block_type, at: block.position, inventory: inv });
  } catch (err) {
    bot.pathfinder.movements.canDig = false;
    res.json({ error: err.message });
  }
});

app.post('/place', async (req, res) => {
  if (!bot || !bot.entity) return res.json({ error: 'not connected' });
  const { block_type, x, y, z } = req.body;

  // In creative mode, findInventoryItem returns null — give the item directly
  let item = bot.inventory.findInventoryItem(bot.registry.itemsByName[block_type]?.id);
  if (!item) {
    if (bot.game?.gameMode !== 'creative') return res.json({ error: `${block_type} not in inventory` });
    // creative: equip by switching to the item via creative inventory
    try { await bot.creative.setInventorySlot(36, bot.registry.itemsByName[block_type] ? { type: bot.registry.itemsByName[block_type].id, count: 1, metadata: 0 } : null); } catch(_) {}
    item = bot.inventory.findInventoryItem(bot.registry.itemsByName[block_type]?.id);
    if (!item) return res.json({ error: `unknown block type: ${block_type}` });
  }

  // Walk close to the target first so placement is in range
  try {
    await bot.pathfinder.goto(new goals.GoalNear(x, y, z, 3));
  } catch(_) {}

  // Try placing on the block below; if air, scan downward for solid surface
  let surface = null;
  for (let dy = 0; dy >= -5; dy--) {
    const b = bot.blockAt(new Vec3(x, y + dy - 1, z));
    if (b && b.name !== 'air') { surface = { block: b, face: new Vec3(0, 1, 0), placeY: y + dy }; break; }
  }
  if (!surface) return res.json({ error: 'no solid surface found below target — try a lower Y' });

  try {
    await bot.equip(item, 'hand');
    await bot.placeBlock(surface.block, surface.face);
    res.json({ ok: true, placed: block_type, at: { x, y: surface.placeY, z } });
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

app.post('/craft', async (req, res) => {
  if (!bot) return res.json({ error: 'not connected' });
  const { item, count = 1 } = req.body;
  const itemData = bot.registry.itemsByName[item];
  if (!itemData) return res.json({ error: `unknown item: "${item}" — use Minecraft item IDs like oak_planks, torch, wooden_pickaxe` });

  // Try hand-crafting (no table needed) first
  let recipes = bot.recipesFor(itemData.id, null, 1, null);
  let craftingTable = null;

  if (!recipes.length) {
    craftingTable = bot.findBlock({
      matching: bot.registry.blocksByName['crafting_table']?.id,
      maxDistance: 64,
    });
    if (!craftingTable) {
      return res.json({ error: `no recipe for "${item}" without a crafting table — place one first with mc_place` });
    }
    recipes = bot.recipesFor(itemData.id, null, 1, craftingTable);
    if (!recipes.length) {
      return res.json({ error: `no recipe found for "${item}" — check you have the right materials` });
    }
  }

  try {
    if (craftingTable) {
      await bot.pathfinder.goto(new goals.GoalNear(
        craftingTable.position.x, craftingTable.position.y, craftingTable.position.z, 2
      ));
    }
    await bot.craft(recipes[0], count, craftingTable);
    const inv = bot.inventory.items().map(i => ({ name: i.name, count: i.count }));
    res.json({ ok: true, crafted: item, count, inventory: inv });
  } catch (err) {
    res.json({ error: err.message });
  }
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
