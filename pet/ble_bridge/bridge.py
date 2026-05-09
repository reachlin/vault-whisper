"""
BLE bridge: forwards simulator events to the M5Stack Pepper display + speaker.

Listens on the simulator WebSocket for three event types:
  {"type": "activity", "activity": "thinking"}
  {"type": "state",    "data": {"pet": {"mood": "happy", ...}}}
  {"type": "speak",    "text": "..."}

Display updates are sent as newline-terminated JSON (NUS RX channel):
  {"mood": "happy", "activity": "thinking", "speech": "INTC is $88.14"}

Audio frames use a compact binary protocol on the same NUS RX channel:
  0xAA + uint16_le_size + int16_le_pcm_data   (8 kHz, 16-bit signed LE mono)
  0xAA + 0x00 0x00                             (end of audio — silences speaker)

TTS backend (auto-selected):
  OPENAI_API_KEY set → OpenAI TTS (neural voice, recommended)
  otherwise          → macOS say + afconvert

Run on the host machine (macOS BLE can't be accessed from Docker):
  python ble_bridge/bridge.py

Environment variables:
  SIMULATOR_WS      ws://localhost:18080/ws   simulator WebSocket URL
  OPENAI_API_KEY    <key>                     enables OpenAI TTS (recommended)
  OPENAI_TTS_VOICE  nova                      OpenAI voice name
  SAY_VOICE         Samantha                  macOS fallback voice name
  VOLUME_BOOST      3.0                       PCM amplitude multiplier
"""

import array
import asyncio
import json
import logging
import os
import struct
import subprocess
import tempfile
import wave

import websockets
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SIMULATOR_WS      = os.getenv("SIMULATOR_WS", "ws://localhost:18080/ws")
SAY_VOICE         = os.getenv("SAY_VOICE", "Samantha")
OPENAI_TTS_VOICE  = os.getenv("OPENAI_TTS_VOICE", "alloy")
_OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")

NUS_SVC = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

AUDIO_MAGIC   = b"\xaa"
AUDIO_RATE    = 8000    # Hz — matches firmware AUDIO_RATE
AUDIO_PAYLOAD = 176     # PCM bytes per BLE frame (even number; 88 int16 samples per frame)


# ── BLE helpers ───────────────────────────────────────────────────────────────

async def find_pepper() -> str:
    """Scan until a device advertising Nordic UART Service appears (that's Pepper).

    Matches by NUS UUID rather than device name because macOS caches BLE names
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


async def ble_write_json(client: BleakClient, payload: dict) -> None:
    data = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
    # chunk to 20 bytes as a safe fallback before MTU negotiation completes
    MTU = 20
    for i in range(0, len(data), MTU):
        await client.write_gatt_char(NUS_RX, data[i : i + MTU], response=False)


# ── TTS + audio streaming ─────────────────────────────────────────────────────

VOLUME_BOOST = float(os.getenv("VOLUME_BOOST", "3.0"))  # 1.0 = unity


def _boost_and_pack16(pcm16_raw: bytes) -> bytes:
    """Boost signed 16-bit LE PCM in place and return as signed 16-bit LE.

    Sent directly to firmware — no bit-depth reduction, so no quantisation noise.
    """
    samples = array.array("h", pcm16_raw)   # signed 16-bit little-endian
    for i, s in enumerate(samples):
        v = int(s * VOLUME_BOOST)
        samples[i] = max(-32768, min(32767, v))
    return samples.tobytes()


def _macos_tts_to_pcm(text: str) -> bytes:
    """macOS say → AIFF → 16-bit 8 kHz WAV (max quality SRC) → boosted 8-bit."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff  = os.path.join(tmp, "s.aiff")
        wav16 = os.path.join(tmp, "s16.wav")
        subprocess.run(
            ["say", "-v", SAY_VOICE, "-o", aiff, "--", text],
            check=True, capture_output=True,
        )
        # -q 127: highest quality sample-rate conversion
        subprocess.run(
            ["afconvert", aiff, wav16, "-f", "WAVE", "-d", "LEI16@8000", "-c", "1", "-q", "127"],
            check=True, capture_output=True,
        )
        with wave.open(wav16, "rb") as wf:
            return _boost_and_pack16(wf.readframes(wf.getnframes()))


def _openai_tts_to_pcm(text: str) -> bytes:
    """OpenAI TTS → WAV (24 kHz) → 8 kHz 8-bit via afconvert."""
    from openai import OpenAI
    client = OpenAI(api_key=_OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=OPENAI_TTS_VOICE,
        input=text,
        response_format="wav",
    )
    with tempfile.TemporaryDirectory() as tmp:
        in_wav  = os.path.join(tmp, "openai.wav")
        out_wav = os.path.join(tmp, "out16.wav")
        in_wav_bytes = b"".join(response.iter_bytes())
        with open(in_wav, "wb") as f:
            f.write(in_wav_bytes)
        subprocess.run(
            ["afconvert", in_wav, out_wav, "-f", "WAVE", "-d", "LEI16@8000", "-c", "1", "-q", "127"],
            check=True, capture_output=True,
        )
        with wave.open(out_wav, "rb") as wf:
            return _boost_and_pack16(wf.readframes(wf.getnframes()))


def _tts_to_pcm(text: str) -> bytes:
    log.info("TTS: macOS say (%s)", SAY_VOICE)
    return _macos_tts_to_pcm(text)


async def stream_audio(client: BleakClient, text: str) -> None:
    """Generate TTS audio and stream it to the M5Stack in PCM frames."""
    try:
        pcm = await asyncio.get_event_loop().run_in_executor(None, _tts_to_pcm, text)
    except Exception as e:
        log.warning("TTS failed: %s", e)
        return

    log.info("streaming %d bytes of audio for: %s", len(pcm), text[:60])
    for i in range(0, len(pcm), AUDIO_PAYLOAD):
        chunk = pcm[i : i + AUDIO_PAYLOAD]
        frame = AUDIO_MAGIC + struct.pack("<H", len(chunk)) + chunk
        await client.write_gatt_char(NUS_RX, frame, response=False)
        # pace slightly faster than playback rate so the DMA buffer stays full
        # len(chunk) is bytes; divide by 2 for 16-bit samples, then by sample rate
        await asyncio.sleep(len(chunk) / (AUDIO_RATE * 2) * 0.85)

    # end-of-audio sentinel — silences the DMA buffer
    await client.write_gatt_char(NUS_RX, AUDIO_MAGIC + b"\x00\x00", response=False)
    log.info("audio stream complete")


# ── Main bridge loop ──────────────────────────────────────────────────────────

async def run_bridge(address: str) -> None:
    async with BleakClient(address) as ble:
        log.info("BLE connected")

        mood     = "neutral"
        activity = "idle"
        audio_task: asyncio.Task | None = None

        await ble_write_json(ble, {"mood": mood, "activity": activity, "speech": ""})

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
                        await ble_write_json(ble, {"mood": mood, "activity": activity})
                        log.info("mood → %s", mood)

                elif kind == "activity":
                    new_act = msg.get("activity", activity)
                    if new_act != activity:
                        activity = new_act
                        await ble_write_json(ble, {"activity": activity, "mood": mood})
                        log.info("activity → %s", activity)

                elif kind == "speak":
                    text = msg.get("text", "")
                    if text:
                        await ble_write_json(
                            ble, {"speech": text, "mood": mood, "activity": activity}
                        )
                        log.info("speech → %s", text[:60])
                        # cancel any in-progress audio before starting new one
                        if audio_task and not audio_task.done():
                            audio_task.cancel()
                        audio_task = asyncio.create_task(stream_audio(ble, text))


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
