from fastapi import FastAPI, WebSocket
from fastapi.responses import PlainTextResponse

app = FastAPI()

print("🚀 voice_app loaded")

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
# WEBSOCKET TEST
# ---------------------------------------------------
@app.websocket("/ws")
async def websocket_test(websocket: WebSocket):

    print("⚡ ENTERED WEBSOCKET FUNCTION")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    while True:

        message = await websocket.receive()

        print("📦 MESSAGE RECEIVED")

        print(message)