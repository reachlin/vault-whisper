const ACTIVITY_COLORS = {
  idle:     '#555',
  thinking: '#79c0ff',
  received: '#ffd33d',
  browsing: '#56d364',
  talking:  '#56d364',
  moving:   '#f5a623',
};

const ZORK_DIRECTIVE =
  'Start playing Zork I using the zork() tool with command="start". ' +
  'Play one move per tick. Before each move speak a short narration of what you are doing or thinking.';

let ws          = null;
let state       = null;
let zorkActive  = false;

// ── WebSocket ──────────────────────────────────────────────────────────────

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => { document.getElementById('h-ws').textContent = 'connected'; };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'state') {
      state = msg.data;
      updateHUD(state);
    } else if (msg.type === 'speak') {
      utter(msg.text);
      showSpeech(msg.text);
    } else if (msg.type === 'transcript') {
      document.getElementById('h-heard').textContent = msg.text;
    } else if (msg.type === 'activity') {
      const el = document.getElementById('h-activity');
      el.textContent = msg.activity;
      el.style.color = ACTIVITY_COLORS[msg.activity] ?? '#e6edf3';
    } else if (msg.type === 'brain_log') {
      if (msg.level === 'zork') {
        addZorkOutput(msg.text);
      } else {
        addBrainLog(msg.text, msg.level || '');
      }
    }
  };

  ws.onclose = () => {
    document.getElementById('h-ws').textContent = 'reconnecting…';
    setTimeout(connect, 1500);
  };
  ws.onerror = () => ws.close();
}

// ── HUD ───────────────────────────────────────────────────────────────────

function updateHUD(s) {
  document.getElementById('h-mood').textContent = s.pet.mood;
  document.getElementById('h-tick').textContent = s.tick;
}

// ── Zork terminal ─────────────────────────────────────────────────────────

const zorkOutput = document.getElementById('zork-output');
const zorkStats  = document.getElementById('zork-stats');

function addZorkOutput(raw) {
  // Format: ">cmd\noutput lines\nscore:N turn:N"
  const lines = raw.split('\n');
  const idle = document.getElementById('zork-idle');
  if (idle) idle.remove();

  lines.forEach((line, i) => {
    if (line.startsWith('>')) {
      // Command line
      const el = document.createElement('div');
      el.className = 'zork-cmd';
      el.textContent = line;
      zorkOutput.appendChild(el);
    } else if (line.startsWith('score:')) {
      // Meta line — parse and update stats, don't render
      const m = line.match(/score:(\d+)\s+turn:(\d+)/);
      if (m) zorkStats.textContent = `Score: ${m[1]} | Turn: ${m[2]}`;
    } else if (line.trim() === '') {
      // Blank line spacer
      zorkOutput.appendChild(document.createElement('br'));
    } else {
      const el = document.createElement('div');
      // First non-blank line after a command tends to be the room name
      const isRoomLine = i === 1 && /^[A-Z]/.test(line) && line.length < 40;
      el.className = isRoomLine ? 'zork-room' : 'zork-line';
      el.textContent = line;
      zorkOutput.appendChild(el);
    }
  });

  zorkOutput.scrollTop = zorkOutput.scrollHeight;
}

// ── Zork button ───────────────────────────────────────────────────────────

const zorkBtn    = document.getElementById('zork-btn');
const zorkStatus = document.getElementById('zork-status');

zorkBtn.addEventListener('click', async () => {
  if (zorkActive) {
    // Stop — clear directive
    await fetch('/directive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'Explore the grid. Speak when something interesting happens.' }),
    });
    zorkActive = false;
    zorkBtn.textContent = '▶ Play Zork';
    zorkBtn.classList.remove('active');
    zorkStatus.textContent = 'not playing';
  } else {
    // Start — set Zork directive
    await fetch('/directive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: ZORK_DIRECTIVE }),
    });
    zorkActive = true;
    zorkBtn.textContent = '■ Stop Zork';
    zorkBtn.classList.add('active');
    zorkStatus.textContent = 'playing…';
  }
});

// ── Speech display ────────────────────────────────────────────────────────

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

// ── TTS ───────────────────────────────────────────────────────────────────

let speakerMuted = false;
document.getElementById('mute-btn').addEventListener('click', () => {
  speakerMuted = !speakerMuted;
  document.getElementById('mute-status').textContent = speakerMuted ? 'speaker off' : 'speaker on';
  document.getElementById('mute-btn').textContent    = speakerMuted ? 'Unmute Speaker' : 'Mute Speaker';
  if (speakerMuted) speechSynthesis.cancel();
});

function utter(text) {
  if (speakerMuted || !window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(text);
  speechSynthesis.speak(u);
}

// ── Send message ──────────────────────────────────────────────────────────

const speakInput = document.getElementById('speak-input');
const speakBtn   = document.getElementById('speak-btn');

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
speakInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') speakBtn.click(); });

// ── Microphone ────────────────────────────────────────────────────────────

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let micActive = false;

document.getElementById('mic-btn').addEventListener('click', () => {
  if (micActive) {
    micActive = false;
    recognition?.stop();
    recognition = null;
    document.getElementById('mic-status').textContent = 'mic off';
    document.getElementById('mic-btn').textContent = 'Enable Mic';
    return;
  }
  if (!SR) { document.getElementById('mic-status').textContent = 'not supported'; return; }
  micActive = true;
  document.getElementById('mic-btn').textContent = 'Disable Mic';
  startRecognition();
});

function startRecognition() {
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = 'en-US';
  recognition.onstart = () => {
    document.getElementById('mic-status').textContent = 'listening…';
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
  recognition.onerror = (e) => { document.getElementById('mic-status').textContent = `error: ${e.error}`; };
  recognition.onend = () => { if (micActive) startRecognition(); };
  recognition.start();
}

// ── Camera ────────────────────────────────────────────────────────────────

let camStream  = null;
let frameTimer = null;
const video    = document.getElementById('cam');

document.getElementById('cam-btn').addEventListener('click', async () => {
  if (camStream) {
    camStream.getTracks().forEach(t => t.stop());
    camStream = null;
    video.srcObject = null;
    video.style.display = 'none';
    clearInterval(frameTimer);
    document.getElementById('cam-status').textContent = 'camera off';
    document.getElementById('cam-btn').textContent = 'Enable Camera';
    return;
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = camStream;
    video.style.display = 'block';
    document.getElementById('cam-status').textContent = 'camera on';
    document.getElementById('cam-btn').textContent = 'Disable Camera';
    frameTimer = setInterval(sendFrame, 1000);
  } catch (err) {
    document.getElementById('cam-status').textContent = `error: ${err.message}`;
  }
});

function sendFrame() {
  if (!camStream) return;
  const off = document.createElement('canvas');
  off.width = 320; off.height = 240;
  off.getContext('2d').drawImage(video, 0, 0, 320, 240);
  fetch('/hardware/camera-frame', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ frame: off.toDataURL('image/jpeg', 0.7) }),
  }).catch(() => {});
}

// ── Brain log ─────────────────────────────────────────────────────────────

const brainLog = document.getElementById('brain-log');
function addBrainLog(text, level) {
  const el = document.createElement('div');
  el.style.padding = '1px 0';
  el.style.color = level === 'tool' ? '#f5a623' : level === 'speak' ? '#56d364' : '#8b949e';
  el.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  brainLog.appendChild(el);
  brainLog.scrollTop = brainLog.scrollHeight;
}

// ── Keyboard movement (still works for grid) ──────────────────────────────

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

// ── Init ──────────────────────────────────────────────────────────────────

connect();
