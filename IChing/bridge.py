#!/usr/bin/env python3
"""
IChing BLE Bridge — connects to the M5StickC S3 IChing device, receives
hexagram cast events, asks Claude for a deep interpretation, and sends
the response back for display on the device.

Usage:
    ANTHROPIC_API_KEY=sk-... python3 bridge.py

Requirements:
    pip install bleak anthropic
"""
import asyncio
import json
import os
import sys
import anthropic
from bleak import BleakScanner, BleakClient

NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # device → host (notify)
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # host → device (write)
DEVICE_PREFIX = "IChing-"

ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

LINE_NAMES = {6: "old yin (→yang)", 7: "young yang", 8: "young yin", 9: "old yang (→yin)"}

async def ask_claude(evt: dict) -> str:
    lines = evt.get("lines", [])
    primary_num  = evt.get("primary", 0)
    primary_zh   = evt.get("primary_zh", "")
    primary_en   = evt.get("primary_en", "")
    relating_num = evt.get("relating", 0)
    relating_zh  = evt.get("relating_zh", "")
    relating_en  = evt.get("relating_en", "")
    has_relating = evt.get("has_relating", False)

    moving = [i + 1 for i, v in enumerate(lines) if v in (6, 9)]
    lines_desc = ", ".join(f"line{i+1}={LINE_NAMES.get(v, v)}" for i, v in enumerate(lines))

    relating_part = (
        f"Relating hexagram (outcome): #{relating_num} {relating_zh} ({relating_en})"
        if has_relating else "No relating hexagram — stable cast, no movement."
    )

    prompt = f"""You are a wise I Ching oracle. Give a direct, insightful interpretation.

Cast result:
- Primary hexagram: #{primary_num} {primary_zh} ({primary_en})
- Lines (bottom→top): {lines_desc}
- Moving lines: {moving if moving else 'none'}
- {relating_part}

Respond in 2–3 sentences maximum. Be specific to this hexagram and its moving lines.
Speak directly to the person holding the oracle — practical, present-tense guidance.
Keep it under 55 words so it fits a small screen."""

    msg = ai.messages.create(
        model="claude-opus-4-7",
        max_tokens=160,
        system="You are a concise I Ching oracle. Respond only with the reading — no preamble, no sign-off.",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


async def run():
    print("Scanning for IChing device (by name or NUS service UUID)...")
    device = None
    while device is None:
        found = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for addr, (d, adv) in found.items():
            name_match = d.name and d.name.startswith(DEVICE_PREFIX)
            svc_match  = NUS_TX[:8] in str(adv.service_uuids).lower() or \
                         "6e400001" in str(adv.service_uuids).lower()
            if name_match or svc_match:
                print(f"  found: {d.name!r} ({addr}) services={adv.service_uuids}")
                device = d
                break
        if device is None:
            names = [d.name for d, _ in found.values() if d.name]
            print(f"  not found (saw: {names}), retrying...")

    print(f"Found: {device.name}  ({device.address})")

    line_buf = ""

    async def handle_cast(client: BleakClient, evt: dict):
        print(f"Hexagram cast: primary=#{evt.get('primary')} {evt.get('primary_en')}, "
              f"relating=#{evt.get('relating')} {evt.get('relating_en')}, "
              f"lines={evt.get('lines')}")
        print("Querying Claude...")
        try:
            text = await ask_claude(evt)
        except Exception as e:
            text = f"Oracle unavailable: {e}"
        print(f"Response ({len(text)} chars): {text}")
        payload = json.dumps({"speech": text}, ensure_ascii=False) + "\n"
        await client.write_gatt_char(NUS_RX, payload.encode("utf-8"), response=False)

    def on_notify(_, data: bytearray):
        nonlocal line_buf
        line_buf += data.decode("utf-8", errors="ignore")
        while "\n" in line_buf:
            line, line_buf = line_buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("evt") == "iching":
                asyncio.ensure_future(handle_cast(ble_client, evt))

    async with BleakClient(device.address) as client:
        # store for closure
        global ble_client
        ble_client = client
        print("Connected. Subscribing to notifications...")
        await client.start_notify(NUS_TX, on_notify)
        print("Ready — shake the device to cast a hexagram. (Ctrl-C to quit)\n")
        while client.is_connected:
            await asyncio.sleep(1)
        print("Device disconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nDone.")
