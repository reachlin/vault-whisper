#pragma once
#include <stdint.h>
#include <stddef.h>

// Nordic UART Service (NUS) BLE bridge — unencrypted for easy Python/bleak pairing.
// Service  6e400001-b5a3-f393-e0a9-e50e24dcca9e
// RX char  6e400002  (host → device, WRITE)
// TX char  6e400003  (device → host, NOTIFY)

void   bleInit(const char* deviceName);
bool   bleConnected();
size_t bleAvailable();
int    bleRead();
size_t bleWrite(const uint8_t* data, size_t len);
