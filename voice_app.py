from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
from openai import OpenAI

import json
import base64
import audioop
import wave
import os

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

            data = await websocket.receive_text()

            print("📦 Received websocket message")

            message = json.loads(data)

            event = message.get("event")

            print("🎯 Event:", event)

            if event == "media":

                payload = message["media"]["payload"]

                chunk = base64.b64decode(payload)

                print("🎤 Received audio chunk:", len(chunk))

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