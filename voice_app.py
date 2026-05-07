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

    print("🔥🔥🔥 NEW WEBSOCKET HANDLER RUNNING 🔥🔥🔥")

    await websocket.accept()

    print("🔌 ACCEPTED")

    try:

        while True:

            msg = await websocket.receive()

            # IMPORTANT:
            # stop immediately on disconnect
            if msg["type"] == "websocket.disconnect":

                print("❌ CLIENT DISCONNECTED")

                break

            print("📦 RECEIVED MESSAGE")

    except RuntimeError as e:

        print("⚠️ NORMAL WEBSOCKET CLOSE")

        print(str(e))

    except Exception as e:

        print("❌ UNEXPECTED ERROR")

        print(type(e))

        print(str(e))