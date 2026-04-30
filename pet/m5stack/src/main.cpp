#include <M5StickCPlus.h>
#include <ArduinoJson.h>
#include "ble_bridge.h"

// Portrait: 135×240
static const int W = 135, H = 240;
static const int CX = W / 2, CY = H / 2;
static const int FACE_R    = 40;
static const int RING_INNER = 52;
static const int RING_OUTER = 58;

TFT_eSprite spr = TFT_eSprite(&M5.Lcd);

// State received from the Python BLE bridge
static char g_mood[24]     = "neutral";
static char g_activity[24] = "idle";
static char g_speech[256]  = "";

enum UIMode : uint8_t { MODE_FACE, MODE_SPEECH };
static UIMode   uiMode      = MODE_FACE;
static uint32_t speechUntil = 0;   // auto-return timer

// ── Colors ────────────────────────────────────────────────────────────────────

static uint16_t ringColor() {
  if (!strcmp(g_activity, "thinking")) return TFT_BLUE;
  if (!strcmp(g_activity, "received")) return TFT_YELLOW;
  if (!strcmp(g_activity, "browsing")) return 0xFD20;  // orange
  if (!strcmp(g_activity, "talking"))  return TFT_GREEN;
  if (!strcmp(g_activity, "moving"))   return TFT_CYAN;
  return 0x2965;  // idle: dim gray
}

static uint16_t faceColor() {
  if (!strcmp(g_mood, "happy"))   return 0xFFE0;  // yellow
  if (!strcmp(g_mood, "excited")) return 0xFD20;  // orange
  if (!strcmp(g_mood, "curious")) return 0x07FF;  // cyan
  if (!strcmp(g_mood, "sad"))     return 0x5D1B;  // muted blue
  if (!strcmp(g_mood, "angry"))   return 0xF800;  // red
  return 0xC618;  // neutral: light gray
}

// ── Activity ring ─────────────────────────────────────────────────────────────

// Rasterise a filled arc band between radii r0..r1, from startDeg to endDeg (CW from top).
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
    // Slow breathing pulse
    if (sinf(t * 0.0015f) > 0.0f) {
      for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
    }

  } else if (!strcmp(g_activity, "thinking")) {
    // 80° arc rotating slowly
    int head = (int)(t / 6) % 360;
    drawArc(CX, CY, ri, ro, head, (head + 80) % 360, col);

  } else if (!strcmp(g_activity, "received")) {
    // Full ring flashing
    if ((t / 200) % 2 == 0)
      for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);

  } else if (!strcmp(g_activity, "browsing")) {
    // 120° arc spinning fast
    int head = (int)(t / 3) % 360;
    drawArc(CX, CY, ri, ro, head, (head + 120) % 360, col);

  } else if (!strcmp(g_activity, "talking")) {
    // Solid ring + one expanding ripple
    for (int r = ri; r <= ro; r++) spr.drawCircle(CX, CY, r, col);
    int ripple = (int)(t / 60) % 18;
    if (ripple < 14) spr.drawCircle(CX, CY, ro + ripple + 2, col);

  } else if (!strcmp(g_activity, "moving")) {
    // 120° arc bouncing around the ring
    int center = (int)(sinf(t * 0.008f) * 180.0f + 180.0f);
    drawArc(CX, CY, ri, ro, (center - 60 + 360) % 360, (center + 60) % 360, col);
  }
}

// ── Face ──────────────────────────────────────────────────────────────────────

