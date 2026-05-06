from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse

app = FastAPI()

print("🚀 CLEAN APP LOADED")

@app.get("/")
async def root():
    return {"status": "running"}

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

import base64
import json
import wave

audio_chunks = []

@app.websocket("/ws")
async def ws(websocket: WebSocket):

    global audio_chunks

    audio_chunks = []

    print("⚡ WEBSOCKET FUNCTION ENTERED")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    try:

        while True:

            msg = await websocket.receive()

            if msg["type"] == "websocket.disconnect":

                print("❌ WEBSOCKET DISCONNECTED")

                break

            text = msg.get("text")

            if not text:
                continue

            data = json.loads(text)

            event = data.get("event")

            if event == "media":

                payload = data["media"]["payload"]

                chunk = base64.b64decode(payload)

                audio_chunks.append(chunk)

            elif event == "stop":

                print("⏹ STREAM STOPPED")

                print(f"🎤 CHUNKS: {len(audio_chunks)}")

                with wave.open("call.wav", "wb") as wf:

                    wf.setnchannels(1)
                    wf.setsampwidth(1)
                    wf.setframerate(8000)

                    wf.writeframes(b"".join(audio_chunks))

                print("💾 WAV FILE SAVED")

                break

    except Exception as e:

        print("❌ WEBSOCKET ERROR")

        print(type(e))

        print(str(e))