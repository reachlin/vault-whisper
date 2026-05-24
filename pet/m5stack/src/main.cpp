#include <M5Unified.h>
#include <ArduinoJson.h>
#include "ble_bridge.h"

// Portrait: 135×240
static const int W = 135, H = 240;
static const int CX = W / 2, CY = H / 2;
static const int FACE_R     = 40;
static const int RING_INNER = 52;
static const int RING_OUTER = 58;

M5Canvas spr(&M5.Display);

static char g_mood[24]     = "neutral";
static char g_activity[24] = "idle";
static char g_speech[256]  = "";

enum UIMode : uint8_t { MODE_FACE, MODE_SPEECH };
static UIMode   uiMode      = MODE_FACE;
static uint32_t speechUntil = 0;

// ── Pip-Boy phosphor green palette ───────────────────────────────────────────
// All colours derived from #00FF00 phosphor CRT green, RGB565 encoding.
static const uint16_t PIP_BRIGHT = 0x07E0;   // #00FF00  full intensity
static const uint16_t PIP_MED    = 0x0560;   // #00AC00  mid phosphor
static const uint16_t PIP_DIM    = 0x01A0;   // #003500  scan-line tint
static const uint16_t PIP_BG     = 0x0060;   // #001800  face fill

// ── Audio backend ─────────────────────────────────────────────────────────────
#ifndef AUDIO_RATE
#define AUDIO_RATE 8000
#endif

#ifdef M5STICK_S3

// S3: ES8311 internal speaker via M5Unified.
// Static buffer in internal SRAM BSS — allocated at link time so it never
// fails at runtime. The linker would refuse to build if it didn't fit.
// Cache_WriteBack_Addr() flushes Core 1's write-back D-cache lines before
// handing the buffer pointer to the Speaker task on Core 0.
#include <esp32s3/rom/cache.h>
static const size_t AUDIO_CAP = (size_t)AUDIO_RATE * 5;  // 5 s @ 16 kHz = 160 KB
static int16_t g_pcmBuf[AUDIO_CAP];
static size_t  g_pcmLen = 0;

static void initAudio() {
    M5.Speaker.setVolume(255);
    M5.Speaker.tone(1000, 300);
    delay(350);
}

static void appendAudio(const uint8_t* src, uint16_t n) {
    const int16_t* s16 = (const int16_t*)src;
    size_t mono = n / 2;
    if (g_pcmLen + mono <= AUDIO_CAP)
        memcpy(g_pcmBuf + g_pcmLen, s16, mono * sizeof(int16_t)), g_pcmLen += mono;
}

static void flushAudio() {
    if (g_pcmLen == 0) return;
    Cache_WriteBack_Addr((uint32_t)g_pcmBuf, g_pcmLen * sizeof(int16_t));
    M5.Speaker.playRaw(g_pcmBuf, g_pcmLen, AUDIO_RATE, false, 1, 0, true);
    g_pcmLen = 0;
}

static void silenceAudio() { M5.Speaker.stop(); g_pcmLen = 0; }

#else

// Plus: Hat SPK2 (MAX98357A) via raw I2S.
#include <driver/i2s.h>
#define I2S_PORT  I2S_NUM_0
#define I2S_BCLK  GPIO_NUM_26
#define I2S_LRCLK GPIO_NUM_0
#define I2S_DOUT  GPIO_NUM_25

static void initAudio() {
    i2s_config_t cfg = {};
    cfg.mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
    cfg.sample_rate          = AUDIO_RATE;
    cfg.bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1;
    cfg.dma_buf_count        = 8;
    cfg.dma_buf_len          = 512;
    cfg.use_apll             = false;
    cfg.tx_desc_auto_clear   = true;
    i2s_driver_install(I2S_PORT, &cfg, 0, nullptr);
    i2s_pin_config_t pins = {};
    pins.mck_io_num   = I2S_PIN_NO_CHANGE;
    pins.bck_io_num   = I2S_BCLK;
    pins.ws_io_num    = I2S_LRCLK;
    pins.data_out_num = I2S_DOUT;
    pins.data_in_num  = I2S_PIN_NO_CHANGE;
    i2s_set_pin(I2S_PORT, &pins);
    i2s_zero_dma_buffer(I2S_PORT);
}

