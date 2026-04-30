"""
BLE bridge: forwards simulator events to the M5Stack Pepper display.

Listens on the simulator WebSocket for three event types:
  {"type": "activity", "activity": "thinking"}
  {"type": "state",    "data": {"pet": {"mood": "happy", ...}}}
  {"type": "speak",    "text": "..."}

Sends newline-terminated JSON to M5Stack via Nordic UART BLE:
  {"mood": "happy", "activity": "thinking", "speech": "INTC is $88.14"}

Run on the host machine (macOS BLE can't be accessed from Docker):
  python ble_bridge/bridge.py

Environment variables:
  SIMULATOR_WS   ws://localhost:18080/ws   simulator WebSocket URL
"""

import asyncio
import json
import logging
import os

import websockets
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SIMULATOR_WS = os.getenv("SIMULATOR_WS", "ws://localhost:18080/ws")

# Nordic UART Service RX characteristic — write here to push data to M5Stack
NUS_SVC = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"   # Nordic UART Service
NUS_RX  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # write to push data to M5Stack
BLE_MTU = 20   # safe chunk before MTU negotiation


async def find_pepper() -> str:
    """Scan until a device advertising Nordic UART Service appears (that's Pepper).

    Matching by NUS UUID rather than device name because macOS caches BLE names
    and may still show the old name after a firmware reflash.
    """
    log.info("Scanning for Pepper BLE device (NUS service)...")
    while True:
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for _addr, (d, adv) in devices.items():
            svcs = [str(s).lower() for s in (adv.service_uuids or [])]
            if NUS_SVC in svcs:
                log.info("Found %s at %s", d.name or "unnamed", d.address)
                return d.address
        log.info("Not found — retrying in 3 s...")
        await asyncio.sleep(3)


async def ble_write(client: BleakClient, payload: dict) -> None:
    data = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
    for i in range(0, len(data), BLE_MTU):
        await client.write_gatt_char(NUS_RX, data[i : i + BLE_MTU], response=False)


async def run_bridge(address: str) -> None:
    async with BleakClient(address) as ble:
        log.info("BLE connected")

        mood     = "neutral"
        activity = "idle"

        # Push initial state so the display wakes up immediately
        await ble_write(ble, {"mood": mood, "activity": activity, "speech": ""})

        async with websockets.connect(SIMULATOR_WS) as ws:
            log.info("Simulator WebSocket connected at %s", SIMULATOR_WS)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                kind = msg.get("type")

                if kind == "state":
                    new_mood = msg.get("data", {}).get("pet", {}).get("mood", mood)
                    if new_mood != mood:
                        mood = new_mood
                        await ble_write(ble, {"mood": mood, "activity": activity})
                        log.info("mood → %s", mood)

                elif kind == "activity":
                    new_act = msg.get("activity", activity)
                    if new_act != activity:
                        activity = new_act
                        await ble_write(ble, {"activity": activity, "mood": mood})
                        log.info("activity → %s", activity)

                elif kind == "speak":
                    text = msg.get("text", "")
                    if text:
                        await ble_write(ble, {"speech": text, "mood": mood, "activity": activity})
                        log.info("speech → %s", text[:60])


async def main() -> None:
    address = await find_pepper()
    while True:
        try:
            await run_bridge(address)
        except Exception as e:
            log.warning("Lost connection: %s — reconnecting in 5 s...", e)
            await asyncio.sleep(5)
            address = await find_pepper()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
