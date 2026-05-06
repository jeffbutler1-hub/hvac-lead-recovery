from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse

import json
import base64
import audioop
import wave

app = FastAPI()

print("🚀 voice_app loaded")

# ---------------------------------------------------
# Store audio chunks
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
# Websocket endpoint
# ---------------------------------------------------
@app.websocket("/ws")
async def websocket_test(websocket: WebSocket):

    global audio_chunks

    audio_chunks = []

    print("⚡ ENTERED WEBSOCKET FUNCTION")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    try:

        while True:

            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                print("❌ Websocket disconnected")
                break

            text_data = message.get("text")

            if not text_data:
                continue

            data = json.loads(text_data)

            event = data.get("event")

            if event == "start":

                print("▶️ Stream started")

            elif event == "media":

                payload = data["media"]["payload"]

                chunk = base64.b64decode(payload)

                # SAVE RAW μ-law CHUNKS
                audio_chunks.append(chunk)

            elif event == "stop":

                print("⏹ Stream stopped")

                print(f"🎤 Saved {len(audio_chunks)} chunks")

                break

    except Exception as e:

        print("❌ WEBSOCKET ERROR")
        print(type(e))
        print(str(e))

# ---------------------------------------------------
# Save WAV file
# ---------------------------------------------------
def save_wav():

    global audio_chunks

    print("💾 Saving WAV")

    with wave.open("call.wav", "wb") as wf:

        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)

        wf.writeframes(b"".join(audio_chunks))

    print("✅ WAV SAVED")