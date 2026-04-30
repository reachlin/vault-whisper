const CELL = 36;
const MOOD_COLORS = {
  neutral: '#4a90e2',
  happy:   '#f5a623',
  curious: '#7ed321',
  tired:   '#9b9b9b',
  scared:  '#d0021b',
};
const DIR_ANGLE = { up: -Math.PI / 2, down: Math.PI / 2, left: Math.PI, right: 0 };

const canvas  = document.getElementById('grid');
const ctx     = canvas.getContext('2d');
const video   = document.getElementById('cam');
const camBtn  = document.getElementById('cam-btn');
const camStatus = document.getElementById('cam-status');
const micBtn    = document.getElementById('mic-btn');
const micStatus = document.getElementById('mic-status');
const speakInput = document.getElementById('speak-input');
const speakBtn   = document.getElementById('speak-btn');
const log     = document.getElementById('log');

let state       = null;
let ws          = null;
let camStream   = null;
let frameTimer  = null;
let petActivity = 'idle';
let animTick    = 0;

const ACTIVITY_COLORS = {
  idle:     '#555',
  thinking: '#79c0ff',
  received: '#ffd33d',
  browsing: '#56d364',
  talking:  '#56d364',
  moving:   '#f5a623',
};

// --- rendering ---

function drawActivityRing(cx, cy, r) {
  const outerR = r * 1.7;
  const t = animTick;
  ctx.save();
  switch (petActivity) {
    case 'idle': {
      const alpha = 0.12 + 0.08 * Math.sin(t * 0.025);
      ctx.strokeStyle = `rgba(120,120,120,${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
      ctx.stroke();
      break;
    }
    case 'thinking': {
      const a = (t * 0.05) % (Math.PI * 2);
      ctx.strokeStyle = '#79c0ff';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#79c0ff';
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, a, a + Math.PI * 1.2);
      ctx.stroke();
      break;
    }
    case 'received': {
      const alpha = 0.5 + 0.5 * Math.sin(t * 0.18);
      ctx.strokeStyle = `rgba(255,211,61,${alpha})`;
      ctx.lineWidth = 3;
      ctx.shadowColor = '#ffd33d';
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
      ctx.stroke();
      break;
    }
    case 'browsing': {
      const a = (t * 0.07) % (Math.PI * 2);
      ctx.strokeStyle = '#56d364';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#56d364';
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, a, a + Math.PI * 1.5);
      ctx.stroke();
      break;
    }
    case 'talking': {
      for (let i = 0; i < 3; i++) {
        const phase = ((t * 0.04) + i * 0.9) % 3;
        const alpha = Math.max(0, (1 - phase / 3) * 0.7);
        ctx.strokeStyle = `rgba(86,211,100,${alpha})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, outerR + phase * 9, 0, Math.PI * 2);
        ctx.stroke();
      }
      break;
    }
    case 'moving': {
      const a = (t * 0.14) % (Math.PI * 2);
      ctx.strokeStyle = '#f5a623';
      ctx.lineWidth = 2.5;
      ctx.shadowColor = '#f5a623';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, a, a + Math.PI * 0.7);
      ctx.stroke();
      break;
    }
  }
  ctx.restore();
}

function render(s) {
  const { config, pet } = s;
  canvas.width  = config.width  * CELL;
  canvas.height = config.height * CELL;

  // background
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // grid lines
  ctx.strokeStyle = '#1c2128';
  ctx.lineWidth = 1;
  for (let x = 0; x <= config.width; x++) {
    ctx.beginPath();
    ctx.moveTo(x * CELL, 0);
    ctx.lineTo(x * CELL, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y <= config.height; y++) {
    ctx.beginPath();
    ctx.moveTo(0, y * CELL);
    ctx.lineTo(canvas.width, y * CELL);
    ctx.stroke();
  }

  const cx = (pet.x + 0.5) * CELL;
  const cy = (pet.y + 0.5) * CELL;
  const r  = CELL * 0.36;

  drawActivityRing(cx, cy, r);

  // pet body
  ctx.fillStyle = MOOD_COLORS[pet.mood] ?? MOOD_COLORS.neutral;
  ctx.shadowColor = ctx.fillStyle;
  ctx.shadowBlur  = 10;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;

  // direction dot
  const angle = DIR_ANGLE[pet.facing] ?? 0;
  const dx = cx + Math.cos(angle) * r * 0.65;
  const dy = cy + Math.sin(angle) * r * 0.65;
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.beginPath();
  ctx.arc(dx, dy, r * 0.22, 0, Math.PI * 2);
  ctx.fill();
}

function rafLoop() {
  animTick++;
  if (state) render(state);
  requestAnimationFrame(rafLoop);
}
requestAnimationFrame(rafLoop);

function updateHUD(s) {
  document.getElementById('h-pos').textContent    = `(${s.pet.x}, ${s.pet.y})`;
  document.getElementById('h-facing').textContent = s.pet.facing;
  document.getElementById('h-mood').textContent   = s.pet.mood;
  document.getElementById('h-tick').textContent   = s.tick;
}

// --- websocket ---

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    document.getElementById('h-ws').textContent = 'connected';
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'state') {
      state = msg.data;
      updateHUD(state);
    } else if (msg.type === 'speak') {
      utter(msg.text);
      showSpeech(msg.text);
      addLog(`pet says: ${msg.text}`, 'log-speak');
    } else if (msg.type === 'transcript') {
      document.getElementById('h-heard').textContent = msg.text;
      addLog(`you said: "${msg.text}"`);
    } else if (msg.type === 'activity') {
      petActivity = msg.activity;
      const el = document.getElementById('h-activity');
      el.textContent = msg.activity;
      el.style.color = ACTIVITY_COLORS[msg.activity] ?? '#e6edf3';
    }
  };

  ws.onclose = () => {
    document.getElementById('h-ws').textContent = 'reconnecting…';
    setTimeout(connect, 1500);
  };

  ws.onerror = () => ws.close();
}

