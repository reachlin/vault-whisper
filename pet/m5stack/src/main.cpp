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

// State received from the Python BLE bridge
static char g_mood[24]     = "neutral";
static char g_activity[24] = "idle";
static char g_speech[256]  = "";

enum UIMode : uint8_t { MODE_FACE, MODE_SPEECH };
static UIMode   uiMode      = MODE_FACE;
static uint32_t speechUntil = 0;

// ── I2S audio (Hat SPK2 / MAX98357) ──────────────────────────────────────────
// GPIO 0 (LRCLK) is a boot-strapping pin; it's fine after boot with no strong pull.

#define I2S_PORT   I2S_NUM_0
#define I2S_BCLK   GPIO_NUM_26
#define I2S_LRCLK  GPIO_NUM_0
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

// Expand unsigned 8-bit PCM chunk to signed 16-bit and push to I2S DMA.
static void writeAudioChunk(const uint8_t* src, uint16_t n) {
    static int16_t pcm16[256];
    for (uint16_t i = 0; i < n; i++)
        pcm16[i] = (int16_t)((src[i] - 128) * 256);
    size_t written;
    i2s_write(I2S_PORT, pcm16, n * 2, &written, portMAX_DELAY);
}

// ── Colors ────────────────────────────────────────────────────────────────────

static uint16_t ringColor() {
    if (!strcmp(g_activity, "thinking")) return TFT_BLUE;
    if (!strcmp(g_activity, "received")) return TFT_YELLOW;
    if (!strcmp(g_activity, "browsing")) return 0xFD20;
    if (!strcmp(g_activity, "talking"))  return TFT_GREEN;
    if (!strcmp(g_activity, "moving"))   return TFT_CYAN;
    return 0x2965;
}

static uint16_t faceColor() {
    if (!strcmp(g_mood, "happy"))   return 0xFFE0;
    if (!strcmp(g_mood, "excited")) return 0xFD20;
    if (!strcmp(g_mood, "curious")) return 0x07FF;
    if (!strcmp(g_mood, "sad"))     return 0x5D1B;
    if (!strcmp(g_mood, "angry"))   return 0xF800;
    return 0xC618;
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
    uint16_t col = ringColor();
    int ri = RING_INNER, ro = RING_OUTER;

    if (!strcmp(g_activity, "idle")) {
        if (sinf(t * 0.0015f) > 0.0f)
            for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
    } else if (!strcmp(g_activity, "thinking")) {
        int head = (int)(t / 6) % 360;
        drawArc(CX, CY, ri, ro, head, (head + 80) % 360, col);
    } else if (!strcmp(g_activity, "received")) {
        if ((t / 200) % 2 == 0)
            for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
    } else if (!strcmp(g_activity, "browsing")) {
        int head = (int)(t / 3) % 360;
        drawArc(CX, CY, ri, ro, head, (head + 120) % 360, col);
    } else if (!strcmp(g_activity, "talking")) {
        for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
        int ripple = (int)(t / 60) % 18;
        if (ripple < 14) spr.drawCircle(CX, CY, ro + ripple + 2, col);
    } else if (!strcmp(g_activity, "moving")) {
        int center = (int)(sinf(t * 0.008f) * 180.0f + 180.0f);
        drawArc(CX, CY, ri, ro, (center - 60 + 360) % 360, (center + 60) % 360, col);
    }
}

// ── Face ──────────────────────────────────────────────────────────────────────

static void drawFaceScreen(uint32_t t) {
    spr.fillSprite(TFT_BLACK);
    drawRing(t);

    uint16_t fc = faceColor();
    spr.fillCircle(CX, CY, FACE_R, fc);
    spr.drawCircle(CX, CY, FACE_R, TFT_WHITE);

    bool blink = (t % 5000) < 130;
    if (blink) {
        spr.fillRoundRect(CX - 19, CY - 13, 14, 3, 1, TFT_BLACK);
        spr.fillRoundRect(CX + 5,  CY - 13, 14, 3, 1, TFT_BLACK);
    } else {
        spr.fillCircle(CX - 12, CY - 11, 5, TFT_BLACK);
        spr.fillCircle(CX + 12, CY - 11, 5, TFT_BLACK);
        spr.fillCircle(CX - 9,  CY - 13, 2, TFT_WHITE);
        spr.fillCircle(CX + 14, CY - 13, 2, TFT_WHITE);
    }

    int mx = CX, my = CY + 10;
    if (!strcmp(g_mood, "happy") || !strcmp(g_mood, "excited")) {
        for (int d = 30; d <= 150; d++) {
            float rad = d * DEG_TO_RAD;
            spr.fillCircle(mx + (int)(15 * cosf(rad)), (my - 6) + (int)(8 * sinf(rad)), 2, TFT_BLACK);
        }
    } else if (!strcmp(g_mood, "sad")) {
        for (int d = 210; d <= 330; d++) {
            float rad = d * DEG_TO_RAD;
            spr.fillCircle(mx + (int)(15 * cosf(rad)), (my + 2) + (int)(8 * sinf(rad)), 2, TFT_BLACK);
        }
    } else {
        spr.fillRoundRect(mx - 13, my, 26, 3, 1, TFT_BLACK);
    }

    spr.setTextFont(1);
    spr.setTextColor(ringColor(), TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString(g_activity, CX, H - 4);

    spr.pushSprite(0, 0);
}

// ── Speech screen ─────────────────────────────────────────────────────────────

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
        } else {
            strlcpy(line, test, sizeof(line));
        }
        tok = strtok(nullptr, " ");
    }
    if (strlen(line) && lineY < H) spr.drawString(line, x, lineY);
}

static void drawSpeechScreen() {
    spr.fillSprite(TFT_BLACK);

    uint16_t col = ringColor();
    spr.fillRect(0, 0, W, 26, col);
    spr.setTextFont(2);
    spr.setTextColor(TFT_BLACK, col);
    spr.setTextDatum(ML_DATUM);
    spr.drawString("Pepper says:", 6, 13);

    if (strlen(g_speech) == 0) {
        spr.setTextFont(2);
        spr.setTextColor(0x4208, TFT_BLACK);
        spr.setTextDatum(TL_DATUM);
        spr.drawString("(nothing yet)", 6, 36);
    } else {
        wrapText(g_speech, 6, 36, W - 12, 22, TFT_WHITE);
    }

    spr.setTextFont(1);
    spr.setTextColor(0x4208, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("[A] back", CX, H - 4);

    spr.pushSprite(0, 0);
}

// ── BLE receive — state machine ───────────────────────────────────────────────
// Handles two frame types on the same NUS RX stream:
//   JSON  : '{' ... '\n'          — display/state updates
//   Audio : 0xAA + uint16_le_len + uint8_data[]   — PCM (8kHz 8-bit unsigned)
//           0xAA + 0x00 0x00      — end of audio (silences DMA)

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
            else               bsState = BS_AUDIO_DATA;
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
