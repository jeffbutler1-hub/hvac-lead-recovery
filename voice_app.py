from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from openai import OpenAI

import os
import json
import base64
import subprocess
import threading

app = FastAPI()

print("🚀 CLEAN APP LOADED")

# ---------------------------------------------------
# OpenAI client
# ---------------------------------------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ---------------------------------------------------
# Audio storage
# ---------------------------------------------------
audio_chunks = []

# ---------------------------------------------------
# Health check
# ---------------------------------------------------
@app.get("/")
async def root():
    return {"status": "running"}

# ---------------------------------------------------
# Incoming call webhook
# ---------------------------------------------------
@app.post("/incoming-call")
async def incoming_call():

    print("📞 INCOMING CALL HIT")

    twiml = """
<Response>
    <Connect>
        <Stream url="wss://hvac-lead-recovery-1.onrender.com/ws"/>
    </Connect>
</Response>
"""

    return PlainTextResponse(
        content=twiml,
        media_type="application/xml"
    )

# ---------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------
@app.websocket("/ws")
async def ws(websocket: WebSocket):

    global audio_chunks

    audio_chunks = []

    print("🔥 WEBSOCKET STARTED")

    await websocket.accept()

    chunk_count = 0

    try:

        while True:

            msg = await websocket.receive()

            # Handle disconnect
            if msg["type"] == "websocket.disconnect":

                print("❌ CLIENT DISCONNECTED")

                break

            # Ignore frames without text
            if "text" not in msg:
                continue

            text_data = msg["text"]

            if not text_data:
                continue

            data = json.loads(text_data)

            event = data.get("event")

            if event == "start":

                print("▶️ STREAM STARTED")

            elif event == "media":

                payload = data["media"]["payload"]

                chunk = base64.b64decode(payload)

                audio_chunks.append(chunk)

                chunk_count += 1

                if chunk_count % 100 == 0:
                    print(f"🎤 {chunk_count} chunks received")

            elif event == "stop":

                print("⏹ STREAM STOPPED")

                # Save + process in background
                audio_copy = audio_chunks.copy()
                
                threading.Thread(
                    target=process_call_audio,
                    args=(audio_copy,)
                ).start()

                break

    except RuntimeError:

        print("⚠️ NORMAL WEBSOCKET CLOSE")

    except Exception as e:

        print("❌ ERROR")

        print(type(e))

        print(str(e))

# ---------------------------------------------------
# Main audio processing pipeline
# ---------------------------------------------------
def process_call_audio(audio_data):

    try:

        # ---------------------------------------------------
        # Save raw μ-law audio
        # ---------------------------------------------------
        raw_filename = "call.ulaw"

        print(f"💾 Saving RAW μ-law audio with {len(audio_data)} chunks")

        with open(raw_filename, "wb") as f:

            f.write(b"".join(audio_data))

        print("✅ RAW AUDIO SAVED")

        # ---------------------------------------------------
        # Convert μ-law -> WAV using ffmpeg
        # ---------------------------------------------------
        wav_filename = "call.wav"

        command = [
            "ffmpeg",
            "-f", "mulaw",
            "-ar", "8000",
            "-ac", "1",
            "-i", raw_filename,
            wav_filename,
            "-y"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        print("🎵 FFMPEG CONVERSION COMPLETE")

        if result.stderr:
            print(result.stderr)

        # ---------------------------------------------------
        # Transcription
        # ---------------------------------------------------
        print("🧠 Starting transcription...")

        with open(wav_filename, "rb") as audio_file:

            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file
            )

        transcript_text = transcript.text

        print("📄 TRANSCRIPT:")

        print(transcript_text)

        # ---------------------------------------------------
        # Structured extraction
        # ---------------------------------------------------
        extract_lead_info(transcript_text)

    except Exception as e:

        print("❌ PROCESSING ERROR")

        print(type(e))

        print(str(e))

# ---------------------------------------------------
# Extract structured lead data
# ---------------------------------------------------
def extract_lead_info(transcript_text):

    try:

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
You extract HVAC lead information.

Return ONLY valid JSON.

Fields:
- customer_name
- phone_number
- issue
- intent
- urgency
"""
                },
                {
                    "role": "user",
                    "content": transcript_text
                }
            ]
        )

        result = response.choices[0].message.content

        print("📋 EXTRACTED LEAD INFO:")

        print(result)

    except Exception as e:

        print("❌ EXTRACTION ERROR")

        print(type(e))

        print(str(e))