// ── Constants ──────────────────────────────────────────────────────────────

const ZORK_DIRECTIVE =
  'Start playing Zork I using the zork() tool with command="start". ' +
  'Play one move per tick. Before each move speak a short narration of what you are doing or thinking.';

const ACTIVITY_COLORS = {
  idle: '#555', thinking: '#79c0ff', received: '#ffd33d',
  browsing: '#56d364', talking: '#56d364', moving: '#f5a623',
};

const DIRECTION_MAP = {
  'go north':'north','go south':'south','go east':'east','go west':'west',
  'go up':'up','go down':'down','go ne':'northeast','go nw':'northwest',
  'go se':'southeast','go sw':'southwest',
  'n':'north','s':'south','e':'east','w':'west','u':'up','d':'down',
  'north':'north','south':'south','east':'east','west':'west','up':'up','down':'down',
  'ne':'northeast','nw':'northwest','se':'southeast','sw':'southwest',
  'northeast':'northeast','northwest':'northwest','southeast':'southeast','southwest':'southwest',
  'climb':'up', 'ascend':'up', 'descend':'down',
};

const DIR_OFFSETS = {
  north:{x:0,y:-1}, south:{x:0,y:1}, east:{x:1,y:0}, west:{x:-1,y:0},
  up:{x:1,y:-1}, down:{x:-1,y:1},
  northeast:{x:1,y:-1}, northwest:{x:-1,y:-1},
  southeast:{x:1,y:1}, southwest:{x:-1,y:1},
};

const REVERSE_DIR = {
  north:'south', south:'north', east:'west', west:'east',
  up:'down', down:'up',
  northeast:'southwest', southwest:'northeast',
  northwest:'southeast', southeast:'northwest',
};

const ROOM_ICONS = {
  house:'🏠', kitchen:'🍳', living:'🛋️', attic:'📦', cellar:'🏚️',
  forest:'🌲', clearing:'🌿', path:'🌲', canyon:'⛰️',
  cave:'🕳️', cavern:'🕳️', river:'🌊', dam:'🏗️',
  shaft:'⬇️', maze:'🌀', grating:'🔒', gallery:'🖼️',
  garden:'🌸', studio:'🎨', shore:'🏖️', beach:'🏖️',
  tomb:'⚰️', altar:'🕍', trophy:'🏆', vault:'🏛️',
};

const OBJECT_ICONS = {
  mailbox:'📬', lamp:'🔦', lantern:'🔦', torch:'🔦',
  sword:'⚔️', knife:'🔪', leaflet:'📄', letter:'📄', note:'📄',
  key:'🗝️', trophy:'🏆', rug:'🟫', carpet:'🟫',
  painting:'🖼️', rope:'🪢', bottle:'🍶', garlic:'🧄',
  egg:'🥚', map:'🗺️', book:'📖', scroll:'📜',
  coin:'🪙', gold:'🪙', diamond:'💎', ruby:'💎', gem:'💎',
  ticket:'🎫', bag:'👜', sack:'👜', pot:'🫙', jar:'🫙',
};

const CELL_W = 150, CELL_H = 110;  // grid cell size in SVG units
const BOX_W = 120, BOX_H = 70;     // room box size

// ── Zork map state ──────────────────────────────────────────────────────────

const zorkMap = {
  rooms: {},    // name → {gridX, gridY, objects: Set(), exits: {dir: name}, visited: int}
  current: null,
  lastDir: null,
};

function getRoomIcon(name) {
  const l = name.toLowerCase();
  for (const [k, v] of Object.entries(ROOM_ICONS)) if (l.includes(k)) return v;
  return '📍';
}

function getObjectIcon(name) {
  const l = name.toLowerCase();
  for (const [k, v] of Object.entries(OBJECT_ICONS)) if (l.includes(k)) return v;
  return '✨';
}

function isRoomName(line) {
  return line.length >= 3 && line.length <= 52 &&
    /^[A-Z]/.test(line) &&
    !/^(You|There|Your|This|It|The |A |An |I |Here|Wait|That|OK|Done|Taken|Dropped|Opened|Closed|Saved|Restored|Score)/.test(line) &&
    !line.includes(':') && !line.endsWith('.') && !line.endsWith('!') &&
    !/^\d/.test(line);
}

