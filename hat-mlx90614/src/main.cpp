#include <M5StickCPlus.h>
#include <Free_Fonts.h>
#include <Wire.h>
#include <Adafruit_MLX90614.h>

Adafruit_MLX90614 mlx;
bool useCelsius = true;

static const int W = 135;
static const int H = 240;

static const uint16_t BG            = TFT_BLACK;
static const uint16_t M5_ORANGE     = 0xFC40;
static const uint16_t M5_ORANGE_DIM = 0x9200;
static const uint16_t GREY_LINE     = 0x2945;

static const float RANGE_MIN_C = -70.0f;
static const float RANGE_MAX_C = 380.0f;

static const int BAR_L      = 120;
static const int BAR_W      = 14;
static const int BAR_TOP    = 10;
static const int BAR_BOTTOM = 230;
static const int BAR_H      = BAR_BOTTOM - BAR_TOP;

// Track previous indicator positions to restore bar colour underneath
static int prevObjY = -1;
static int prevAmbY = -1;

int barY(float tempC) {
    float c = tempC < RANGE_MIN_C ? RANGE_MIN_C
            : tempC > RANGE_MAX_C ? RANGE_MAX_C : tempC;
    return BAR_TOP + (int)((RANGE_MAX_C - c) / (RANGE_MAX_C - RANGE_MIN_C) * BAR_H);
}

// Return the bar segment colour for a given y pixel
uint16_t barColor(int y) {
    int y100 = barY(100.0f);
    int y375 = barY(37.5f);
    int y0   = barY(0.0f);
    if (y < y100) return M5.Lcd.color565(200, 40,  40);   // red
    if (y < y375) return M5.Lcd.color565(220, 120, 20);   // orange
    if (y < y0  ) return M5.Lcd.color565(30,  180, 140);  // teal
    return              M5.Lcd.color565(40,  80,  200);   // blue
}

float toDisplay(float c) {
    return useCelsius ? c : c * 9.0f / 5.0f + 32.0f;
}

// Called once — draws everything that never changes
void drawStatic() {
    M5.Lcd.fillScreen(BG);

    // Bar colour zones
    int y100 = barY(100.0f);
    int y375 = barY(37.5f);
    int y0   = barY(0.0f);
    M5.Lcd.fillRect(BAR_L, BAR_TOP,        BAR_W, y100 - BAR_TOP,        M5.Lcd.color565(200, 40,  40));
    M5.Lcd.fillRect(BAR_L, y100,           BAR_W, y375 - y100,           M5.Lcd.color565(220, 120, 20));
    M5.Lcd.fillRect(BAR_L, y375,           BAR_W, y0   - y375,           M5.Lcd.color565(30,  180, 140));
    M5.Lcd.fillRect(BAR_L, y0,             BAR_W, BAR_BOTTOM - y0,       M5.Lcd.color565(40,  80,  200));

    // Divider
    M5.Lcd.fillRect(8, 172, 104, 1, GREY_LINE);

    // Hint
    M5.Lcd.setTextFont(1);
    M5.Lcd.setTextSize(1);
    M5.Lcd.setTextColor(GREY_LINE, BG);
    M5.Lcd.setTextDatum(BC_DATUM);
    M5.Lcd.drawString("A: C / F", 60, H - 6);
}

// Called every tick — only touches dynamic areas
void updateReadings(float ambC, float objC) {
    // ── Main reading ─────────────────────────────────────────────────────────
    char numBuf[8];
    snprintf(numBuf, sizeof(numBuf), "%.1f", toDisplay(objC));

    M5.Lcd.fillRect(0, 55, 114, 75, BG);   // erase old number
    M5.Lcd.setFreeFont(FSSB24);
    M5.Lcd.setTextDatum(MC_DATUM);
    M5.Lcd.setTextColor(TFT_WHITE, BG);
    M5.Lcd.drawString(numBuf, 57, 90);

    // ── Unit ─────────────────────────────────────────────────────────────────
    char unitBuf[5];
    snprintf(unitBuf, sizeof(unitBuf), "\xB0%s", useCelsius ? "C" : "F");

    M5.Lcd.fillRect(0, 125, 114, 45, BG);  // erase old unit
    M5.Lcd.setFreeFont(FSS18);
    M5.Lcd.setTextColor(M5_ORANGE, BG);
    M5.Lcd.drawString(unitBuf, 57, 148);

    // ── Ambient (number only, no label or unit) ───────────────────────────────
    char ambBuf[8];
    snprintf(ambBuf, sizeof(ambBuf), "%.1f", toDisplay(ambC));

    M5.Lcd.fillRect(0, 178, 114, 38, BG);  // erase old ambient
    M5.Lcd.setFreeFont(FSS12);
    M5.Lcd.setTextColor(M5_ORANGE_DIM, BG);
    M5.Lcd.drawString(ambBuf, 57, 197);

    // ── Bar indicators ────────────────────────────────────────────────────────
    // Restore bar colour under previous indicators
    auto restoreBar = [](int y, int h) {
        if (y < 0) return;
        for (int row = y; row < y + h; row++) {
            M5.Lcd.fillRect(BAR_L, row, BAR_W, 1, barColor(row));
        }
    };
    restoreBar(prevObjY - 2, 4);
    restoreBar(prevAmbY - 1, 3);

    // Draw new indicators
    int yObj = barY(objC);
    int yAmb = barY(ambC);
    M5.Lcd.fillRect(BAR_L, yObj - 2, BAR_W, 4, TFT_WHITE);
    M5.Lcd.fillRect(BAR_L, yAmb - 1, BAR_W, 3, M5_ORANGE);

    prevObjY = yObj;
    prevAmbY = yAmb;
}

void setup() {
    M5.begin();
    M5.Lcd.setRotation(0);
    M5.Lcd.fillScreen(BG);
    M5.Lcd.setFreeFont(FSS18);
    M5.Lcd.setTextDatum(MC_DATUM);
    M5.Lcd.setTextColor(M5_ORANGE, BG);
    M5.Lcd.drawString("Starting", 60, H / 2);

    Wire.begin(0, 26);

    if (!mlx.begin(MLX90614_I2CADDR, &Wire)) {
        M5.Lcd.fillScreen(BG);
        M5.Lcd.setTextColor(TFT_RED, BG);
        M5.Lcd.drawString("sensor", 60, H / 2 - 25);
        M5.Lcd.drawString("not found", 60, H / 2 + 25);
        while (true) delay(1000);
    }

    drawStatic();
}

void loop() {
    M5.update();

    if (M5.BtnA.wasPressed()) {
        useCelsius = !useCelsius;
        prevObjY = prevAmbY = -1;  // force full indicator redraw
        drawStatic();               // redraw (unit didn't change the bar but keeps it clean)
    }

    float ambC = mlx.readAmbientTempC();
    float objC = mlx.readObjectTempC();

    if (!isnan(ambC) && !isnan(objC)) {
        updateReadings(ambC, objC);
    }

    delay(300);
}