static void appendAudio(const uint8_t* src, uint16_t n) {
    size_t written;
    i2s_write(I2S_PORT, src, n, &written, portMAX_DELAY);
}

static void flushAudio()  { i2s_zero_dma_buffer(I2S_PORT); }
static void silenceAudio(){ i2s_zero_dma_buffer(I2S_PORT); }

#endif

// ── Activity ring ─────────────────────────────────────────────────────────────

static void drawArc(int cx, int cy, int r0, int r1, int startDeg, int endDeg, uint16_t col) {
    startDeg = ((startDeg % 360) + 360) % 360;
    endDeg   = ((endDeg   % 360) + 360) % 360;
    for (int d = 0; d < 360; d++) {
        bool in = (startDeg <= endDeg) ? (d >= startDeg && d <= endDeg)
                                       : (d >= startDeg || d <= endDeg);
        if (!in) continue;
        float rad = d * DEG_TO_RAD;
        float cs = cosf(rad), sn = sinf(rad);
        for (int r = r0; r <= r1; r++)
            spr.drawPixel(cx + (int)(r * cs), cy + (int)(r * sn), col);
    }
}

static void drawRing(uint32_t t) {
    int ri = RING_INNER, ro = RING_OUTER;

    if (!strcmp(g_activity, "idle")) {
        // Targeting crosshair: four 60° arcs rotating slowly
        int head = (int)(t / 20) % 360;
        for (int q = 0; q < 4; q++) {
            int s = (head + q * 90) % 360;
            drawArc(CX, CY, ri, ro, s, (s + 55) % 360, PIP_MED);
        }
    } else if (!strcmp(g_activity, "thinking")) {
        // Single fast-spinning 100° arc — LOADING...
        int head = (int)(t / 5) % 360;
        drawArc(CX, CY, ri, ro, head, (head + 100) % 360, PIP_BRIGHT);
    } else if (!strcmp(g_activity, "received")) {
        // Full ring pulsing bright/med
        uint16_t col = ((t / 250) % 2 == 0) ? PIP_BRIGHT : PIP_MED;
        for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
    } else if (!strcmp(g_activity, "browsing")) {
        // Radar sweep: bright leading edge with fading trail
        int head = (int)(t / 3) % 360;
        drawArc(CX, CY, ri, ro, head,             (head +  30) % 360, PIP_BRIGHT);
        drawArc(CX, CY, ri, ro, (head + 30) % 360, (head + 60) % 360, PIP_MED);
        drawArc(CX, CY, ri, ro, (head + 60) % 360, (head + 90) % 360, PIP_DIM);
    } else if (!strcmp(g_activity, "talking")) {
        // Sonar: solid ring with expanding ripple
        for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, PIP_MED);
        int ripple = (int)(t / 55) % 20;
        if (ripple < 15) spr.drawCircle(CX, CY, ro + ripple + 2, PIP_BRIGHT);
    } else if (!strcmp(g_activity, "moving")) {
        // Two opposing arcs sweeping around
        int head = (int)(t / 4) % 360;
        drawArc(CX, CY, ri, ro, (head - 60 + 360) % 360, (head + 60) % 360,        PIP_BRIGHT);
        drawArc(CX, CY, ri, ro, (head + 120)       % 360, (head + 240) % 360,       PIP_MED);
    }
}

// ── Face ──────────────────────────────────────────────────────────────────────

