#include <M5StickCPlus.h>
#include <Wire.h>
#include <Adafruit_MLX90614.h>

// MLX90614 is on the HAT port: SDA=GPIO0, SCL=GPIO26
Adafruit_MLX90614 mlx;
bool useCelsius = true;

float toDisplay(float c) {
    return useCelsius ? c : c * 9.0f / 5.0f + 32.0f;
}

const char* unit() { return useCelsius ? "C" : "F"; }

// Returns colour based on object temp in Celsius
uint16_t feverColor(float objC) {
    if (objC >= 37.5f) return TFT_RED;
    if (objC >= 36.5f) return TFT_YELLOW;
    return TFT_GREEN;
}

void drawScreen(float ambC, float objC) {
    uint16_t col = feverColor(objC);

    M5.Lcd.fillScreen(TFT_BLACK);

    // ── Object temp (big, centred) ──────────────────────────────────────────
    M5.Lcd.setTextDatum(MC_DATUM);
    M5.Lcd.setTextColor(col, TFT_BLACK);
    M5.Lcd.setTextSize(4);
    char buf[16];
    snprintf(buf, sizeof(buf), "%.1f %s", toDisplay(objC), unit());
    M5.Lcd.drawString(buf, M5.Lcd.width() / 2, 55);

    // ── Status label ────────────────────────────────────────────────────────
    M5.Lcd.setTextSize(2);
    const char* label = (objC >= 37.5f) ? "FEVER"
                      : (objC >= 36.5f) ? "ELEVATED"
                                        : "NORMAL";
    M5.Lcd.drawString(label, M5.Lcd.width() / 2, 95);

    // ── Ambient (small, bottom-left) ─────────────────────────────────────
    M5.Lcd.setTextDatum(BL_DATUM);
    M5.Lcd.setTextColor(TFT_DARKGREY, TFT_BLACK);
    M5.Lcd.setTextSize(1);
    snprintf(buf, sizeof(buf), "Amb %.1f%s", toDisplay(ambC), unit());
    M5.Lcd.drawString(buf, 4, M5.Lcd.height() - 4);

    // ── Button hint (small, bottom-right) ───────────────────────────────
    M5.Lcd.setTextDatum(BR_DATUM);
    M5.Lcd.drawString("A:C/F", M5.Lcd.width() - 4, M5.Lcd.height() - 4);
}

void setup() {
    M5.begin();
    M5.Lcd.setRotation(3);  // landscape, power button on right
    M5.Lcd.fillScreen(TFT_BLACK);
    M5.Lcd.setTextDatum(MC_DATUM);
    M5.Lcd.setTextColor(TFT_WHITE, TFT_BLACK);
    M5.Lcd.setTextSize(2);
    M5.Lcd.drawString("Starting...", M5.Lcd.width() / 2, M5.Lcd.height() / 2);

    // HAT port I2C on GPIO0/26. Wire1 is taken by AXP192 (GPIO21/22) internally.
    Wire.begin(0, 26);

    if (!mlx.begin(MLX90614_I2CADDR, &Wire)) {
        M5.Lcd.fillScreen(TFT_RED);
        M5.Lcd.drawString("MLX90614", M5.Lcd.width() / 2, 50);
        M5.Lcd.drawString("not found!", M5.Lcd.width() / 2, 80);
        while (true) delay(1000);
    }

    M5.Lcd.fillScreen(TFT_BLACK);
}

void loop() {
    M5.update();

    if (M5.BtnA.wasPressed()) {
        useCelsius = !useCelsius;
    }

    float ambC = mlx.readAmbientTempC();
    float objC = mlx.readObjectTempC();

    if (!isnan(ambC) && !isnan(objC)) {
        drawScreen(ambC, objC);
    }

    delay(500);
}
