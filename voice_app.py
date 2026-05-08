from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from openai import OpenAI

import os
import json
import base64

app = FastAPI()

print("🚀 CLEAN APP LOADED")

# ---------------------------------------------------
# OpenAI client
# ---------------------------------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

            # Handle disconnect cleanly
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

                # Reduce log spam
                if chunk_count % 100 == 0:
                    print(f"🎤 {chunk_count} chunks received")

            elif event == "stop":

                print("⏹ STREAM STOPPED")

                save_raw_audio()

                break

    except RuntimeError:

        print("⚠️ NORMAL WEBSOCKET CLOSE")

    except Exception as e:

        print("❌ ERROR")

        print(type(e))

        print(str(e))

# ---------------------------------------------------
# Save raw μ-law audio
# ---------------------------------------------------
def save_raw_audio():

    global audio_chunks

    filename = "call.ulaw"

    print(f"💾 Saving RAW μ-law audio with {len(audio_chunks)} chunks")

    with open(filename, "wb") as f:

        f.write(b"".join(audio_chunks))

    print("✅ RAW AUDIO SAVED")