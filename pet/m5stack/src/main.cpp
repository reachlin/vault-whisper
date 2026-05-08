#include <M5StickCPlus.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include "ble_bridge.h"

// Portrait: 135×240
static const int W = 135, H = 240;
static const int CX = W / 2, CY = H / 2;
static const int FACE_R     = 40;
static const int RING_INNER = 52;
static const int RING_OUTER = 58;

TFT_eSprite spr = TFT_eSprite(&M5.Lcd);

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

// ── I2S audio (Hat SPK2 / MAX98357) ──────────────────────────────────────────
#define I2S_PORT   I2S_NUM_0
#define I2S_BCLK   GPIO_NUM_26
#define I2S_LRCLK  GPIO_NUM_0    // boot-strapping pin; fine after boot
#define I2S_DOUT   GPIO_NUM_25
#define AUDIO_RATE 8000

static void initI2S() {
    i2s_config_t cfg = {};
    cfg.mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
    cfg.sample_rate          = AUDIO_RATE;
    cfg.bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1;
    cfg.dma_buf_count        = 8;
    cfg.dma_buf_len          = 256;
    cfg.use_apll             = false;
    cfg.tx_desc_auto_clear   = true;
    i2s_driver_install(I2S_PORT, &cfg, 0, nullptr);
    i2s_pin_config_t pins = {};
    pins.bck_io_num   = I2S_BCLK;
    pins.ws_io_num    = I2S_LRCLK;
    pins.data_out_num = I2S_DOUT;
    pins.data_in_num  = I2S_PIN_NO_CHANGE;
    i2s_set_pin(I2S_PORT, &pins);
    i2s_zero_dma_buffer(I2S_PORT);
}

static void writeAudioChunk(const uint8_t* src, uint16_t n) {
    static int16_t pcm16[256];
    for (uint16_t i = 0; i < n; i++)
        pcm16[i] = (int16_t)((src[i] - 128) * 256);
    size_t written;
    i2s_write(I2S_PORT, pcm16, n * 2, &written, portMAX_DELAY);
}

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

// ── BLE receive — state machine ───────────────────────────────────────────────
// '{' ... '\n'                  → JSON display/state update
// 0xAA + uint16_le + uint8[]   → PCM audio chunk (8 kHz, 8-bit unsigned)
// 0xAA + 0x00 0x00             → end of audio

enum BleState : uint8_t { BS_IDLE, BS_JSON, BS_AUDIO_SZ_LO, BS_AUDIO_SZ_HI, BS_AUDIO_DATA };
static BleState bsState  = BS_IDLE;
static char     bleBuf[512] = {};
static int      bleLen   = 0;
static uint16_t audioSz  = 0;
static uint16_t audioPos = 0;
static uint8_t  audioBuf[256] = {};

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
            if (audioSz == 0) { i2s_zero_dma_buffer(I2S_PORT); bsState = BS_IDLE; }
            else                 bsState = BS_AUDIO_DATA;
            break;
        case BS_AUDIO_DATA:
            if (audioPos < sizeof(audioBuf)) audioBuf[audioPos] = b;
            audioPos++;
            if (audioPos >= audioSz) {
                writeAudioChunk(audioBuf, min(audioSz, (uint16_t)sizeof(audioBuf)));
                bsState = BS_IDLE;
            }
            break;
        }
    }
}

// ── Arduino entry ─────────────────────────────────────────────────────────────

void setup() {
    M5.begin();
    M5.Lcd.setRotation(0);
    M5.Axp.ScreenBreath(80);

    spr.setColorDepth(16);
    spr.createSprite(W, H);

    initI2S();

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