// --- movement ---

document.addEventListener('keydown', async (e) => {
  const map = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };
  const dir = map[e.key];
  if (!dir) return;
  e.preventDefault();
  await fetch('/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction: dir }),
  });
});

// --- TTS ---

function utter(text) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  speechSynthesis.speak(u);
}

speakBtn.addEventListener('click', async () => {
  const text = speakInput.value.trim();
  if (!text) return;
  await fetch('/hardware/transcript', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  speakInput.value = '';
});

speakInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') speakBtn.click();
});

// --- microphone ---

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let micActive = false;

micBtn.addEventListener('click', () => {
  if (micActive) {
    micActive = false;
    recognition?.stop();
    recognition = null;
    micStatus.textContent = 'mic off';
    micStatus.classList.remove('listening');
    micBtn.textContent = 'Enable Mic';
    return;
  }
  if (!SR) {
    micStatus.textContent = 'not supported in this browser';
    return;
  }
  micActive = true;
  micBtn.textContent = 'Disable Mic';
  startRecognition();
});

function startRecognition() {
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    micStatus.textContent = 'listening…';
    micStatus.classList.add('listening');
  };

  recognition.onresult = (e) => {
    const text = e.results[e.results.length - 1][0].transcript.trim();
    if (!text) return;
    fetch('/hardware/transcript', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).catch(() => {});
  };

  recognition.onerror = (e) => {
    micStatus.textContent = `error: ${e.error}`;
    micStatus.classList.remove('listening');
  };

  recognition.onend = () => {
    if (micActive) startRecognition(); // auto-restart while active
  };

  recognition.start();
}

// --- camera ---

camBtn.addEventListener('click', async () => {
  if (camStream) {
    camStream.getTracks().forEach(t => t.stop());
    camStream = null;
    video.srcObject = null;
    clearInterval(frameTimer);
    camStatus.textContent = 'camera off';
    camBtn.textContent = 'Enable Camera';
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = camStream;
    camStatus.textContent = 'camera on — sending frames';
    camBtn.textContent = 'Disable Camera';
    frameTimer = setInterval(sendFrame, 1000);
  } catch (err) {
    camStatus.textContent = `error: ${err.message}`;
  }
});

function sendFrame() {
  if (!camStream) return;
  const off = document.createElement('canvas');
  off.width  = 320;
  off.height = 240;
  off.getContext('2d').drawImage(video, 0, 0, 320, 240);
  const dataUrl = off.toDataURL('image/jpeg', 0.7);
  fetch('/hardware/camera-frame', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frame: dataUrl }),
  }).catch(() => {});
}

// --- speech display ---

let speechClearTimer = null;

function showSpeech(text) {
  const el = document.getElementById('speech-text');
  el.textContent = text;
  el.classList.remove('empty');
  clearTimeout(speechClearTimer);
  speechClearTimer = setTimeout(() => {
    el.textContent = '—';
    el.classList.add('empty');
  }, 8000);
}

// --- log ---

function addLog(msg, cls = '') {
  const el = document.createElement('div');
  el.className = `log-entry ${cls}`;
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  log.prepend(el);
}

// --- init ---

connect();
addLog('simulator ready — use arrow keys to move');
