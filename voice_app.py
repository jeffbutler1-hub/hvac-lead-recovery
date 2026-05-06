from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from openai import OpenAI

import json
import base64
import audioop
import wave
import os

print("🚀 voice_app loaded")

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------
# Store audio chunks
# ---------------------------------------------------
audio_chunks = []

# ---------------------------------------------------
# Health check
# ---------------------------------------------------
@app.get("/")
async def root():
    return {"status": "voice streaming server running"}

# ---------------------------------------------------
# Incoming call webhook
# ---------------------------------------------------
@app.post("/incoming-call")
async def incoming_call():

    print("📞 Incoming call webhook hit")

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
async def websocket_endpoint(websocket: WebSocket):

    print("⚡ WebSocket connection attempt")

    await websocket.accept()

    print("🔌 WebSocket connected")

    try:

        while True:

            message = await websocket.receive()

            # Log raw structure
            print("📦 Raw websocket message:", message.keys())

            # Handle disconnect cleanly
            if message["type"] == "websocket.disconnect":
                print("⏹ WebSocket disconnected")
                break

            # Extract text payload
            text_data = message.get("text")

            if not text_data:
                continue

            data = json.loads(text_data)

            event = data.get("event")

            print("🎯 Event:", event)

            if event == "start":
                print("▶️ Stream started")

            elif event == "media":

                payload = data["media"]["payload"]

                chunk = base64.b64decode(payload)

                print("🎤 Audio chunk received:", len(chunk))

            elif event == "stop":
                print("⏹ Stream stopped")
                break

    except Exception as e:

        print("❌ WEBSOCKET EXCEPTION")
        print(type(e))
        print(str(e))

# ---------------------------------------------------
# Save WAV + transcribe
# ---------------------------------------------------
def save_and_transcribe():

    global audio_chunks

    filename = "call.wav"

    print("💾 Saving WAV file...")

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)

        wf.writeframes(b"".join(audio_chunks))

    print("🧠 Sending to OpenAI transcription...")

    with open(filename, "rb") as audio_file:

        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )

    print("📄 TRANSCRIPT:")
    print(transcript.text)