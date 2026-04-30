# M5StickC Plus — Claude Desktop Buddy Setup

## Hardware

- **Device:** M5Stack Stick C Plus (ESP32)
- **USB port detected:** `/dev/cu.usbserial-7952E01338`
- **Battery:** built-in, runs over BLE after flashing (no USB needed)

## Prerequisites

```bash
brew install platformio
pio --version  # 6.1.19
```

## Flash Firmware

From `/Users/lincai/dev/claude-desktop-buddy`:

```bash
pio run -t upload
```

First run downloads ~300MB of ESP32 toolchain and Arduino framework — takes ~4 min. Subsequent flashes are fast.

If previously flashed with something else, wipe first:

```bash
pio run -t erase && pio run -t upload
```

platformio.ini settings used:

```ini
[env:m5stickc-plus]
platform = espressif32
board = m5stick-c
framework = arduino
monitor_speed = 115200
board_build.filesystem = littlefs
board_build.partitions = no_ota.csv
board_build.f_cpu = 160000000L
lib_deps =
    m5stack/M5StickCPlus
    bitbank2/AnimatedGIF @ ^2.1.1
    bblanchon/ArduinoJson @ ^7.0.0
```

## Pair with Claude Desktop

1. Open Claude for macOS
2. **Help → Troubleshooting → Enable Developer Mode**
3. A new **Developer** menu appears in the macOS menu bar
4. **Developer → Open Hardware Buddy…**
5. Click **Connect**, pick device from list
6. Grant Bluetooth permission when macOS prompts

Unplug USB after pairing — device runs on battery over BLE. Auto-reconnects whenever both Claude and the device are awake.

## Controls

| Button | Action |
|---|---|
| A (front) | next screen / **approve** prompt |
| B (right) | scroll / **deny** prompt |
| Hold A | menu |
| Power short | toggle screen off |
| Power ~6s | hard power off |
| Shake | dizzy animation |
| Face-down | nap (recharges energy) |

## Pet States

| State | Trigger |
|---|---|
| `sleep` | BLE not connected |
| `idle` | connected, nothing happening |
| `busy` | Claude session active |
| `attention` | approval prompt pending (LED blinks) |
| `celebrate` | every 50K tokens |
| `dizzy` | shook the device |
| `heart` | approved prompt in under 5s |

## Factory Reset (from device)

Hold A → Settings → Reset → Factory Reset → tap twice