function extractObject(line) {
  const pats = [
    /There (?:is|are) (?:a|an|the|some) (.+?) here/i,
    /You (?:can see|notice|spot) (?:a|an|the) (.+?) here/i,
    /(?:A|An) (.+?) (?:is|lies|sits|rests) here/i,
    /(?:A|An) (.+?) is lying here/i,
  ];
  for (const p of pats) {
    const m = line.match(p);
    if (m) {
      let obj = m[1].replace(/\s*\(.*?\)/g, '').replace(/\s*,.*$/, '').trim();
      if (obj.length > 0 && obj.length < 35) return obj;
    }
  }
  return null;
}

function parseZorkOutput(raw) {
  const lines = raw.split('\n').map(l => l.trim());
  if (!lines.length) return;

  // Parse command from first line (">cmd")
  const cmdLine = lines[0].startsWith('>') ? lines[0].slice(1).toLowerCase().trim() : '';
  const direction = DIRECTION_MAP[cmdLine] || null;

  // Filter out meta lines
  const outputLines = lines.slice(1).filter(l => l && !l.startsWith('score:'));

  // Detect room name: first line that looks like a title
  let roomName = null;
  for (const line of outputLines) {
    if (isRoomName(line)) { roomName = line; break; }
  }

  if (!roomName) return;

  // Calculate grid position
  let gridX = 0, gridY = 0;
  const prev = zorkMap.current ? zorkMap.rooms[zorkMap.current] : null;

  if (prev && direction) {
    const off = DIR_OFFSETS[direction] || {x:0, y:0};
    gridX = prev.gridX + off.x;
    gridY = prev.gridY + off.y;
    // Record exit from previous room
    prev.exits[direction] = roomName;
    // Record reverse exit in new room (set below)
  } else if (Object.keys(zorkMap.rooms).length === 0) {
    gridX = 0; gridY = 0; // start room
  } else if (!zorkMap.rooms[roomName] && prev) {
    // Non-directional entry (examine, open, etc.) — stay at same position
    gridX = prev.gridX; gridY = prev.gridY;
  }

  if (!zorkMap.rooms[roomName]) {
    zorkMap.rooms[roomName] = { gridX, gridY, objects: new Set(), exits: {}, visited: 0 };
    // Record reverse exit
    if (direction && zorkMap.current) {
      const rev = REVERSE_DIR[direction];
      if (rev) zorkMap.rooms[roomName].exits[rev] = zorkMap.current;
    }
  }

  const room = zorkMap.rooms[roomName];
  room.visited++;

  // Extract objects from description
  for (const line of outputLines) {
    const obj = extractObject(line);
    if (obj) room.objects.add(obj);
  }

  zorkMap.current = roomName;
  drawMap();
  updateZorkHUD();
}

// ── SVG map drawing ────────────────────────────────────────────────────────

const mapCanvas = document.getElementById('map-canvas');
// Replace canvas with SVG
const mapSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
mapSvg.setAttribute('width', '100%');
mapSvg.style.display = 'block';
mapSvg.style.background = '#060e06';
mapSvg.style.border = '1px solid #1a3a1a';
mapSvg.style.borderRadius = '6px';
mapSvg.style.minHeight = '380px';
mapCanvas.replaceWith(mapSvg);

// SVG defs (glow filter)
mapSvg.innerHTML = `
<defs>
  <filter id="glow">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="glow-strong">
    <feGaussianBlur stdDeviation="5" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#1a5a1a"/>
  </marker>
</defs>
<g id="connections"></g>
<g id="rooms"></g>
<text id="map-empty" x="50%" y="50%" text-anchor="middle"
      font-family="Courier New" font-size="13" fill="#1a4a1a"
      dominant-baseline="middle">
  Press ▶ Play Zork to start Pepper's adventure
</text>`;

function svgPos(gridX, gridY) {
  return {
    x: gridX * CELL_W + CELL_W / 2 - BOX_W / 2,
    y: gridY * CELL_H + CELL_H / 2 - BOX_H / 2,
  };
}

