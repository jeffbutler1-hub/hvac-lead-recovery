from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse
import json

app = FastAPI()

# ---------------------------------------------------
# Health check
# ---------------------------------------------------
@app.get("/")
async def root():
    return {"status": "voice streaming server running"}

# ---------------------------------------------------
# Twilio incoming call webhook
# ---------------------------------------------------
@app.post("/incoming-call")
async def incoming_call():

    print("📞 Incoming call webhook hit")

    twiml = f"""
<Response>
    <Connect>
        <Stream url="wss://hvac-lead-recovery-1.onrender.com/ws"/>
    </Connect>
</Response>
"""

    print("📡 Returning TwiML:")
    print(twiml)

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

            print("📦 Raw message received")

            message = json.loads(data)

            event = message.get("event")

            print("🎯 Event:", event)

            if event == "start":
                print("▶️ Stream started")

            elif event == "media":
                print("🎤 Audio chunk received")

            elif event == "stop":
                print("⏹ Stream stopped")
                break

    except Exception as e:
        print("❌ WebSocket error:")
        print(str(e))