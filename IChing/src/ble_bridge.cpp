#include "ble_bridge.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Arduino.h>

#define NUS_SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_RX_UUID      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_TX_UUID      "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

static const size_t RX_CAP = 2048;
static uint8_t          rxBuf[RX_CAP];
static volatile size_t  rxHead = 0;
static volatile size_t  rxTail = 0;

static BLEServer*         g_server  = nullptr;
static BLECharacteristic* g_txChar  = nullptr;
static volatile bool      g_connected = false;
static volatile uint16_t  g_mtu    = 23;

static void rxPush(const uint8_t* p, size_t n) {
    for (size_t i = 0; i < n; i++) {
        size_t next = (rxHead + 1) % RX_CAP;
        if (next == rxTail) return;
        rxBuf[rxHead] = p[i];
        rxHead = next;
    }
}

class RxCB : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override {
        std::string v = c->getValue();
        if (!v.empty()) rxPush((const uint8_t*)v.data(), v.size());
    }
};

class SrvCB : public BLEServerCallbacks {
    void onConnect(BLEServer*) override {
        g_connected = true;
        BLEDevice::stopAdvertising();
        Serial.println("[ble] connected");
    }
    void onDisconnect(BLEServer*) override {
        g_connected = false;
        g_mtu = 23;
        BLEDevice::startAdvertising();
        Serial.println("[ble] disconnected, re-advertising");
    }
    void onMtuChanged(BLEServer*, esp_ble_gatts_cb_param_t* p) override {
        g_mtu = p->mtu.mtu;
        Serial.printf("[ble] mtu=%u\n", g_mtu);
    }
};

void bleInit(const char* name) {
    BLEDevice::init(name);
    BLEDevice::setMTU(517);

    g_server = BLEDevice::createServer();
    g_server->setCallbacks(new SrvCB());

    BLEService* svc = g_server->createService(NUS_SERVICE_UUID);

    g_txChar = svc->createCharacteristic(NUS_TX_UUID, BLECharacteristic::PROPERTY_NOTIFY);
    g_txChar->addDescriptor(new BLE2902());

    BLECharacteristic* rxChar = svc->createCharacteristic(
        NUS_RX_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );
    rxChar->setCallbacks(new RxCB());

    svc->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(NUS_SERVICE_UUID);
    adv->setScanResponse(true);
    adv->setMinPreferred(0x06);
    adv->setMaxPreferred(0x12);
    BLEDevice::startAdvertising();
    Serial.printf("[ble] advertising as '%s'\n", name);
}

bool bleConnected() { return g_connected; }

size_t bleAvailable() {
    return (rxHead + RX_CAP - rxTail) % RX_CAP;
}

int bleRead() {
    if (rxHead == rxTail) return -1;
    int b = rxBuf[rxTail];
    rxTail = (rxTail + 1) % RX_CAP;
    return b;
}

size_t bleWrite(const uint8_t* data, size_t len) {
    if (!g_connected || !g_txChar) return 0;
    size_t chunk = g_mtu > 3 ? g_mtu - 3 : 20;
    if (chunk > 180) chunk = 180;
    size_t sent = 0;
    while (sent < len) {
        size_t n = len - sent;
        if (n > chunk) n = chunk;
        g_txChar->setValue((uint8_t*)(data + sent), n);
        g_txChar->notify();
        sent += n;
        delay(4);
    }
    return sent;
}
