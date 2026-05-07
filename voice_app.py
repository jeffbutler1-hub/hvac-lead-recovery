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

    media_count = 0

    try:

        while True:

            msg = await websocket.receive()

            # Disconnect handling
            if msg["type"] == "websocket.disconnect":

                print("❌ WEBSOCKET DISCONNECTED")

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

                media_count += 1

                payload = data["media"]["payload"]

                chunk = base64.b64decode(payload)

                audio_chunks.append(chunk)

                # Log every 100 chunks only
                if media_count % 100 == 0:
                    print(f"🎤 RECEIVED {media_count} AUDIO CHUNKS")

            elif event == "stop":

                print("⏹ STREAM STOPPED")

                print(f"🎤 TOTAL CHUNKS: {media_count}")

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