function drawMap() {
  const rooms = Object.entries(zorkMap.rooms);
  if (!rooms.length) return;

  // Remove placeholder
  const empty = mapSvg.getElementById('map-empty');
  if (empty) empty.remove();

  // Update viewBox to fit all rooms + padding
  const allX = rooms.map(([,r]) => r.gridX);
  const allY = rooms.map(([,r]) => r.gridY);
  const minX = Math.min(...allX), maxX = Math.max(...allX);
  const minY = Math.min(...allY), maxY = Math.max(...allY);
  const pad = 1.2;
  const vx = (minX - pad) * CELL_W;
  const vy = (minY - pad) * CELL_H;
  const vw = (maxX - minX + pad * 2 + 1) * CELL_W;
  const vh = (maxY - minY + pad * 2 + 1) * CELL_H;
  mapSvg.setAttribute('viewBox', `${vx} ${vy} ${vw} ${vh}`);

  // Draw connections
  const connG = mapSvg.getElementById('connections');
  connG.innerHTML = '';
  const drawn = new Set();
  for (const [name, room] of rooms) {
    const p1 = svgPos(room.gridX, room.gridY);
    const cx1 = p1.x + BOX_W / 2, cy1 = p1.y + BOX_H / 2;
    for (const [dir, target] of Object.entries(room.exits)) {
      const t = zorkMap.rooms[target];
      if (!t) continue;
      const edgeKey = [name, target].sort().join('|');
      if (drawn.has(edgeKey)) continue;
      drawn.add(edgeKey);
      const p2 = svgPos(t.gridX, t.gridY);
      const cx2 = p2.x + BOX_W / 2, cy2 = p2.y + BOX_H / 2;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', cx1); line.setAttribute('y1', cy1);
      line.setAttribute('x2', cx2); line.setAttribute('y2', cy2);
      line.setAttribute('stroke', '#1a5a1a');
      line.setAttribute('stroke-width', '2');
      connG.appendChild(line);
    }
  }

  // Draw rooms
  const roomG = mapSvg.getElementById('rooms');
  roomG.innerHTML = '';
  for (const [name, room] of rooms) {
    const { x, y } = svgPos(room.gridX, room.gridY);
    const isCurrent = name === zorkMap.current;
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', `translate(${x},${y})`);

    // Room box
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', BOX_W);
    rect.setAttribute('height', BOX_H);
    rect.setAttribute('rx', '8');
    rect.setAttribute('fill', isCurrent ? '#0d2e0d' : '#0a180a');
    rect.setAttribute('stroke', isCurrent ? '#56ff90' : '#1a5a1a');
    rect.setAttribute('stroke-width', isCurrent ? '2.5' : '1.5');
    if (isCurrent) rect.setAttribute('filter', 'url(#glow)');
    g.appendChild(rect);

    // Room icon
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    icon.setAttribute('x', BOX_W / 2);
    icon.setAttribute('y', '22');
    icon.setAttribute('text-anchor', 'middle');
    icon.setAttribute('font-size', '18');
    icon.textContent = getRoomIcon(name);
    g.appendChild(icon);

    // Room name (word-wrapped into up to 2 lines)
    const words = name.split(' ');
    const mid = Math.ceil(words.length / 2);
    const line1 = words.slice(0, mid).join(' ');
    const line2 = words.slice(mid).join(' ');
    const addNameLine = (text, dy) => {
      const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      t.setAttribute('x', BOX_W / 2);
      t.setAttribute('y', dy);
      t.setAttribute('text-anchor', 'middle');
      t.setAttribute('font-family', 'Courier New');
      t.setAttribute('font-size', '9');
      t.setAttribute('font-weight', 'bold');
      t.setAttribute('fill', isCurrent ? '#56ff90' : '#00cc00');
      t.textContent = text;
      g.appendChild(t);
    };
    if (line2) {
      addNameLine(line1, 38);
      addNameLine(line2, 48);
    } else {
      addNameLine(line1, 44);
    }

    // Objects row (emoji icons)
    if (room.objects.size > 0) {
      const objStr = [...room.objects].slice(0, 4).map(getObjectIcon).join(' ');
      const ot = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      ot.setAttribute('x', BOX_W / 2);
      ot.setAttribute('y', BOX_H - 8);
      ot.setAttribute('text-anchor', 'middle');
      ot.setAttribute('font-size', '11');
      ot.textContent = objStr;
      g.appendChild(ot);
    }

    // Pepper dot on current room
    if (isCurrent) {
      const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', BOX_W - 10);
      dot.setAttribute('cy', '10');
      dot.setAttribute('r', '5');
      dot.setAttribute('fill', '#ff6b6b');
      dot.setAttribute('filter', 'url(#glow-strong)');
      g.appendChild(dot);
    }

    roomG.appendChild(g);
  }

  // Update stats
  document.getElementById('map-stats').textContent =
    `${rooms.length} room${rooms.length !== 1 ? 's' : ''} discovered · current: ${zorkMap.current || '—'}`;
}