static void drawFaceScreen(uint32_t t) {
    spr.fillSprite(TFT_BLACK);

    // --- Pip-Boy face ball ---
    // Dark green fill, CRT scan lines, bright border
    spr.fillCircle(CX, CY, FACE_R, PIP_BG);
    for (int y = CY - FACE_R + 2; y < CY + FACE_R; y += 4) {
        int dx = (int)sqrtf((float)(FACE_R * FACE_R - (y - CY) * (y - CY)));
        spr.drawFastHLine(CX - dx, y, 2 * dx, PIP_DIM);
    }
    spr.drawCircle(CX, CY, FACE_R,     PIP_BRIGHT);
    spr.drawCircle(CX, CY, FACE_R - 1, PIP_MED);

    // Activity ring (outside face)
    drawRing(t);

    // --- Eyes ---
    // Block-pixel style; blink every ~4 s
    bool blink = (t % 4000) < 120;
    if (blink) {
        spr.fillRect(CX - 20, CY - 13, 14, 2, PIP_BRIGHT);
        spr.fillRect(CX +  6, CY - 13, 14, 2, PIP_BRIGHT);
    } else {
        spr.fillRect(CX - 20, CY - 15, 14, 7, PIP_BRIGHT);
        spr.fillRect(CX +  6, CY - 15, 14, 7, PIP_BRIGHT);
        // inner dark pupil
        spr.fillRect(CX - 17, CY - 13, 8, 3, PIP_BG);
        spr.fillRect(CX +  9, CY - 13, 8, 3, PIP_BG);
    }

    // --- Mouth (pixelated, mood-aware) ---
    int mx = CX, my = CY + 13;
    if (!strcmp(g_mood, "happy") || !strcmp(g_mood, "excited")) {
        // Stepped smile
        spr.fillRect(mx - 14, my + 3, 5, 3, PIP_BRIGHT);
        spr.fillRect(mx -  9, my + 1, 4, 3, PIP_BRIGHT);
        spr.fillRect(mx -  5, my - 1, 10, 3, PIP_BRIGHT);
        spr.fillRect(mx +  5, my + 1, 4, 3, PIP_BRIGHT);
        spr.fillRect(mx +  9, my + 3, 5, 3, PIP_BRIGHT);
    } else if (!strcmp(g_mood, "sad")) {
        // Stepped frown
        spr.fillRect(mx - 14, my - 1, 5, 3, PIP_BRIGHT);
        spr.fillRect(mx -  9, my + 1, 4, 3, PIP_BRIGHT);
        spr.fillRect(mx -  5, my + 3, 10, 3, PIP_BRIGHT);
        spr.fillRect(mx +  5, my + 1, 4, 3, PIP_BRIGHT);
        spr.fillRect(mx +  9, my - 1, 5, 3, PIP_BRIGHT);
    } else if (!strcmp(g_mood, "angry")) {
        // Flat line with downward inner corners (angry brow implied by mouth)
        spr.fillRect(mx - 14, my + 1, 28, 3, PIP_BRIGHT);
        spr.fillRect(mx - 14, my + 4,  5, 2, PIP_BRIGHT);
        spr.fillRect(mx +  9, my + 4,  5, 2, PIP_BRIGHT);
    } else {
        // Neutral flat line
        spr.fillRect(mx - 14, my + 1, 28, 3, PIP_BRIGHT);
    }

    // --- Labels ---
    spr.setTextFont(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("PIP-BOY 3000", CX, 5);

    spr.setTextDatum(BC_DATUM);
    spr.drawString(g_activity, CX, H - 5);

    spr.pushSprite(0, 0);
}

// ── Speech screen (AUDIO LOG) ─────────────────────────────────────────────────

static void wrapText(const char* src, int x, int y, int maxW, int lineH, uint16_t col) {
    char buf[256];
    strncpy(buf, src, 255); buf[255] = '\0';
    spr.setTextFont(2);
    spr.setTextColor(col, TFT_BLACK);
    spr.setTextDatum(TL_DATUM);
    char* tok = strtok(buf, " ");
    char  line[64] = "";
    int   lineY = y;
    while (tok && lineY < H - lineH) {
        char test[64];
        snprintf(test, sizeof(test), "%s%s%s", line, strlen(line) ? " " : "", tok);
        if ((int)spr.textWidth(test) > maxW && strlen(line)) {
            spr.drawString(line, x, lineY);
            lineY += lineH;
            strlcpy(line, tok, sizeof(line));
        } else { strlcpy(line, test, sizeof(line)); }
        tok = strtok(nullptr, " ");
    }
    if (strlen(line) && lineY < H) spr.drawString(line, x, lineY);
}

static void drawSpeechScreen() {
    spr.fillSprite(TFT_BLACK);

    // Header bar
    spr.fillRect(0, 0, W, 26, PIP_BG);
    spr.drawFastHLine(0, 26, W, PIP_BRIGHT);
    spr.setTextFont(2);
    spr.setTextColor(PIP_BRIGHT, PIP_BG);
    spr.setTextDatum(ML_DATUM);
    spr.drawString("AUDIO LOG:", 6, 13);

    if (strlen(g_speech) == 0) {
        spr.setTextFont(2);
        spr.setTextColor(PIP_MED, TFT_BLACK);
        spr.setTextDatum(TL_DATUM);
        spr.drawString("[NO SIGNAL]", 6, 36);
    } else {
        wrapText(g_speech, 6, 36, W - 12, 22, PIP_BRIGHT);
    }

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("[A] CLOSE", CX, H - 5);

    spr.pushSprite(0, 0);
}

// ── Sleep screen (BLE disconnected) ──────────────────────────────────────────
// Fallout Robco terminal aesthetic: dim phosphor green, floating ZZZs,
// blinking "SIGNAL: NULL_" cursor.

static void drawZ(int x, int y, int sz, uint16_t col) {
    // Draw a pixel-art Z of given size
    spr.fillRect(x,          y,          sz, 2, col);   // top bar
    spr.fillRect(x + sz - 2, y + 2,      2,  sz - 4, col); // right diagonal hint
    spr.fillRect(x,          y + sz - 2, sz, 2, col);   // bottom bar
    // diagonal: draw a few pixels
    int steps = sz - 2;
    for (int i = 0; i < steps; i++)
        spr.drawPixel(x + sz - 2 - i * sz / steps, y + 2 + i, col);
}

static void drawSleepScreen(uint32_t t) {
    spr.fillSprite(TFT_BLACK);

    // ── Robco terminal header ────────────────────────────────────────────────
    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("ROBCO INDUSTRIES (TM)", CX, 6);
    spr.drawString("UNIFIED OPERATING SYSTEM", CX, 16);
    spr.drawFastHLine(4, 27, W - 8, PIP_DIM);

    // ── Sleeping pip-boy face ────────────────────────────────────────────────
    const int FCY = 110;
    spr.fillCircle(CX, FCY, FACE_R, PIP_BG);
    // scan lines
    for (int y = FCY - FACE_R + 2; y < FCY + FACE_R; y += 4) {
        int dx = (int)sqrtf((float)(FACE_R * FACE_R - (y - FCY) * (y - FCY)));
        spr.drawFastHLine(CX - dx, y, 2 * dx, PIP_DIM);
    }
    spr.drawCircle(CX, FCY, FACE_R, PIP_DIM);

    // Closed eyes: thin arched lines
    spr.fillRect(CX - 20, FCY - 12, 14, 3, PIP_MED);
    spr.fillRect(CX + 6,  FCY - 12, 14, 3, PIP_MED);
    // droopy inner corners
    spr.fillRect(CX - 8,  FCY - 10, 3, 3, PIP_MED);
    spr.fillRect(CX + 6,  FCY - 10, 3, 3, PIP_MED);

    // Flat sleepy mouth
    spr.fillRect(CX - 10, FCY + 12, 20, 2, PIP_DIM);

    // ── Floating ZZZs (three sizes, rising loop every 3 s) ──────────────────
    // Each Z rises 30px over 3 s then resets; they're offset in time.
    const uint32_t PERIOD = 3000;
    auto zY = [&](uint32_t offset) -> int {
        uint32_t phase = (t + offset) % PERIOD;
        return FCY - FACE_R - 6 - (int)(phase * 28 / PERIOD);
    };
    uint8_t zAlpha = 255 - (uint8_t)((t % PERIOD) * 180 / PERIOD);
    // draw three Zs: large, medium, small, staggered
    drawZ(CX + 20, zY(0),       10, PIP_BRIGHT);
    drawZ(CX + 32, zY(1000) - 8, 7, PIP_MED);
    drawZ(CX + 41, zY(2000) - 14, 5, PIP_DIM);

    // ── Terminal status at bottom ────────────────────────────────────────────
    spr.setTextFont(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TL_DATUM);
    spr.drawString("> SIGNAL: NULL", 6, H - 34);

    // Blinking cursor
    if ((t / 500) % 2 == 0)
        spr.fillRect(6 + 90, H - 34, 6, 8, PIP_MED);

    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.drawString("> STANDBY MODE...", 6, H - 22);

    spr.pushSprite(0, 0);
}

// ── Passkey screen ───────────────────────────────────────────────────────────

static void drawPasskeyScreen(uint32_t pk) {
    char top[4], bot[4];
    snprintf(top, sizeof(top), "%03lu", (unsigned long)(pk / 1000));
    snprintf(bot, sizeof(bot), "%03lu", (unsigned long)(pk % 1000));

    spr.fillSprite(TFT_BLACK);

    spr.setTextFont(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("PAIRING CODE", CX, 10);
    spr.drawFastHLine(8, 22, W - 16, PIP_DIM);

    // Two rows of 3 digits — font 7 is ~24px/char, 3 chars = 72px fits 135px screen
    spr.setTextFont(7);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.setTextDatum(MC_DATUM);
    spr.drawString(top, CX, CY - 30);
    spr.drawString(bot, CX, CY + 30);

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("TYPE ON HOST", CX, H - 5);

    spr.pushSprite(0, 0);
}

// ── BLE receive — state machine ───────────────────────────────────────────────
// '{' ... '\n'                   → JSON display/state update
// 0xAA + uint16_le + int16_le[] → PCM audio chunk (AUDIO_RATE Hz, 16-bit signed LE)
// 0xAA + 0x00 0x00              → end of audio (Plus: silence; S3: play accumulated)

enum BleState : uint8_t { BS_IDLE, BS_JSON, BS_AUDIO_SZ_LO, BS_AUDIO_SZ_HI, BS_AUDIO_DATA };
static BleState bsState  = BS_IDLE;
static char     bleBuf[512] = {};
static int      bleLen   = 0;
static uint16_t audioSz  = 0;
static uint16_t audioPos = 0;
static uint8_t  audioBuf[512] = {};

static void parseLine(const char* s) {
    JsonDocument doc;
    if (deserializeJson(doc, s) != DeserializationError::Ok) return;
    if (doc["mood"].is<const char*>())     strlcpy(g_mood,     doc["mood"],     sizeof(g_mood));
    if (doc["activity"].is<const char*>()) strlcpy(g_activity, doc["activity"], sizeof(g_activity));
    if (doc["speech"].is<const char*>())   strlcpy(g_speech,   doc["speech"],   sizeof(g_speech));
}

static void pollBle() {
    while (bleAvailable()) {
        int ch = bleRead();
        if (ch < 0) break;
        uint8_t b = (uint8_t)ch;
        switch (bsState) {
        case BS_IDLE:
            if      (b == '{')  { bleBuf[0] = '{'; bleLen = 1; bsState = BS_JSON; }
            else if (b == 0xAA) { bsState = BS_AUDIO_SZ_LO; }
            break;
        case BS_JSON:
            if (b == '\n' || bleLen >= 510) {
                bleBuf[bleLen] = '\0';
                if (bleLen > 0) parseLine(bleBuf);
                bleLen = 0; bsState = BS_IDLE;
            } else { bleBuf[bleLen++] = (char)b; }
            break;
        case BS_AUDIO_SZ_LO:
            audioSz = b; bsState = BS_AUDIO_SZ_HI;
            break;
        case BS_AUDIO_SZ_HI:
            audioSz |= (uint16_t)b << 8;
            audioPos = 0;
            if (audioSz == 0) { flushAudio(); bsState = BS_IDLE; }
            else               bsState = BS_AUDIO_DATA;
            break;
        case BS_AUDIO_DATA:
            if (audioPos < sizeof(audioBuf)) audioBuf[audioPos] = b;
            audioPos++;
            if (audioPos >= audioSz) {
                appendAudio(audioBuf, min(audioSz, (uint16_t)sizeof(audioBuf)));
                bsState = BS_IDLE;
            }
            break;
        }
    }
}

// ── Arduino entry ─────────────────────────────────────────────────────────────

void setup() {
    auto cfg = M5.config();
    // M5StickS3 isn't auto-detected from the ESP32-S3-PICO-1 eFuse alone;
    // set fallback so M5Unified configures the display and power IC correctly.
    cfg.fallback_board = m5::board_t::board_M5StickS3;
    M5.begin(cfg);
    M5.Display.setRotation(0);
    M5.Display.setBrightness(80);

    spr.setColorDepth(16);
    spr.createSprite(W, H);

    initAudio();

    char name[20];
    uint8_t mac[6] = {};
    esp_read_mac(mac, ESP_MAC_BT);
    snprintf(name, sizeof(name), "Pepper-%02X%02X", mac[4], mac[5]);
    bleInit(name);

    Serial.begin(115200);
}

void loop() {
    M5.update();
    uint32_t t = millis();

    // ── BLE connect / disconnect transitions ─────────────────────────────────
    static bool wasConnected = false;
    bool connected = bleConnected();

    if (connected && !wasConnected) {
        // just reconnected — restore brightness and reset state.
        // end()+begin() is required: begin() returns early if the task is already
        // running, so _speaker_enabled_cb_sticks3 (ES8311 init + PA enable) is
        // never called again after the first disconnect unless we end() first.
        M5.Display.setBrightness(80);
        M5.Speaker.setVolume(255);
        strlcpy(g_activity, "idle",    sizeof(g_activity));
        strlcpy(g_mood,     "neutral", sizeof(g_mood));
        uiMode = MODE_FACE;
    } else if (!connected && wasConnected) {
        // just disconnected — dim screen and silence speaker
        M5.Display.setBrightness(20);
        silenceAudio();
    }
    wasConnected = connected;

    // Passkey must be shown regardless of connection state — onPassKeyNotify
    // fires while connected (mid-stream security upgrade) and is cleared by
    // onDisconnect before we'd see it in the !connected branch.
    uint32_t pk = blePasskey();
    if (pk) { drawPasskeyScreen(pk); delay(30); return; }

    if (!connected) {
        drawSleepScreen(t);
        delay(40);
        return;
    }

    pollBle();

    if (M5.BtnA.wasPressed()) {
        if (uiMode == MODE_FACE) { uiMode = MODE_SPEECH; speechUntil = t + 10000; }
        else                       uiMode = MODE_FACE;
    }
    if (M5.BtnB.wasPressed()) uiMode = MODE_FACE;
    if (uiMode == MODE_SPEECH && t > speechUntil) uiMode = MODE_FACE;

    if (uiMode == MODE_FACE) drawFaceScreen(t);
    else                     drawSpeechScreen();

    delay(30);
}
