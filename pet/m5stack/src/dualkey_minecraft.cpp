// BLE Minecraft controller for M5Stack Chain DualKey + 2× Chain Joystick
// Uses Bluedroid BLE stack (BLEDevice.h) matching official M5Stack examples.
//
// G5/G6  port (Key2 side)  → left joystick  → WASD movement
// G47/G48 port (Key1 side) → right joystick → mouse look
// G0  KEY_1 (farther from lanyard)  → left click (mine/attack)
// G17 KEY_2 (closer to lanyard)     → space (jump)
//
// Set hardware switch to BLE before powering on.

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEHIDDevice.h>
#include <HIDTypes.h>
#include <M5Chain.h>

// ── Pins ────────────────────────────────────────────────────────────────────
#define L_RX GPIO_NUM_5
#define L_TX GPIO_NUM_6
#define R_RX GPIO_NUM_47
#define R_TX GPIO_NUM_48
#define PIN_BTN_L 0   // KEY_1 — left click
#define PIN_BTN_R 17  // KEY_2 — jump (space)

// ── Tuning ───────────────────────────────────────────────────────────────────
#define DEADZONE    20
#define MOUSE_SPEED 10
#define LOOP_MS     16

// ── Combined keyboard (ID 1) + mouse (ID 2) HID descriptor ──────────────────
static const uint8_t kHidDesc[] = {
    0x05,0x01, 0x09,0x06, 0xA1,0x01,
    0x85,0x01,
    0x75,0x01, 0x95,0x08, 0x05,0x07, 0x19,0xE0, 0x29,0xE7, 0x15,0x00, 0x25,0x01, 0x81,0x02,
    0x75,0x08, 0x95,0x01, 0x81,0x01,
    0x75,0x08, 0x95,0x06, 0x05,0x07, 0x19,0x00, 0x29,0x65, 0x15,0x00, 0x25,0x65, 0x81,0x00,
    0xC0,
    0x05,0x01, 0x09,0x02, 0xA1,0x01,
    0x85,0x02,
    0x09,0x01, 0xA1,0x00,
    0x05,0x09, 0x19,0x01, 0x29,0x02, 0x15,0x00, 0x25,0x01, 0x75,0x01, 0x95,0x02, 0x81,0x02,
    0x75,0x06, 0x95,0x01, 0x81,0x01,
    0x05,0x01, 0x09,0x30, 0x09,0x31, 0x15,0x81, 0x25,0x7F, 0x75,0x08, 0x95,0x02, 0x81,0x06,
    0xC0, 0xC0,
};

static const uint8_t KEY_W = 0x1A, KEY_A = 0x04,
                     KEY_S = 0x16, KEY_D = 0x07, KEY_SPACE = 0x2C;

static BLEHIDDevice*      hid        = nullptr;
static BLECharacteristic* inputKb    = nullptr;
static BLECharacteristic* inputMouse = nullptr;
static bool connected = false;

static uint8_t kbReport[8]    = {};
static uint8_t mouseReport[3] = {};

Chain leftChain;
Chain rightChain;
static uint8_t leftJoyId  = 1;
static uint8_t rightJoyId = 1;

class ServerCB : public BLEServerCallbacks {
    void onConnect(BLEServer*)    override { connected = true; }
    void onDisconnect(BLEServer*) override {
        connected = false;
        BLEDevice::startAdvertising();
    }
};

static void setKey(uint8_t code, bool on) {
    for (int i = 2; i < 8; i++) {
        if (on  && kbReport[i] == code) return;
        if (on  && kbReport[i] == 0)    { kbReport[i] = code; return; }
        if (!on && kbReport[i] == code) { kbReport[i] = 0;    return; }
    }
}

static int8_t toMouseDelta(int8_t v) {
    if (abs(v) < DEADZONE) return 0;
    return (int8_t)constrain((int)((float)v / 100.0f * MOUSE_SPEED), -127, 127);
}