function updateZorkHUD() {
  const hud = document.getElementById('zork-hud');
  hud.style.display = 'flex';
  document.getElementById('zh-room').textContent = zorkMap.current || '—';
  document.getElementById('zh-rooms').textContent = Object.keys(zorkMap.rooms).length;
}

// ── Zork text log ──────────────────────────────────────────────────────────

const zorkLog = document.getElementById('zork-log');

function addZorkOutput(raw) {
  const lines = raw.split('\n');
  // Clear placeholder on first output
  if (zorkLog.querySelector('span')) zorkLog.innerHTML = '';

  lines.forEach(line => {
    if (!line.trim()) return;
    if (line.startsWith('score:')) {
      const m = line.match(/score:(\d+)\s+turn:(\d+)/);
      if (m) {
        document.getElementById('zh-score').textContent = m[1];
        document.getElementById('zh-turn').textContent = m[2];
      }
      return;
    }
    const el = document.createElement('div');
    if (line.startsWith('>')) {
      el.className = 'zork-cmd';
      el.textContent = line;
    } else if (isRoomName(line)) {
      el.className = 'zork-room';
      el.textContent = line;
    } else {
      el.className = 'zork-line';
      el.textContent = line;
    }
    zorkLog.appendChild(el);
  });
  zorkLog.scrollTop = zorkLog.scrollHeight;

  // Parse for map update
  parseZorkOutput(raw);
}

// ── WebSocket ──────────────────────────────────────────────────────────────

let ws = null;

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { document.getElementById('h-ws').textContent = 'connected'; };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'state') {
      document.getElementById('h-mood').textContent = msg.data.pet.mood;
      document.getElementById('h-tick').textContent = msg.data.tick;
    } else if (msg.type === 'speak') {
      utter(msg.text); showSpeech(msg.text);
    } else if (msg.type === 'transcript') {
      document.getElementById('h-heard').textContent = msg.text;
    } else if (msg.type === 'activity') {
      const el = document.getElementById('h-activity');
      el.textContent = msg.activity;
      el.style.color = ACTIVITY_COLORS[msg.activity] ?? '#e6edf3';
    } else if (msg.type === 'brain_log') {
      if (msg.level === 'zork') addZorkOutput(msg.text);
      else addBrainLog(msg.text, msg.level || '');
    }
  };
  ws.onclose = () => { document.getElementById('h-ws').textContent = 'reconnecting…'; setTimeout(connect, 1500); };
  ws.onerror = () => ws.close();
}

// ── Zork button ────────────────────────────────────────────────────────────

let zorkActive = false;
const zorkBtn = document.getElementById('zork-btn');

zorkBtn.addEventListener('click', async () => {
  if (zorkActive) {
    await fetch('/directive', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: 'Explore the grid. Speak when something interesting happens.'}),
    });
    zorkActive = false;
    zorkBtn.textContent = '▶ Play Zork';
    zorkBtn.classList.remove('active');
    document.getElementById('zork-status').textContent = 'not playing';
  } else {
    await fetch('/directive', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: ZORK_DIRECTIVE}),
    });
    zorkActive = true;
    zorkBtn.textContent = '■ Stop Zork';
    zorkBtn.classList.add('active');
    document.getElementById('zork-status').textContent = 'playing…';
  }
});

// ── Speech ────────────────────────────────────────────────────────────────

let speechClearTimer = null;
function showSpeech(text) {
  const el = document.getElementById('speech-text');
  el.textContent = text; el.classList.remove('empty');
  clearTimeout(speechClearTimer);
  speechClearTimer = setTimeout(() => { el.textContent = '—'; el.classList.add('empty'); }, 8000);
}

