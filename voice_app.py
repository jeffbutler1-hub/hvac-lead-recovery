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

    print("⚡ ENTERED WEBSOCKET FUNCTION")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    try:

        while True:

            message = await websocket.receive()

            print("📦 RECEIVED MESSAGE")

            print(message.keys())

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