static void drawFaceScreen(uint32_t t) {
  spr.fillSprite(TFT_BLACK);

  drawRing(t);

  // Ball
  uint16_t fc = faceColor();
  spr.fillCircle(CX, CY, FACE_R, fc);
  spr.drawCircle(CX, CY, FACE_R, TFT_WHITE);

  // Eyes — blink briefly every ~5 s
  bool blink = (t % 5000) < 130;
  if (blink) {
    spr.fillRoundRect(CX - 19, CY - 13, 14, 3, 1, TFT_BLACK);
    spr.fillRoundRect(CX + 5,  CY - 13, 14, 3, 1, TFT_BLACK);
  } else {
    spr.fillCircle(CX - 12, CY - 11, 5, TFT_BLACK);
    spr.fillCircle(CX + 12, CY - 11, 5, TFT_BLACK);
    spr.fillCircle(CX - 9,  CY - 13, 2, TFT_WHITE);   // shine
    spr.fillCircle(CX + 14, CY - 13, 2, TFT_WHITE);
  }

  // Mouth
  // Center anchor: (CX, CY+10). Smile/frown arcs on a 15×8 ellipse.
  int mx = CX, my = CY + 10;
  if (!strcmp(g_mood, "happy") || !strcmp(g_mood, "excited")) {
    // Smile: lower half of ellipse centered at (mx, my-6)  → center dips to my+2
    for (int d = 30; d <= 150; d++) {
      float rad = d * DEG_TO_RAD;
      spr.fillCircle(mx + (int)(15 * cosf(rad)), (my - 6) + (int)(8 * sinf(rad)), 2, TFT_BLACK);
    }
  } else if (!strcmp(g_mood, "sad")) {
    // Frown: upper half of ellipse centered at (mx, my+2)  → center rises to my-6
    for (int d = 210; d <= 330; d++) {
      float rad = d * DEG_TO_RAD;
      spr.fillCircle(mx + (int)(15 * cosf(rad)), (my + 2) + (int)(8 * sinf(rad)), 2, TFT_BLACK);
    }
  } else {
    spr.fillRoundRect(mx - 13, my, 26, 3, 1, TFT_BLACK);
  }

  // Tiny activity label at bottom
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

  // Coloured header bar
  uint16_t col = ringColor();
  spr.fillRect(0, 0, W, 26, col);
  spr.setTextFont(2);
  spr.setTextColor(TFT_BLACK, col);
  spr.setTextDatum(ML_DATUM);
  spr.drawString("Pepper says:", 6, 13);

  // Speech text
  if (strlen(g_speech) == 0) {
    spr.setTextFont(2);
    spr.setTextColor(0x4208, TFT_BLACK);
    spr.setTextDatum(TL_DATUM);
    spr.drawString("(nothing yet)", 6, 36);
  } else {
    wrapText(g_speech, 6, 36, W - 12, 22, TFT_WHITE);
  }

  // Footer hint
  spr.setTextFont(1);
  spr.setTextColor(0x4208, TFT_BLACK);
  spr.setTextDatum(BC_DATUM);
  spr.drawString("[A] back", CX, H - 4);

  spr.pushSprite(0, 0);
}

// ── BLE receive ───────────────────────────────────────────────────────────────

static char bleBuf[512];
static int  bleLen = 0;

static void parseLine(const char* s) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, s) != DeserializationError::Ok) return;
  if (doc["mood"].is<const char*>())     strlcpy(g_mood,     doc["mood"],     sizeof(g_mood));
  if (doc["activity"].is<const char*>()) strlcpy(g_activity, doc["activity"], sizeof(g_activity));
  if (doc["speech"].is<const char*>())   strlcpy(g_speech,   doc["speech"],   sizeof(g_speech));
}

static void pollBle() {
  while (bleAvailable()) {
    int ch = bleRead();
    if (ch == '\n' || bleLen >= 510) {
      bleBuf[bleLen] = '\0';
      if (bleLen > 0) parseLine(bleBuf);
      bleLen = 0;
    } else {
      bleBuf[bleLen++] = (char)ch;
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

  // Side button (A): toggle face ↔ speech; auto-returns after 10 s
  if (M5.BtnA.wasPressed()) {
    if (uiMode == MODE_FACE) {
      uiMode = MODE_SPEECH;
      speechUntil = t + 10000;
    } else {
      uiMode = MODE_FACE;
    }
  }

  // Front button (B): back to face from anywhere
  if (M5.BtnB.wasPressed()) uiMode = MODE_FACE;

  if (uiMode == MODE_SPEECH && t > speechUntil) uiMode = MODE_FACE;

  if (uiMode == MODE_FACE) drawFaceScreen(t);
  else                     drawSpeechScreen();

  delay(30);   // ~33 fps
}