// ── TTS ───────────────────────────────────────────────────────────────────

let speakerMuted = false;
document.getElementById('mute-btn').addEventListener('click', () => {
  speakerMuted = !speakerMuted;
  document.getElementById('mute-status').textContent = speakerMuted ? 'speaker off' : 'speaker on';
  document.getElementById('mute-btn').textContent = speakerMuted ? 'Unmute Speaker' : 'Mute Speaker';
  if (speakerMuted) speechSynthesis.cancel();
});
function utter(text) {
  if (speakerMuted || !window.speechSynthesis) return;
  speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

// ── Send message ──────────────────────────────────────────────────────────

const speakInput = document.getElementById('speak-input');
document.getElementById('speak-btn').addEventListener('click', async () => {
  const text = speakInput.value.trim(); if (!text) return;
  await fetch('/hardware/transcript', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
  speakInput.value = '';
});
speakInput.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('speak-btn').click(); });

// ── Mic ───────────────────────────────────────────────────────────────────

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null, micActive = false;
document.getElementById('mic-btn').addEventListener('click', () => {
  if (micActive) {
    micActive = false; recognition?.stop(); recognition = null;
    document.getElementById('mic-status').textContent = 'mic off';
    document.getElementById('mic-btn').textContent = 'Enable Mic';
    return;
  }
  if (!SR) { document.getElementById('mic-status').textContent = 'not supported'; return; }
  micActive = true; document.getElementById('mic-btn').textContent = 'Disable Mic';
  startRecognition();
});
function startRecognition() {
  recognition = new SR();
  recognition.continuous = true; recognition.interimResults = false; recognition.lang = 'en-US';
  recognition.onstart = () => { document.getElementById('mic-status').textContent = 'listening…'; };
  recognition.onresult = e => {
    const text = e.results[e.results.length-1][0].transcript.trim(); if (!text) return;
    fetch('/hardware/transcript', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})}).catch(()=>{});
  };
  recognition.onerror = e => { document.getElementById('mic-status').textContent = `error: ${e.error}`; };
  recognition.onend = () => { if (micActive) startRecognition(); };
  recognition.start();
}

// ── Camera ────────────────────────────────────────────────────────────────

let camStream = null, frameTimer = null;
const video = document.getElementById('cam');
document.getElementById('cam-btn').addEventListener('click', async () => {
  if (camStream) {
    camStream.getTracks().forEach(t => t.stop()); camStream = null;
    video.srcObject = null; video.style.display = 'none'; clearInterval(frameTimer);
    document.getElementById('cam-status').textContent = 'camera off';
    document.getElementById('cam-btn').textContent = 'Enable Camera';
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({video:true, audio:false});
    video.srcObject = camStream; video.style.display = 'block';
    document.getElementById('cam-status').textContent = 'camera on';
    document.getElementById('cam-btn').textContent = 'Disable Camera';
    frameTimer = setInterval(() => {
      if (!camStream) return;
      const c = document.createElement('canvas'); c.width=320; c.height=240;
      c.getContext('2d').drawImage(video, 0, 0, 320, 240);
      fetch('/hardware/camera-frame', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({frame: c.toDataURL('image/jpeg',0.7)})}).catch(()=>{});
    }, 1000);
  } catch(err) { document.getElementById('cam-status').textContent = `error: ${err.message}`; }
});

// ── Brain log ─────────────────────────────────────────────────────────────

const brainLog = document.getElementById('brain-log');
function addBrainLog(text, level) {
  const el = document.createElement('div');
  el.style.cssText = `padding:1px 0;color:${level==='tool'?'#f5a623':level==='speak'?'#56d364':'#8b949e'}`;
  el.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  brainLog.appendChild(el);
  brainLog.scrollTop = brainLog.scrollHeight;
}

// ── Arrow keys still move Pepper ──────────────────────────────────────────

document.addEventListener('keydown', async e => {
  const map = {ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right'};
  const dir = map[e.key]; if (!dir) return; e.preventDefault();
  await fetch('/move', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({direction:dir})});
});

// ── Init ──────────────────────────────────────────────────────────────────

connect();
