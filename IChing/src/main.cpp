#include <M5Unified.h>
#include <ArduinoJson.h>
#include "hexagram.h"
#include "ble_bridge.h"
#include <esp_random.h>
#include <esp_mac.h>

static const int W = 135, H = 240, CX = W / 2;
static const uint16_t PIP_BRIGHT = 0x07E0;
static const uint16_t PIP_MED    = 0x0560;
static const uint16_t PIP_DIM    = 0x01A0;

M5Canvas spr(&M5.Display);

// efontCN_16 is compiled into M5GFX; use it for CJK, bitmap fonts for Western.
static inline void setCjk(int scale = 1) {
    spr.setFont(&fonts::efontCN_16);
    spr.setTextSize(scale);
}
static inline void setWest(int n) {
    spr.setFont(nullptr);
    spr.setTextFont(n);
    spr.setTextSize(1);
}

// ── State machine ─────────────────────────────────────────────────────────────
enum State : uint8_t { IDLE, SHAKING, INTERPRETING, INTERPRETATION, REVEAL_PRIMARY, REVEAL_RELATING };
static State state = IDLE;

// Cast data
static uint8_t  castLines[6];
static int      currentLine = 0;
static int      shakesThis  = 0;
static uint32_t imuSeed     = 0;

// Hexagram results
static uint8_t primaryBits  = 0;
static uint8_t movingMask   = 0;
static uint8_t relatingBits = 0;
static uint8_t primaryNum   = 0;
static uint8_t relatingNum  = 0;
static bool    hasRelating  = false;

// Claude interpretation
static char interpretation[512] = "";
static bool hasInterpretation   = false;

// BLE receive buffer
static char bleBuf[512] = "";
static int  bleLen = 0;

// ── Audio ─────────────────────────────────────────────────────────────────────
static void coinClick() {
    // Two-tone metal click: sharp high transient + quick low tail
    M5.Speaker.setVolume(160);
    M5.Speaker.tone(3800, 14);
    delay(16);
    M5.Speaker.tone(1600, 10);
    delay(12);
    M5.Speaker.stop();
}

// ── Shake detection ───────────────────────────────────────────────────────────
static const float    SHAKE_G     = 2.2f;
static const uint32_t DEBOUNCE_MS = 350;
static uint32_t lastShakeMs = 0;

static bool detectShake(uint32_t now) {
    float ax, ay, az;
    if (!M5.Imu.getAccel(&ax, &ay, &az)) return false;
    imuSeed ^= (uint32_t)(ax * 1000) ^ (uint32_t)(ay * 1000) ^ now;
    float mag = sqrtf(ax*ax + ay*ay + az*az);
    if (mag > SHAKE_G && (now - lastShakeMs) > DEBOUNCE_MS) {
        lastShakeMs = now;
        return true;
    }
    return false;
}

// ── Line generation ───────────────────────────────────────────────────────────
// Coin method probabilities: 6=1/8, 7=3/8, 8=3/8, 9=1/8
static uint8_t generateLine() {
    uint32_t r = esp_random() ^ imuSeed ^ millis();
    switch (r & 0x07) {
        case 0:              return 6;
        case 1: case 2: case 3: return 7;
        case 4: case 5: case 6: return 8;
        default:             return 9;
    }
}

// ── Hexagram computation ──────────────────────────────────────────────────────
static void computeHexagram() {
    primaryBits = 0; movingMask = 0;
    for (int i = 0; i < 6; i++) {
        if (castLines[i] == 7 || castLines[i] == 9) primaryBits |= (1 << i);
        if (castLines[i] == 6 || castLines[i] == 9) movingMask  |= (1 << i);
    }
    relatingBits = hexRelating(primaryBits, movingMask);
    primaryNum   = hexLookup(primaryBits);
    relatingNum  = hexLookup(relatingBits);
    hasRelating  = (movingMask != 0);
}

