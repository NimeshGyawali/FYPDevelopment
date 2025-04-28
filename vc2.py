#!/usr/bin/env python3


import os
import time
import wave
import tempfile
import subprocess
import requests
import numpy as np

import pvporcupine
import pyaudio
import whisper

# ─── CONFIG ────────────────────────────────────────────────────────────────
ACCESS_KEY         = os.getenv("PICO_ACCESS_KEY",
                        "YfpcpbQh/5+jb/Qb19imj5uUHlHE5uHqLzSaK4+3GsNE3ZCzuzbgsA==")
WAKE_WORD          = os.getenv("WAKE_KEYWORD", "terminator")
PC_HOST            = os.getenv("PC_HOST",      "192.168.1.100")
FLASK_PORT         = os.getenv("FLASK_PORT",   "5000")
API_KEY            = os.getenv("API_KEY",      "fyp_super_secure_2025_key")
RECORD_SECONDS     = int(os.getenv("RECORD_SECONDS", "5"))
INPUT_DEVICE_INDEX = int(os.getenv("INPUT_DEVICE_INDEX", "1"))

VOICE_API_URL      = f"http://{PC_HOST}:{FLASK_PORT}/api/voice"

# ─── INITIALIZE MODELS & AUDIO ────────────────────────────────────────────

# 1) Porcupine wake-word detector
porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keywords=[WAKE_WORD]
)

# 2) PyAudio for capture
pa = pyaudio.PyAudio()
stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    input_device_index=INPUT_DEVICE_INDEX,
    frames_per_buffer=porcupine.frame_length
)

# 3) Whisper for transcription
whisper_model = whisper.load_model("base")
# ─── UTILS ────────────────────────────────────────────────────────────────

def tts(text: str):
    """
    Speak text by piping:
      espeak → sox (down to 16 kHz) → aplay on plughw:3,0
    """
    # 1) generate WAV on stdout
    p1 = subprocess.Popen(
        ["espeak", "--stdout", text],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    # 2) resample to 16 kHz
    p2 = subprocess.Popen(
        ["sox", "-t", "wav", "-", "-t", "wav", "-", "rate", "16000"],
        stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    p1.stdout.close()

    # 3) play on ReSpeaker
    subprocess.run(
        ["aplay", "-D", "plughw:3,0", "-q"],
        stdin=p2.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    p2.stdout.close()
    p1.wait()
    p2.wait()

def record_audio(duration: int) -> str:
    """
    Record `duration` seconds into a temp WAV file.
    Returns the filepath.
    """
    frames = []
    num_frames = int(porcupine.sample_rate / porcupine.frame_length * duration)
    for _ in range(num_frames):
        pcm = stream.read(porcupine.frame_length,
                          exception_on_overflow=False)
        frames.append(pcm)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(porcupine.sample_rate)
        wf.writeframes(b"".join(frames))
    return tmp.name
# ─── MAIN LOOP ────────────────────────────────────────────────────────────

def main():
    print("✅ Voice control ready. Say the wake-word…")
    try:
        while True:
            pcm = stream.read(porcupine.frame_length,
                              exception_on_overflow=False)
            if porcupine.process(np.frombuffer(pcm, np.int16)) >= 0:
                # Wake word detected
                tts("Yes?")

                # 1) Record your command
                wav_path = record_audio(RECORD_SECONDS)
                tts("Processing")

                # 2) Transcribe
                result = whisper_model.transcribe(wav_path)
                text = result.get("text","").strip()
                print("🗣 You said:", text)
                os.remove(wav_path)

                # 3) Send to your unified API
                if text:
                    try:
                        r = requests.post(
                            VOICE_API_URL,
                            json={"text": text},
                            headers={"x-api-key": API_KEY},
                            timeout=20
                        )
                        r.raise_for_status()
                        resp = r.json()
                        print("🔒 API response:", resp)
                    except Exception as e:
                        print("⚠️ API error:", e)
                else:
                    print("⚠️ No speech detected")

                # 4) Final feedback
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down…")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        porcupine.delete()

if __name__ == "__main__":
    main()