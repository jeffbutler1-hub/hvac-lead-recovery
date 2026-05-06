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

@app.websocket("/ws")
async def ws(websocket: WebSocket):

    print("⚡ WEBSOCKET FUNCTION ENTERED")

    await websocket.accept()

    print("🔌 WEBSOCKET ACCEPTED")

    while True:

        print("⏳ WAITING FOR MESSAGE")

        msg = await websocket.receive()

        print("📦 MESSAGE RECEIVED")

        print(msg)