// ── BLE ───────────────────────────────────────────────────────────────────────
static void sendHexagramEvent() {
    char buf[320];
    int n = snprintf(buf, sizeof(buf),
        "{\"evt\":\"iching\","
        "\"primary\":%d,\"primary_zh\":\"%s\",\"primary_en\":\"%s\","
        "\"relating\":%d,\"relating_zh\":\"%s\",\"relating_en\":\"%s\","
        "\"has_relating\":%s,"
        "\"lines\":[%d,%d,%d,%d,%d,%d]}\n",
        primaryNum, HEXDB[primaryNum].zh, HEXDB[primaryNum].en,
        relatingNum, HEXDB[relatingNum].zh, HEXDB[relatingNum].en,
        hasRelating ? "true" : "false",
        castLines[0], castLines[1], castLines[2],
        castLines[3], castLines[4], castLines[5]);
    bleWrite((const uint8_t*)buf, n);
    Serial.printf("[iching] sent: %s", buf);
}

static void pollBle() {
    while (bleAvailable()) {
        int ch = bleRead();
        if (ch < 0) break;
        char c = (char)ch;
        if (c == '\n' || bleLen >= 510) {
            bleBuf[bleLen] = '\0';
            bleLen = 0;
            if (bleBuf[0] == '\0') continue;
            JsonDocument doc;
            if (deserializeJson(doc, bleBuf) == DeserializationError::Ok) {
                if (doc["speech"].is<const char*>()) {
                    strlcpy(interpretation, doc["speech"], sizeof(interpretation));
                    hasInterpretation = true;
                    if (state == INTERPRETING) state = INTERPRETATION;
                    Serial.printf("[iching] interpretation received (%d chars)\n",
                                  strlen(interpretation));
                }
            }
        } else {
            bleBuf[bleLen++] = c;
        }
    }
}

