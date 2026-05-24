#!/usr/bin/env python3
"""
Standalone Pepper TTS tester.

Usage:
    python3 pepper_say.py 'hello world'
    AUDIO_RATE=16000 SAY_VOICE=Samantha python3 pepper_say.py 'hello world'

Scans for Pepper's BLE device, connects, streams TTS audio, then exits.
"""

import array
import asyncio
import json
import os
import struct
import subprocess
import sys
import tempfile
import wave

from bleak import BleakClient, BleakScanner

NUS_SVC = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

AUDIO_RATE    = int(os.getenv("AUDIO_RATE", "16000"))
SAY_VOICE     = os.getenv("SAY_VOICE", "Samantha")
VOLUME_BOOST  = float(os.getenv("VOLUME_BOOST", "3.0"))
AUDIO_MAGIC   = b"\xaa"
_ATT_MAX      = 176   # MTU-3=182, minus 3-byte frame header, rounded even
AUDIO_PAYLOAD = min(AUDIO_RATE * 22 // 1000, _ATT_MAX)


async def find_pepper() -> str:
    print("Scanning for Pepper (NUS service)...")
    while True:
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for _, (d, adv) in devices.items():
            svcs = [str(s).lower() for s in (adv.service_uuids or [])]
            if NUS_SVC in svcs:
                print(f"Found {d.name or 'unnamed'} at {d.address}")
                return d.address
        print("Not found — retrying...")


def _tts_pcm(text: str) -> bytes:
    print(f"TTS: '{text}' via say ({SAY_VOICE}) @ {AUDIO_RATE} Hz")
    with tempfile.TemporaryDirectory() as tmp:
        aiff  = f"{tmp}/s.aiff"
        wav16 = f"{tmp}/s16.wav"
        subprocess.run(
            ["say", "-v", SAY_VOICE, "-o", aiff, "--", text],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["afconvert", aiff, wav16, "-f", "WAVE",
             "-d", f"LEI16@{AUDIO_RATE}", "-c", "1", "-q", "127"],
            check=True, capture_output=True,
        )
        with wave.open(wav16, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
    samples = array.array("h", raw)
    for i, s in enumerate(samples):
        samples[i] = max(-32768, min(32767, int(s * VOLUME_BOOST)))
    pcm = samples.tobytes()
    print(f"PCM: {len(pcm)} bytes (~{len(pcm)//(AUDIO_RATE*2):.1f}s)")
    return pcm


async def stream(client: BleakClient, text: str) -> None:
    # update display
    payload = json.dumps({"speech": text, "mood": "happy", "activity": "talking"},
                         separators=(",", ":")) + "\n"
    for i in range(0, len(payload), 20):
        await client.write_gatt_char(NUS_RX, payload[i:i+20].encode(), response=False)

    pcm = await asyncio.get_event_loop().run_in_executor(None, _tts_pcm, text)

    print(f"Streaming {len(pcm)//AUDIO_PAYLOAD + 1} frames...")
    for i in range(0, len(pcm), AUDIO_PAYLOAD):
        chunk = pcm[i:i + AUDIO_PAYLOAD]
        frame = AUDIO_MAGIC + struct.pack("<H", len(chunk)) + chunk
        await client.write_gatt_char(NUS_RX, frame, response=False)
        await asyncio.sleep(len(chunk) / (AUDIO_RATE * 2) * 0.85)

    # end-of-stream sentinel triggers playRaw on firmware
    await client.write_gatt_char(NUS_RX, AUDIO_MAGIC + b"\x00\x00", response=False)
    # wait for playback to finish before disconnecting
    duration = len(pcm) / (AUDIO_RATE * 2)
    print(f"Waiting {duration:.1f}s for playback...")
    # Extra 1.5s: firmware loop runs at ~60ms/iter, playRaw fires after EOS
    # is polled, and the Speaker task needs a moment to start I2S output.
    await asyncio.sleep(duration + 1.5)
    print("Done.")


async def main(text: str) -> None:
    address = await find_pepper()
    async with BleakClient(address) as ble:
        print("Connected.")
        await stream(ble, text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pepper_say.py 'text to say'")
        sys.exit(1)
    asyncio.run(main(" ".join(sys.argv[1:])))
