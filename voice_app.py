from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
import uvicorn
import json

app = FastAPI()

# -------------------------
# Health check
# -------------------------
@app.get("/")
async def root():
    return {"status": "voice server running"}

# -------------------------
# Twilio webhook
# -------------------------
@app.post("/incoming-call")
async def incoming_call():

    twiml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Connecting you to the AI assistant.</Say>
        <Connect>
            <Stream url="wss://encore-dingbat-available.ngrok-free.dev/ws" />
        </Connect>
    </Response>
    """

    return Response(content=twiml, media_type="application/xml")

# -------------------------
# WebSocket stream
# -------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    print("🔌 WebSocket connected")

    try:
        while True:
            data = await websocket.receive_text()

            message = json.loads(data)

            event = message.get("event")

            if event == "start":
                print("▶️ Stream started")

            elif event == "media":
                print("🎤 Receiving audio chunk")

            elif event == "stop":
                print("⏹ Stream stopped")
                break

    except Exception as e:
        print("❌ WebSocket error:", e)

# -------------------------
# Run locally
# -------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)