// Discovers the first joystick device ID on a chain bus. Returns 1 on failure.
static uint8_t discoverJoystick(Chain& chain, const char* label) {
    if (!chain.isDeviceConnected()) {
        Serial.printf("[%s] no device\n", label);
        return 1;
    }
    uint16_t count = 0;
    if (chain.getDeviceNum(&count) != CHAIN_OK || count == 0) {
        Serial.printf("[%s] getDeviceNum failed\n", label);
        return 1;
    }
    device_list_t list;
    list.count   = count;
    list.devices = (device_info_t*)malloc(sizeof(device_info_t) * count);
    uint8_t found = 1;
    if (chain.getDeviceList(&list)) {
        for (int i = 0; i < (int)count; i++) {
            Serial.printf("[%s] dev%d id=%d type=0x%04X\n",
                label, i, list.devices[i].id, list.devices[i].device_type);
            if (list.devices[i].device_type == CHAIN_JOYSTICK_TYPE_CODE) {
                found = list.devices[i].id;
            }
        }
    } else {
        Serial.printf("[%s] getDeviceList failed\n", label);
    }
    free(list.devices);
    return found;
}

void setup() {
    Serial.begin(115200);
    delay(3000);
    Serial.println("Boot: initializing Chain Bus...");
    pinMode(PIN_BTN_L, INPUT);
    pinMode(PIN_BTN_R, INPUT);

    leftChain.begin(&Serial1, 115200, L_RX, L_TX);
    delay(1000);
    rightChain.begin(&Serial2, 115200, R_RX, R_TX);
    delay(1000);

    leftJoyId  = discoverJoystick(leftChain,  "LEFT");
    rightJoyId = discoverJoystick(rightChain, "RIGHT");
    Serial.printf("Joystick IDs: left=%d right=%d\n", leftJoyId, rightJoyId);

    BLEDevice::init("DualKey MC");
    BLEServer* srv = BLEDevice::createServer();
    srv->setCallbacks(new ServerCB());

    hid = new BLEHIDDevice(srv);
    hid->manufacturer()->setValue("M5Stack");
    hid->pnp(0x02, 0x045E, 0x0B12, 0x0110);
    hid->hidInfo(0x00, 0x01);
    hid->reportMap((uint8_t*)kHidDesc, sizeof(kHidDesc));

    inputKb    = hid->inputReport(1);
    inputMouse = hid->inputReport(2);
    hid->startServices();

    BLESecurity* sec = new BLESecurity();
    sec->setAuthenticationMode(ESP_LE_AUTH_BOND);

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->setAppearance(HID_KEYBOARD);
    adv->addServiceUUID(hid->hidService()->getUUID());
    adv->start();
    Serial.println("BLE advertising started.");
}

void loop() {
    if (!connected) { delay(100); return; }

    int8_t lx = 0, ly = 0, rx = 0, ry = 0;
    leftChain.getJoystickMappedInt8Value(leftJoyId, &lx, &ly);
    rightChain.getJoystickMappedInt8Value(rightJoyId, &rx, &ry);

    static uint32_t lastLog = 0;
    if (millis() - lastLog > 500) {
        Serial.printf("L(id=%d) x=%d y=%d  R(id=%d) x=%d y=%d  btnL=%d btnR=%d\n",
            leftJoyId, lx, ly, rightJoyId, rx, ry,
            digitalRead(PIN_BTN_L), digitalRead(PIN_BTN_R));
        lastLog = millis();
    }

    // rightChain = Key2-side joystick → WASD
    // leftChain  = Key1-side joystick → mouse look
    setKey(KEY_W, ry < -DEADZONE);
    setKey(KEY_S, ry >  DEADZONE);
    setKey(KEY_A, rx >  DEADZONE);
    setKey(KEY_D, rx < -DEADZONE);
    setKey(KEY_SPACE, digitalRead(PIN_BTN_L) == LOW);
    inputKb->setValue(kbReport, sizeof(kbReport));
    inputKb->notify();

    bool click = digitalRead(PIN_BTN_R) == LOW;
    mouseReport[0] = click ? 0x01 : 0x00;
    mouseReport[1] = (uint8_t)toMouseDelta(lx);
    mouseReport[2] = (uint8_t)toMouseDelta(ly);
    inputMouse->setValue(mouseReport, sizeof(mouseReport));
    inputMouse->notify();

    delay(LOOP_MS);
}