// ── Draw helpers ──────────────────────────────────────────────────────────────
static void wrapText(const char* src, int x, int y, int maxW, int lineH, uint16_t col) {
    char buf[512];
    strncpy(buf, src, 511); buf[511] = '\0';
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

static void drawLine(int y, uint8_t lineVal) {
    const int LW = 88, LH = 7, GAP = 12;
    const int LX = (W - LW) / 2;
    bool yang   = (lineVal == 7 || lineVal == 9);
    bool moving = (lineVal == 6 || lineVal == 9);
    uint16_t col = moving ? PIP_BRIGHT : PIP_MED;
    if (yang) {
        spr.fillRect(LX, y, LW, LH, col);
    } else {
        int hw = (LW - GAP) / 2;
        spr.fillRect(LX,           y, hw, LH, col);
        spr.fillRect(LX + hw + GAP, y, hw, LH, col);
    }
    if (moving) spr.fillCircle(LX + LW + 8, y + LH/2, 3, PIP_BRIGHT);
}

static void drawHexagram(int topY, uint8_t bits, uint8_t moving) {
    for (int i = 5; i >= 0; i--) {
        int y = topY + (5 - i) * 13;
        bool yang = (bits >> i) & 1;
        bool mov  = (moving >> i) & 1;
        uint8_t val = yang ? (mov ? 9 : 7) : (mov ? 6 : 8);
        drawLine(y, val);
    }
}

static void bleDot(bool bright) {
    spr.fillCircle(W - 8, 8, 4, bright ? PIP_BRIGHT : PIP_DIM);
}

// ── Screen renderers ──────────────────────────────────────────────────────────
static void drawIdle(uint32_t t) {
    spr.fillSprite(TFT_BLACK);

    setCjk(2);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("易经", CX, 18);

    setWest(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.drawString("I CHING ORACLE", CX, 52);
    spr.drawFastHLine(10, 62, W - 20, PIP_DIM);

    // Animated yang lines appear one by one
    int vis = (int)(t / 500) % 7;
    for (int i = 0; i < vis && i < 6; i++)
        drawLine(80 + (5 - i) * 13, 7);

    bleDot(bleConnected());

    spr.setTextFont(2);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("Shake 3x per line", CX, 162);
    spr.drawString("for each of 6 lines", CX, 182);

    if ((t / 600) % 2 == 0) {
        spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
        spr.drawString("[ SHAKE TO BEGIN ]", CX, 210);
    }

    spr.pushSprite(0, 0);
}

static void drawShaking(uint32_t t) {
    spr.fillSprite(TFT_BLACK);

    char hdr[32];
    snprintf(hdr, sizeof(hdr), "LINE %d / 6", currentLine + 1);
    spr.setTextFont(2);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString(hdr, CX, 8);
    spr.drawFastHLine(10, 26, W - 20, PIP_DIM);

    for (int i = 0; i < 3; i++)
        spr.fillCircle(CX - 30 + i * 30, 55, 9, i < shakesThis ? PIP_BRIGHT : PIP_DIM);

    spr.setTextFont(2);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("shakes", CX, 74);

    if (currentLine > 0) {
        spr.setTextFont(1);
        spr.setTextColor(PIP_DIM, TFT_BLACK);
        spr.drawString("cast so far:", CX, 100);
        int bottomY = H - 48;
        for (int i = 0; i < currentLine; i++)
            drawLine(bottomY - i * 13, castLines[i]);
    }

    int bounce = (int)(sinf(t * 0.01f) * 5);
    spr.setTextFont(4);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("~SHAKE~", CX, H - 10 + bounce);

    spr.pushSprite(0, 0);
}

static void drawInterpreting(uint32_t t) {
    spr.fillSprite(TFT_BLACK);

    spr.setTextFont(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("ORACLE CONSULTING", CX, 4);
    spr.drawFastHLine(10, 14, W - 20, PIP_DIM);

    // Hexagram in center
    drawHexagram(22, primaryBits, movingMask);

    // Spinning arc
    int cx2 = CX, cy2 = 145, r = 26;
    int head = (int)(t / 4) % 360;
    for (int d = 0; d < 120; d++) {
        float rad = ((head + d) % 360) * DEG_TO_RAD;
        uint16_t col = d < 60 ? PIP_BRIGHT : PIP_MED;
        spr.drawPixel(cx2 + (int)(r * cosf(rad)), cy2 + (int)(r * sinf(rad)), col);
    }

    spr.setTextFont(2);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("Consulting Claude", CX, 178);

    // Animated ellipsis
    char dots[5] = "";
    int nd = (t / 400) % 4;
    for (int i = 0; i < nd; i++) dots[i] = '.', dots[i+1] = '\0';
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.drawString(dots, CX, 198);

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("[B] SKIP TO HEX", CX, H - 2);

    spr.pushSprite(0, 0);
}

static void drawInterpretation() {
    spr.fillSprite(TFT_BLACK);

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString("CLAUDE READING", CX, 4);
    spr.drawFastHLine(10, 14, W - 20, PIP_DIM);

    setCjk(2);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.drawString(HEXDB[primaryNum].zh, CX, 20);

    setWest(1);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.drawString(HEXDB[primaryNum].en, CX, 46);
    spr.drawFastHLine(10, 56, W - 20, PIP_DIM);

    wrapText(interpretation, 6, 62, W - 12, 20, PIP_BRIGHT);

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    spr.drawString("[A] HEXAGRAM  [B] RESET", CX, H - 2);

    spr.pushSprite(0, 0);
}

static void drawReveal(bool relating) {
    spr.fillSprite(TFT_BLACK);

    uint8_t num  = relating ? relatingNum   : primaryNum;
    uint8_t bits = relating ? relatingBits  : primaryBits;
    uint8_t mov  = relating ? 0             : movingMask;
    const HexData& h = HEXDB[num];

    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString(relating ? "RELATING HEX" : "PRIMARY HEX", CX, 4);
    spr.drawFastHLine(10, 14, W - 20, PIP_DIM);

    drawHexagram(20, bits, mov);

    char numStr[8];
    snprintf(numStr, sizeof(numStr), "#%d", num);
    spr.setTextFont(2);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.setTextDatum(TC_DATUM);
    spr.drawString(numStr, CX, 102);

    setCjk(2);
    spr.setTextColor(PIP_BRIGHT, TFT_BLACK);
    spr.drawString(h.zh, CX, 116);

    setWest(2);
    spr.setTextColor(PIP_MED, TFT_BLACK);
    spr.drawString(h.en, CX, 142);
    spr.drawFastHLine(10, 158, W - 20, PIP_DIM);

    wrapText(relating ? h.relating : h.primary, 8, 164, W - 16, 20, PIP_BRIGHT);

    // Footer: cycle through available views
    spr.setTextFont(1);
    spr.setTextColor(PIP_DIM, TFT_BLACK);
    spr.setTextDatum(BC_DATUM);
    if (!relating && hasRelating && hasInterpretation)
        spr.drawString("[A] RELATING  [B] RESET", CX, H - 2);
    else if (!relating && hasRelating)
        spr.drawString("[A] RELATING  [B] RESET", CX, H - 2);
    else if (!relating && hasInterpretation)
        spr.drawString("[A] READING  [B] RESET", CX, H - 2);
    else if (relating && hasInterpretation)
        spr.drawString("[A] READING  [B] RESET", CX, H - 2);
    else if (relating)
        spr.drawString("[A] PRIMARY  [B] RESET", CX, H - 2);
    else
        spr.drawString("[B] RESET", CX, H - 2);

    spr.pushSprite(0, 0);
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    auto cfg = M5.config();
    cfg.fallback_board = m5::board_t::board_M5StickS3;
    M5.begin(cfg);
    M5.Display.setRotation(0);
    M5.Display.setBrightness(100);

    spr.setColorDepth(16);
    spr.createSprite(W, H);

    M5.Imu.begin();
    hexBuildIndex();

    char name[20];
    uint8_t mac[6] = {};
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(name, sizeof(name), "IChing-%02X%02X", mac[4], mac[5]);
    bleInit(name);

    // M5PM1 (0x6E) charging LED: hardware-driven by PMIC state machine.
    // The LED_EN default-level register (0x06 bit4) only sets power-on reset,
    // not runtime — the charging state machine overrides it autonomously.
    // Physical tape over the LED is the reliable fix.

    Serial.begin(115200);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    M5.update();
    uint32_t t = millis();

    pollBle();

    switch (state) {

    case IDLE:
        drawIdle(t);
        if (detectShake(t)) {
            currentLine = 0; shakesThis = 0; imuSeed = 0;
            hasInterpretation = false; interpretation[0] = '\0';
            state = SHAKING;
        }
        break;

    case SHAKING:
        drawShaking(t);
        if (detectShake(t)) {
            coinClick();
            shakesThis++;
            if (shakesThis >= 3) {
                castLines[currentLine] = generateLine();
                currentLine++;
                shakesThis = 0;
                if (currentLine >= 6) {
                    computeHexagram();
                    if (bleConnected()) {
                        sendHexagramEvent();
                        state = INTERPRETING;
                    } else {
                        state = REVEAL_PRIMARY;
                    }
                }
            }
        }
        if (M5.BtnB.wasPressed()) state = IDLE;
        break;

    case INTERPRETING:
        drawInterpreting(t);
        if (M5.BtnB.wasPressed()) state = REVEAL_PRIMARY;
        break;

    case INTERPRETATION:
        drawInterpretation();
        if (M5.BtnA.wasPressed()) state = REVEAL_PRIMARY;
        if (M5.BtnB.wasPressed()) state = IDLE;
        break;

    case REVEAL_PRIMARY:
        drawReveal(false);
        if (M5.BtnA.wasPressed()) {
            if (hasRelating)            state = REVEAL_RELATING;
            else if (hasInterpretation) state = INTERPRETATION;
        }
        if (M5.BtnB.wasPressed()) state = IDLE;
        break;

    case REVEAL_RELATING:
        drawReveal(true);
        if (M5.BtnA.wasPressed())
            state = hasInterpretation ? INTERPRETATION : REVEAL_PRIMARY;
        if (M5.BtnB.wasPressed()) state = IDLE;
        break;
    }

    delay(25);
}
